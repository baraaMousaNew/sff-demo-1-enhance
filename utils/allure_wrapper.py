"""
Allure Pytest Wrapper - Converts Excel test cases to pytest-compatible tests
COMPLETE VERSION - With full response extraction support
"""

from utils.common_variables import tc_scenario_type
from utils.asserter.asserter import XMLAsserterContext
from utils.asserter.report_row_type import ReportRowType
from utils.env_vars import EnvVar
from utils.execution_mode import ExecutionMode
import allure
import os
import threading
from utils.common_variables import tc_id, tc_description, tc_name, tc_request_name, tc_test_data, tc_rule_id, \
    tc_objective, tc_precondition, tc_error_text, tc_object, tc_element, tc_skip_env1
from utils.request_mapper.request_mapper_context import do_requests
from utils.request_sender.system_enums import Systems
from utils.request_sender.send_request_context import reset_step_delay
from utils.excel_handler import ExcelHandler
from utils.api_client import APIClient
from utils.variable_processor import VariableProcessor
from utils.allure_reporter import AllureReporter
from utils.error_validator import ErrorValidator

class SOAPTestExecutor:
    def __init__(self):
        self.excel_handler = ExcelHandler()
        self.api_client = APIClient()
        self.variable_processor = VariableProcessor()
        self.allure_reporter = AllureReporter()
        self.error_validator = ErrorValidator()

    def load_test_cases_from_excel(self, excel_file_path, sheets_to_test):
        split_sheets_to_test = sheets_to_test.split(",")
        sheets_to_test_list = [sheet.strip() for sheet in split_sheets_to_test]
        data = []
        for sheet in sheets_to_test_list:
            """Load and parse test cases from Excel"""
            sheet_cases = self.excel_handler.load_excel(excel_file_path, sheet)
            for case in sheet_cases:
                case['_sheet_name'] = sheet
            data = data + sheet_cases

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
        test_cases = SOAPTestExecutor().load_test_cases_from_excel(excel_file, sheets_to_test)

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

    executor = SOAPTestExecutor()
    test_case = soap_test_case
    worker_id = get_worker_id()

    # Add worker info to Allure report for debugging parallel execution
    allure.dynamic.description(f"Test ID: {test_case[tc_id]}\nExecuted by worker {worker_id}")
    allure.dynamic.label("worker", worker_id)

    # Add test case info for better tracking
    print(f"Worker {worker_id}: Executing test {test_case[tc_id]}")

    # Initialize Allure reporting
    executor.allure_reporter.start_test_case(
        test_case[tc_id],
        f"{test_case[tc_name]}",
        os.environ.get(EnvVar.SOAP_EXECUTION_MODE, ExecutionMode.BOTH_SYSTEMS),
    )
    execution_mode = os.environ.get(EnvVar.SOAP_EXECUTION_MODE, ExecutionMode.BOTH_SYSTEMS)

    # Dynamic Suite Labeling
    allure.dynamic.parent_suite("SOAP API Automation")
    if execution_mode == ExecutionMode.SYSTEM1_ONLY:
        allure.dynamic.suite("System 1 Validation")
        allure.dynamic.sub_suite("Error Collection")
    elif execution_mode == ExecutionMode.SYSTEM2_ONLY:
        allure.dynamic.suite("System 2 Validation")
        allure.dynamic.sub_suite("Error Collection")
    elif execution_mode == ExecutionMode.SYSTEM1_BOTH_ENVS:
        allure.dynamic.suite("Regression Tests")
        allure.dynamic.sub_suite("Dual Legacy System Verification")
    else:
        allure.dynamic.suite("Regression Tests")
        allure.dynamic.sub_suite("Dual System Verification")

    reset_step_delay()
    try:
        if execution_mode == ExecutionMode.SYSTEM1_ONLY:
            _execute_system1_baseline(test_case)
        elif execution_mode == ExecutionMode.SYSTEM2_ONLY:
            _execute_system2_only(test_case)
        elif execution_mode == ExecutionMode.SYSTEM1_BOTH_ENVS:
            _execute_system1_both_envs(test_case)
        else:
            _execute_dual_system_regression(test_case)
        print(f"Worker {worker_id}: Completed test {test_case[tc_id]} - PASSED")

    except Exception as e:
        print(f"Worker {worker_id}: Test {test_case[tc_id]} FAILED: {str(e)}")
        raise

