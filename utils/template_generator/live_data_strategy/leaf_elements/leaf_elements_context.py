from utils.template_generator.live_data_strategy.leaf_elements.leaf_elements import XmlnsLeafElement, NoXmlnsLeafElement


class LeafElementsContext:

    def __init__(self, template):
        self.template = template

    def decide_template_type(self):
        if '{' in self.template.tag and '}' in self.template.tag:
            return XmlnsLeafElement()
        else:
            return NoXmlnsLeafElement()
