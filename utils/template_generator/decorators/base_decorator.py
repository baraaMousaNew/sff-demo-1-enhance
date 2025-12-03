from utils.template_generator.request_template import AbstractRequestTemplate


class BaseDecorator(AbstractRequestTemplate):

    _abstract_request_template: AbstractRequestTemplate = None

    def __init__(self, abstract_request_template: AbstractRequestTemplate) -> None:
        self._abstract_request_template = abstract_request_template

    @property
    def component(self) -> AbstractRequestTemplate:
        """
        The Decorator delegates all work to the wrapped component.
        """

        return self._abstract_request_template

    def create_template(self, request_name, template, parent="", results=None, results_index=0, live_data=None, prerequisites=None, health_checker=None):
        return self._abstract_request_template.create_template(request_name=request_name, template=template, parent=parent, results=results, live_data=live_data, results_index=results_index, prerequisites=prerequisites, health_checker=health_checker)

