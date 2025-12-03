import allure

from utils.allure_reporter import AllureReporter
from utils.template_generator.decorators.base_decorator import BaseDecorator
from utils.variable_processor import VariableProcessor


class GenerateVariablesValuesDecorator(BaseDecorator):

    def create_template(self, request_name,template, parent="", results=None, results_index=0, live_data=None, prerequisites=None, health_checker=None):
        VariableProcessor().evaluate_variable(results, health_checker)
        allure.attach(
                str(results),
                name="Generate values for variables",
                attachment_type=allure.attachment_type.TEXT
            )
        template, results, live_data = super().create_template(request_name=request_name,template=template, parent=parent, results=results, live_data=live_data, results_index=results_index, prerequisites=prerequisites, health_checker=health_checker)
        return template, results, live_data