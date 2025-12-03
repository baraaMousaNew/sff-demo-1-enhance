from utils.template_generator.replace_data_strategy.replace_data_in_template import XmlnsTemplateReplace, \
    NoXmlnsTemplateReplace


class ReplaceDataContext:

    def __init__(self, template):
        self.template = template

    def decide_template_type(self):
        if '{' in self.template.tag and '}' in self.template.tag:
            return XmlnsTemplateReplace()
        else:
            return NoXmlnsTemplateReplace()