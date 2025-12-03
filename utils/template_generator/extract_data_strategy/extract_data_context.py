import re

from utils.template_generator.extract_data_strategy.extract_from_template import NoXmlnsTemplateExtract, \
    XmlnsTemplateExtract


class ExtractDataContext:

    def __init__(self, template):
        self.template = template

    def decide_template_type(self):
        if '{' in self.template.tag and '}' in self.template.tag:
            return XmlnsTemplateExtract()
        else:
            return NoXmlnsTemplateExtract()