from utils.request_sender.send_request import SendPriorRequestMultipleXmls, SendPersonRegisterTPA, \
    SendPriorAuthorizationTPA, SendRemittanceAdviceTPA, SendClaimCountConciliation, SendGetPersonInsuranceHistory, \
    SendPersonRegisterProvider, SendPayForQuality
import os
from abc import abstractmethod, ABC

import allure
import pytest

from functions.custom_functions import get_login_from_id, get_password_from_id
from utils.asserter.asserter import XMLAsserterContext
from utils.request_sender.send_request import SendPersonRegister, SendPriorRequest, SendPriorAuthorization, \
    SendClaimSubmission, SendClaimSubmissionZipped, SendRemittanceAdvice, SendSearchTransactions, SendGetNewTransaction, \
    SendDownloadTransaction, SendSetTransactionDownloaded, SendPriorRequestZipped, \
    SendGetNewPriorAuthorizationTransactions, SendCostSubmission, SendCostSubmissionZipped, SendClaimChecker, \
    SendClaimCheckerZipped
from utils.request_sender.send_request_context import SendRequestContext
from utils.request_sender.system_enums import Systems
from utils.template_generator.request_transaction_mapper import get_transaction_from_request
from utils.template_generator.requests_name_enums import RequestsName, RequestPrefix
from utils.template_generator.template_generator import GetRequestTemplate
from utils.env_vars import EnvVar
import xml.etree.ElementTree as ET


def extract_step_live_data(prerequisites, step_prefix):
    """Pull the 'StepPrefix.path=value' entries for one chain step out of the Precondition string.

    Returns (step_live_data, remaining_prerequisites). remaining_prerequisites has this step's entries
    removed and is meant to be threaded into the next step's extract_step_live_data call, so that whatever
    is left after the last step in a chain didn't match any known step prefix — the caller should raise on
    a non-empty remainder at that point.

    For the bare (1st-occurrence) prefix, 'StepPrefix[1].path=value' is also accepted as an alias.
    """
    if not prerequisites:
        return None, prerequisites
    prefixes = [f"{step_prefix}."]
    if "[" not in step_prefix:
        prefixes.append(f"{step_prefix}[1].")
    matches = []
    remaining = []
    for pair in prerequisites.split(';'):
        stripped = pair.strip()
        if not stripped:
            continue
        for prefix in prefixes:
            if stripped.lower().startswith(prefix.lower()):
                matches.append(stripped[len(prefix):])
                break
        else:
            remaining.append(stripped)
    step_live_data = ';'.join(matches) if matches else None
    remaining_prerequisites = ';'.join(remaining) if remaining else None
    return step_live_data, remaining_prerequisites


class AbstractRequestMapper(ABC):

    def __init__(self, prerequisites):
        self.person_register_template = None
        self.second_person_register_template = None
        self.prior_request_template = None
        self.prior_authorization_template = None
        self.prior_authorization_resubmission_template = None
        self.claim_submission_template = None
        self.claim_submission_resubmission_template = None
        self.claim_checker_template = None
        self.claim_checker_resubmission_template = None
        self.claim_checker_no_remittance_template = None
        self.claim_checker_self_pay_template = None
        self.claim_submission_second_resubmission_template = None
        self.claim_checker_second_resubmission_template = None
        self.remittance_advice_template = None
        self.remittance_advice_tkbk_template = None
        self.remittance_advice_tkbk_2_template = None
        self.second_remittance_advice_template = None
        self.search_transaction_template = None
        self.get_new_prior_authorization_template = None
        self.get_new_transaction_template = None
        self.prior_request_resubmission_template = None
        self.prerequisites = prerequisites
        self.template_flow = []
        self.cost_Submission_template = None
        self.cost_resubmission_template = None
        self.claim_count_reconciliation_template = None
        self.get_person_insurance_history_template = None
        self.pay_for_quality_template = None

    def _should_use_single_request(self):
        """Check if execution sequence is not 'full_scenario'"""
        execution_sequence = os.environ.get(EnvVar.SOAP_EXECUTION_SEQUENCE)
        return execution_sequence != "full_scenario"

    def _record_template(self, base_label, template):
        occurrence = 1 + sum(1 for label, _ in self.template_flow
                              if label == base_label or label.startswith(f"{base_label}["))
        label = base_label if occurrence == 1 else f"{base_label}[{occurrence}]"
        self.template_flow.append((label, template))

    @abstractmethod
    def do_request(self, live_data, system: Systems):
        pass


class AbstractAssertionRequestMapper(AbstractRequestMapper):
    """Assertion-tab-only transactions — utils/allure_wrapper.py rejects any request mapper of this type."""


class PersonRegister(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value, live_data=live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
        return SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, live_data)), self.person_register_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.person_register_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value, live_data=live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
        return SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, live_data)), self.person_register_template, list(self.template_flow)

class PersonRegisterResubmission(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                    self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get person register request"):
                self.person_register_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.person_register_resubmission.value, variables=variables, live_data=live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
        return SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,
                                                                                live_data)), self.person_register_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.person_register_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value, live_data=live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
        return SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, live_data)), self.person_register_template, list(self.template_flow)


class PersonRegisterTPA(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_tpa.value, live_data=live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
        return SendRequestContext().send_request(system, SendPersonRegisterTPA(self.person_register_template, live_data)), self.person_register_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.person_register_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_tpa.value, live_data=live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
        return SendRequestContext().send_request(system, SendPersonRegisterTPA(self.person_register_template, live_data)), self.person_register_template, list(self.template_flow)

class PriorRequest(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
        return SendRequestContext().send_request(system,SendPriorRequest(self.prior_request_template, live_data)), self.prior_request_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.prior_request_template is None:
            with allure.step("Get prior request"):
                self.prior_request_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
        return SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template,
                                                                          live_data)), self.prior_request_template, list(self.template_flow)

class PriorRequestToTPA(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_to_tpa.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegisterTPA(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
        return SendRequestContext().send_request(system,SendPriorRequest(self.prior_request_template, live_data)), self.prior_request_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.prior_request_template is None:
            with allure.step("Get prior request"):
                self.prior_request_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request_to_tpa_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
        return SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template,
                                                                          live_data)), self.prior_request_template, list(self.template_flow)


class PriorRequestMultipleXmls(AbstractRequestMapper):
    
    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request.value, variables=variables, live_data=live_data)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            return SendRequestContext().send_request(system, SendPriorRequestMultipleXmls(self.prior_request_template,
                                                                                        live_data)), self.prior_request_template, list(self.template_flow)
    
    def _do_single_request(self, system: Systems, live_data=None):
        if self.prior_request_template is None:
            with allure.step("Get prior request"):
                self.prior_request_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
        return SendRequestContext().send_request(system, SendPriorRequestMultipleXmls(self.prior_request_template,
                                                                          live_data)), self.prior_request_template, list(self.template_flow)