def _execute_system1_baseline(test_case):
    allure.dynamic.tag(f"Scenario Type - {test_case[tc_scenario_type]}")
    allure.dynamic.tag(f"RuleID - {test_case[tc_rule_id]}")
    allure.dynamic.tag(f"Transaction Type - {test_case[tc_request_name]}")
    allure.dynamic.tag(f"Sheet - {test_case.get('_sheet_name', 'Unknown')}")
    allure.dynamic.tag(f"Object - {test_case[tc_object]}")
    allure.dynamic.tag(f"Element - {test_case[tc_element]}")
    try:
        skip_env1 = str(test_case.get(tc_skip_env1, '')).strip().lower() not in ('', 'false', 'no', '0', 'nan')
        if skip_env1:
            allure.dynamic.tag("Skip Env 1")
        request = do_requests(test_case[tc_request_name], test_case[tc_precondition])
        response, template, template_flow = request.do_request(system= Systems.OLD_SYSTEM ,live_data=test_case[tc_test_data])
        check_error_text = os.environ.get(EnvVar.ASSERT_ERROR_TEXT) == 'true'
        check_object_element = os.environ.get(EnvVar.ASSERT_OBJECT_ELEMENT) == 'true'
        check_field_additional = os.environ.get(EnvVar.ASSERT_FIELD_ADDITIONAL) == 'true'
        if test_case.get(tc_objective).lower().startswith('pass'):
            XMLAsserterContext(response).assert_error_doesnt_exist(test_case, template, assert_text=check_error_text, assert_object_element=check_object_element, assert_field_additional=check_field_additional, template_flow=template_flow)
        elif test_case.get(tc_objective).lower().startswith('fail'):
            XMLAsserterContext(response).assert_error_exists(test_case, check_error_text, template, assert_object_element=check_object_element, assert_field_additional=check_field_additional, expected_type=ReportRowType.ERROR, template_flow=template_flow)
        elif test_case.get(tc_objective).lower().startswith('warning'):
            XMLAsserterContext(response).assert_error_exists(test_case, check_error_text, template, assert_object_element=check_object_element, assert_field_additional=check_field_additional, expected_type=ReportRowType.WARNING, template_flow=template_flow)
        elif test_case.get(tc_objective).lower().startswith('notification'):
            XMLAsserterContext(response).assert_error_exists(test_case, check_error_text, template, assert_object_element=check_object_element, assert_field_additional=check_field_additional, expected_type=ReportRowType.NOTIFICATION, template_flow=template_flow)
        else:
            XMLAsserterContext(response).custom_assert(test_case, template)
    except Exception as e:
        worker_id = get_worker_id()
        print(f"Worker {worker_id}: Error in system1 baseline for {test_case[tc_id]}: {str(e)}")
        raise

