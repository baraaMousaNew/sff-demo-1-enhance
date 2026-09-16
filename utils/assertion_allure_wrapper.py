"""
Assertion Allure Wrapper - Converts Excel assertion test cases to pytest-compatible tests
Enhanced version of allure_wrapper.py with assertion support
"""
import re
import threading
import xml.etree.ElementTree as ET

import pytest
import allure
import os
import sys
from pathlib import Path

from utils.asserter.custom_requests_asserter import CustomAsserter, CustomAsserterContext
from utils.asserter.error_text_processor import ErrorTextProcessor
from utils.common_variables import tc_id, tc_name, tc_request_name, tc_rule_id, tc_objective, tc_test_data, \
    tc_precondition, tc_scenario_type, tc_object, tc_element, tc_dependency, tc_dependency_variables
from utils.template_generator.extract_data_strategy.extract_data_context import ExtractDataContext
from utils.request_mapper.request_mapper_context import do_assertion_requests
from utils import dependency_tracker
from utils.request_sender.system_enums import Systems
from utils.env_vars import EnvVar
from utils.execution_mode import ExecutionMode

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from utils.excel_handler import ExcelHandler
from utils.api_client import APIClient
from utils.variable_processor import VariableProcessor
from utils.assertion_validator import AssertionValidator
from utils.allure_reporter import AllureReporter


class AssertionTestExecutor:
    def __init__(self):
        self.excel_handler = ExcelHandler()
        self.api_client = APIClient()
        self.variable_processor = VariableProcessor()
        self.assertion_validator = AssertionValidator()
        self.allure_reporter = AllureReporter()

    def load_test_cases_from_excel(self, excel_file_path, sheets_to_test):
        split_sheets_to_test = sheets_to_test.split(",")
        sheets_to_test_list = [sheet.strip() for sheet in split_sheets_to_test]
        data = []
        for sheet in sheets_to_test_list:
            """Load and parse test cases from Excel"""
            sheet_data = self.excel_handler.load_excel(excel_file_path, sheet)
            for case in sheet_data:
                case['_sheet_name'] = sheet
            data = data + sheet_data

        return data


_test_cases_cache = None
_cache_lock = threading.Lock()


def get_worker_id():
    """Get xdist worker ID if available"""
    return os.environ.get(EnvVar.PYTEST_XDIST_WORKER, 'main')


def pytest_generate_tests(metafunc):
    """Pytest hook to generate parameterized tests from Excel - xdist compatible"""

    if "soap_test_case" in metafunc.fixturenames:
        excel_file = os.environ.get(EnvVar.SOAP_EXCEL_FILE, 'test_cases.xlsx')
        sheets_to_test = os.environ.get(EnvVar.EXCEL_FILE_TEST_SHEETS, None)
        specific_cases = os.environ.get(EnvVar.SPECIFIC_TEST_CASES, None)
        # Load test cases (this will be the same for all workers)
        test_cases = AssertionTestExecutor().load_test_cases_from_excel(excel_file, sheets_to_test)

        # Filter by specific test case IDs if provided
        if specific_cases:
            specific_case_list = [tc.strip() for tc in specific_cases.split(',')]
            test_cases = [tc for tc in test_cases if str(tc.get('TC ID', '')) in specific_case_list]
            worker_id = get_worker_id()
            print(f"Worker {worker_id}: Filtered to {len(test_cases)} specific test cases: {specific_case_list}")

        # Filter by specific Rule IDs if provided
        specific_rule_ids = os.environ.get(EnvVar.SPECIFIC_RULE_IDS, None)
        if specific_rule_ids:
            rule_id_list = [rid.strip() for rid in specific_rule_ids.split(',')]
            test_cases = [tc for tc in test_cases if str(tc.get('Rule ID', '')).strip() in rule_id_list]
            worker_id = get_worker_id()
            print(f"Worker {worker_id}: Filtered to {len(test_cases)} test cases for Rule ID(s): {rule_id_list}")

        if test_cases:
            # Sort so dependencies always come before their dependents.
            # This reduces (but does not eliminate) the need for polling in parallel mode.
            test_cases = dependency_tracker.topological_sort(test_cases, tc_id, tc_dependency)

            # Mark whether each test case's dependency is part of the current run.
            # If the dependency is not being run, the check is skipped at runtime.
            runnable_ids = {str(tc.get(tc_id, '')).strip() for tc in test_cases}
            for tc in test_cases:
                dep = str(tc.get(tc_dependency, '')).strip()
                tc['_dep_in_run'] = bool(dep) and dep in runnable_ids

            # Create test IDs
            ids = [case['TC ID'] for case in test_cases]

            worker_id = get_worker_id()
            print(f"Worker {worker_id}: Parameterizing {len(test_cases)} tests")

            # CRITICAL: Let pytest-xdist handle the distribution
            # All workers get the same parameterization, but xdist will distribute them
            metafunc.parametrize("soap_test_case", test_cases, ids=ids)

        else:
            print(f"Worker {get_worker_id()}: WARNING: No test cases found to execute")