class PriorRequestGreaterThan6MB(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None and
            self.prior_request_resubmission_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template,
                                                                                        None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization"):
                self.prior_authorization_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_authorization.value, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
            prior_authorization_response = SendRequestContext().send_request(system,
                                                                       SendPriorAuthorization(self.prior_authorization_template,
                                                                                        None))
            XMLAsserterContext(prior_authorization_response).assert_no_errors()
            with allure.step("Get prior request resubmission"):
                self.prior_request_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request_greater_than_6MB.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_resubmission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template,
                                                                                        None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            prior_authorization_response = SendRequestContext().send_request(system,SendPriorAuthorization(self.prior_authorization_template, None))
            XMLAsserterContext(prior_authorization_response).assert_no_errors()
        return SendRequestContext().send_request(system,SendPriorRequest(self.prior_request_resubmission_template, live_data)), self.prior_request_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.prior_request_resubmission_template is None:
            with allure.step("Get prior request resubmission"):
                self.prior_request_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request_greater_than_6MB_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_resubmission_template)
        return SendRequestContext().send_request(system,SendPriorRequest(self.prior_request_resubmission_template, live_data)), self.prior_request_resubmission_template, list(self.template_flow)

class PriorRequestResubmission(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None and
            self.prior_request_resubmission_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template,
                                                                                        None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization"):
                self.prior_authorization_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_authorization.value, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
            prior_authorization_response = SendRequestContext().send_request(system,
                                                                       SendPriorAuthorization(self.prior_authorization_template,
                                                                                        None))
            XMLAsserterContext(prior_authorization_response).assert_no_errors()
            with allure.step("Get prior request resubmission"):
                self.prior_request_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request_resubmission.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_resubmission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template,
                                                                                        None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            prior_authorization_response = SendRequestContext().send_request(system,SendPriorAuthorization(self.prior_authorization_template, None))
            XMLAsserterContext(prior_authorization_response).assert_no_errors()
        return SendRequestContext().send_request(system,SendPriorRequest(self.prior_request_resubmission_template, live_data)), self.prior_request_resubmission_template, list(self.template_flow)


    def _do_single_request(self, system: Systems, live_data=None):
        if self.prior_request_resubmission_template is None:
            with allure.step("Get prior request resubmission"):
                self.prior_request_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request_resubmission_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_resubmission_template)
        return SendRequestContext().send_request(system,SendPriorRequest(self.prior_request_resubmission_template, live_data)), self.prior_request_resubmission_template, list(self.template_flow)

class PriorRequestZipped(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorRequestZipped(self.prior_request_template,
                                                                          live_data)), self.prior_request_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.prior_request_template is None:
            with allure.step("Get prior request"):
                self.prior_request_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
        return SendRequestContext().send_request(system, SendPriorRequestZipped(self.prior_request_template,
                                                                                live_data)), self.prior_request_template, list(self.template_flow)

class PriorAuthorizationPrescription(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request - prescription"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_prescription.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization_prescription.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, live_data)), self.prior_authorization_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.prior_authorization_template is None:
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization_prescription_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template,
                                                                                live_data)), self.prior_authorization_template, list(self.template_flow)


class PriorAuthorizationCancellation(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request - cancellation"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_cancellation.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization_cancellation.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, live_data)), self.prior_authorization_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.prior_authorization_template is None:
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_authorization_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template,
                                                                                live_data)), self.prior_authorization_template, list(self.template_flow)

class PriorAuthorizationExtension(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request - extension"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_extension.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization_extension.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, live_data)), self.prior_authorization_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data):
        if self.prior_authorization_template is None:
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_authorization_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template,
                                                                                live_data)), self.prior_authorization_template, list(self.template_flow)

class PriorAuthorizationEligibility(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request - eligibility"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_eligibility.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization_eligibility.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, live_data)), self.prior_authorization_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.prior_authorization_template is None:
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_authorization_eligibility_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template,
                                                                                live_data)), self.prior_authorization_template, list(self.template_flow)

class PriorAuthorizationLarge(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request - large"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization_large.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, live_data)), self.prior_authorization_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.prior_authorization_template is None:
            with allure.step("Get prior authorization request - large"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_authorization_large.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template,
                                                                                live_data)), self.prior_authorization_template, list(self.template_flow)

class PriorAuthorization(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, live_data)), self.prior_authorization_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.prior_authorization_template is None:
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_authorization_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template,
                                                                                live_data)), self.prior_authorization_template, list(self.template_flow)

class PriorAuthorizationTPA(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_to_tpa.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization_tpa.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegisterTPA(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorizationTPA(self.prior_authorization_template, live_data)), self.prior_authorization_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.prior_authorization_template is None:
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_authorization_tpa_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
        return SendRequestContext().send_request(system, SendPriorAuthorizationTPA(self.prior_authorization_template,
                                                                                live_data)), self.prior_authorization_template, list(self.template_flow)

class ClaimSubmission(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, live_data)), self.claim_submission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_submission_template is None:
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template,
                                                                             live_data)), self.claim_submission_template, list(self.template_flow)

class ClaimChecker(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None and self.claim_checker_template is None:
            person_register_live_data, remaining = extract_step_live_data(self.prerequisites, RequestPrefix.person_register.value)
            prior_request_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.prior_request.value)
            prior_authorization_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.prior_authorization.value)
            if remaining:
                raise Exception(f"Unconsumed precondition entries (no matching step in this flow): {remaining}")
            with allure.step("Get person register request"):
                self.person_register_template, variables, person_register_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value, live_data=person_register_live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, person_register_live_data))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, prior_request_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, live_data=prior_request_live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, prior_request_live_data))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, prior_authorization_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization.value, live_data=prior_authorization_live_data, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
            prior_authorization_response = SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, prior_authorization_live_data))
            XMLAsserterContext(prior_authorization_response).assert_no_errors()
            with allure.step("Get claim checker request"):
                self.claim_checker_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_checker.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_checker.value, self.claim_checker_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            prior_authorization_response = SendRequestContext().send_request(system,
                                                                       SendPriorAuthorization(self.prior_authorization_template, None))
            XMLAsserterContext(prior_authorization_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_template, live_data)), self.claim_checker_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_checker_template is None:
            with allure.step("Get claim checker request"):
                self.claim_checker_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_checker_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.claim_checker.value, self.claim_checker_template)
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_template,
                                                                             live_data)), self.claim_checker_template, list(self.template_flow)

