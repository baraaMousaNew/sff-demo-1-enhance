from abc import abstractmethod, ABC

import allure
import pytest

from utils.asserter.asserter import XMLAsserter
from utils.request_sender.send_request import SendPersonRegister, SendPriorRequest, SendPriorAuthorization, \
    SendClaimSubmission, SendRemittanceAdvice, SendSearchTransactions, SendGetNewTransaction, \
    SendDownloadTransaction, SendSetTransactionDownloaded, SendPriorRequestZipped
from utils.request_sender.send_request_context import SendRequestContext
from utils.request_sender.system_enums import Systems
from utils.template_generator.requests_name_enums import RequestsName
from utils.template_generator.template_generator import GetRequestTemplate
import xml.etree.ElementTree as ET

class AbstractRequestMapper(ABC):

    def __init__(self, prerequisites):
        self.person_register_template = None
        self.prior_request_template = None
        self.prior_authorization_template = None
        self.prior_authorization_resubmission_template = None
        self.claim_submission_template = None
        self.remittance_advice_template = None
        self.search_transaction_template = None
        self.get_new_transaction_template = None
        self.prior_request_resubmission_template = None
        self.prerequisites = prerequisites

    @abstractmethod
    def do_request(self, live_data, system: Systems):
        pass

class PersonRegister(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self.person_register_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value, live_data=live_data)
        return SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, live_data)), self.person_register_template, None

class PersonRegisterResubmission(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self.person_register_template is None:
            with allure.step("Get person register request - new registration"):
                self.person_register_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_new.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get person register request - resubmission"):
                self.person_register_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register_resubmission.value, live_data=live_data, variables=variables)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, live_data)), self.person_register_template, None

class PriorAuthorizationResubmission(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if (self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None
            and self.prior_authorization_resubmission_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization.value, variables=variables)
            prior_auth_response = SendRequestContext().send_request(system,
                                                                           SendPriorAuthorization(self.prior_authorization_template,
                                                                                            None))
            XMLAsserter(prior_auth_response).assert_no_errors()
            with allure.step("Get prior authorization - resubmission"):
                self.prior_authorization_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_authorization.value, variables=variables, live_data=live_data)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
            prior_auth_response = SendRequestContext().send_request(system,
                                                                       SendPriorAuthorization(self.prior_authorization_template,
                                                                                        None))
            XMLAsserter(prior_auth_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_resubmission_template, live_data)), self.prior_authorization_resubmission_template, None

class PriorRequest(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self.person_register_template is None and self.prior_request_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, live_data=live_data, variables=variables)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
        return SendRequestContext().send_request(system,SendPriorRequest(self.prior_request_template, live_data)), self.prior_request_template, None

class PriorRequestResubmission(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if (self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None and
            self.prior_request_resubmission_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.person_register.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request.value, variables=variables)
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template,
                                                                                        None))
            XMLAsserter(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization"):
                self.prior_authorization_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_authorization.value, variables=variables)
            prior_authorization_response = SendRequestContext().send_request(system,
                                                                       SendPriorAuthorization(self.prior_authorization_template,
                                                                                        None))
            XMLAsserter(prior_authorization_response).assert_no_errors()
            with allure.step("Get prior request resubmission"):
                self.prior_request_resubmission_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request_resubmission.value, live_data=live_data, variables=variables)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template,
                                                                                        None))
            XMLAsserter(prior_request_response).assert_no_errors()
            prior_authorization_response = SendRequestContext().send_request(system,SendPriorAuthorization(self.prior_authorization_template, None))
            XMLAsserter(prior_authorization_response).assert_no_errors()
        return SendRequestContext().send_request(system,SendPriorRequest(self.prior_request_resubmission_template, live_data)), self.prior_request_template, None

class PriorRequestZipped(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self.person_register_template is None and self.prior_request_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.person_register.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.prior_request.value, live_data=live_data, variables=variables)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorRequestZipped(self.prior_request_template,
                                                                          live_data)), self.prior_request_template, None


class PriorAuthorizationPrescription(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get prior request - prescription"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_prescription.value, variables=variables)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization.value, live_data=live_data, variables=variables)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, live_data)), self.prior_authorization_template, None

class PriorAuthorizationCancellation(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get prior request - cancellation"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_cancellation.value, variables=variables)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization.value, live_data=live_data, variables=variables)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, live_data)), self.prior_authorization_template, None

class PriorAuthorizationExtension(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get prior request - extension"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_extension.value, variables=variables)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization.value, live_data=live_data, variables=variables)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, live_data)), self.prior_authorization_template, None

class PriorAuthorizationEligibility(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get prior request - eligibility"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request_eligibility.value, variables=variables)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization.value, live_data=live_data, variables=variables)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, live_data)), self.prior_authorization_template, None

class PriorAuthorizationLarge(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request - large"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization_large.value, live_data=live_data, variables=variables)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, live_data)), self.prior_authorization_template, None

class PriorAuthorization(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self.person_register_template is None and self.prior_request_template is None and self.prior_authorization_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template,None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
            with allure.step("Get prior authorization request"):
                self.prior_authorization_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_authorization.value, live_data=live_data, variables=variables)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendPriorAuthorization(self.prior_authorization_template, live_data)), self.prior_authorization_template, None

class ClaimSubmission(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None:
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, live_data=live_data, variables=variables)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, live_data)), self.claim_submission_template, None

class RemittanceAdvice(AbstractRequestMapper):

    def do_request(self, system: Systems, live_data=None):
        if (self.person_register_template is None and self.prior_request_template is None and self.claim_submission_template is None
            and self.remittance_advice_template is None):
            with allure.step("Get person register request"):
                self.person_register_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.person_register.value)
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            with allure.step("Get prior request"):
                self.prior_request_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.prior_request.value, variables=variables)
            prior_request_response = SendRequestContext().send_request(system, SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
            with allure.step("Get claim submission request"):
                self.claim_submission_template, variables, empty_live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.claim_submission.value, variables=variables)
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(self.claim_submission_template, None))
            XMLAsserter(claim_submission_response).assert_no_errors()
            with allure.step("Get remittance advice request"):
                self.remittance_advice_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.remittance_advice.value, live_data=live_data, variables=variables)
        else:
            person_register_response = SendRequestContext().send_request(system, SendPersonRegister(
                self.person_register_template, None))
            XMLAsserter(person_register_response).assert_no_errors()
            prior_request_response = SendRequestContext().send_request(system,
                                                                       SendPriorRequest(self.prior_request_template, None))
            XMLAsserter(prior_request_response).assert_no_errors()
            claim_submission_response = SendRequestContext().send_request(system, SendClaimSubmission(
                self.claim_submission_template, None))
            XMLAsserter(claim_submission_response).assert_no_errors()
        return SendRequestContext().send_request(system, SendRemittanceAdvice(self.remittance_advice_template, live_data)), self.remittance_advice_template, None