@allure.feature("SOAP API Testing")
@allure.story("Dual System Comparison")
def test_soap(soap_test_case):
    """Main pytest test function for dual-system regression testing"""

    executor = AssertionTestExecutor()
    test_case = soap_test_case
    worker_id = get_worker_id()

    # Add worker info to Allure report for debugging parallel execution
    allure.dynamic.description(f"Test ID: {test_case[tc_id]}\nExecuted by worker {worker_id}")
    allure.dynamic.label("worker", worker_id)

    # Enforce dependency: skip this test if its prerequisite did not pass.
    # Only enforced when the dependency is part of the current test run.
    dependency = str(test_case.get(tc_dependency, '')).strip()
    if dependency and test_case.get('_dep_in_run', False):
        dep_result = dependency_tracker.check_dependency(dependency)
        if dep_result != 'passed':
            reason = f"Dependency '{dependency}' {dep_result}"
            print(f"Worker {worker_id}: Skipping {test_case[tc_id]} — {reason}")
            dependency_tracker.record_result(test_case[tc_id], 'skipped')
            pytest.skip(reason)

        # Inject variables extracted from the dependency's response into this test case's
        # Test Data, substituting {{EXTRACT.variable_name}} placeholders with actual values.
        dep_vars = dependency_tracker.get_extracted_variables(dependency)
        if dep_vars:
            test_case = dict(test_case)  # shallow copy — don't mutate the parametrized fixture

            # Test Data: simple {{EXTRACT.var}} substitution (format processed downstream by template generator)
            test_data = str(test_case.get(tc_test_data, ''))
            for var_name, var_value in dep_vars.items():
                test_data = test_data.replace(f'{{{{EXTRACT.{var_name}}}}}', str(var_value))
            test_case[tc_test_data] = test_data

            # Objective: full expression evaluation so EXTRACT refs work inside function calls
            # e.g. {{CUSTOM.add_to_number(EXTRACT.download_count, 1)}}
            test_case[tc_objective] = _process_objective_with_dep_vars(
                str(test_case.get(tc_objective, '')), dep_vars)

            print(f"Worker {worker_id}: Injected dependency variables into {test_case[tc_id]}: {list(dep_vars.keys())}")

    # Add test case info for better tracking
    print(f"Worker {worker_id}: Executing test {test_case[tc_id]}")

    # Initialize Allure reporting
    executor.allure_reporter.start_test_case(
        test_case[tc_id],
        f"{test_case[tc_name]}",
        os.environ.get(EnvVar.SOAP_EXECUTION_MODE),
    )
    execution_mode = os.environ.get(EnvVar.SOAP_EXECUTION_MODE)

    try:
        if execution_mode == ExecutionMode.SYSTEM1_ONLY:
            response, template = _execute_system1_baseline(test_case)
        else:
            response, template = _execute_system2_regression(test_case)

        # Extract and store variables from this test's response/template so dependents can use them.
        # Must happen before record_result so dependents find variables ready when unblocked.
        _extract_and_store_dep_variables(test_case, response, template)

        dependency_tracker.record_result(test_case[tc_id], 'passed')
        print(f"Worker {worker_id}: Completed test {test_case[tc_id]} - PASSED")

    except (Exception, pytest.fail.Exception) as e:
        dependency_tracker.record_result(test_case[tc_id], 'failed')
        print(f"Worker {worker_id}: Test {test_case[tc_id]} FAILED: {str(e)}")
        raise


