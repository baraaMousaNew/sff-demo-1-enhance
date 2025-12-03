import re

from utils.template_generator.common_variables import enclosed_variable_pattern
from utils.template_generator.live_data_strategy.live_elements import LiveLeafElement, LiveParentElement


class LiveDataContext:

    def get_data_context(self, key):
        # pattern = r'^{([^}]*)}$|^<([^>]*)>$|^\(([^)]*)\)$|^\[([^\]]*)\]$'
        if bool(re.search(enclosed_variable_pattern, key)):
            return LiveParentElement()
        else:
            return LiveLeafElement()
