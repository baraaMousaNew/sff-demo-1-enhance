from utils.template_generator.decorators.production_template_decorator import ProductionTemplateDecorator
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
                    name='c9a155 - -- Person Register --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/person_register_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        if request_name.lower() == RequestsName.person_register_resubmission.value:
            # with allure.step('Get person register request'):
                allure.attach(
                    "Starting the process of getting person register request",
                    name='c9a155 - -- Person Register --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/person_register_resubmission_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.person_register_self_pay.value:
            # with allure.step('Get person register request'):
                allure.attach(
                    "Starting the process of getting person register request",
                    name='c9a155 - -- Person Register --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/person_register_selfpay_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_self_pay.value:
            # with allure.step('Get person register request'):
                allure.attach(
                    "Starting the process of getting claim submission request",
                    name='c9a155 - -- Claim Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/claim_submission_selfpay_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker_self_pay.value:
            # with allure.step('Get claim checker request'):
                allure.attach(
                    "Starting the process of getting claim checker request",
                    name='c9a155 - -- Claim Checker --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/claim_checker_selfpay_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker_self_pay_isolated.value:
            # with allure.step('Get claim checker request'):
                allure.attach(
                    "Starting the process of getting claim checker request",
                    name='c9a155 - -- Claim Checker --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/claim_checker_selfpay_template_isolated.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_resubmission_no_remittance.value:
            # with allure.step('Get person register request'):
                allure.attach(
                    "Starting the process of getting claim submission request",
                    name='c9a155 - -- Claim Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/claim_resubmission_no_remittance_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.person_register_tpa.value:
            # with allure.step('Get person register request'):
                allure.attach(
                    "Starting the process of getting person register request",
                    name='c9a155 - -- Person Register --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/person_register_tpa_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.person_register_new.value:
            # with allure.step('Get person register request'):
                allure.attach(
                    "Starting the process of getting person register request",
                    name='c9a155 - -- New Person Register --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/person_register_template_new.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.person_register_resubmission.value:
            # with allure.step('Get person register request'):
                allure.attach(
                    "Starting the process of getting person register request",
                    name='c9a155 - -- Person Register Resubmission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/person_register_template_resubmission.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request",
                    name='c9a155 - -- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_multiple_activities.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request",
                    name='c9a155 - -- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_multiple_activities_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_consultation.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request",
                    name='c9a155 - -- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_consultation_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_to_tpa.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request",
                    name='c9a155 - -- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_to_tpa_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_isolated.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request",
                    name='c9a155 - -- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_template_isolated.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_to_tpa_isolated.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request",
                    name='c9a155 - -- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_to_tpa_template_isolated.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_greater_than_6MB.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request",
                    name='c9a155 - -- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_resubmission_greater_6MB_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_greater_than_6MB_isolated.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request",
                    name='c9a155 - -- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_resubmission_greater_6MB_template_isolated.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)                                
        elif request_name.lower() == RequestsName.prior_request_prescription.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request - prescription",
                    name='c9a155 - -- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_prescription_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_cancellation.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request - cancellation",
                    name='c9a155 - -- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_cancellation_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_extension.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request - extension",
                    name='c9a155 - -- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_extension_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_eligibility.value:
            # with allure.step('Get prior request'):
                allure.attach(
                    "Starting the process of getting prior request - eligibility",
                    name='c9a155 - -- Prior Request --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_eligibility_template.xml",
                                                     live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_resubmission.value:
            allure.attach(
                "Starting the process of getting prior request",
                name='c9a155 - -- Prior Request --',
                attachment_type=allure.attachment_type.TEXT
            )
            self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
            return self.template.create_template(request_name=request_name,
                                                 template="xml_templates/prior_request_resubmission_template.xml",
                                                 live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization",
                    name='c9a155 - -- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization_prescription.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization",
                    name='c9a155 - -- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_prescription_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization_prescription_isolated.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization",
                    name='c9a155 - -- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_prescription_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization_eligibility_isolated.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization",
                    name='c9a155 - -- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_eligibility_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization_tpa.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization",
                    name='c9a155 - -- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_tpa_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization_cancellation.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization",
                    name='c9a155 - -- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_cancellation_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization_extension.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization",
                    name='c9a155 - -- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_extension_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization_eligibility.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization",
                    name='c9a155 - -- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_eligibility_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization_isolated.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization",
                    name='c9a155 - -- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization_tpa_isolated.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization",
                    name='c9a155 - -- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_tpa_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_authorization_large.value:
            # with allure.step('Get prior authorization'):
                allure.attach(
                    "Starting the process of getting prior authorization - large",
                    name='c9a155 - -- Person Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(ProductionTemplateDecorator(RequestTemplate()))
                return self.template.create_template(request_name=request_name, template="xml_templates/prior_authorization_large.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='c9a155 - -- Claim Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_submission_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_multiple_activities.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='c9a155 - -- Claim Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_submission_multiple_activities_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_multiple_activities_isolated.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='c9a155 - -- Claim Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_submission_multiple_activities_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_to_tpa.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='c9a155 - -- Claim Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_submission_to_tpa_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_isolated.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='c9a155 - -- Claim Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_submission_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker.value:
            # with allure.step('Get claim checker'):
                allure.attach(
                    "Starting the process of getting claim checker",
                    name='c9a155 - -- Claim Checker --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_checker_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker_isolated.value:
            # with allure.step('Get claim checker'):
                allure.attach(
                    "Starting the process of getting claim checker",
                    name='c9a155 - -- Claim Checker --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_checker_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker_no_prior_authorization.value:
            # with allure.step('Get claim checker'):
                allure.attach(
                    "Starting the process of getting claim checker with no prior authorization",
                    name='c9a155 - -- Claim Checker No Prior Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_checker_no_prior_authorization_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker_no_prior_authorization_isolated.value:
            # with allure.step('Get claim checker'):
                allure.attach(
                    "Starting the process of getting claim checker with no prior authorization",
                    name='c9a155 - -- Claim Checker No Prior Authorization --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_checker_no_prior_authorization_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker_resubmission.value:
            # with allure.step('Get claim checker'):
                allure.attach(
                    "Starting the process of getting claim checker resubmission",
                    name='c9a155 - -- Claim Checker Re-Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_checker_resubmission_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker_resubmission_isolated.value:
            # with allure.step('Get claim checker'):
                allure.attach(
                    "Starting the process of getting claim checker resubmission",
                    name='c9a155 - -- Claim Checker Re-Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_checker_resubmission_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker_no_remittance.value:
            # with allure.step('Get claim checker'):
                allure.attach(
                    "Starting the process of getting claim checker no remittance",
                    name='c9a155 - -- Claim Checker No Remittance --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_checker_no_remittance_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker_no_remittance_isolated.value:
            # with allure.step('Get claim checker'):
                allure.attach(
                    "Starting the process of getting claim checker no remittance",
                    name='c9a155 - -- Claim Checker No Remittance --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_checker_no_remittance_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker_multiple_claims.value:
            # with allure.step('Get claim checker'):
                allure.attach(
                    "Starting the process of getting claim checker",
                    name='c9a155 - -- Claim Checker --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_checker_multiple_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker_multiple_claims_isolated.value:
            # with allure.step('Get claim checker'):
                allure.attach(
                    "Starting the process of getting claim checker",
                    name='c9a155 - -- Claim Checker --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_checker_multiple_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_to_tpa_isolated.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='c9a155 - -- Claim Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_submission_to_tpa_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_multiple_claims.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='c9a155 - -- Claim Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_submission_multiple_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_multiple_claims_isolated.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='c9a155 - -- Claim Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_submission_multiple_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_resubmission.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='c9a155 - -- Claim Re-Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_resubmission_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_resubmission_correction.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='c9a155 - -- Claim Re-Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_resubmission_correction_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_second_resubmission.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='c9a155 - -- Claim Re-Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_second_resubmission_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_checker_second_resubmission.value:
            # with allure.step('Get claim checker'):
                allure.attach(
                    "Starting the process of getting claim checker second resubmission",
                    name='c9a155 - -- Claim Checker Second Re-Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_checker_second_resubmission_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_haad.value:
            # with allure.step('Get claim submission'):
                allure.attach(
                    "Starting the process of getting claim submission",
                    name='c9a155 - -- Claim Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/claim_submission_HAAD_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.remittance_advice.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting remittance advice",
                    name='c9a155 - -- Remittance Advice --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/remittance_advice_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.remittance_advice_multiple_activities.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting remittance advice",
                    name='c9a155 - -- Remittance Advice --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/remittance_advice_multiple_activities_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.remittance_advice_multiple_activities_isolated.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting remittance advice",
                    name='c9a155 - -- Remittance Advice --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/remittance_advice_multiple_activities_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.remittance_advice_tpa.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting remittance advice",
                    name='c9a155 - -- Remittance Advice --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/remittance_advice_tpa_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.remittance_advice_tkbk.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting remittance advice",
                    name='c9a155 - -- Remittance Advice tkbk --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/remittance_advice_tkbk_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.remittance_advice_second_tkbk.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting remittance advice",
                    name='c9a155 - -- Remittance Advice tkbk --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/remittance_advice_tkbk_2_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.remittance_advice_isolated.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting remittance advice",
                    name='c9a155 - -- Remittance Advice --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/remittance_advice_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.remittance_advice_tpa_isolated.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting remittance advice",
                    name='c9a155 - -- Remittance Advice --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/remittance_advice_tpa_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.cost_submission.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting cost submission",
                    name='c9a155 - -- Cost Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/cost_submission_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.cost_submission_isolated.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting cost submission",
                    name='c9a155 - -- Cost Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/cost_submission_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() in (RequestsName.cost_submission_multiple_claims.value, RequestsName.cost_submission_multiple_claims_isolated.value):
                allure.attach(
                    "Starting the process of getting cost submission multiple claims",
                    name='c9a155 - -- Cost Submission Multiple Claims --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/cost_submission_multiple_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.cost_resubmission.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting cost submission",
                    name='c9a155 - -- Cost Submission --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/cost_resubmission_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.remittance_advice_multiple_claims.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting remittance advice",
                    name='c9a155 - -- Remittance Advice --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/remittance_advice_multiple_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.remittance_advice_multiple_claims_isolated.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting remittance advice",
                    name='c9a155 - -- Remittance Advice --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/remittance_advice_multiple_template_isolated.xml", live_data=live_data, results=variables, health_checker=health_checker)
        elif request_name.lower() == RequestsName.second_remittance_advice.value:
            # with allure.step('Get remittance advice'):
                allure.attach(
                    "Starting the process of getting remittance advice",
                    name='c9a155 - -- Remittance Advice --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template =  GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/remittance_advice_second_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        # NOTE: Cannot use ProductionTemplateDecorator because this request doesn't post any data
        elif request_name.lower() == RequestsName.search_transactions.value:
            # with allure.step('Get search transactions'):
                allure.attach(
                    "Starting the process of getting search transactions",
                    name='c9a155 - -- Search Transactions --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/search_transactions_template.xml", live_data=live_data, results=variables, prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Cannot use ProductionTemplateDecorator because this request doesn't post any data
        elif request_name.lower() == RequestsName.reconciliation_transaction.value:
            # with allure.step('Get search transactions'):
                allure.attach(
                    "Starting the process of getting claim count reconciliation",
                    name='c9a101 - -- Reconciliation Transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/reconciliation.xml", live_data=live_data, results=variables, prerequisites=prerequisites, health_checker=health_checker)
            # NOTE: Cannot use ProductionTemplateDecorator because this request doesn't post any data
        elif request_name.lower() == RequestsName.get_person_insurance_history.value:
            # with allure.step('Get search transactions'):
            allure.attach(
                "Starting the process of get person insurance history",
                name='c9awe1 - -- Get Person Insurance History Transaction --',
                attachment_type=allure.attachment_type.TEXT
            )
            self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                ReplaceTemplateVariablesValuesDecorator(
                    ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
            return self.template.create_template(request_name=request_name, template="xml_templates/get_person_insurance_history.xml",
                                                 live_data=live_data, results=variables, prerequisites=prerequisites,
                                                 health_checker=health_checker)
        # NOTE: Cannot use ProductionTemplateDecorator because this request doesn't post any data
        elif request_name.lower() == RequestsName.get_new_prior_authorization.value:
            # with allure.step('Get search transactions'):
                allure.attach(
                    "Starting the process of getting search transactions",
                    name='c9a155 - -- Search Transactions --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/get_new_prior_authorization_transactions.xml", live_data=live_data, results=variables, prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Cannot use ProductionTemplateDecorator because this request doesn't post any data
        elif request_name.lower() == RequestsName.get_new_transactions.value:
            # with allure.step('Get new transactions'):
                allure.attach(
                    "Starting the process of getting new transactions",
                    name='c9a155 - -- Get New Transactions --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(ReplaceTemplateVariablesValuesDecorator(ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/get_new_transactions_template.xml", live_data=live_data, results=variables, prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Cannot use ProductionTemplateDecorator because this request doesn't post any data
        elif request_name.lower() == RequestsName.download_transaction.value:
            # with allure.step('Download transaction file'):
                allure.attach(
                    "Starting the process of getting new transactions",
                    name='c9a155 - -- Download Transaction File --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/download_transaction_file_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Cannot use ProductionTemplateDecorator because this request doesn't post any data
        elif request_name.lower() == RequestsName.set_transaction_downloaded.value:
            # with allure.step('Set transaction downloaded'):
                allure.attach(
                    "Starting the process of getting new transactions",
                    name='c9a155 - -- Set Transaction Downloaded --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/set_transaction_downloaded_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Upload transaction requests should NOT use ProductionTemplateDecorator
        elif request_name.lower() == RequestsName.person_register_upload_transaction.value:
            # with allure.step('Get upload transaction for person register'):
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='c9a155 - -- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_person_register_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
            # NOTE: Upload transaction requests should NOT use ProductionTemplateDecorator
        elif request_name.lower() == RequestsName.person_register_provider_upload_transaction.value:
            # with allure.step('Get upload transaction for person register'):
            allure.attach(
                "Starting the process of getting upload transaction",
                name='c9a155 - -- Upload transaction --',
                attachment_type=allure.attachment_type.TEXT
            )
            self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                ReplaceTemplateVariablesValuesDecorator(
                    ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
            return self.template.create_template(request_name=request_name,
                                                 template="xml_templates/upload_transaction_person_register_provider_template.xml",
                                                 live_data=live_data, results=variables,
                                                 prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Upload transaction requests should NOT use ProductionTemplateDecorator
        elif request_name.lower() == RequestsName.person_register_tpa_upload_transaction.value:
            # with allure.step('Get upload transaction for person register'):
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='c9a155 - -- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_person_register_tpa_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Upload transaction requests should NOT use ProductionTemplateDecorator
        elif request_name.lower() == RequestsName.prior_request_upload_transaction.value:
            # with allure.step('Get upload transaction for prior request'):
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='c9a155 - -- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_prior_request_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Upload transaction requests should NOT use ProductionTemplateDecorator
        elif request_name.lower() == RequestsName.prior_authorization_upload_transaction.value:
            # with allure.step('Get upload transaction for prior authorization'):
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='c9a155 - -- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))  
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_prior_authorization_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Upload transaction requests should NOT use ProductionTemplateDecorator
        elif request_name.lower() == RequestsName.prior_authorization_tpa_upload_transaction.value:
            # with allure.step('Get upload transaction for prior authorization'):
            allure.attach(
                "Starting the process of getting upload transaction",
                name='c9a155 - -- Upload transaction --',
                attachment_type=allure.attachment_type.TEXT
            )
            self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                ReplaceTemplateVariablesValuesDecorator(
                    ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
            return self.template.create_template(request_name=request_name,
                                                 template="xml_templates/upload_transaction_prior_authorization_tpa_template.xml",
                                                 live_data=live_data, results=variables,
                                                 prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Upload transaction requests should NOT use ProductionTemplateDecorator
        elif request_name.lower() == RequestsName.claim_submission_upload_transaction.value:
            # with allure.step('Get upload transaction for claim submission'):
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='c9a155 - -- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_claim_submission_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Upload transaction requests should NOT use ProductionTemplateDecorator
        elif request_name.lower() == RequestsName.remittance_advice_upload_transaction.value:
            # with allure.step('Get upload transaction for remittance advice'):
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='c9a155 - -- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_remittance_advice_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Upload transaction requests should NOT use ProductionTemplateDecorator
        elif request_name.lower() == RequestsName.remittance_advice_tpa_upload_transaction.value:
            # with allure.step('Get upload transaction for remittance advice'):
            allure.attach(
                "Starting the process of getting upload transaction",
                name='c9a155 - -- Upload transaction --',
                attachment_type=allure.attachment_type.TEXT
            )
            self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                ReplaceTemplateVariablesValuesDecorator(
                    ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
            return self.template.create_template(request_name=request_name,
                                                 template="xml_templates/upload_transaction_remittance_advice_tpa_template.xml",
                                                 live_data=live_data, results=variables,
                                                 prerequisites=prerequisites, health_checker=health_checker)
        # NOTE: Upload transaction requests should NOT use ProductionTemplateDecorator
        elif request_name.lower() == RequestsName.cost_submission_upload_transaction.value:
            # with allure.step('Get upload transaction for remittance advice'):
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='c9a155 - -- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_cost_submission_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.claim_submission_resubmission_isolated.value:
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='c9a155 - -- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate())))))))  
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/claim_resubmission_template_isolated.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.cost_resubmission_isolated.value:
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='c9a155 - -- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate())))))))  
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/cost_resubmission_template_isolated.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.prior_request_resubmission_isolated.value:
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='c9a155 - -- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate())))))))  
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/prior_request_resubmission_template_isolated.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.pay_for_quality_upload_transaction.value:
                allure.attach(
                    "Starting the process of getting upload transaction",
                    name='c9a155 - -- Upload transaction --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(
                        ExtractFromPrerequisitesDecorator(ReplaceLiveValueDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name,
                                                     template="xml_templates/upload_transaction_pay_for_quality_template.xml",
                                                     live_data=live_data, results=variables,
                                                     prerequisites=prerequisites, health_checker=health_checker)
        elif request_name.lower() == RequestsName.pay_for_quality.value:
                allure.attach(
                    "Starting the process of getting pay for quality",
                    name='c9a155 - -- Pay For Quality --',
                    attachment_type=allure.attachment_type.TEXT
                )
                self.template = GetTemplateDecorator(GetVariablesDecorator(GenerateVariablesValuesDecorator(
                    ReplaceTemplateVariablesValuesDecorator(ReplaceLiveValueDecorator(ProductionTemplateDecorator(RequestTemplate()))))))
                return self.template.create_template(request_name=request_name, template="xml_templates/pay_for_quality_template.xml", live_data=live_data, results=variables, health_checker=health_checker)
        else:
            raise Exception(f"Template of request name {request_name} is not found")