def _execute_system1_baseline(test_case):
    allure.dynamic.tag(f"Scenario Type - {test_case[tc_scenario_type]}")
    allure.dynamic.tag(f"RuleID - {test_case[tc_rule_id]}")
    allure.dynamic.tag(f"Transaction Type - {test_case[tc_request_name]}")
    allure.dynamic.tag(f"Sheet - {test_case.get('_sheet_name', 'Unknown')}")
    allure.dynamic.tag(f"Object - {test_case[tc_object]}")
    allure.dynamic.tag(f"Element - {test_case[tc_element]}")
    allure.dynamic.tag(f"Precondition - {test_case[tc_precondition]}")
    try:
        request = do_assertion_requests(test_case[tc_request_name], test_case[tc_precondition])
        response, template, prerequisite_response = request.do_request(system=Systems.OLD_SYSTEM,
                                                                      live_data=test_case[tc_test_data])
        CustomAsserterContext(test_case[tc_request_name]).get_request_strategy().determine(template,response, prerequisite_response, test_case[tc_objective])
        return response, template
    except Exception as e:
        worker_id = get_worker_id()
        print(f"Worker {worker_id}: Error in system1 baseline for {test_case[tc_id]}: {str(e)}")
        raise

def _execute_system2_regression(test_case):
    allure.dynamic.tag(f"Scenario Type - {test_case[tc_scenario_type]}")
    allure.dynamic.tag(f"RuleID - {test_case[tc_rule_id]}")
    allure.dynamic.tag(f"Transaction Type - {test_case[tc_request_name]}")
    allure.dynamic.tag(f"Sheet - {test_case.get('_sheet_name', 'Unknown')}")
    allure.dynamic.tag(f"Object - {test_case[tc_object]}")
    allure.dynamic.tag(f"Element - {test_case[tc_element]}")
    allure.dynamic.tag(f"Precondition - {test_case[tc_precondition]}")
    try:
        request = do_assertion_requests(test_case[tc_request_name], test_case[tc_precondition])
        response, template, prerequisite_response = request.do_request(system=Systems.NEW_SYSTEM,
                                                                                                            live_data=test_case[tc_test_data])
        CustomAsserterContext(test_case[tc_request_name]).get_request_strategy().determine(template,response, prerequisite_response, test_case[tc_objective])
        return response, template
    except Exception as e:
        worker_id = get_worker_id()
        print(f"Worker {worker_id}: Error in system1 baseline for {test_case[tc_id]}: {str(e)}")
        raise


def _process_objective_with_dep_vars(objective: str, dep_vars: dict) -> str:
    """
    Resolve EXTRACT variable references in the objective string, including when they appear
    as parameters inside {{...}} expressions such as {{CUSTOM.add_to_number(EXTRACT.var, 1)}}.

    Step 1 — replace standalone {{EXTRACT.var_name}} with their bare values so they are
              fully resolved before any further processing (e.g. filter values in
              Element assertions such as ParentTag[child={{EXTRACT.var}}].tag=value).
    Step 2 — within remaining {{...}} blocks, replace bare EXTRACT.var_name references
              (embedded inside function calls) with their actual values.
    Step 3 — run the result through VariableProcessor so {{CUSTOM.*}}, {{DATE()}}, etc.
              are fully evaluated.
    """
    # Step 1: direct substitution for standalone {{EXTRACT.xxx}} — produces a bare value
    for var_name, var_value in dep_vars.items():
        objective = objective.replace(f'{{{{EXTRACT.{var_name}}}}}', str(var_value))

    # Step 2: resolve embedded EXTRACT.xxx refs inside complex expressions like
    # {{CUSTOM.add_to_number(EXTRACT.download_count, 1)}}
    def resolve_in_block(match):
        block = match.group(1)
        for var_name, var_value in dep_vars.items():
            block = block.replace(f'EXTRACT.{var_name}', str(var_value))
        return '{{' + block + '}}'

    objective = re.sub(r'\{\{([^}]+)\}\}', resolve_in_block, objective)

    # Step 3: evaluate remaining {{CUSTOM.*}}, {{DATE()}}, etc.
    vp = VariableProcessor()
    vp.extracted_variables = dict(dep_vars)
    return vp.process_all_variables(objective)


