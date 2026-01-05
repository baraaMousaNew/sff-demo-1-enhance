import re
from abc import ABC

from utils.template_generator.common_variables import ordered_variable_pattern, enclosed_variable_pattern
from utils.variable_processor import VariableProcessor


class LeafElements(ABC):

    def update_leaf_element(self, template, leaf_element, value, variables):
        pass

class XmlnsLeafElement(LeafElements):

    def update_leaf_element(self, template, leaf_element, value, variables):
        tags_list = [item.strip() for item in leaf_element.split('.')]
        value = value.strip()
        def search_element(main, tags):
            order = 0
            ## This pattern looks for ordered variables such as claim[2].ID
            element = re.match(ordered_variable_pattern, tags[0])
            for child in main:
                if not element:
                    if bool(re.search(rf'\{{[^}}]*\}}{tags[0]}$', child.tag)):
                        tags.pop(0)
                        if len(tags) > 0:
                            return search_element(child, tags)
                        else:
                            child_text = child.text if child.text else ''
                            child.text = LeafValueContext().get_leaf_value(child_text, value, variables)
                            return template, True
                else:
                    if bool(re.search(rf'\{{[^}}]*\}}{element.group(1)}$', child.tag)):
                        order += 1
                        if order == int(element.group(2)):
                            tags.pop(0)
                            if len(tags) > 0:
                                return search_element(child, tags)
                            else:
                                child_text = child.text if child.text else ''
                                child.text = LeafValueContext().get_leaf_value(child_text, value, variables)
                                return template, True
            return template, False
        template, is_updated = search_element(template, tags_list)
        return template, is_updated

class NoXmlnsLeafElement(LeafElements):

    def update_leaf_element(self, template, leaf_element, value, variables):
        tags_list = [item.strip() for item in leaf_element.split('.')]
        value = value.strip()
        def search_element(main, tags):
            order = 0
            element = re.match(ordered_variable_pattern, tags[0])
            for child in main:
                if not element:
                    if child.tag == tags[0]:
                        tags.pop(0)
                        if len(tags) > 0:
                            return search_element(child, tags)
                        else:
                            ## this line is used to handle the elements with empty value
                            child_text = child.text if child.text else ''
                            child.text = LeafValueContext().get_leaf_value(child_text, value, variables)
                            return template, True
                else:
                    if child.tag == element.group(1):
                        order += 1
                        if order == int(element.group(2)):
                            tags.pop(0)
                            if len(tags) > 0:
                                return search_element(child, tags)
                            else:
                                child_text = child.text if child.text else ''
                                child.text = LeafValueContext().get_leaf_value(child_text, value, variables)
                                return template, True
            return template, False
        template = search_element(template, tags_list)
        return template

class LeafValueContext:

    def get_leaf_value(self, current_value, value, variables):
        # variable_pattern = r'{([^}]*)}|<([^>]*)>|\(([^)]*)\)|\[([^\]]*)\]'
        if bool(re.match(enclosed_variable_pattern, value)):
            try:
                # pattern = r'{([^}]*)}|<([^>]*)>|\(([^)]*)\)|\[([^\]]*)\]'
                match = re.match(enclosed_variable_pattern, value)
                if match:
                    matched_value = None
                    for group in match.groups():
                        if group:
                            matched_value = group.lower()
                    if matched_value == 'empty':
                        return ""
                    elif matched_value == 'valid':
                        return ValidLeafValue().get_value(matched_value)
                    elif matched_value == 'invalid':
                        return InvalidLeafValue().get_value(matched_value)
                    elif matched_value is not None: ## and matched_value.isspace():
                        return matched_value
                    else:
                        raise Exception(f"Invalid enclosed value: {matched_value}")
                else:
                    raise Exception(f"Error finding a match using enclosed variables pattern: {value}")
            except Exception as e:
                raise Exception(f"Error while processing enclosed value {value}: {e}")
        elif bool(re.search(r'\{\{(.*?)\}\}', value)):
            try:
                match = re.search(r'\{\{(.*?)\}\}', value)
                generated_value = VariableLeafValue().get_value(match.group(1), current_value, variables)
                result = re.sub(r'\{\{(.*?)\}\}', str(generated_value), value)
            except Exception as e:
                raise Exception(f"Error while parsing function value {value}: {e}")
            return result
        else:
            return value

class LeafValues(ABC):

    def get_value(self, variable, current_value, variables):
        pass

class ValidLeafValue(LeafValues):

    def get_value(self, variable, current_value=None, declared_variables=None):
        return f"ERROR: <InvalidLeafSyntax> ValidLeafValue Currently not handled {variable}"

class InvalidLeafValue(LeafValues):

    def get_value(self, variable, current_value=None, declared_variables=None):
        return f"ERROR: <InvalidLeafSyntax> InvalidLeafValue Currently not handled {variable}"

class VariableLeafValue(LeafValues):
    def get_value(self, variable, current_value=None, declared_variables=None):
        variable = re.sub(r'\bvalue\b(?=[^()]*\))', current_value, variable)
        return VariableProcessor().evaluate_variable_manual(variable, declared_variables)