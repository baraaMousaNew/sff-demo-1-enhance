import re
from abc import ABC
import xml.etree.ElementTree as ET

class Extract(ABC):

    def extract_from_template(self, template, element):
        pass

    def extract_xml_element_from_template(self, template, element):
        pass

class XmlnsTemplateExtract(Extract):

    def extract_from_template(self, template, element):
        value = None
        def get_element_value(main, sub):
            for child in main:
                if bool(re.search(rf'\{{[^}}]*\}}{sub}$', child.tag)):  # Using 'is' for identity comparison
                    nonlocal value
                    value = child.text
                    return True
                if get_element_value(child, sub):
                    return True
            return False
        get_element_value(template, element)
        return value

    def extract_xml_element_from_template(self, template, element):
        found_element = None
        def get_element(main, sub):
            for child in main:
                if bool(re.search(rf'\{{[^}}]*\}}{sub}$', child.tag)):  # Using 'is' for identity comparison
                    nonlocal found_element
                    found_element = child
                    return True
                if get_element(child, sub):
                    return True
            return False

        get_element(template, element)
        return found_element


class NoXmlnsTemplateExtract(Extract):

    def extract_from_template(self, template, element):
        value = None
        def get_element_value(main, sub):
            for child in main:
                if child.tag == sub:  # Using 'is' for identity comparison
                    nonlocal value
                    value = child.text
                    return True
                if get_element_value(child, sub):
                    return True
            return False
        get_element_value(template, element)
        return value

    def extract_xml_element_from_template(self, template, element):
        found_element = None
        def get_element(main, sub):
            for child in main:
                if child.tag == sub:  # Using 'is' for identity comparison
                    nonlocal found_element
                    found_element = child
                    return True
                if get_element(child, sub):
                    return True
            return False
        get_element(template, element)
        return found_element