def _local_tag(elem):
    """Strip XML namespace from an element tag."""
    tag = elem.tag
    return tag.split('}')[-1] if '}' in tag else tag


def _extract_from_matching_parent(xml_root, parent_tag, filters, extract_tag):
    """
    Search the entire XML tree for elements whose local tag equals parent_tag.
    Among those, return the text of extract_tag from the first element where ALL
    filter conditions (filterChild=filterValue) match.

    Supports multiple filters:  ParentElement[child1=val1,child2=val2].extractChild
    Returns None if no matching element is found.
    """
    for elem in xml_root.iter():
        if _local_tag(elem) != parent_tag:
            continue
        # Check every filter condition against the children of this element
        all_match = all(
            any(_local_tag(child) == fk and child.text == fv for child in elem.iter())
            for fk, fv in filters.items()
        )
        if not all_match:
            continue
        # Found a matching parent — extract the target child value
        for child in elem.iter():
            if _local_tag(child) == extract_tag:
                return child.text
    return None


def _extract_and_store_dep_variables(test_case, response, template):
    """
    Parse the 'Dependency Variables' column and extract the specified element values
    from the test case's response or request template, then store them in the shared state file.

    Three formats are supported (semicolon or newline separated):

    Simple — extract a named element directly from the response:
        varName = ElementTag

    Filtered — search repeated parent elements, match on child values, then extract:
        varName = ParentElement[filterChild=filterValue].extractChild
        varName = ParentElement[child1=val1,child2=val2].extractChild

    Template — extract a value from the request template using dot-path navigation:
        varName = TEMPLATE.Body.Request.fileName

    Example:
        transactionId = TransactionID
        downloadCount = ClaimCountReconciliationData[status=Active].downloadCount
        fileName = TEMPLATE.fileName

    Stored values are later injected into dependent test cases as {{EXTRACT.varName}}.
    """
    dep_var_defs = str(test_case.get(tc_dependency_variables, '')).strip()
    if not dep_var_defs:
        return
    try:
        xml_root = ET.fromstring(response['content']) if response else None
        extracted = {}

        def _resolve_template_refs(text):
            """Replace all {{TEMPLATE.path}} occurrences in text with their template values."""
            def _repl(m):
                try:
                    return ErrorTextProcessor('', template)._search_through_template(m.group(1))
                except Exception:
                    return m.group(0)  # leave unresolved if path not found
            return re.sub(r'\{\{TEMPLATE\.([^}]+)\}\}', _repl, text)

        for rule in re.split(r'[;\n]', dep_var_defs):
            rule = rule.strip()
            if not rule or '=' not in rule:
                continue
            var_name, rhs = [p.strip() for p in rule.split('=', 1)]
            if not var_name or not rhs:
                continue

            # Template extraction (no-braces): TEMPLATE.dot.path
            if rhs.upper().startswith('TEMPLATE.'):
                path = rhs[9:]
                try:
                    value = ErrorTextProcessor('', template)._search_through_template(path)
                    extracted[var_name] = value
                    print(f"Extracted dep variable '{var_name}' = '{value}' from {test_case[tc_id]} "
                          f"(template path: {path})")
                except Exception as ex:
                    print(f"WARNING: Could not extract dep variable '{var_name}' (template path '{path}') "
                          f"from {test_case[tc_id]}: {ex}")
                continue

            # Template extraction (braces): {{TEMPLATE.dot.path}} — entire RHS is a template reference
            template_only_match = re.match(r'^\{\{TEMPLATE\.([^}]+)\}\}$', rhs)
            if template_only_match:
                path = template_only_match.group(1)
                try:
                    value = ErrorTextProcessor('', template)._search_through_template(path)
                    extracted[var_name] = value
                    print(f"Extracted dep variable '{var_name}' = '{value}' from {test_case[tc_id]} "
                          f"(template path: {path})")
                except Exception as ex:
                    print(f"WARNING: Could not extract dep variable '{var_name}' (template path '{path}') "
                          f"from {test_case[tc_id]}: {ex}")
                continue

            # Resolve any {{TEMPLATE.xxx}} references embedded in the RHS (e.g. filter values)
            rhs = _resolve_template_refs(rhs)

            # Filtered response search: ParentElement[filterChild=filterValue,...].extractChild
            if xml_root is not None and re.match(r'^(\w+)\[([^\]]+)\]\.(\w+)$', rhs):
                complex_match = re.match(r'^(\w+)\[([^\]]+)\]\.(\w+)$', rhs)
                parent_tag  = complex_match.group(1)
                filters_str = complex_match.group(2)
                extract_tag = complex_match.group(3)
                filters = {}
                for f in filters_str.split(','):
                    if '=' in f:
                        fk, fv = [p.strip() for p in f.split('=', 1)]
                        filters[fk] = fv
                value = _extract_from_matching_parent(xml_root, parent_tag, filters, extract_tag)
                if value is not None:
                    extracted[var_name] = value
                    print(f"Extracted dep variable '{var_name}' = '{value}' from {test_case[tc_id]} "
                          f"(filtered: {parent_tag}{filters})")
                else:
                    print(f"WARNING: No '{parent_tag}' element matched filters {filters} "
                          f"in {test_case[tc_id]} response")

            # Simple response search: ElementTag
            elif xml_root is not None:
                element = ExtractDataContext(xml_root).decide_template_type().extract_xml_element_from_template(
                    xml_root, rhs)
                if element is not None and element.text is not None:
                    extracted[var_name] = element.text
                    print(f"Extracted dep variable '{var_name}' = '{element.text}' from {test_case[tc_id]}")
                else:
                    print(f"WARNING: Could not extract dep variable '{var_name}' (element '{rhs}') "
                          f"from {test_case[tc_id]} response")

            else:
                print(f"WARNING: Cannot extract dep variable '{var_name}' — no response available "
                      f"for non-TEMPLATE extraction in {test_case[tc_id]}")

        if extracted:
            dependency_tracker.record_extracted_variables(test_case[tc_id], extracted)
            allure.attach(
                '\n'.join(f"{k} = {v}" for k, v in extracted.items()),
                name='Extracted Dependency Variables',
                attachment_type=allure.attachment_type.TEXT
            )
    except Exception as e:
        print(f"WARNING: Failed to extract dependency variables for {test_case[tc_id]}: {e}")

def _capture_raw_xml_processing(executor, step_data):
    """Capture Raw XML processing for Allure reporting"""
    raw_xml_sections = {}

    for key, value in step_data.items():
        if key.startswith('Raw_XML_') and value and str(value).strip():
            suffix = key[8:]  # Remove 'Raw_XML_' prefix

            original_content = str(value).strip()
            processed_content = executor.variable_processor.process_raw_xml_variables(original_content)

            import base64
            encoded_content = base64.b64encode(processed_content.encode('utf-8')).decode('utf-8')

            raw_xml_sections[suffix] = {
                'original': original_content,
                'processed': processed_content,
                'encoded': encoded_content
            }

    return raw_xml_sections