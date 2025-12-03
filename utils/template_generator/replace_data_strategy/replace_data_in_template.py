import re
from abc import ABC
import xml.etree.ElementTree as ET


class Replace(ABC):

    def replace_in_template(self, template, element, value):
        pass

class XmlnsTemplateReplace(Replace):

    def replace_in_template(self, template, element, value):
        def replace_element_value(main, sub):
            for child in main:
                if bool(re.search(rf'\{{[^}}]*\}}{sub}$', child.tag)):  # Using 'is' for identity comparison
                    child.text = value
                    return True
                if replace_element_value(child, sub):
                    return True
            return False
        replace_element_value(template, element)
        return template

class NoXmlnsTemplateReplace(Replace):

    def replace_in_template(self, template, element, value):
        def replace_element_value(main, sub):
            for child in main:
                if child.tag == sub:  # Using 'is' for identity comparison
                    child.text = value
                    return True
                if replace_element_value(child, sub):
                    return True
            return False
        replace_element_value(template, element)
        return template