class PersonCorrectedClaimChecker(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.second_person_register_template is None
                and self.prior_request_template is None and self.prior_authorization_template is None
                and self.claim_checker_template is None):
            person_register_live_data, remaining = extract_step_live_data(self.prerequisites, RequestPrefix.person_register.value)
            second_person_register_live_data, remaining = extract_step_live_data(remaining, f"{RequestPrefix.person_register.value}[2]")
            prior_request_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.prior_request.value)
            prior_authorization_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.prior_authorization.value)
            if remaining:
                raise Exception(f"Unconsumed precondition entries (no matching step in this flow): {remaining}")
            with allure.step("Get person register request"):
                self.person_register_template, variables, person_register_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value, live_data=person_register_live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, person_register_live_data))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get second person register request"):
                self.second_person_register_template, variables, second_person_register_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_resubmission.value, live_data=second_person_register_live_data, variables=variables)
                self._record_template(RequestPrefix.person_register.value, self.second_person_register_template)
            second_person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.second_person_register_template, second_person_register_live_data))
            XMLAsserterContext(second_person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, prior_request_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, live_data=prior_request_live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, prior_request_live_data))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, prior_authorization_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization.value, live_data=prior_authorization_live_data, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
            prior_authorization_response = SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, prior_authorization_live_data))
            XMLAsserterContext(prior_authorization_response).assert_no_errors()
            with allure.step("Get claim checker request"):
                self.claim_checker_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_checker.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_checker.value, self.claim_checker_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            second_person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.second_person_register_template, None))
            XMLAsserterContext(second_person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            prior_authorization_response = SendRequestContext().send_request(system,
                                                                       SendPriorAuthorization(self.prior_authorization_template, None))
            XMLAsserterContext(prior_authorization_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_template, live_data)), self.claim_checker_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        raise Exception("Please use full scenario for this transaction type")

class ClaimCheckerNoPriorAuthorization(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_checker_template is None:
            person_register_live_data, remaining = extract_step_live_data(self.prerequisites, RequestPrefix.person_register.value)
            prior_request_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.prior_request.value)
            if remaining:
                raise Exception(f"Unconsumed precondition entries (no matching step in this flow): {remaining}")
            with allure.step("Get person register request"):
                self.person_register_template, variables, person_register_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value, live_data=person_register_live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, person_register_live_data))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, prior_request_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, live_data=prior_request_live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, prior_request_live_data))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim checker request"):
                self.claim_checker_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_checker_no_prior_authorization.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_checker.value, self.claim_checker_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_template, live_data)), self.claim_checker_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_checker_template is None:
            with allure.step("Get claim checker request"):
                self.claim_checker_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_checker_no_prior_authorization_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.claim_checker.value, self.claim_checker_template)
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_template,
                                                                             live_data)), self.claim_checker_template, list(self.template_flow)

class ClaimCheckerResubmission(AbstractRequestMapper):
    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None and self.claim_checker_resubmission_template is None:
            person_register_live_data, remaining = extract_step_live_data(self.prerequisites, RequestPrefix.person_register.value)
            prior_request_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.prior_request.value)
            claim_submission_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.claim_submission.value)
            remittance_advice_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.remittance_advice.value)
            if remaining:
                raise Exception(f"Unconsumed precondition entries (no matching step in this flow): {remaining}")
            with allure.step("Get person register request"):
                self.person_register_template, variables, person_register_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value, live_data=person_register_live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, person_register_live_data))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, prior_request_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, live_data=prior_request_live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, prior_request_live_data))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, claim_submission_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, live_data=claim_submission_live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        claim_submission_live_data))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, remittance_advice_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice.value, live_data=remittance_advice_live_data, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
            remittance_response = SendRequestContext().send_request(system,
                                                                       SendRemittanceAdvice(self.remittance_advice_template,
                                                                                        remittance_advice_live_data))
            XMLAsserterContext(remittance_response).assert_no_errors()
            with allure.step("Get claim checker resubmission request"):
                self.claim_checker_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_checker_resubmission.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_checker.value, self.claim_checker_resubmission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_resubmission_template, live_data)), self.claim_checker_resubmission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_checker_resubmission_template is None:
            with allure.step("Get claim checker resubmission request"):
                self.claim_checker_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_checker_resubmission_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.claim_checker.value, self.claim_checker_resubmission_template)
        return SendRequestContext().send_request(system,
                                                 SendClaimChecker(self.claim_checker_resubmission_template,
                                                                     live_data)), self.claim_checker_resubmission_template, list(self.template_flow)

class ClaimSubmissionMultipleActivities(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_multiple_activities.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission_multiple_activities.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, live_data)), self.claim_submission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_submission_template is None:
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_multiple_activities_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template,
                                                                             live_data)), self.claim_submission_template, list(self.template_flow)

class ClaimSubmissionSelfPay(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_self_pay.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegisterProvider(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission_self_pay.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, live_data)), self.claim_submission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_submission_template is None:
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template,
                                                                             live_data)), self.claim_submission_template, list(self.template_flow)

class PreconditionClaimSubmission(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=self.prerequisites)
        live_data = self.prerequisites
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, live_data)), self.claim_submission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_submission_template is None:
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template,
                                                                             live_data)), self.claim_submission_template, list(self.template_flow)

class SecondClaimNoRemittance(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template,
                                                                                        None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get claim resubmission request"):
                self.claim_submission_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_resubmission_no_remittance.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_resubmission_template)

        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template,
                                                                                        None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_resubmission_template,
                                                                             live_data)), self.claim_submission_resubmission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        raise Exception("Please use full scenario for this transaction type")


class ClaimCheckerNoRemittance(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None and self.claim_checker_no_remittance_template is None:
            person_register_live_data, remaining = extract_step_live_data(self.prerequisites, RequestPrefix.person_register.value)
            prior_request_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.prior_request.value)
            claim_submission_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.claim_submission.value)
            if remaining:
                raise Exception(f"Unconsumed precondition entries (no matching step in this flow): {remaining}")
            with allure.step("Get person register request"):
                self.person_register_template, variables, person_register_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value, live_data=person_register_live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, person_register_live_data))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, prior_request_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, live_data=prior_request_live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, prior_request_live_data))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, claim_submission_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, live_data=claim_submission_live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        claim_submission_live_data))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get claim checker no remittance request"):
                self.claim_checker_no_remittance_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_checker_no_remittance.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_checker_no_remittance.value, self.claim_checker_no_remittance_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_no_remittance_template, live_data)), self.claim_checker_no_remittance_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_checker_no_remittance_template is None:
            with allure.step("Get claim checker no remittance request"):
                self.claim_checker_no_remittance_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_checker_no_remittance_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.claim_checker_no_remittance.value, self.claim_checker_no_remittance_template)
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_no_remittance_template,
                                                                             live_data)), self.claim_checker_no_remittance_template, list(self.template_flow)


class ClaimCheckerConsultationNoRemittance(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None and self.claim_checker_no_remittance_template is None:
            person_register_live_data, remaining = extract_step_live_data(self.prerequisites, RequestPrefix.person_register.value)
            prior_request_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.prior_request.value)
            claim_submission_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.claim_submission.value)
            if remaining:
                raise Exception(f"Unconsumed precondition entries (no matching step in this flow): {remaining}")
            with allure.step("Get person register request"):
                self.person_register_template, variables, person_register_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value, live_data=person_register_live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, person_register_live_data))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, prior_request_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_consultation.value, live_data=prior_request_live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, prior_request_live_data))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, claim_submission_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, live_data=claim_submission_live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        claim_submission_live_data))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get claim checker no remittance request"):
                self.claim_checker_no_remittance_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_checker_no_remittance.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_checker_no_remittance.value, self.claim_checker_no_remittance_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_no_remittance_template, live_data)), self.claim_checker_no_remittance_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_checker_no_remittance_template is None:
            with allure.step("Get claim checker no remittance request"):
                self.claim_checker_no_remittance_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_checker_no_remittance_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.claim_checker_no_remittance.value, self.claim_checker_no_remittance_template)
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_no_remittance_template,
                                                                             live_data)), self.claim_checker_no_remittance_template, list(self.template_flow)