def _execute_system2_only(test_case):
    allure.dynamic.tag(f"Scenario Type - {test_case[tc_scenario_type]}")
    allure.dynamic.tag(f"RuleID - {test_case[tc_rule_id]}")
    allure.dynamic.tag(f"Transaction Type - {test_case[tc_request_name]}")
    allure.dynamic.tag(f"Sheet - {test_case.get('_sheet_name', 'Unknown')}")
    allure.dynamic.tag(f"Object - {test_case[tc_object]}")
    allure.dynamic.tag(f"Element - {test_case[tc_element]}")
    try:
        request = do_requests(test_case[tc_request_name], test_case[tc_precondition])
        response, template, template_flow = request.do_request(system= Systems.NEW_SYSTEM ,live_data=test_case[tc_test_data])
        check_error_text = os.environ.get(EnvVar.ASSERT_ERROR_TEXT) == 'true'
        check_object_element = os.environ.get(EnvVar.ASSERT_OBJECT_ELEMENT) == 'true'
        check_field_additional = os.environ.get(EnvVar.ASSERT_FIELD_ADDITIONAL) == 'true'
        if test_case.get(tc_objective).lower().startswith('pass'):
            XMLAsserterContext(response).assert_error_doesnt_exist(test_case, template, assert_text=check_error_text, assert_object_element=check_object_element, assert_field_additional=check_field_additional, template_flow=template_flow)
        elif test_case.get(tc_objective).lower().startswith('fail'):
            XMLAsserterContext(response).assert_error_exists(test_case, check_error_text, template, assert_object_element=check_object_element, assert_field_additional=check_field_additional, expected_type=ReportRowType.ERROR, template_flow=template_flow)
        elif test_case.get(tc_objective).lower().startswith('warning'):
            XMLAsserterContext(response).assert_error_exists(test_case, check_error_text, template, assert_object_element=check_object_element, assert_field_additional=check_field_additional, expected_type=ReportRowType.WARNING, template_flow=template_flow)
        elif test_case.get(tc_objective).lower().startswith('notification'):
            XMLAsserterContext(response).assert_error_exists(test_case, check_error_text, template, assert_object_element=check_object_element, assert_field_additional=check_field_additional, expected_type=ReportRowType.NOTIFICATION, template_flow=template_flow)
        else:
            XMLAsserterContext(response).custom_assert(test_case, template)
    except Exception as e:
        worker_id = get_worker_id()
        print(f"Worker {worker_id}: Error in system2 only for {test_case[tc_id]}: {str(e)}")
        raise

def _execute_dual_system_regression(test_case):
    allure.dynamic.tag(f"Scenario Type - {test_case[tc_scenario_type]}")
    allure.dynamic.tag(f"RuleID - {test_case[tc_rule_id]}")
    allure.dynamic.tag(f"Transaction Type - {test_case[tc_request_name]}")
    allure.dynamic.tag(f"Sheet - {test_case.get('_sheet_name', 'Unknown')}")
    allure.dynamic.tag(f"Object - {test_case[tc_object]}")
    allure.dynamic.tag(f"Element - {test_case[tc_element]}")
    try:
        request = do_requests(test_case[tc_request_name], test_case[tc_precondition])
        skip_env1 = str(test_case.get(tc_skip_env1, '')).strip().lower() not in ('', 'false', 'no', '0', 'nan')
        if skip_env1:
            allure.dynamic.tag("Skip Env 1")
            system = Systems.NEW_SYSTEM
        else:
            system = Systems.DUAL_SYSTEMS
        system_response, template, template_flow = request.do_request(system=system, live_data=test_case[tc_test_data])
        asserter = XMLAsserterContext(system_response, system_index=2 if skip_env1 else 1)
        check_error_text = os.environ.get(EnvVar.ASSERT_ERROR_TEXT) == 'true'
        check_object_element = os.environ.get(EnvVar.ASSERT_OBJECT_ELEMENT) == 'true'
        check_field_additional = os.environ.get(EnvVar.ASSERT_FIELD_ADDITIONAL) == 'true'
        if test_case.get(tc_objective).lower().startswith('pass'):
            asserter.assert_error_doesnt_exist(test_case, template, assert_text=check_error_text, assert_object_element=check_object_element, assert_field_additional=check_field_additional, template_flow=template_flow)
        elif test_case.get(tc_objective).lower().startswith('fail'):
            asserter.assert_error_exists(test_case, check_error_text, template, assert_object_element=check_object_element, assert_field_additional=check_field_additional, expected_type=ReportRowType.ERROR, template_flow=template_flow)
        elif test_case.get(tc_objective).lower().startswith('warning'):
            asserter.assert_error_exists(test_case, check_error_text, template, assert_object_element=check_object_element, assert_field_additional=check_field_additional, expected_type=ReportRowType.WARNING, template_flow=template_flow)
        elif test_case.get(tc_objective).lower().startswith('notification'):
            asserter.assert_error_exists(test_case, check_error_text, template, assert_object_element=check_object_element, assert_field_additional=check_field_additional, expected_type=ReportRowType.NOTIFICATION, template_flow=template_flow)
        else:
            asserter.custom_assert(test_case, template)
    ##  BaseException is used here to catch all exceptions including the pytest.fail() exceptions. If normal Exception is used, pytest.fail() exceptions will not be caught.
    except Exception as e:
        worker_id = get_worker_id()
        print(f"Worker {worker_id}: Error in dual system regression (System 1) for {test_case[tc_id]}: {str(e)}")
        raise

