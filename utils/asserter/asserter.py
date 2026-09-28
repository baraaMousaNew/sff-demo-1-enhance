from utils.asserter.text_similarity import get_strings_difference
from utils.common_variables import tc_element
from utils.common_variables import tc_object
from utils.common_variables import tc_field_value
from utils.common_variables import tc_additional_reference
from utils.common_variables import tc_error_text
from utils.asserter.error_text_processor import ErrorTextProcessor
from utils.asserter.response_codes import warning_only
from utils.asserter.response_codes import failed_with_errors
from utils.asserter.response_codes import success
import json
import os
import inspect
from functools import wraps
from abc import ABC

import allure
import pytest

from utils.asserter.schema_rules_validator import SchemaRulesValidator, render_grid_csv
from utils.asserter.report_row_type import ReportRowType
from utils.env_vars import EnvVar
from utils.common_variables import tc_rule_id
from utils.common_variables import tc_occurrences
from utils.common_variables import tc_objective
from utils.error_validator import ErrorValidator
import xml.etree.ElementTree as ET
from utils.template_generator.extract_data_strategy.extract_data_context import ExtractDataContext


def fail_with_tag(tag, reason, message):
    """Tag/label the allure result for a failure, then fail the test."""
    allure.dynamic.tag(tag)
    allure.dynamic.label("failure_reason", reason)
    pytest.fail(message)


def dispatch_to_systems(compare_reports=False, compare_rows=False):
    """
    Decorate an XMLAsserterContext method that mirrors a same-named XMLSingleAsserter method.

    Calls XMLSingleAsserter(...).<method>(...) once when self.response is a single response,
    or twice (system_index=1 and 2) when it's a two-element list. For the list case, optionally
    runs XMLDualAsserter/XMLDualSingleRowAsserter comparisons afterward, gated by the matching
    env var. The decorated function's body is never executed — its signature only documents the
    arguments forwarded to XMLSingleAsserter.
    """
    def decorator(func):
        method_name = func.__name__

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            bound = inspect.signature(func).bind(self, *args, **kwargs)
            bound.apply_defaults()
            call_kwargs = {name: value for name, value in bound.arguments.items() if name != 'self'}

            if type(self.response) != list:
                getattr(XMLSingleAsserter(self.response), method_name)(system_index=self.system_index, **call_kwargs)
                return

            if len(self.response) != 2:
                raise ValueError("Response list should have exactly 2 elements")

            result_first = getattr(XMLSingleAsserter(self.response[0]), method_name)(system_index=1, **call_kwargs)
            result_second = getattr(XMLSingleAsserter(self.response[1]), method_name)(system_index=2, **call_kwargs)

            if compare_reports and os.environ.get(EnvVar.FULL_REPORT_COMPARISON) == 'true':
                XMLDualAsserter(self.response[0], self.response[1]).assert_responses_errors()

            if compare_rows and os.environ.get(EnvVar.FULL_ROW_COMPARISON) == 'true':
                _, row_num_first = result_first
                _, row_num_second = result_second
                XMLDualSingleRowAsserter(self.response[0], self.response[1], call_kwargs['test_case']).assert_responses_errors(row_num_first, row_num_second)
        return wrapper
    return decorator


class XMLAsserterContext:

    def __init__(self, response, system_index=1):
        self.response = response
        self.system_index = system_index

    @dispatch_to_systems(compare_reports=True)
    def assert_no_warnings_or_errors(self):
        pass

    @dispatch_to_systems(compare_reports=True)
    def assert_no_errors(self):
        pass

    @dispatch_to_systems(compare_reports=True, compare_rows=True)
    def assert_error_exists(self, test_case, assert_text, request_template, assert_object_element: bool = False, assert_field_additional: bool = False, expected_type: ReportRowType = ReportRowType.ERROR, template_flow=None):
        pass

    @dispatch_to_systems(compare_reports=True)
    def assert_error_doesnt_exist(self, test_case, request_template, assert_text: bool = False, assert_object_element: bool = False, assert_field_additional: bool = False, expected_type: ReportRowType = None, template_flow=None):
        pass

    @dispatch_to_systems()
    def custom_assert(self, test_case, request_template, template_flow=None):
        pass


