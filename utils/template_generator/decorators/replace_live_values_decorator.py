import re

import allure
import pytest

from utils.allure_reporter import AllureReporter
from utils.template_generator.common_variables import enclosed_variable_pattern
from utils.template_generator.decorators.base_decorator import BaseDecorator
from utils.template_generator.live_data_strategy.live_data_context import LiveDataContext
import xml.etree.ElementTree as ET

class ReplaceLiveValueDecorator(BaseDecorator):


    def create_template(self, request_name, template, parent="", results=None, results_index=0, live_data=None, prerequisites=None, health_checker=None):
        final_live_data = live_data
        if live_data is not None and live_data.strip() != '':
            live_data = ";".join(part for part in live_data.split(";") if part.strip())
            live_data_dict = {}
            parent_elements = {}
            leaf_elements = {}
            split_values = [item.strip() for item in live_data.split(";")]
            for value in split_values:
                if "=" in value:
                    try:
                       values_split = [item.strip() for item in value.split("=", 1)]
                       if bool(re.match(enclosed_variable_pattern, values_split[0])):
                           parent_elements.update({values_split[0]: values_split[1]})
                       else:
                           leaf_elements.update({values_split[0]: values_split[1]})
                    except Exception as e:
                        pytest.fail(f'Exception while parsing live data: {value};\nError: {e}')
                else:
                    # pytest.fail(f'Value {value} is not a valid value')
                    raise Exception(f'Value {value} is not a valid value')
            parent_elements = dict(sorted(parent_elements.items(), key=lambda item: len(item[0])))
            live_data_dict.update(parent_elements)
            live_data_dict.update(leaf_elements)
            final_data_dict = live_data_dict.copy()
            # the results list is copied to new one so variables generated do the template next don't affect later requests in the chain
            variable_copy = results.copy()
            for key, value in live_data_dict.items():
                template, is_done = LiveDataContext().get_data_context(key).get_full_element(request_name=request_name,
                                                                                    template=template, tag=key,
                                                                                    value=value, variables=variable_copy)
                if is_done:
                    final_data_dict.pop(key)
            final_live_data = ';'.join(f"{key}={value}" for key, value in final_data_dict.items())
            allure.attach(
                    ET.tostring(template, encoding="unicode"),
                    name="e86ab1 - Replace live variables",
                    attachment_type=allure.attachment_type.XML)

        template, results, live_data =super().create_template(request_name=request_name, template=template, parent=parent, results=results, live_data=final_live_data, results_index=results_index, prerequisites=prerequisites, health_checker=health_checker)
        return template, results, live_data