class ClaimCheckerSelfPay(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.claim_checker_self_pay_template is None:
            person_register_live_data, remaining = extract_step_live_data(self.prerequisites, RequestPrefix.person_register.value)
            if remaining:
                raise Exception(f"Unconsumed precondition entries (no matching step in this flow): {remaining}")
            with allure.step("Get person register request"):
                self.person_register_template, variables, person_register_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_self_pay.value, live_data=person_register_live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegisterProvider(self.person_register_template, person_register_live_data))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get claim checker self pay request"):
                self.claim_checker_self_pay_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_checker_self_pay.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_checker_self_pay.value, self.claim_checker_self_pay_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegisterProvider(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_self_pay_template, live_data)), self.claim_checker_self_pay_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_checker_self_pay_template is None:
            with allure.step("Get claim checker self pay request"):
                self.claim_checker_self_pay_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_checker_self_pay_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.claim_checker_self_pay.value, self.claim_checker_self_pay_template)
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_self_pay_template,
                                                                             live_data)), self.claim_checker_self_pay_template, list(self.template_flow)


class ClaimSubmissionToTPA(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_to_tpa.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission_to_tpa.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegisterTPA(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, live_data)), self.claim_submission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_submission_template is None:
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_to_tpa_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template,
                                                                             live_data)), self.claim_submission_template, list(self.template_flow)

class ClaimSubmissionMultipleClaims(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization"):
                self.prior_authorization_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization.value, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
            prior_auth_response = SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, None))
            XMLAsserterContext(prior_auth_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission_multiple_claims.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, live_data)), self.claim_submission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_submission_template is None:
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_multiple_claims_isolated.value, live_data=live_data,
                    variables=None)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template,
                                                                             live_data)), self.claim_submission_template, list(self.template_flow)


class ClaimSubmissionMultipleClaimsZipped(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization"):
                self.prior_authorization_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization.value, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
            prior_auth_response = SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, None))
            XMLAsserterContext(prior_auth_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission_multiple_claims.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmissionZipped(self.claim_submission_template, live_data)), self.claim_submission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_submission_template is None:
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_multiple_claims_isolated.value, live_data=live_data,
                    variables=None)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        return SendRequestContext().send_request(system, SendClaimSubmissionZipped(self.claim_submission_template,
                                                                                  live_data)), self.claim_submission_template, list(self.template_flow)

class ClaimCheckerMultipleClaimsZipped(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None and self.claim_checker_template is None:
            person_register_live_data, remaining = extract_step_live_data(self.prerequisites, RequestPrefix.person_register.value)
            prior_request_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.prior_request.value)
            prior_authorization_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.prior_authorization.value)
            if remaining:
                raise Exception(f"Unconsumed precondition entries (no matching step in this flow): {remaining}")
            with allure.step("Get person register request"):
                self.person_register_template, variables, person_register_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value, live_data=person_register_live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, person_register_live_data))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, prior_request_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, live_data=prior_request_live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, prior_request_live_data))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, prior_authorization_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization.value, live_data=prior_authorization_live_data, variables=variables)
                self._record_template(RequestPrefix.prior_authorization.value, self.prior_authorization_template)
            prior_authorization_response = SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, prior_authorization_live_data))
            XMLAsserterContext(prior_authorization_response).assert_no_errors()
            with allure.step("Get claim checker request"):
                self.claim_checker_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_checker_multiple_claims.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_checker.value, self.claim_checker_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            prior_authorization_response = SendRequestContext().send_request(system,
                                                                       SendPriorAuthorization(self.prior_authorization_template, None))
            XMLAsserterContext(prior_authorization_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimCheckerZipped(self.claim_checker_template, live_data)), self.claim_checker_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_checker_template is None:
            with allure.step("Get claim checker request"):
                self.claim_checker_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_checker_multiple_claims_isolated.value, live_data=live_data,
                    variables=None)
                self._record_template(RequestPrefix.claim_checker.value, self.claim_checker_template)
        return SendRequestContext().send_request(system, SendClaimCheckerZipped(self.claim_checker_template,
                                                                              live_data)), self.claim_checker_template, list(self.template_flow)

class ClaimResubmissionToTakeBack(AbstractRequestMapper):
    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None and self.claim_submission_resubmission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice_tkbk.value, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
            remittance_response = SendRequestContext().send_request(system,
                                                                       SendRemittanceAdvice(self.remittance_advice_template,
                                                                                        None))
            XMLAsserterContext(remittance_response).assert_no_errors()
            with allure.step("Get claim resubmission request"):
                self.claim_submission_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_resubmission_correction.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_resubmission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_resubmission_template, live_data)), self.claim_submission_resubmission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        raise Exception("Please use full scenario for this transaction type")



class ClaimResubmission(AbstractRequestMapper):
    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None and self.claim_submission_resubmission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice.value, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
            remittance_response = SendRequestContext().send_request(system,
                                                                       SendRemittanceAdvice(self.remittance_advice_template,
                                                                                        None))
            XMLAsserterContext(remittance_response).assert_no_errors()
            with allure.step("Get claim resubmission request"):
                self.claim_submission_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_resubmission.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_resubmission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_resubmission_template, live_data)), self.claim_submission_resubmission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.claim_submission_resubmission_template is None:
            with allure.step("Get claim resubmission request"):
                self.claim_submission_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_resubmission_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_resubmission_template)
        return SendRequestContext().send_request(system,
                                                 SendClaimSubmission(self.claim_submission_resubmission_template,
                                                                     live_data)), self.claim_submission_resubmission_template, list(self.template_flow)


class ClaimResubmissionConsultation(AbstractRequestMapper):
    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None and self.claim_submission_resubmission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_consultation.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice.value, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
            remittance_response = SendRequestContext().send_request(system,
                                                                       SendRemittanceAdvice(self.remittance_advice_template,
                                                                                        None))
            XMLAsserterContext(remittance_response).assert_no_errors()
            with allure.step("Get claim resubmission request"):
                self.claim_submission_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_resubmission.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_resubmission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_resubmission_template, live_data)), self.claim_submission_resubmission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        raise Exception("Please use full scenario for this transaction type")


class ClaimResubmissionConsultationNoRemittance(AbstractRequestMapper):
    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None and self.claim_submission_resubmission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_consultation.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get claim resubmission request"):
                self.claim_submission_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_resubmission_no_remittance.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_resubmission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_resubmission_template, live_data)), self.claim_submission_resubmission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        raise Exception("Please use full scenario for this transaction type")

