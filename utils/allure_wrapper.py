"""
Allure Pytest Wrapper - Converts Excel test cases to pytest-compatible tests
COMPLETE VERSION - With full response extraction support
"""

import allure
import os
import threading
from utils.asserter.asserter import XMLAsserter
from utils.common_variables import tc_id, tc_description, tc_name, tc_request_name, tc_test_data, tc_rule_id, \
    tc_objective, tc_precondition
from utils.request_mapper.request_mapper_context import do_requests
from utils.request_sender.system_enums import Systems
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
            data = data + (self.excel_handler.load_excel(excel_file_path, sheet))

        return data

_test_cases_cache = None
_cache_lock = threading.Lock()


def get_worker_id():
    """Get xdist worker ID if available"""
    return os.environ.get('PYTEST_XDIST_WORKER', 'main')


def pytest_generate_tests(metafunc):
    """Pytest hook to generate parameterized tests from Excel - xdist compatible"""

    if "soap_test_case" in metafunc.fixturenames:
        excel_file = os.environ.get('SOAP_EXCEL_FILE', 'test_cases.xlsx')
        sheets_to_test = os.environ.get('EXCEL_FILE_TEST_SHEETS', None)
        # Load test cases (this will be the same for all workers)
        test_cases = SOAPTestExecutor().load_test_cases_from_excel(excel_file, sheets_to_test)

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
        os.environ.get('SOAP_EXECUTION_MODE', 'both_systems'),
    )
    execution_mode = os.environ.get('SOAP_EXECUTION_MODE', 'both_systems')

    try:
        if execution_mode == "system1_only":
            _execute_system1_baseline(test_case)
        else:
            _execute_dual_system_regression(test_case)

        print(f"Worker {worker_id}: Completed test {test_case[tc_id]} - PASSED")

    except Exception as e:
        print(f"Worker {worker_id}: Test {test_case[tc_id]} FAILED: {str(e)}")
        raise

def _execute_system1_baseline(test_case):
    try:
        response, template, prerequisite_response = do_requests(test_case[tc_request_name], test_case[tc_precondition]).do_request(system= Systems.OLD_SYSTEM ,live_data=test_case[tc_test_data])
        if 'Pass'.lower() in test_case.get(tc_objective).lower():
            XMLAsserter(response).assert_error_doesnt_exist(test_case)
        else:
            XMLAsserter(response).assert_error_exists(test_case)
    except Exception as e:
        worker_id = get_worker_id()
        print(f"Worker {worker_id}: Error in system1 baseline for {test_case[tc_id]}: {str(e)}")
        raise

def _execute_dual_system_regression(test_case):
    try:
        request = do_requests(test_case[tc_request_name], test_case[tc_precondition])
        old_system_response, template, prerequisite_response = request.do_request(system= Systems.OLD_SYSTEM ,live_data=test_case[tc_test_data])
        if 'Pass'.lower() in test_case.get(tc_objective).lower():
            XMLAsserter(old_system_response).assert_error_doesnt_exist(test_case)
        else:
            XMLAsserter(old_system_response).assert_error_exists(test_case)
        new_system_response, template, prerequisite_response = request.do_request(system= Systems.NEW_SYSTEM ,live_data=test_case[tc_test_data])
        XMLAsserter(old_system_response).assert_responses_errors(new_system_response)
    except Exception as e:
        worker_id = get_worker_id()
        print(f"Worker {worker_id}: Error in dual system regression for {test_case[tc_id]}: {str(e)}")
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