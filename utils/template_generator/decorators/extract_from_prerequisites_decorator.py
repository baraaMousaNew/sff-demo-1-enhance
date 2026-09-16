import re

import allure

from utils.template_generator.decorators.base_decorator import BaseDecorator
from utils.template_generator.decorators.get_template_decorator import GetTemplateDecorator
import xml.etree.ElementTree as ET

from utils.template_generator.extract_data_strategy.extract_data_context import ExtractDataContext
from utils.template_generator.replace_data_strategy.replace_data_context import ReplaceDataContext


class ExtractFromPrerequisitesDecorator(BaseDecorator):

    def create_template(self, request_name, template, parent="", results=None, results_index=0, live_data=None, prerequisites=None, health_checker=None):
        if prerequisites:
           for prereq in prerequisites:
               if prereq['source']:
                   if not prereq['process']:
                        if type(prereq['source']) == str:
                            source = ET.fromstring(prereq['source'])
                        else:
                            source = prereq['source']
                        value = ExtractDataContext(source).decide_template_type().extract_from_template(source, prereq['from'])
                        template = ReplaceDataContext(template).decide_template_type().replace_in_template(template, prereq['to'], value)
                   else:
                       if type(prereq['source']) == str:
                           source = ET.fromstring(prereq['source'])
                       else:
                           source = prereq['source']
                       value = ExtractDataContext(source).decide_template_type().extract_from_template(source,
                                                                                                       prereq['from'])
                       value_processed = prereq['process'](value)
                       template = ReplaceDataContext(template).decide_template_type().replace_in_template(template,
                                                                                                          prereq['to'],
                                                                                                          value_processed)
               else:
                   template = ReplaceDataContext(template).decide_template_type().replace_in_template(template,
                                                                                                      prereq['to'],
                                                                                                      prereq['from'])
        allure.attach(
            ET.tostring(template).decode('utf-8'),
            name="53d1c0 - Extracting data from prerequisites",
            attachment_type=allure.attachment_type.XML
        )
        template, results, live_data = super().create_template(request_name=request_name, template=template, parent=parent, results=results, results_index=results_index, live_data=live_data, prerequisites=prerequisites, health_checker=health_checker)
        return template, results, live_data