def _execute_system1_both_envs(test_case):
    allure.dynamic.tag(f"Scenario Type - {test_case[tc_scenario_type]}")
    allure.dynamic.tag(f"RuleID - {test_case[tc_rule_id]}")
    allure.dynamic.tag(f"Transaction Type - {test_case[tc_request_name]}")
    allure.dynamic.tag(f"Sheet - {test_case.get('_sheet_name', 'Unknown')}")
    allure.dynamic.tag(f"Object - {test_case[tc_object]}")
    allure.dynamic.tag(f"Element - {test_case[tc_element]}")
    try:
        request = do_requests(test_case[tc_request_name], test_case[tc_precondition])
        skip_env1 = str(test_case.get(tc_skip_env1, '')).strip().lower() not in ('', 'false', 'no', '0', 'nan')
        if skip_env1:
            allure.dynamic.tag("Skip Env 1")
            system = Systems.OLD_SYSTEM
        else:
            system = Systems.DUAL_OLD_SYSTEM
        system_response, template, template_flow = request.do_request(system=system, live_data=test_case[tc_test_data])
        asserter = XMLAsserterContext(system_response, system_index=2 if skip_env1 else 1)
        check_error_text = os.environ.get(EnvVar.ASSERT_ERROR_TEXT) == 'true'
        check_object_element = os.environ.get(EnvVar.ASSERT_OBJECT_ELEMENT) == 'true'
        check_field_additional = os.environ.get(EnvVar.ASSERT_FIELD_ADDITIONAL) == 'true'
        if test_case.get(tc_objective).lower().startswith('pass'):
            asserter.assert_error_doesnt_exist(test_case, template, assert_text=check_error_text, assert_object_element=check_object_element, assert_field_additional=check_field_additional, template_flow=template_flow)
        elif test_case.get(tc_objective).lower().startswith('fail'):
            asserter.assert_error_exists(test_case, check_error_text, template, assert_object_element=check_object_element, assert_field_additional=check_field_additional, expected_type=ReportRowType.ERROR, template_flow=template_flow)
        elif test_case.get(tc_objective).lower().startswith('warning'):
            asserter.assert_error_exists(test_case, check_error_text, template, assert_object_element=check_object_element, assert_field_additional=check_field_additional, expected_type=ReportRowType.WARNING, template_flow=template_flow)
        elif test_case.get(tc_objective).lower().startswith('notification'):
            asserter.assert_error_exists(test_case, check_error_text, template, assert_object_element=check_object_element, assert_field_additional=check_field_additional, expected_type=ReportRowType.NOTIFICATION, template_flow=template_flow)
        else:
            asserter.custom_assert(test_case, template)
    ##  BaseException is used here to catch all exceptions including the pytest.fail() exceptions. If normal Exception is used, pytest.fail() exceptions will not be caught.
    except Exception as e:
        worker_id = get_worker_id()
        print(f"Worker {worker_id}: Error in dual system regression (System 1) for {test_case[tc_id]}: {str(e)}")
        raise

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