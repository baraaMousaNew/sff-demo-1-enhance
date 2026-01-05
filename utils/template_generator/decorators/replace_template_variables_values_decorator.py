import re
import xml.etree.ElementTree as ET

import allure

from utils.allure_reporter import AllureReporter
from utils.template_generator.decorators.base_decorator import BaseDecorator


class ReplaceTemplateVariablesValuesDecorator(BaseDecorator):

    def create_template(self, request_name,template:ET.Element, parent="", results=None, results_index=0, live_data=None, prerequisites=None, health_checker=None):
        for variable_expression in results[results_index:]:
            tag = variable_expression.get("tag_location")
            values = variable_expression.get("tag_values")
            functions = variable_expression.get("tag_functions")
            def find_element_by_identity(main, sub, sub_values, sub_functions):
                # Check direct children first
                for child in main:
                    if child is sub: # Using 'is' for identity comparison
                        current_text = child.text
                        pattern = r'\{\{(.*?)\}\}'
                        items_to_replace = re.findall(pattern, current_text)
                        for i in range(len(items_to_replace)):
                            if items_to_replace[i] == sub_functions[i]:
                                current_text = current_text.replace("{{" + items_to_replace[i] + "}}", str(values[i]))
                                child.text = current_text
                            else:
                                current_text = current_text.replace("{{" + items_to_replace[i] + "}}", f"{{ERROR: function {functions[i]}}}")
                                child.text = current_text
                        return True
                    if find_element_by_identity(child, sub, sub_values, sub_functions):
                        return True
                return False
            find_element_by_identity(template, tag, values, functions)
        allure.attach(
                ET.tostring(template).decode("utf-8"),
                name="Replace variables values",
                attachment_type=allure.attachment_type.XML)
        template, results, live_data = super().create_template(request_name=request_name, template=template, parent=parent, results=results, live_data=live_data, results_index=results_index, prerequisites=prerequisites, health_checker=health_checker)
        return template, results, live_data