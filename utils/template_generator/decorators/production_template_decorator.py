from utils.template_generator.decorators.base_decorator import BaseDecorator
import os
import allure
import xml.etree.ElementTree as ET
from utils.env_vars import EnvVar
from utils.execution_mode import ExecutionMode



class ProductionTemplateDecorator(BaseDecorator):

    def create_template(self, request_name,template, parent="", results=None, results_index=0, live_data=None, prerequisites=None, health_checker=None):
        if (os.environ.get(EnvVar.TARGET_ENVIRONMENT) == 'production' or
        os.environ.get(EnvVar.SOAP_EXECUTION_MODE) == ExecutionMode.SYSTEM1_BOTH_ENVS):
            element = template.find('Header/DispositionFlag')
            if element is not None:
                element.text = 'TEST'
                allure.attach(
                    ET.tostring(template, encoding="unicode"),
                    name="d7f3a2 - Replace production necessary variables",
                    attachment_type=allure.attachment_type.XML)
            else:
                raise Exception("Transaction must have disposition flag in header")
        elif os.environ.get(EnvVar.CUSTOM_DISPOSITION_FLAG):
            element = template.find('Header/DispositionFlag')
            if element is not None:
                element.text = os.environ.get(EnvVar.CUSTOM_DISPOSITION_FLAG)
                allure.attach(
                    ET.tostring(template, encoding="unicode"),
                    name="d7f3a2 - Replace production necessary variables",
                    attachment_type=allure.attachment_type.XML)
            else:
                raise Exception("Transaction must have disposition flag in header")
        template, results, live_data = super().create_template(request_name=request_name, template=template, parent=parent, results=results, live_data=live_data, results_index=results_index, prerequisites=prerequisites, health_checker=health_checker)
        return template, results, live_data
                
            
            