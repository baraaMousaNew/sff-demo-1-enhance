import json
from abc import ABC

import allure
import pytest

from utils.asserter.schema_rules_validator import SchemaRulesValidator
from utils.assertion_validator import AssertionValidator
from utils.common_variables import tc_rule_id
from utils.error_validator import ErrorValidator


class Asserter(ABC):

    def __init__(self, response):
        self.response = response

    def assert_no_errors(self):
        pass

    def assert_no_warnings_or_errors(self):
        pass

    def assert_error_exists(self, rule_id):
        pass

    def assert_responses_errors(self, second_response):
        pass


class XMLAsserter(Asserter):

    def assert_no_warnings_or_errors(self):
        error_validator = ErrorValidator()
        response_code = error_validator.extract_response_code(self.response['content'])
        with allure.step('Assert no errors or warnings are found'):
            if response_code != '0':
                pytest.fail(f"Response code '{response_code}' is not 0")

    def assert_no_errors(self):
        error_validator = ErrorValidator()
        base64_report = error_validator.extract_error_report(self.response['content'])
        response_code = error_validator.extract_response_code(self.response['content'])
        with allure.step("Assert no errors found"):
            if base64_report:
                file = error_validator.decode_and_parse_error_report(base64_report)
                for element in file:
                    if element.get("Type") == 'ERROR':
                        allure.attach(
                            json.dumps(file, indent=2),
                            name="Assert no errors failed",
                            attachment_type=allure.attachment_type.JSON)
                        pytest.fail(f"Error exists in the report")
            if response_code not in ['0', '1']:
                pytest.fail(f"Response code '{response_code}' is not 0 or 1")

    def assert_error_exists(self, test_case):
        rule_id = test_case.get(tc_rule_id)
        error_validator = ErrorValidator()
        base64_report = error_validator.extract_error_report(self.response['content'])
        response_code = error_validator.extract_response_code(self.response['content'])
        with allure.step(f"Assert error {rule_id} exists in the report"):
            if not base64_report:
                allure.attach(
                    "No error file exists",
                    name=f"Assert rule id {rule_id} does exist",
                    attachment_type=allure.attachment_type.TEXT)
                pytest.fail("Error report is empty")
            else:
                file = error_validator.decode_and_parse_error_report(base64_report)
                found = SchemaRulesValidator(rule_id, test_case).validate_strategy(file)
                if not found:
                    allure.attach(
                        f"Error file doesn't contain the rule id\n\n" + f"{json.dumps(file, indent=2)}",
                        name=f"Assert rule id {rule_id} does exist",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    pytest.fail("Error report doesn't contain the ruleID")
                else:
                    allure.attach(
                        "Error file contains the rule id\n\n" + f"{json.dumps(file, indent=2)}",
                        name=f"Assert rule id {rule_id} does exist",
                        attachment_type=allure.attachment_type.TEXT
                    )
            if response_code != '-2':
                pytest.fail(f"Response code is '{response_code}' while expecting response code of -2")


    def assert_error_doesnt_exist(self, test_case):
        rule_id = test_case.get(tc_rule_id)
        error_validator = ErrorValidator()
        base64_report = error_validator.extract_error_report(self.response['content'])
        response_code = error_validator.extract_response_code(self.response['content'])
        with allure.step(f"Assert {rule_id} does not exist"):
            if not base64_report:
                allure.attach(
                    "No error file exists",
                    name=f"Assert rule id {rule_id} does not exist",
                    attachment_type=allure.attachment_type.TEXT)
            else:
                file = error_validator.decode_and_parse_error_report(base64_report)
                found = SchemaRulesValidator(rule_id, test_case).validate_strategy(file)
                if not found:
                    allure.attach(
                        f"Error file doesn't contain the rule id\n\n" + f"{json.dumps(file, indent=2)}",
                        name=f"Assert rule id {rule_id} does not exist",
                        attachment_type=allure.attachment_type.TEXT
                    )
                else:
                    allure.attach(
                        f"Error file contains the rule id\n\n" + f"{json.dumps(file, indent=2)}",
                        name=f"Assert rule id {rule_id} does not exist",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    pytest.fail("Error report contains the ruleID")
            if response_code in ['-3','-4','-5','-6','-7','-8','-9','-10']:
                pytest.fail(f'Incorrect error code: {response_code}')

    def assert_responses_errors(self, second_response):
        error_validator = ErrorValidator()
        base64_report_first = error_validator.extract_error_report(self.response['content'])
        base64_report_second = error_validator.extract_error_report(second_response['content'])
        with allure.step(f"Assert both responses have same errors"):
            if base64_report_first and base64_report_second:
                file_first = error_validator.decode_and_parse_error_report(base64_report_first)
                file_second = error_validator.decode_and_parse_error_report(base64_report_second)
                if len(file_first) == len(file_second):
                    for element in file_first:
                        found = False
                        for second_element in file_second:
                            if (element.get("Type") == second_element.get("Type") and
                                element.get("RuleID") == second_element.get("RuleID")):
                                found = True
                                break
                        if not found:
                            allure.attach(
                                f"Error in old system response is not found in new system response:\n\nError:\n{element}\n\nOld system errors:\n{file_first}\n\nNew system errors:\n{file_second}",
                                name="Compare responses errors",
                                attachment_type=allure.attachment_type.TEXT
                            )
                            pytest.fail()
                else:
                    allure.attach(
                        f"files don't have same error count: \n\nOld System:\n{file_first}\n\nNew System:\n{file_second}",
                        name="Compare responses errors",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    pytest.fail("Error files don't contains same count of errors")
            else:
                allure.attach(
                    f"Old system response has error report: \n\n{base64_report_first}\n\nNew system response has error report: \n\n{base64_report_second}",
                    name="Compare responses errors",
                    attachment_type=allure.attachment_type.TEXT
                )
                pytest.fail("One of the responses doesn't have an error report")