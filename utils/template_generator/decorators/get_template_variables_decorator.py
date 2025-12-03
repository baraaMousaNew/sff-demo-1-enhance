import re

import allure

from utils.allure_reporter import AllureReporter
from utils.template_generator.decorators.base_decorator import BaseDecorator


class GetVariablesDecorator(BaseDecorator):

    def create_template(self, request_name,template, parent="", results=None, results_index=0, live_data=None, prerequisites=None, health_checker=None):
        # Dictionary to store results
        if results is None:
            results = []
        else:
            results_index = len(results)
        pattern = r'\{\{(.*?)\}\}'
        def collect_vars(collect_template, collect_parent, collect_results=None):
            for tag in collect_template.findall("*"):
                try:
                    tag_name = tag.tag
                    tag_value = tag.text
                    if tag_value is not None:
                        tag_value = tag_value.strip()
                        if tag_value != "" and bool(re.search(pattern, tag_value)):
                            collect_results.append({"tag_location":tag, "tag_name":collect_parent + "." + tag_name,"tag_functions": re.findall(pattern, tag_value), "tag_values":[], "tag_variables":[]})
                        elif tag_value == "":
                            collect_vars(tag, collect_parent + "." + tag_name, collect_results)
                except Exception as e:
                    raise Exception(f"Error found while parsing attribute {tag}: {e}")
            return collect_results
        collect_vars(template, template.tag, results)
        allure.attach(
                        str(results),
                        name="Get variables for request",
                        attachment_type=allure.attachment_type.TEXT)
        template, results, live_data = super().create_template(request_name=request_name,template=template, parent=parent, results=results, live_data=live_data, results_index=results_index, prerequisites=prerequisites, health_checker=health_checker)
        return template, results, live_data
