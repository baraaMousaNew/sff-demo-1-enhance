import allure

from utils.template_generator.decorators.extract_from_prerequisites_decorator import ExtractFromPrerequisitesDecorator
from utils.template_generator.decorators.generate_template_variables_values_decorator import \
    GenerateVariablesValuesDecorator
from utils.template_generator.decorators.get_template_decorator import GetTemplateDecorator
from utils.template_generator.decorators.get_template_variables_decorator import GetVariablesDecorator
from utils.template_generator.decorators.replace_live_values_decorator import ReplaceLiveValueDecorator
from utils.template_generator.decorators.replace_template_variables_values_decorator import \
    ReplaceTemplateVariablesValuesDecorator
from utils.template_generator.request_template import AbstractRequestTemplate, RequestTemplate
from utils.template_generator.requests_name_enums import RequestsName


class GetRequestTemplate:

    def __init__(self):
        self.template:AbstractRequestTemplate = RequestTemplate()

    def get_template_request(self, request_name, variables=None, live_data=None, prerequisites=None, health_checker=None):
        if request_name.lower() == RequestsName.person_register.value:
            # with allure.step('Get person register request'):
                allure.attach(
                    "Starting the process of getting person register request",
                    name='-- Person Register --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(RequestTemplate())))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/person_register_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.person_register_new.value:
            # with allure.step('Get person register request'):
                allure.attach(
                    "Starting the process of getting person register request",
                    name='-- New Person Register --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(RequestTemplate())))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/person_register_template_new.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.person_register_resubmission.value:
            # with allure.step('Get person register request'):
                allure.attach(
                    "Starting the process of getting person register request",
                    name='-- Person Register Resubmission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(RequestTemplate())))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/person_register_template_resubmission.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request",
                    name='-- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(RequestTemplate())))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_prescription.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request - prescription",
                    name='-- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(RequestTemplate())))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_prescription_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_cancellation.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request - cancellation",
                    name='-- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(RequestTemplate())))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_cancellation_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_extension.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request - extension",
                    name='-- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(RequestTemplate())))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_extension_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_eligibility.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request - eligibility",
                    name='-- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(RequestTemplate())))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_eligibility_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_resubmission.value:
            allure.attach(
                "Starting the process of getting prior request",
                name='-- Prior Request --',
                attachment_type=allure.attachment_type.TEXT
            )
            self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(RequestTemplate())))))
            return self.template.create_template(request_name=request_name,
                                                 template="xml_templates/prior_request_resubmission_template.xml",
                                                 live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization",
                    name='-- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(RequestTemplate())))))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization_large.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization - large",
                    name='-- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator((RequestTemplate()))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_large.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='-- Claim Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(RequestTemplate())))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_submission_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.remittance_advice.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting remittance advice",
                    name='-- Remittance Advice --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(RequestTemplate())))))
                return self.template.create_template(request_name=request_name, template="xml_templates/remittance_advice_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.search_transactions.value:
            # with allure.step('Get search transactions'):
                allure.attach(
                    "Starting the process of getting search transactions",
                    name='-- Search Transactions --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/search_transactions_template.xml", live_data=live_data, results=variables, prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.get_new_transactions.value:
            # with allure.step('Get new transactions'):
                allure.attach(
                    "Starting the process of getting new transactions",
                    name='-- Get New Transactions --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/get_new_transactions_template.xml", live_data=live_data, results=variables, prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.download_transaction.value:
            # with allure.step('Download transaction file'):
                allure.attach(
                    "Starting the process of getting new transactions",
                    name='-- Download Transaction File --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/download_transaction_file_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.set_transaction_downloaded.value:
            # with allure.step('Set transaction downloaded'):
                allure.attach(
                    "Starting the process of getting new transactions",
                    name='-- Set Transaction Downloaded --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/set_transaction_downloaded_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.person_register_upload_transaction.value:
            # with allure.step('Get upload transaction for person register'):
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='-- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_person_register_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_upload_transaction.value:
            # with allure.step('Get upload transaction for prior request'):
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='-- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_prior_request_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization_upload_transaction.value:
            # with allure.step('Get upload transaction for prior authorization'):
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='-- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_prior_authorization_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_upload_transaction.value:
            # with allure.step('Get upload transaction for claim submission'):
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='-- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_claim_submission_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.remittance_advice_upload_transaction.value:
            # with allure.step('Get upload transaction for remittance advice'):
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='-- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_remittance_advice_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        else:
            self.template = "<Empty Body>"
            return self.template