import re
from abc import ABC
from xml.etree.ElementTree import Element

import allure
import pytest

from utils.template_generator.common_variables import enclosed_variable_pattern, ordered_variable_pattern
from utils.template_generator.health_check.health_checker import HealthChecker
from utils.template_generator.live_data_strategy.leaf_elements.leaf_elements_context import LeafElementsContext
import xml.etree.ElementTree as ET


class AbstractLiveDataStrategy(ABC):

    def get_full_element(self, request_name, template: Element, tag, value, variables):
        pass


class LiveParentElement(AbstractLiveDataStrategy):

    def get_full_element(self, request_name, template: Element, tag, value, variables):
        # match = re.match(r'{([^}]*)}|<([^>]*)>|\(([^)]*)\)|\[([^\]]*)\]', tag)
        match = re.match(enclosed_variable_pattern, tag)
        tag = match.group(2)
        tag_path = tag.split('.')
        counter = 1
        try:
            counter = int(value)
        except ValueError as e:
            raise Exception(f"Error while measuring the count repeats of element from value: {value}\n\nError: {e}")
        from utils.template_generator.template_generator import GetRequestTemplate
        is_found = False
        is_added = False
        health_checker = HealthChecker()
        while counter > 1:
            minor_template, results, live_data = GetRequestTemplate().get_template_request(request_name=request_name, variables=variables, health_checker=None)
            element, is_found = self._get_element_by_identity(minor_template, tag_path)
            template, is_added = self._add_element_to_template(template, element, tag_path)
            allure.attach(
                f"Element: {element}\n\nTemplate: {template}" ,
                name='Get element for template',
                attachment_type=allure.attachment_type.TEXT
            )
            counter -=1
        # del health_checker
        if counter == 0:
            is_found, is_added = self._delete_element_by_identity(template, tag_path)
        if counter == 1:
            is_found, is_added = True, True
        return template, is_found and is_added


    def _get_element_by_identity(self, template, tag_path:list, counter=0):
        for child in template:
            tag = re.sub(r'\[\d+\]', '',tag_path[counter])
            if child.tag == tag:
                counter += 1
                if len(tag_path) <= counter:
                    return child, True
                else:
                    return self._get_element_by_identity(child, tag_path, counter)
        return f"<Error generating element {tag_path}", False

    def _delete_element_by_identity(self, template, tag_path:list, counter=0):
        element_order = 1
        element_actual_order = 1
        ## This pattern looks for ordered variables such as claim[2].ID
        is_ordered = re.match(ordered_variable_pattern, tag_path[counter])
        if is_ordered and is_ordered.groups():
            element_order = int(is_ordered.groups()[1])
        element_tag = re.sub(r'\[\d+\]', '', tag_path[counter])
        for child in template:
            if child.tag == element_tag:
                if element_actual_order == element_order:
                    counter += 1
                    if len(tag_path) <= counter:
                        template.remove(child)
                        return True, True
                    else:
                        return self._delete_element_by_identity(child, tag_path, counter)
                else:
                    element_actual_order += 1
        return False, False

    def _add_element_to_template(self, template, element, tag_path:list, counter=0):
        element_order = 1
        element_actual_order = 1
        ## This pattern looks for ordered variables such as claim[2].ID
        is_ordered = re.match(ordered_variable_pattern, tag_path[counter])
        if is_ordered and is_ordered.groups():
            element_order = int(is_ordered.groups()[1])
        element_tag = re.sub(r'\[\d+\]', '',tag_path[counter])
        for child in template:
            if child.tag == element_tag:
                if element_actual_order == element_order:
                    counter += 1
                    if len(tag_path) - counter < 1:
                        template.insert(list(template).index(child) + 1, element )
                        return template, True
                    else:
                        element, result = self._add_element_to_template(child, element, tag_path, counter)
                        old_index = list(template).index(child)
                        # Remove the old Authorization element
                        template.remove(child)
                        # Insert the new Authorization element at the same position
                        template.insert(old_index, element)
                        return template, result
                else:
                    element_actual_order = element_actual_order + 1
        return template, False


class LiveLeafElement(AbstractLiveDataStrategy):

    def get_full_element(self, request_name, template:Element, tag, value, variables):
        template, is_updated = LeafElementsContext(template).decide_template_type().update_leaf_element(template=template, leaf_element=tag, value=value, variables=variables)
        return template, is_updated