class ClaimSecondResubmission(AbstractRequestMapper):
    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None
                and self.claim_submission_template is None and self.claim_submission_resubmission_template is None
                and self.claim_submission_second_resubmission_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get first claim resubmission request"):
                self.claim_submission_resubmission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_resubmission.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_resubmission_template)
            claim_submission_response = SendRequestContext().send_request(system,
                                                                          SendClaimSubmission(
                                                                              self.claim_submission_resubmission_template,
                                                                              None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get second claim resubmission request"):
                self.claim_submission_second_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_second_resubmission.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_second_resubmission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system,
                                                                          SendClaimSubmission(
                                                                              self.claim_submission_resubmission_template,
                                                                              None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_second_resubmission_template, live_data)), self.claim_submission_second_resubmission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        raise Exception("Please use full scenario for this transaction type")

class ClaimCheckerSecondResubmission(AbstractRequestMapper):
    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None
                and self.claim_submission_template is None and self.claim_submission_resubmission_template is None
                and self.claim_checker_second_resubmission_template is None):
            person_register_live_data, remaining = extract_step_live_data(self.prerequisites, RequestPrefix.person_register.value)
            prior_request_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.prior_request.value)
            claim_submission_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.claim_submission.value)
            claim_submission_resubmission_live_data, remaining = extract_step_live_data(remaining, f"{RequestPrefix.claim_submission.value}[2]")
            remittance_advice_live_data, remaining = extract_step_live_data(remaining, RequestPrefix.remittance_advice.value)
            second_remittance_advice_live_data, remaining = extract_step_live_data(remaining, f"{RequestPrefix.remittance_advice.value}[2]")
            if remaining:
                raise Exception(f"Unconsumed precondition entries (no matching step in this flow): {remaining}")
            with allure.step("Get person register request"):
                self.person_register_template, variables, person_register_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value, live_data=person_register_live_data)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, person_register_live_data))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, prior_request_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, live_data=prior_request_live_data, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, prior_request_live_data))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, claim_submission_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, live_data=claim_submission_live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        claim_submission_live_data))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, remittance_advice_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice.value, live_data=remittance_advice_live_data, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
            remittance_response = SendRequestContext().send_request(system,
                                                                       SendRemittanceAdvice(self.remittance_advice_template,
                                                                                        remittance_advice_live_data))
            XMLAsserterContext(remittance_response).assert_no_errors()
            with allure.step("Get first claim resubmission request"):
                self.claim_submission_resubmission_template, variables, claim_submission_resubmission_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_submission_resubmission.value, live_data=claim_submission_resubmission_live_data, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_resubmission_template)
            claim_submission_response = SendRequestContext().send_request(system,
                                                                          SendClaimSubmission(
                                                                              self.claim_submission_resubmission_template,
                                                                              claim_submission_resubmission_live_data))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get second remittance advice request"):
                self.second_remittance_advice_template, variables, second_remittance_advice_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.second_remittance_advice.value, live_data=second_remittance_advice_live_data, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.second_remittance_advice_template)
            second_remittance_response = SendRequestContext().send_request(system,
                                                                       SendRemittanceAdvice(self.second_remittance_advice_template,
                                                                                        second_remittance_advice_live_data))
            XMLAsserterContext(second_remittance_response).assert_no_errors()
            with allure.step("Get second claim checker resubmission request"):
                self.claim_checker_second_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.claim_checker_second_resubmission.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.claim_checker.value, self.claim_checker_second_resubmission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system,
                                                                       SendClaimSubmission(self.claim_submission_template,
                                                                                        None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            remittance_response = SendRequestContext().send_request(system,
                                                                       SendRemittanceAdvice(self.remittance_advice_template,
                                                                                        None))
            XMLAsserterContext(remittance_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system,
                                                                          SendClaimSubmission(
                                                                              self.claim_submission_resubmission_template,
                                                                              None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            second_remittance_response = SendRequestContext().send_request(system,
                                                                       SendRemittanceAdvice(self.second_remittance_advice_template,
                                                                                        None))
            XMLAsserterContext(second_remittance_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimChecker(self.claim_checker_second_resubmission_template, live_data)), self.claim_checker_second_resubmission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        raise Exception("Please use full scenario for this transaction type")

class RemittanceAdvice(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None
            and self.remittance_advice_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(
                self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendRemittanceAdvice(self.remittance_advice_template, live_data)), self.remittance_advice_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.remittance_advice_template is None:
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
        return SendRequestContext().send_request(system, SendRemittanceAdvice(self.remittance_advice_template,
                                                                              live_data)), self.remittance_advice_template, list(self.template_flow)


class RemittanceAdviceMultipleActivities(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None
            and self.remittance_advice_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_multiple_activities.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission_multiple_activities.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice_multiple_activities.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(
                self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendRemittanceAdvice(self.remittance_advice_template, live_data)), self.remittance_advice_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.remittance_advice_template is None:
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice_multiple_activities_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
        return SendRequestContext().send_request(system, SendRemittanceAdvice(self.remittance_advice_template,
                                                                              live_data)), self.remittance_advice_template, list(self.template_flow)


class RemittanceAdviceTPA(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None
            and self.remittance_advice_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_to_tpa.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission_to_tpa.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice_tpa.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegisterTPA(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(
                self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendRemittanceAdviceTPA(self.remittance_advice_template, live_data)), self.remittance_advice_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.remittance_advice_template is None:
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
        return SendRequestContext().send_request(system, SendRemittanceAdvice(self.remittance_advice_template,
                                                                              live_data)), self.remittance_advice_template, list(self.template_flow)

class CostSubmission(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None
            and self.remittance_advice_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get cost submission request"):
                self.cost_Submission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.cost_submission.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.cost_submission.value, self.cost_Submission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(
                self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendCostSubmission(self.cost_Submission_template, live_data)), self.cost_Submission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.cost_Submission_template is None:
            with allure.step("Get cost submission request"):
                self.cost_Submission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.cost_submission_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.cost_submission.value, self.cost_Submission_template)
        return SendRequestContext().send_request(system, SendCostSubmission(self.cost_Submission_template,
                                                                            live_data)), self.cost_Submission_template, list(self.template_flow)

class CostSubmissionMultipleClaims(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None
            and self.remittance_advice_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission_multiple_claims.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get cost submission multiple claims request"):
                self.cost_Submission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.cost_submission_multiple_claims.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.cost_submission.value, self.cost_Submission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendCostSubmission(self.cost_Submission_template, live_data)), self.cost_Submission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.cost_Submission_template is None:
            with allure.step("Get cost submission multiple claims request"):
                self.cost_Submission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.cost_submission_multiple_claims_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.cost_submission.value, self.cost_Submission_template)
        return SendRequestContext().send_request(system, SendCostSubmission(self.cost_Submission_template,
                                                                            live_data)), self.cost_Submission_template, list(self.template_flow)


class CostSubmissionZipped(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None
            and self.remittance_advice_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get cost submission request"):
                self.cost_Submission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.cost_submission.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.cost_submission.value, self.cost_Submission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendCostSubmissionZipped(self.cost_Submission_template, live_data)), self.cost_Submission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.cost_Submission_template is None:
            with allure.step("Get cost submission request"):
                self.cost_Submission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.cost_submission_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.cost_submission.value, self.cost_Submission_template)
        return SendRequestContext().send_request(system, SendCostSubmissionZipped(self.cost_Submission_template,
                                                                                  live_data)), self.cost_Submission_template, list(self.template_flow)


class CostResubmission(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None
            and self.remittance_advice_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get cost submission request"):
                self.cost_Submission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.cost_submission.value, variables=variables)
                self._record_template(RequestPrefix.cost_submission.value, self.cost_Submission_template)
            cost_submission_response = SendRequestContext().send_request(system, SendCostSubmission(
                self.cost_Submission_template, None))
            XMLAsserterContext(cost_submission_response).assert_no_errors()
            with allure.step("Get cost resubmission request"):
                self.cost_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.cost_resubmission.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.cost_submission.value, self.cost_resubmission_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(
                self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            cost_submission_response = SendRequestContext().send_request(system, SendCostSubmission(
                self.cost_Submission_template, None))
            XMLAsserterContext(cost_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendCostSubmission(self.cost_resubmission_template, live_data)), self.cost_resubmission_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.cost_resubmission_template is None:
            with allure.step("Get cost resubmission request"):
                self.cost_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.cost_resubmission_isolated.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.cost_submission.value, self.cost_resubmission_template)
        return SendRequestContext().send_request(system, SendCostSubmission(self.cost_resubmission_template,
                                                                            live_data)), self.cost_resubmission_template, list(self.template_flow)

class RemittanceAdviceMultipleClaims(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None
            and self.remittance_advice_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission_multiple_claims.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice_multiple_claims.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(
                self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendRemittanceAdvice(self.remittance_advice_template, live_data)), self.remittance_advice_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        if self.remittance_advice_template is None:
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.remittance_advice_multiple_claims_isolated.value, live_data=live_data,
                    variables=None)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
        return SendRequestContext().send_request(system, SendRemittanceAdvice(self.remittance_advice_template,
                                                                              live_data)), self.remittance_advice_template, list(self.template_flow)


class SecondRemittanceAdvice(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)

        with allure.step("Get person register request"):
            self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
            self._record_template(RequestPrefix.person_register.value, self.person_register_template)
        person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
        XMLAsserterContext(person_register_response).assert_no_errors()
        with allure.step("Get prior request"):
            self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
            self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
        prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
        XMLAsserterContext(prior_request_response).assert_no_errors()
        with allure.step("Get claim submission request"):
            self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
            self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
        XMLAsserterContext(claim_submission_response).assert_no_errors()
        with allure.step("Get remittance advice request"):
            self.remittance_advice_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice_tkbk.value, variables=variables)
            self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
        remittance_advice_response = SendRequestContext().send_request(system, SendRemittanceAdvice(
            self.remittance_advice_template, None))
        XMLAsserterContext(remittance_advice_response).assert_no_errors()
        with allure.step("Get claim resubmission request"):
            self.claim_submission_resubmission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_resubmission_correction.value, variables=variables)
            self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_resubmission_template)
        claim_resubmission_response = SendRequestContext().send_request(system, SendClaimSubmission(
            self.claim_submission_resubmission_template, None))
        XMLAsserterContext(claim_resubmission_response).assert_no_errors()
        with allure.step("Get remittance advice request"):
            self.second_remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.second_remittance_advice.value, live_data=live_data, variables=variables)
            self._record_template(RequestPrefix.remittance_advice.value, self.second_remittance_advice_template)
        return SendRequestContext().send_request(system, SendRemittanceAdvice(self.second_remittance_advice_template, live_data)), self.second_remittance_advice_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        raise Exception("Please use full scenario for this transaction type")


class ThirdRemittanceAdvice(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)

        with allure.step("Get person register request"):
            self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
            self._record_template(RequestPrefix.person_register.value, self.person_register_template)
        person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
        XMLAsserterContext(person_register_response).assert_no_errors()
        with allure.step("Get prior request"):
            self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
            self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
        prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
        XMLAsserterContext(prior_request_response).assert_no_errors()
        with allure.step("Get claim submission request"):
            self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
            self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
        claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
        XMLAsserterContext(claim_submission_response).assert_no_errors()
        with allure.step("Get remittance advice request"):
            self.remittance_advice_tkbk_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice_tkbk.value, variables=variables)
            self._record_template(RequestPrefix.remittance_advice_tkbk.value, self.remittance_advice_tkbk_template)
        remittance_advice_response = SendRequestContext().send_request(system, SendRemittanceAdvice(
            self.remittance_advice_tkbk_template, None))
        XMLAsserterContext(remittance_advice_response).assert_no_errors()
        with allure.step("Get claim resubmission request"):
            self.claim_submission_resubmission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_resubmission_correction.value, variables=variables)
            self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_resubmission_template)
        claim_resubmission_response = SendRequestContext().send_request(system, SendClaimSubmission(
            self.claim_submission_resubmission_template, None))
        XMLAsserterContext(claim_resubmission_response).assert_no_errors()
        with allure.step("Get remittance advice request"):
            self.remittance_advice_tkbk_2_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice_second_tkbk.value, variables=variables)
            self._record_template(RequestPrefix.remittance_advice_tkbk.value, self.remittance_advice_tkbk_2_template)
        remittance_advice_response = SendRequestContext().send_request(system, SendRemittanceAdvice(
            self.remittance_advice_tkbk_2_template, None))
        XMLAsserterContext(remittance_advice_response).assert_no_errors()
        with allure.step("Get claim resubmission request"):
            self.claim_submission_second_resubmission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                request_name=RequestsName.claim_resubmission_correction.value, variables=variables)
            self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_second_resubmission_template)
        claim_second_resubmission_response = SendRequestContext().send_request(system, SendClaimSubmission(
            self.claim_submission_second_resubmission_template, None))
        XMLAsserterContext(claim_second_resubmission_response).assert_no_errors()
        with allure.step("Get remittance advice request"):
            self.second_remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.second_remittance_advice.value, live_data=live_data, variables=variables)
            self._record_template(RequestPrefix.remittance_advice.value, self.second_remittance_advice_template)
        return SendRequestContext().send_request(system, SendRemittanceAdvice(self.second_remittance_advice_template, live_data)), self.second_remittance_advice_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        raise Exception("Please use full scenario for this transaction type")


