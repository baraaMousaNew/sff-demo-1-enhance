from utils.template_generator.common_variables import variable_pattern, ordered_variable_pattern, template_path_variable
import xml.etree.ElementTree as ET
import re
from utils.variable_processor import VariableProcessor

class ErrorTextProcessor:

    def __init__(self, error_text, template, template_flow=None):
        self.error_text = error_text
        self.template = template
        self.template_flow = template_flow

    def process_error_text(self):
        pattern = variable_pattern
        matches = re.findall(pattern, self.error_text)
        for match in matches:
            value = None
            match_processed = match
            if match_processed.startswith('CUSTOM.'):
                match_processed = self._process_function(match_processed)
                value = VariableProcessor().evaluate_custom_function(match_processed[7:], None, None)
            elif '(' in match_processed and ')' in match_processed:
                match_processed = self._process_function(match_processed)
                value = VariableProcessor().evaluate_builtin_function(match_processed)
            elif match_processed.startswith('PRE_TEMPLATE.'):
                value = self._search_through_flow(match_processed[13:])
            elif match_processed.startswith('TEMPLATE.'):
                value = self._search_through_template(match_processed[9:])
            if value is None:
                raise Exception(f"Cannot find the value for variable: {match}")
            self.error_text = self.error_text.replace(f'{{{{{match}}}}}', value)
        return self.error_text

    def _process_function(self, match_processed):
        start = match_processed.find('(')
        end = match_processed.find(')')
        function_variables = match_processed[start+1:end]
        function_variables = function_variables.split(',')
        for function_variable in function_variables:
            function_variable = function_variable.strip()
            if function_variable.startswith('PRE_TEMPLATE.'):
                function_variable_path = function_variable.replace('PRE_TEMPLATE.', '')
                function_variable_value = self._search_through_flow(function_variable_path)
                match_processed = match_processed.replace(function_variable, function_variable_value)
            elif function_variable.startswith('TEMPLATE.'):
                function_variable_path = function_variable.replace('TEMPLATE.', '')
                function_variable_value = self._search_through_template(function_variable_path)
                match_processed = match_processed.replace(function_variable, function_variable_value)
        return match_processed

    def _search_through_template(self, variable):
        tags_list = [item.strip() for item in variable.split('.')]
        return self._search_element(self.template, tags_list, variable)

    def _search_through_flow(self, variable):
        if not self.template_flow:
            raise Exception(f"No template flow available to resolve variable: PRE_TEMPLATE.{variable}")
        tags_list = [item.strip() for item in variable.split('.')]
        step_name = tags_list.pop(0)
        step_template = next((step_template for label, step_template in self.template_flow if label == step_name), None)
        if step_template is None:
            available = ', '.join(label for label, _ in self.template_flow)
            raise Exception(f"Cannot find step '{step_name}' in the template flow using variable path: PRE_TEMPLATE.{variable}. Available steps: {available}")
        if not tags_list:
            raise Exception(f"PRE_TEMPLATE variable path must include a field path after the step name: PRE_TEMPLATE.{variable}")
        return self._search_element(step_template, tags_list, variable)

    def _search_element(self, main, tags, variable):
        order = 0
        element = re.match(ordered_variable_pattern, tags[0])
        for child in main:
            if not element:
                if child.tag == tags[0]:
                    tags.pop(0)
                    if len(tags) > 0:
                        return self._search_element(child, tags, variable)
                    else:
                        ## this line is used to handle the elements with empty value
                        child_text = child.text if child.text else ''
                        return child_text
            else:
                if child.tag == element.group(1):
                    order += 1
                    if order == int(element.group(2)):
                        tags.pop(0)
                        if len(tags) > 0:
                            return self._search_element(child, tags, variable)
                        else:
                            child_text = child.text if child.text else ''
                            return child_text
        raise Exception(f"Cannot find the element in the template using variable path: {variable}")