class XMLSingleAsserter:

    def __init__(self, response):
        self.response = response

    def assert_no_warnings_or_errors(self, system_index):
        error_validator = ErrorValidator()
        response_code = error_validator.extract_response_code(self.response['content'])
        with allure.step('Assert no errors or warnings are found'):
            if response_code != success:
                # allure.dynamic.tag(f"System {system_index} Failure")
                # allure.dynamic.label("failure_reason", f"system_{system_index}_issue")
                pytest.fail(f"Response code '{response_code}' is not {success}")

    def assert_no_errors(self, system_index):
        error_validator = ErrorValidator()
        base64_report = error_validator.extract_error_report(self.response['content'])
        response_code = error_validator.extract_response_code(self.response['content'])
        with allure.step("Assert no errors found"):
            # if response_code not in ['0', '1']:
            if response_code != success and response_code != warning_only:
                # allure.dynamic.tag(f"System {system_index} Failure")
                # allure.dynamic.label("failure_reason", f"system_{system_index}_issue")
                pytest.fail(f"Response code '{response_code}' is not {success} or {warning_only}")
            if base64_report:
                file = error_validator.decode_and_parse_error_report(base64_report)
                for element in file:
                    if element.get("Type") == 'ERROR':
                        allure.attach(
                            json.dumps(file, indent=2),
                            name="39ae3c - Assert no errors failed",
                            attachment_type=allure.attachment_type.JSON)
                        # allure.dynamic.tag(f"System {system_index} Failure")
                        # allure.dynamic.label("failure_reason", f"system_{system_index}_issue")
                        pytest.fail(f"Error exists in the report")

    def assert_error_exists(self, test_case, request_template, assert_text: bool, system_index, assert_object_element: bool = False, assert_field_additional: bool = False, expected_type: ReportRowType = ReportRowType.ERROR, template_flow=None):
        rule_id = test_case.get(tc_rule_id)
        tc_object_id = test_case[tc_object]
        tc_element_id = test_case[tc_element]
        try:
            error_text = test_case[tc_error_text]
        except ValueError:
            raise Exception(f"Error retrieving error text from test case")
        tc_field_value_expected = test_case.get(tc_field_value, '')
        tc_additional_reference_expected = test_case.get(tc_additional_reference, '')

        error_validator = ErrorValidator()
        error_text = ErrorTextProcessor(error_text, request_template, template_flow).process_error_text()
        if assert_field_additional:
            if str(tc_field_value_expected).strip():
                tc_field_value_expected = ErrorTextProcessor(str(tc_field_value_expected), request_template, template_flow).process_error_text()
            if str(tc_additional_reference_expected).strip():
                tc_additional_reference_expected = ErrorTextProcessor(str(tc_additional_reference_expected), request_template, template_flow).process_error_text()
        base64_report = error_validator.extract_error_report(self.response['content'])
        response_code = error_validator.extract_response_code(self.response['content'])
        # A notification-only response can still return the success code, since notifications
        # don't affect the overall response status the way errors/warnings do.
        allowed_response_codes = (success, warning_only, failed_with_errors) if expected_type == ReportRowType.NOTIFICATION else (failed_with_errors, warning_only)
        with allure.step(f"Assert {expected_type.lower()} {rule_id} exists in the report of system {system_index}"):
            self._assert_response_code_allowed(response_code, allowed_response_codes, system_index)
            self._assert_report_not_empty(base64_report, rule_id, system_index)

            file = error_validator.decode_and_parse_error_report(base64_report)
            grid = SchemaRulesValidator(rule_id, expected_type, {
                tc_error_text: error_text if assert_text else None,
                tc_object: tc_object_id if assert_object_element else None,
                tc_element: tc_element_id if assert_object_element else None,
                tc_field_value: tc_field_value_expected if assert_field_additional else None,
                tc_additional_reference: tc_additional_reference_expected if assert_field_additional else None,
            }).validate_strategy(file)

            allure.attach(
                render_grid_csv(grid.rows),
                name=f"9c2d47 - Match grid for rule {rule_id}",
                attachment_type=allure.attachment_type.CSV
            )

            found = bool(grid.rows)
            best = grid.best_row()
            row_num = best["row_num"] if best else -1
            actual_error_text = best["columns"].get(tc_error_text, {"actual": ''})["actual"] if best else ''
            self._assert_rule_found(found, rule_id, error_text, actual_error_text, file, system_index)

            strict_occurrences = self._assert_occurrence_count_matches(test_case, rule_id, grid.count(), system_index)
            # When an explicit occurrence count was requested, every matched row must be
            # checked — not just the single "best" match — otherwise a second/third
            # occurrence could silently carry the wrong Object/Element or Error Text.
            rows_to_check = grid.matched_rows() if strict_occurrences and grid.matched_rows() else [best]

            # Soft assertions: run every enabled check regardless of the others' outcome,
            # then fail once at the end with every mismatch tagged and reported together.
            soft_failures = []
            if assert_text:
                result = self._assert_error_text_matches(rows_to_check, error_text, system_index)
                if result:
                    soft_failures.append(result)
            if assert_object_element:
                result = self._assert_object_element_matches(rows_to_check, tc_object_id, tc_element_id, system_index)
                if result:
                    soft_failures.append(result)
            if assert_field_additional:
                result = self._assert_field_additional_matches(rows_to_check, tc_field_value_expected, tc_additional_reference_expected, system_index)
                if result:
                    soft_failures.append(result)

            if soft_failures:
                for tag, reason, _ in soft_failures:
                    allure.dynamic.tag(tag)
                    allure.dynamic.label("failure_reason", reason)
                pytest.fail("\n".join(message for _, _, message in soft_failures))
        return found, row_num

    def _assert_response_code_allowed(self, response_code, allowed_response_codes, system_index):
        if response_code not in allowed_response_codes:
            fail_with_tag(
                f"System {system_index} Failure",
                f"system_{system_index}_issue",
                f"Response code is '{response_code}' while expecting response code among {allowed_response_codes}"
            )

    def _assert_report_not_empty(self, base64_report, rule_id, system_index):
        if not base64_report:
            allure.attach(
                "No error file exists",
                name=f"ad668e - Assert rule id {rule_id} does exist",
                attachment_type=allure.attachment_type.TEXT)
            fail_with_tag(f"System {system_index} Failure", f"system_{system_index}_issue", "Error report is empty")

    def _assert_rule_found(self, found, rule_id, error_text, actual_error_text, file, system_index):
        if not found:
            allure.attach(
                f"Error file doesn't contain the rule id\n\nExpected error: {error_text}\n\nError file: {json.dumps(file, indent=2)}",
                name=f"35b0bf - Expected rule id {rule_id} wasn't found",
                attachment_type=allure.attachment_type.TEXT
            )
            fail_with_tag(f"System {system_index} Failure", f"system_{system_index}_issue", "Error report doesn't contain the ruleID")
        else:
            allure.attach(
                f"Error file contains the rule id\n\nExpected error: '{error_text}'\n\nMatched error: '{actual_error_text}'\n\nError file: {json.dumps(file, indent=2)}",
                name=f"418d8f - Expected rule id {rule_id} was found",
                attachment_type=allure.attachment_type.TEXT
            )

    def _assert_occurrence_count_matches(self, test_case, rule_id, actual_occurrences, system_index):
        """Checks the occurrence count if the test case specifies one; returns whether it did (strict_occurrences)."""
        raw_occurrences = test_case.get(tc_occurrences, '')
        strict_occurrences = str(raw_occurrences).strip() != ''
        if not strict_occurrences:
            return False  # No expected occurrence count provided — skip the occurrence check.

        expected_occurrences = int(float(raw_occurrences))
        if actual_occurrences != expected_occurrences:
            allure.attach(
                f"Expected rule {rule_id} to occur {expected_occurrences} time(s), found {actual_occurrences}",
                name=f"6f2c9a - Rule {rule_id} occurrence count mismatch",
                attachment_type=allure.attachment_type.TEXT
            )
            fail_with_tag(
                f"System {system_index} Failure",
                f"system_{system_index}_issue",
                f"Expected rule {rule_id} to occur {expected_occurrences} time(s) in the report, found {actual_occurrences}"
            )
        else:
            allure.attach(
                f"Rule {rule_id} occurred {actual_occurrences} time(s) as expected",
                name=f"1d7e4b - Rule {rule_id} occurrence count matches",
                attachment_type=allure.attachment_type.TEXT
            )
        return True

    def _assert_object_element_matches(self, rows_to_check, tc_object_id, tc_element_id, system_index):
        """Returns (tag, reason, message) on mismatch, or None when everything matches."""
        mismatches = []
        for idx, row in enumerate(rows_to_check, start=1):
            object_col = row["columns"].get(tc_object, {"matched": True, "actual": ''})
            element_col = row["columns"].get(tc_element, {"matched": True, "actual": ''})
            if not object_col["matched"] or not element_col["matched"]:
                mismatches.append((idx, object_col["actual"], element_col["actual"]))
        if mismatches:
            details = "\n".join(
                f"Occurrence {idx}: Expected Object Name '{tc_object_id}', Actual '{actual_object}' | "
                f"Expected HAAD Field '{tc_element_id}', Actual '{actual_element}'"
                for idx, actual_object, actual_element in mismatches
            )
            allure.attach(
                f"Object Name/HAAD Field mismatch on {len(mismatches)} of {len(rows_to_check)} occurrence(s)\n\n{details}",
                name=f"b3d91c - Object/Element mismatch in system {system_index}",
                attachment_type=allure.attachment_type.TEXT
            )
            return (
                f"System {system_index} Object/Element Failure",
                f"system_{system_index}_object_element_issue",
                f"Object Name or HAAD Field does not match expected values on {len(mismatches)} of {len(rows_to_check)} occurrence(s)"
            )
        else:
            allure.attach(
                f"Object Name and HAAD Field match expected values on all {len(rows_to_check)} occurrence(s)\nObject Name: '{tc_object_id}'\nHAAD Field: '{tc_element_id}'",
                name=f"a1c7d4 - Object/Element match in system {system_index}",
                attachment_type=allure.attachment_type.TEXT
            )
            return None

    def _assert_field_additional_matches(self, rows_to_check, tc_field_value_expected, tc_additional_reference_expected, system_index):
        """Returns (tag, reason, message) on mismatch, or None when everything matches (or nothing to check)."""
        check_field_value = str(tc_field_value_expected).strip() != ''
        check_additional_reference = str(tc_additional_reference_expected).strip() != ''
        if not check_field_value and not check_additional_reference:
            return None
        mismatches = []
        for idx, row in enumerate(rows_to_check, start=1):
            field_col = row["columns"].get(tc_field_value, {"matched": True, "actual": ''})
            reference_col = row["columns"].get(tc_additional_reference, {"matched": True, "actual": ''})
            is_mismatch = (
                (check_field_value and not field_col["matched"])
                or (check_additional_reference and not reference_col["matched"])
            )
            if is_mismatch:
                row_mismatches = []
                if check_field_value:
                    row_mismatches.append(f"Expected Field Value '{tc_field_value_expected}', Actual '{field_col['actual']}'")
                if check_additional_reference:
                    row_mismatches.append(f"Expected Additional Reference '{tc_additional_reference_expected}', Actual '{reference_col['actual']}'")
                mismatches.append((idx, row_mismatches))
        if mismatches:
            details = "\n".join(
                f"Occurrence {idx}: " + " | ".join(msgs)
                for idx, msgs in mismatches
            )
            allure.attach(
                f"Field Value/Additional Reference mismatch on {len(mismatches)} of {len(rows_to_check)} occurrence(s)\n\n{details}",
                name=f"c7e592 - Field/Additional mismatch in system {system_index}",
                attachment_type=allure.attachment_type.TEXT
            )
            return (
                f"System {system_index} Field/Additional Failure",
                f"system_{system_index}_field_additional_issue",
                f"Field Value or Additional Reference does not match expected values on {len(mismatches)} of {len(rows_to_check)} occurrence(s)"
            )
        else:
            allure.attach(
                f"Field Value and Additional Reference match expected values on all {len(rows_to_check)} occurrence(s)\nField Value: '{tc_field_value_expected}'\nAdditional Reference: '{tc_additional_reference_expected}'",
                name=f"6a3fd8 - Field/Additional match in system {system_index}",
                attachment_type=allure.attachment_type.TEXT
            )
            return None

    def _assert_error_text_matches(self, rows_to_check, error_text, system_index):
        """Returns (tag, reason, message) on mismatch, or None when everything matches (or nothing to check)."""
        if not str(error_text).strip():
            return None
        mismatches = []
        for idx, row in enumerate(rows_to_check, start=1):
            text_col = row["columns"].get(tc_error_text, {"matched": True, "actual": ''})
            if not text_col["matched"]:
                mismatches.append((idx, text_col["actual"]))
        if mismatches:
            details = "\n\n".join(
                f"Occurrence {idx}: Actual: '{txt}'\nDifference: '{get_strings_difference(error_text, txt)}'"
                for idx, txt in mismatches
            )
            allure.attach(
                f"Expected: '{error_text}'\n\nMismatched on {len(mismatches)} of {len(rows_to_check)} occurrence(s)\n\n{details}",
                name=f"392130 - Error text doesn't fully match with expected",
                attachment_type=allure.attachment_type.TEXT
            )
            return (
                f"System {system_index} Error Text Failure",
                f"system_{system_index}_error_text_issue",
                f"Error report doesn't contain the error text on {len(mismatches)} of {len(rows_to_check)} occurrence(s)"
            )
        else:
            allure.attach(
                f"Actual matches expected on all {len(rows_to_check)} occurrence(s): '{error_text}'",
                name=f"3b4195 - Error text fully matches the expected",
                attachment_type=allure.attachment_type.TEXT
            )
            return None

    def assert_error_doesnt_exist(self, test_case, request_template, system_index, assert_text: bool = False, assert_object_element: bool = False, assert_field_additional: bool = False, expected_type: ReportRowType = None, template_flow=None):
        rule_id = test_case.get(tc_rule_id)
        tc_object_id = test_case[tc_object]
        tc_element_id = test_case[tc_element]
        try:
            error_text = test_case[tc_error_text]
        except ValueError:
            raise Exception(f"Error retrieving error text from test case")
        tc_field_value_expected = test_case.get(tc_field_value, '')
        tc_additional_reference_expected = test_case.get(tc_additional_reference, '')

        error_validator = ErrorValidator()
        error_text = ErrorTextProcessor(error_text, request_template, template_flow).process_error_text()
        if assert_field_additional:
            if str(tc_field_value_expected).strip():
                tc_field_value_expected = ErrorTextProcessor(str(tc_field_value_expected), request_template, template_flow).process_error_text()
            if str(tc_additional_reference_expected).strip():
                tc_additional_reference_expected = ErrorTextProcessor(str(tc_additional_reference_expected), request_template, template_flow).process_error_text()
        base64_report = error_validator.extract_error_report(self.response['content'])
        response_code = error_validator.extract_response_code(self.response['content'])
        found = False
        row_num = -1
        with allure.step(f"Assert {rule_id} does not exist in the report of system {system_index}"):
            if response_code not in [success, warning_only, failed_with_errors]:
                fail_with_tag(
                    f"System {system_index} Failure",
                    f"system_{system_index}_issue",
                    f'Incorrect error code: {response_code}\nExpected either of: {success}, {warning_only}, {failed_with_errors}'
                )
            if not base64_report:
                allure.attach(
                    "No error file exists",
                    name=f"72bb78 - Assert rule id {rule_id} does not exist",
                    attachment_type=allure.attachment_type.TEXT)
            else:
                file = error_validator.decode_and_parse_error_report(base64_report)
                grid = SchemaRulesValidator(rule_id, expected_type, {
                    tc_error_text: error_text if assert_text else None,
                    tc_object: tc_object_id if assert_object_element else None,
                    tc_element: tc_element_id if assert_object_element else None,
                    tc_field_value: tc_field_value_expected if assert_field_additional else None,
                    tc_additional_reference: tc_additional_reference_expected if assert_field_additional else None,
                }).validate_strategy(file)

                allure.attach(
                    render_grid_csv(grid.rows),
                    name=f"1b6e93 - Match grid for rule {rule_id}",
                    attachment_type=allure.attachment_type.CSV
                )

                found = grid.exists()
                best = grid.best_row()
                row_num = best["row_num"] if best else -1
                actual_error_text = best["columns"].get(tc_error_text, {"actual": ''})["actual"] if best else ''
                if not found:
                    allure.attach(
                        f"Error file doesn't contain the rule id\n\n" + f"{json.dumps(file, indent=2)}",
                        name=f"1fa57f - Assert rule id {rule_id} does not exist",
                        attachment_type=allure.attachment_type.TEXT
                    )
                else:
                    allure.attach(
                        f"Error file contains the rule id\n\nError Text:{actual_error_text}\n\n" + f"{json.dumps(file, indent=2)}",
                        name=f"7efb21 - Assert rule id {rule_id} does not exist",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    fail_with_tag(f"System {system_index} Failure", f"system_{system_index}_issue", "Error report contains the ruleID")
        return found, row_num

    def custom_assert(self, test_case, request_template, system_index, template_flow=None):
        expected = test_case.get(tc_objective)
        if not expected:
            pytest.fail("No expected result found in test case")
        lines = [line.strip() for line in expected.split('\n') if line.strip()]
        for line in lines:
            line_lower = line.lower()
            if line_lower.startswith('errorcode'):
                try:
                    error_code = line.split('-', 1)[1].strip()
                    self._assert_error_code(error_code, system_index)
                except IndexError:
                    pytest.fail("Issue with error code. Make sure to use the format ErrorCode - {error_code}")
            elif line_lower.startswith('errorreport'):
                try:
                    pairs_str = line.split('-', 1)[1].strip()
                    self._assert_error_report(pairs_str, system_index)
                except IndexError:
                    pytest.fail("Issue with error report. Make sure to use the format ErrorReport - Column1=Value1;Column2=Value2")
            elif line_lower.startswith('response matches xml template'):
                try:
                    template_filename = line.split('-', 1)[1].strip()
                    self._assert_response_matches_xml_template(template_filename, system_index)
                except IndexError:
                    pytest.fail("Issue with xml template assertion. Make sure to use the format Response matches xml template - filename.xml")
            elif line_lower.startswith('no errors'):
                self._assert_no_errors(system_index)
            elif line_lower.startswith('error'):
                try:
                    error_message = line.split('-', 1)[1].strip()
                    self._assert_error_message(error_message, request_template, system_index, template_flow)
                except IndexError:
                    pytest.fail("Issue with error message. Make sure to use the format Error - {error_message}")
            else:
                pytest.fail(f"Unexpected assertion: {line}")

    def _assert_no_errors(self, system_index):
        error_validator = ErrorValidator()
        base64_report = error_validator.extract_error_report(self.response['content'])
        response_code = error_validator.extract_response_code(self.response['content'])
        with allure.step("Assert no errors found"):
            if response_code != success and response_code != warning_only:
                fail_with_tag(
                    f"System {system_index} Failure",
                    f"system_{system_index}_issue",
                    f"Response code '{response_code}' is not {success} or {warning_only}"
                )
            if base64_report:
                file = error_validator.decode_and_parse_error_report(base64_report)
                for element in file:
                    if element.get("Type") == 'ERROR':
                        allure.attach(
                            json.dumps(file, indent=2),
                            name="39ae3c - Assert no errors failed",
                            attachment_type=allure.attachment_type.JSON)
                        fail_with_tag(f"System {system_index} Failure", f"system_{system_index}_issue", f"Error exists in the report")

    def _assert_error_code(self, error_code, system_index):
        error_validator = ErrorValidator()
        actual_error_code = error_validator.extract_response_code(self.response['content'])
        with allure.step(f"Assert error code is '{error_code}' in system {system_index}"):
            allure.attach(
                f"Expected error code: {error_code}\nActual error code: {actual_error_code}",
                name='f3a1c9 - Check error code',
                attachment_type=allure.attachment_type.TEXT
            )
            if actual_error_code != error_code:
                fail_with_tag(
                    f"System {system_index} Failure",
                    f"system_{system_index}_issue",
                    f"Error code is incorrect\nExpected: {error_code}\nActual: {actual_error_code}"
                )

    def _assert_error_message(self, error_message, request_template, system_index, template_flow=None):
        if request_template is not None:
            error_message = ErrorTextProcessor(error_message, request_template, template_flow).process_error_text()
        xml_response_body = ET.fromstring(self.response['content'])
        error_element = ExtractDataContext(xml_response_body).decide_template_type().extract_xml_element_from_template(
            xml_response_body, 'errorMessage')
        if error_element is None:
            raise Exception("'errorMessage' element was not found in the response")
        with allure.step(f"Assert error message in system {system_index}"):
            allure.attach(
                f"Expected error message: {error_message}\nActual error message: {error_element.text}",
                name='d8b2e5 - Check error message',
                attachment_type=allure.attachment_type.TEXT
            )
            if error_element.text != error_message:
                fail_with_tag(
                    f"System {system_index} Failure",
                    f"system_{system_index}_issue",
                    f"Expected error message doesn't match actual\nExpected: {error_message}\nActual: {error_element.text}"
                )

    def _assert_error_report(self, pairs_str, system_index):
        expected_pairs = {}
        for pair in pairs_str.split(';'):
            pair = pair.strip()
            if '=' not in pair:
                pytest.fail(f"Invalid error report pair '{pair}'. Use the format Column=Value")
            col, val = pair.split('=', 1)
            expected_pairs[col.strip()] = val.strip()
        error_validator = ErrorValidator()
        base64_report = error_validator.extract_error_report(self.response['content'])
        with allure.step(f"Assert error report contains {expected_pairs} in system {system_index}"):
            if not base64_report:
                allure.attach(
                    f"Expected: {expected_pairs}\n\nNo error report found in response",
                    name='a3f8b1 - Check error report',
                    attachment_type=allure.attachment_type.TEXT
                )
                fail_with_tag(f"System {system_index} Failure", f"system_{system_index}_issue", "Error report is empty but expected values were specified")
            rows = error_validator.decode_and_parse_error_report(base64_report)
            found = any(
                all(str(row.get(col, '')).strip() == val for col, val in expected_pairs.items())
                for row in rows
            )
            allure.attach(
                f"Expected columns/values: {expected_pairs}\n\nError report rows:\n{json.dumps(rows, indent=2)}",
                name='a3f8b1 - Check error report',
                attachment_type=allure.attachment_type.TEXT
            )
            if not found:
                fail_with_tag(f"System {system_index} Failure", f"system_{system_index}_issue", f"No row in the error report matched the expected values: {expected_pairs}")

    def _assert_response_matches_xml_template(self, template_filename, system_index):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_path = os.path.join(project_root, "xml_templates", template_filename)
        if not os.path.exists(template_path):
            pytest.fail(f"XML template file not found: {template_path}")
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        template_string = ET.tostring(ET.fromstring(template_content), encoding='unicode')
        response_string = ET.tostring(ET.fromstring(self.response['content']), encoding='unicode')
        with allure.step(f"Assert response matches xml template '{template_filename}' in system {system_index}"):
            allure.attach(
                f"Template: {template_string}\n\nResponse: {response_string}",
                name='b5c3e7 - Response vs XML template',
                attachment_type=allure.attachment_type.TEXT
            )
            if response_string != template_string:
                fail_with_tag(f"System {system_index} Failure", f"system_{system_index}_issue", f"Response does not match XML template '{template_filename}'")


class XMLDualAsserter:

    def __init__(self, response, second_response):
        self.response = response
        self.second_response = second_response

    def assert_responses_errors(self):
        error_validator = ErrorValidator()
        base64_report_first = error_validator.extract_error_report(self.response['content'])
        response_code_first = error_validator.extract_response_code(self.response['content'])
        base64_report_second = error_validator.extract_error_report(self.second_response['content'])
        response_code_second = error_validator.extract_response_code(self.second_response['content'])
        with allure.step(f"Assert both responses have same errors"):
            if response_code_first != response_code_second:
                allure.attach(
                                f"Error codes are different on both systems\nOld system code: {response_code_first}\nNew system code: {response_code_second}",
                                name="979b2c - Compare responses codes",
                                attachment_type=allure.attachment_type.TEXT
                            )
                fail_with_tag("Dual System Failure", "dual_system_failure", "Error code of old system doesn't match new system")
            if base64_report_first and base64_report_second:
                file_first = error_validator.decode_and_parse_error_report(base64_report_first)
                file_second = error_validator.decode_and_parse_error_report(base64_report_second)
                if len(file_first) == len(file_second):
                    for element in file_first:
                        found = False
                        partial_match = None
                        for second_element in file_second:
                            if (element.get("Type") == second_element.get("Type") and
                                    element.get("RuleID") == second_element.get("RuleID")):
                                if (element.get("Transaction") == second_element.get("Transaction")
                                        and element.get("Object Name") == second_element.get("Object Name")
                                        and element.get("HAAD Field") == second_element.get("HAAD Field")
                                        and element.get("Field Value") == second_element.get("Field Value")
                                        and element.get("Additional Reference") == second_element.get("Additional Reference")):
                                    if element.get("Error Text") != second_element.get("Error Text"):
                                        allure.attach(
                                            f"Error text in old system response doesn't match new system response:\n\nError:\n{element}\n\nOld system text:\n{element}\n\nNew system text:\n{second_element}",
                                            name="76b634 - Compare responses error texts",
                                            attachment_type=allure.attachment_type.TEXT
                                        )
                                        fail_with_tag("Dual System Error Text Failure", "dual_system_error_text_failure", "Error text in old system response doesn't match new system response")
                                    found = True
                                    break
                                elif partial_match is None:
                                    partial_match = second_element
                        if not found:
                            if partial_match is not None:
                                allure.attach(
                                    f"Error fields don't match between old and new system response:\n\nOld system error:\n{element}\n\nNew system error:\n{partial_match}\n\nOld system errors:\n{file_first}\n\nNew system errors:\n{file_second}",
                                    name="c4f21a - Compare responses error fields",
                                    attachment_type=allure.attachment_type.TEXT
                                )
                                fail_with_tag("Dual System Failure", "dual_system_failure", "Error fields in old system response don't match new system response")
                            else:
                                allure.attach(
                                    f"Error in old system response is not found in new system response:\n\nError:\n{element}\n\nOld system errors:\n{file_first}\n\nNew system errors:\n{file_second}",
                                    name="bedd20 - Compare responses errors",
                                    attachment_type=allure.attachment_type.TEXT
                                )
                                fail_with_tag("Dual System Failure", "dual_system_failure", "Error in old system response is not found in new system response")
                else:
                    allure.attach(
                        f"files don't have same error count: \n\nOld System:\n{file_first}\n\nNew System:\n{file_second}",
                        name="bb87e7 - Compare responses errors",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    fail_with_tag("Dual System Failure", "dual_system_failure", "Error files don't contains same count of errors")
            else:
                allure.attach(
                    f"Old system response has error report: \n\n{base64_report_first}\n\nNew system response has error report: \n\n{base64_report_second}",
                    name="731468 - Compare responses errors",
                    attachment_type=allure.attachment_type.TEXT
                )
                fail_with_tag("Dual System Failure", "dual_system_failure", "One of the responses doesn't have an error report")

class XMLDualSingleRowAsserter:

    def __init__(self, response, second_response, test_case):
        self.response = response
        self.second_response = second_response
        self.test_case = test_case

    def assert_responses_errors(self, row_num_first, row_num_second):
        rule_id = self.test_case.get(tc_rule_id)
        error_validator = ErrorValidator()
        base64_report_first = error_validator.extract_error_report(self.response['content'])
        base64_report_second = error_validator.extract_error_report(self.second_response['content'])
        with allure.step(f"Assert row values match between both systems for rule {rule_id}"):
            if not base64_report_first or not base64_report_second:
                return
            if row_num_first == -1 or row_num_second == -1:
                return
            file_first = error_validator.decode_and_parse_error_report(base64_report_first)
            file_second = error_validator.decode_and_parse_error_report(base64_report_second)
            row_first = file_first[row_num_first]
            row_second = file_second[row_num_second]
            mismatches = []
            for column in row_first:
                val_first = str(row_first.get(column, ''))
                val_second = str(row_second.get(column, ''))
                if val_first != val_second:
                    mismatches.append(f"Column '{column}': System 1='{val_first}' | System 2='{val_second}'")
            if mismatches:
                allure.attach(
                    f"Row mismatch for rule {rule_id}:\n\n" + '\n'.join(mismatches) +
                    f"\n\nSystem 1 row:\n{json.dumps(row_first, indent=2)}\n\nSystem 2 row:\n{json.dumps(row_second, indent=2)}",
                    name=f"e8f3d2 - Row comparison failed for rule {rule_id}",
                    attachment_type=allure.attachment_type.TEXT
                )
                fail_with_tag("Dual System Row Failure", "dual_system_row_failure", f"Row values differ between systems for rule {rule_id}")
            else:
                allure.attach(
                    f"All column values match for rule {rule_id}\n\nRow:\n{json.dumps(row_first, indent=2)}",
                    name=f"Row comparison passed for rule {rule_id}",
                    attachment_type=allure.attachment_type.TEXT
                )
