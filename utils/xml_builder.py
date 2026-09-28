import re
from enum import Enum
from xml.etree.ElementTree import tostring, Element, fromstring

import xmlschema

from utils.variable_processor import VariableProcessor


class XmlTemplates(Enum):
    prior_request_template = "xml_templates/person_register_template.xml"

class XsdSchema(Enum):
    prior_request_xsd = "xsd/PersonRegister.xsd"


class XmlBuilder:

    def __init__(self, template:XmlTemplates, xsd:XsdSchema):
        self.template = template
        self.xsd = xsd
        self.variable_processor = VariableProcessor()

    def get_dummy_xml(self):
        schema = xmlschema.XMLSchema(self.xsd.value)
        with open(self.template.value, 'r', encoding='utf-8') as f:
            xml_file_string = f.read()
            # pattern = r"{{.*}}"
            # matches = re.findall(pattern, xml_file_string)
            processed_xml = self.variable_processor.process_variables(xml_file_string)


