import allure

from utils.allure_reporter import AllureReporter
from utils.template_generator.decorators.base_decorator import BaseDecorator
import xml.etree.ElementTree as ET


class GetTemplateDecorator(BaseDecorator):

    def create_template(self, request_name,template:str, parent="", results=None, results_index=0, live_data=None, prerequisites=None, health_checker=None):
        tree = ET.parse(template)
        root = tree.getroot()
        allure.attach(
                ET.tostring(root).decode('utf-8'),
                name="b8ec2b - Get template",
                attachment_type=allure.attachment_type.XML
                          )
        template, results, live_data = super().create_template(request_name=request_name,template=root, parent=parent, results=results, live_data=live_data, results_index=results_index, prerequisites=prerequisites, health_checker=health_checker)
        return template, results, live_data