class SearchTransactions(AbstractRequestMapper):

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
            XMLAsserter(prerequisite_transaction_response).assert_no_errors()
            with allure.step("Get search transactions request"):
                self.search_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.search_transactions.value, live_data=live_data, prerequisites=[{"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "fileName", "to":"transactionFileName"},
                                                                                                                                                                        {"source": prerequisite_transaction_template, "from":"SenderID", "to":"callerLicense"},
                                                                                                                                                                        {"source": prerequisite_transaction_template, "from":"ReceiverID", "to":"ePartner"},
                                                                                                                                                                        {"source": prerequisite_transaction_response['request_xml'], "from": "login", "to":"login"},
                                                                                                                                                                        {"source": prerequisite_transaction_response['request_xml'], "from": "pwd", "to":"pwd"}])
        else:
            with allure.step("Get search transactions request"):
                self.search_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.search_transactions.value, live_data=live_data)
        # the condition is important so that any API search, get new, download, set downloaded can reach the upload transaction data
        return SendRequestContext().send_request(system, SendSearchTransactions(self.search_transaction_template, live_data)), prerequisite_transaction_template, prerequisite_transaction_response if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response


class GetNewTransactions(AbstractRequestMapper):

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
            XMLAsserter(prerequisite_transaction_response).assert_no_errors()
            with allure.step("Get 'get new transactions' request"):
                self.get_new_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.get_new_transactions.value, live_data=live_data, prerequisites=[
                        {"source": prerequisite_transaction_template, "from": "SenderID", "to": "SenderID"},
                        {"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "login", "to": "login"},
                        {"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "pwd", "to": "pwd"}])
        else:
            with allure.step("Get 'get new transactions' request"):
                self.get_new_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(request_name=RequestsName.get_new_transactions.value, live_data=live_data)
        return SendRequestContext().send_request(system, SendGetNewTransaction(self.get_new_transaction_template, live_data)), prerequisite_transaction_template, prerequisite_transaction_response if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response


class DownloadTransaction(AbstractRequestMapper):

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
            XMLAsserter(prerequisite_transaction_response).assert_no_errors()
            with allure.step("Get download transaction request"):
                self.get_new_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.download_transaction.value, live_data=live_data, prerequisites=[
                        {"source": prerequisite_transaction_response['content'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['content'], "from": "TransactionID", "to": "fileId"},
                        {"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "login", "to": "login"},
                        {"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "pwd", "to": "pwd"}])
        else:
            with allure.step("Get download transaction request"):
                self.get_new_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.download_transaction.value, live_data=live_data)
        return SendRequestContext().send_request(system, SendDownloadTransaction(
            self.get_new_transaction_template, live_data)), prerequisite_transaction_template, prerequisite_transaction_response if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response

class SetTransactionDownloaded(AbstractRequestMapper):

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
            XMLAsserter(prerequisite_transaction_response).assert_no_errors()
            with allure.step("Get set transaction downloaded request"):
                self.get_new_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.set_transaction_downloaded.value, live_data=live_data, prerequisites=[
                        {"source": prerequisite_transaction_response['content'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['content'], "from": "TransactionID",
                         "to": "fileId"},
                        {"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "login", "to": "login"},
                        {"source": prerequisite_transaction_response['request_xml'] if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response['request_xml'], "from": "pwd", "to": "pwd"}])
        else:
            with allure.step("Get set transaction downloaded request"):
                self.get_new_transaction_template, variables, live_data = GetRequestTemplate().get_template_request(
                    request_name=RequestsName.set_transaction_downloaded.value, live_data=live_data)
        return SendRequestContext().send_request(system, SendSetTransactionDownloaded(
            self.get_new_transaction_template, live_data)), prerequisite_transaction_template, prerequisite_transaction_response if prerequisite_prerequisite_response is None else prerequisite_prerequisite_response




class DefaultAbstractRequest(AbstractRequestMapper):

    def __init__(self, prerequisites, request_name):
        super().__init__(prerequisites)
        self.request_name = request_name

    def do_request(self, system: Systems, live_data=None):
        return pytest.fail(f"<Error: Unexpected type of request {self.request_name}> ")
