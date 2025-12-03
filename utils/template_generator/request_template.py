class AbstractRequestTemplate:

    def create_template(self, request_name, template, parent, results, results_index, live_data, prerequisites, health_checker):
        pass


class RequestTemplate(AbstractRequestTemplate):

    def create_template(self, request_name, template, parent="", results=None, results_index=0, live_data=None, prerequisites=None, health_checker=None):
        return template, results, live_data

