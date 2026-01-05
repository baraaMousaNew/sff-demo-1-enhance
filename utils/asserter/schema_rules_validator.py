import pytest

from utils.common_variables import tc_object, tc_element


class SchemaRulesValidator:

    def __init__(self, rule_id, test_case):
        self.rule_id = rule_id
        self.test_case = test_case

    def validate_strategy(self, report_file) -> tuple[bool, str]:
        # if str(self.rule_id).isdigit():
        #     return self._validate_rule_in_report(report_file)
        if str(self.rule_id).lower() == 'schema validation':
            return self._validate_schema_in_report(report_file)
        elif str(self.rule_id).lower() == 'common types':
            return self._validate_common_types_in_report(report_file)
        else:
            return self._validate_rule_in_report(report_file)
            # raise Exception(f'rule id is neither a valid numeric rule nor schema validation.\n\nValue: {self.rule_id}')

    def _validate_rule_in_report(self, report_file) -> tuple[bool, str]:
        for element in report_file:
            if element.get("Type") == 'ERROR' or element.get("Type") == 'WARNING':
                if str(element.get("RuleID")) == str(self.rule_id):
                    return True, element["Error Text"]
        return False, ''

    def _validate_schema_in_report(self, report_file) -> tuple[bool, str]:
        found = False
        error_text = ''
        for element in report_file:
            if element.get("Type") == 'ERROR':
                if str(element.get("Object Name")) == str(self.rule_id):
                    if str(element.get("Transaction")) == str(self.rule_id):
                        if str(element.get("HAAD Field")) == '':
                            found = True
                            error_text = element["Error Text"]
                elif str(element.get("Object Name")) != str(self.rule_id) and str(element.get("RuleID")) == '':
                    return False, ''
        return found, error_text

    def _validate_common_types_in_report(self, report_file) -> tuple[bool, str]:
        found = False
        error_text = ''
        for element in report_file:
            if element.get("Type") == 'ERROR':
                if str(element.get("Object Name")) == str(self.test_case.get(tc_object)):
                    if str(element.get("HAAD Field")) == str(self.test_case.get(tc_element)):
                        if str(element.get("RuleID")) == '':
                            found = True
                            error_text = element["Error Text"]
                elif str(element.get("Object Name")) == 'Schema Validation':
                    return False, ''
        return found, error_text