class SecondRemittanceAdviceAfterTKBK(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None
            and self.remittance_advice_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice_tkbk.value, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
            remittance_advice_response = SendRequestContext().send_request(system, SendRemittanceAdvice(
                self.remittance_advice_template, None))
            XMLAsserterContext(remittance_advice_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.second_remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.second_remittance_advice.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.second_remittance_advice_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(
                self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            remittance_advice_response = SendRequestContext().send_request(system, SendRemittanceAdvice(
                self.remittance_advice_template, None))
            XMLAsserterContext(remittance_advice_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendRemittanceAdvice(self.second_remittance_advice_template, live_data)), self.remittance_advice_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        raise Exception("Please use full scenario for this transaction type")

class RemittanceAdviceHAADClaim(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self._should_use_single_request():
            return self._do_single_request(system=system, live_data=live_data)
        if (self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None
            and self.remittance_advice_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
                self._record_template(RequestPrefix.person_register.value, self.person_register_template)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
                self._record_template(RequestPrefix.prior_request.value, self.prior_request_template)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission_haad.value, variables=variables)
                self._record_template(RequestPrefix.claim_submission.value, self.claim_submission_template)
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice.value, live_data=live_data, variables=variables)
                self._record_template(RequestPrefix.remittance_advice.value, self.remittance_advice_template)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserterContext(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserterContext(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(
                self.claim_submission_template, None))
            XMLAsserterContext(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendRemittanceAdvice(self.remittance_advice_template, live_data)), self.remittance_advice_template, list(self.template_flow)

    def _do_single_request(self, system: Systems, live_data=None):
        raise Exception("Please use full scenario for this transaction type")

class SearchTransactions(AbstractAssertionRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        prerequisite_transaction_response = None
        prerequisite_transaction_template = None
        prerequisite_prerequisite_response = None
        if self.prerequisites:
            try:
                self.prerequisites = self.prerequisites.split('\n')
            except AttributeError:
                pass
            prerequisite = self.prerequisites[-1].replace('\t','').replace('•','').strip()
            from utils.request_mapper.request_mapper_context import do_requests
            prerequisite_transaction_response, prerequisite_transaction_template, prerequisite_prerequisite_response = do_requests(under_test_request=prerequisite, prerequisites=self.prerequisites[:-1]).do_request(system)
            XMLAsserterContext(prerequisite_transaction_response).assert_no_errors()
            upload_transaction_id = get_transaction_from_request(prerequisite_transaction_template.tag)
            with allure.step("Get search transactions request"):
                self.search_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.search_transactions.value, live_data=live_data, prerequisites=[{"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "fileName", "to":"transactionFileName", "process":None},
                                                                                                                                                                        {"source": prerequisite_transaction_template, "from":"SenderID", "to":"callerLicense", "process":None},
                                                                                                                                                                        {"source": prerequisite_transaction_template, "from":"ReceiverID", "to":"ePartner", "process":None},
                                                                                                                                                                        {"source": prerequisite_transaction_response['request_xml'], "from": "login", "to":"login", "process":None},
                                                                                                                                                                        {"source": prerequisite_transaction_response['request_xml'], "from": "pwd", "to":"pwd", "process":None},
                                                                                                                                                                        {"source": None, "from": upload_transaction_id, "to":"transactionID", "process":None}])
        else:
            with allure.step("Get search transactions request"):
                self.search_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.search_transactions.value, live_data=live_data)
        # the condition is important so that any API search, get new, download, set downloaded can reach the upload transaction data
        return SendRequestContext().send_request(system, SendSearchTransactions(self.search_transaction_template, live_data)), prerequisite_transaction_template, prerequisite_transaction_response if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response

   


class GetNewPriorAuthorizationTransactions(AbstractAssertionRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        prerequisite_transaction_response = None
        prerequisite_transaction_template = None
        prerequisite_prerequisite_response = None
        if self.prerequisites:
            try:
                self.prerequisites = self.prerequisites.split('\n')
            except AttributeError:
                pass
            prerequisite = self.prerequisites[-1].replace('\t','').replace('•','').strip()
            from utils.request_mapper.request_mapper_context import do_requests
            prerequisite_transaction_response, prerequisite_transaction_template, prerequisite_prerequisite_response = do_requests(under_test_request=prerequisite, prerequisites=self.prerequisites[:-1]).do_request(system)
            XMLAsserterContext(prerequisite_transaction_response).assert_no_errors()

            with allure.step("Get new prior authorization transactions request"):
                self.get_new_prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.get_new_prior_authorization.value, live_data=live_data, prerequisites=[
                                                                                                                                                                        {"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "fileName", "to":"transactionFileName", "process":None},
                                                                                                                                                                        {"source": prerequisite_transaction_template, "from":"SenderID", "to":"SenderID", "process":None},
                                                                                                                                                                        {"source": prerequisite_transaction_template, "from": "ReceiverID", "to":"login", "process":get_login_from_id},
                                                                                                                                                                        {"source": prerequisite_transaction_template, "from": "ReceiverID", "to":"pwd", "process":get_password_from_id}])
        else:
            with allure.step("Get new prior authorization transactions request"):
                self.get_new_prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.get_new_prior_authorization.value, live_data=live_data)
        # the condition is important so that any API search, get new, download, set downloaded can reach the upload transaction data
        return SendRequestContext().send_request(system, SendGetNewPriorAuthorizationTransactions(self.get_new_prior_authorization_template, live_data)), prerequisite_transaction_template, prerequisite_transaction_response if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response

class GetNewTransactions(AbstractAssertionRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        prerequisite_transaction_response = None
        prerequisite_transaction_template = None
        prerequisite_prerequisite_response = None
        if self.prerequisites:
            try:
                self.prerequisites = self.prerequisites.split('\n')
            except AttributeError:
                pass
            prerequisite = self.prerequisites[-1].replace('\t', '').replace('•','').strip()
            from utils.request_mapper.request_mapper_context import do_requests
            prerequisite_transaction_response, prerequisite_transaction_template, prerequisite_prerequisite_response = do_requests(
                under_test_request=prerequisite, prerequisites=self.prerequisites[:-1]).do_request(system)
            XMLAsserterContext(prerequisite_transaction_response).assert_no_errors()
            with allure.step("Get (get new transactions) request"):
                self.get_new_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.get_new_transactions.value, live_data=live_data, prerequisites=[
                        {"source": prerequisite_transaction_template, "from": "SenderID", "to": "SenderID", 'process':None},
                        {"source": prerequisite_transaction_template, "from": "ReceiverID", "to": "login","process": get_login_from_id},
                        {"source": prerequisite_transaction_template, "from": "ReceiverID", "to": "pwd","process": get_password_from_id}])
        else:
            with allure.step("Get 'get new transactions' request"):
                self.get_new_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.get_new_transactions.value, live_data=live_data)
        return SendRequestContext().send_request(system, SendGetNewTransaction(self.get_new_transaction_template, live_data)), prerequisite_transaction_template, prerequisite_transaction_response if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response

class DownloadTransaction(AbstractAssertionRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        prerequisite_transaction_response = None
        prerequisite_transaction_template = None
        prerequisite_prerequisite_response = None
        if self.prerequisites:
            try:
                self.prerequisites = self.prerequisites.split('\n')
            except AttributeError:
                pass
            prerequisite = self.prerequisites[-1].replace('\t', '').replace('•', '').strip()
            from utils.request_mapper.request_mapper_context import do_requests
            prerequisite_transaction_response, prerequisite_transaction_template, prerequisite_prerequisite_response = do_requests(
                under_test_request=prerequisite, prerequisites=self.prerequisites[:-1]).do_request(system)
            XMLAsserterContext(prerequisite_transaction_response).assert_no_errors()
            with allure.step("Get download transaction request"):
                self.get_new_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.download_transaction.value, live_data=live_data, prerequisites=[
                        {"source": prerequisite_transaction_response['content'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['content'], "from": "TransactionID", "to": "fileId", 'process':None},
                        # {"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "login", "to": "login", 'process':None},
                        # {"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "pwd", "to": "pwd", 'process':None}])
                        {"source": prerequisite_transaction_template, "from": "ReceiverID", "to": "login",
                         "process": get_login_from_id},
                        {"source": prerequisite_transaction_template, "from": "ReceiverID", "to": "pwd",
                         "process": get_password_from_id}])
        else:
            with allure.step("Get download transaction request"):
                self.get_new_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.download_transaction.value, live_data=live_data)
        return SendRequestContext().send_request(system, SendDownloadTransaction(
            self.get_new_transaction_template, live_data)), prerequisite_transaction_template, prerequisite_transaction_response if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response

class SetTransactionDownloaded(AbstractAssertionRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        prerequisite_transaction_response = None
        prerequisite_transaction_template = None
        prerequisite_prerequisite_response = None
        if self.prerequisites:
            try:
                self.prerequisites = self.prerequisites.split('\n')
            except AttributeError:
                pass
            prerequisite = self.prerequisites[-1].replace('\t', '').replace('•', '').strip()
            from utils.request_mapper.request_mapper_context import do_requests
            prerequisite_transaction_response, prerequisite_transaction_template, prerequisite_prerequisite_response = do_requests(
                under_test_request=prerequisite, prerequisites=self.prerequisites[:-1]).do_request(system)
            XMLAsserterContext(prerequisite_transaction_response).assert_no_errors()
            with allure.step("Get set transaction downloaded request"):
                self.get_new_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.set_transaction_downloaded.value, live_data=live_data, prerequisites=[
                        {"source": prerequisite_transaction_response['content'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['content'], "from": "TransactionID",
                         "to": "fileId", 'process':None},
                        # {"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "login", "to": "login", 'process':None},
                        # {"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "pwd", "to": "pwd", 'process':None}])
                        {"source": prerequisite_transaction_template, "from": "ReceiverID", "to": "login",
                         "process": get_login_from_id},
                        {"source": prerequisite_transaction_template, "from": "ReceiverID", "to": "pwd",
                         "process": get_password_from_id}])
        else:
            with allure.step("Get set transaction downloaded request"):
                self.get_new_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.set_transaction_downloaded.value, live_data=live_data)
        return SendRequestContext().send_request(system, SendSetTransactionDownloaded(
            self.get_new_transaction_template, live_data)), prerequisite_transaction_template, prerequisite_transaction_response if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response

class Reconciliation(AbstractAssertionRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        prerequisite_transaction_response = None
        prerequisite_transaction_template = None
        prerequisite_prerequisite_response = None
        if self.prerequisites:
            try:
                self.prerequisites = self.prerequisites.split('\n')
            except AttributeError:
                pass
            prerequisite = self.prerequisites[-1].replace('\t', '').replace('•', '').strip()
            from utils.request_mapper.request_mapper_context import do_requests
            prerequisite_transaction_response, prerequisite_transaction_template, prerequisite_prerequisite_response = do_requests(
                under_test_request=prerequisite, prerequisites=self.prerequisites[:-1]).do_request(system)
            XMLAsserterContext(prerequisite_transaction_response).assert_no_errors()
            with allure.step("Get Claim Count Reconciliation"):
                self.claim_count_reconciliation_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.reconciliation_transaction.value, live_data=live_data, prerequisites=[
                                                                                                             {"source":
                                                                                                                  prerequisite_transaction_response[
                                                                                                                      'request_xml'],
                                                                                                              "from": "login",
                                                                                                              "to": "login",
                                                                                                              "process": None},
                                                                                                             {"source":None,
                                                                                                              "from": prerequisite_transaction_template.tag,
                                                                                                              "to": "transactionName",
                                                                                                              "process": None},
                                                                                                             {"source":
                                                                                                                  prerequisite_transaction_response[
                                                                                                                      'request_xml'],
                                                                                                              "from": "pwd",
                                                                                                              "to": "pwd",
                                                                                                              "process": None}])
        else:
            with allure.step("Get Claim Count Reconciliation"):
                self.claim_count_reconciliation_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.reconciliation_transaction.value, live_data=live_data)
        # the condition is important so that any API search, get new, download, set downloaded can reach the upload transaction data
        return SendRequestContext().send_request(system, SendClaimCountConciliation(self.claim_count_reconciliation_template,
                                                                                live_data)), prerequisite_transaction_template, prerequisite_transaction_response if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response

class GetPersonInsuranceHistory(AbstractAssertionRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        prerequisite_transaction_response = None
        prerequisite_transaction_template = None
        prerequisite_prerequisite_response = None
        if self.prerequisites:
            try:
                self.prerequisites = self.prerequisites.split('\n')
            except AttributeError:
                pass
            prerequisite = self.prerequisites[-1].replace('\t', '').replace('•', '').strip()
            from utils.request_mapper.request_mapper_context import do_requests
            prerequisite_transaction_response, prerequisite_transaction_template, prerequisite_prerequisite_response = do_requests(
                under_test_request=prerequisite, prerequisites=self.prerequisites[:-1]).do_request(system)
            XMLAsserterContext(prerequisite_transaction_response).assert_no_errors()
            with allure.step("Get Person Insurance History"):
                self.get_person_insurance_history_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.get_person_insurance_history.value, live_data=live_data, prerequisites=[
                        {"source":
                             prerequisite_transaction_response[
                                 'request_xml'],
                         "from": "login",
                         "to": "login",
                         "process": None},
                        {"source": prerequisite_transaction_template,
                         "from": "EmiratesIDNumber",
                         "to": "EmiratesID",
                         "process": None},
                        {"source": prerequisite_transaction_template,
                         "from": "UnifiedNumber",
                         "to": "UnifiedID",
                         "process": None},
                        {"source":
                             prerequisite_transaction_response[
                                 'request_xml'],
                         "from": "pwd",
                         "to": "pwd",
                         "process": None}])
        else:
            with allure.step("Get Person Insurance History"):
                self.get_person_insurance_history_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.get_person_insurance_history.value, live_data=live_data)
        # the condition is important so that any API search, get new, download, set downloaded can reach the upload transaction data
        return SendRequestContext().send_request(system,
                                                 SendGetPersonInsuranceHistory(self.get_person_insurance_history_template,
                                                                            live_data)), prerequisite_transaction_template, prerequisite_transaction_response if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response

class PayForQuality(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self.pay_for_quality_template is None:
            with allure.step("Get pay for quality request"):
                self.pay_for_quality_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.pay_for_quality.value, live_data=live_data, variables=None)
                self._record_template(RequestPrefix.pay_for_quality.value, self.pay_for_quality_template)
        return SendRequestContext().send_request(system, SendPayForQuality(self.pay_for_quality_template, live_data)), self.pay_for_quality_template, list(self.template_flow)


class DefaultAbstractRequest(AbstractRequestMapper):

    def __init__(self, prerequisites, request_name):
        super().__init__(prerequisites)
        self.request_name = request_name

    def do_request(self, system: Systems, live_data=None):
        raise Exception(f"Unexpected type of request {self.request_name}")
