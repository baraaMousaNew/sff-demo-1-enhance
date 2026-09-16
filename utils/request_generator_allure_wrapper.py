"""
Request Generator Allure Wrapper - Executes raw payload requests from an Excel sheet
and records each response in the Allure report.

Environment variables read at runtime:
    REQUEST_GEN_EXCEL_FILE       Path to the Excel file
    REQUEST_GEN_SHEET            Sheet name to load
    REQUEST_GEN_TRANSACTION_COL  Column that holds the transaction / request name (used for tagging)
    REQUEST_GEN_PAYLOAD_COL      Column that holds the raw XML payload to send
    REQUEST_GEN_RESPONSE_COL     Column name that will receive the response (used for labelling only here)
    REQUEST_GEN_URL              Target endpoint URL
    REQUEST_GEN_SOAP_ACTION      SOAPAction header value (optional)
"""

import os
import threading

import allure
import pytest

from utils.api_client import APIClient
from utils.excel_handler import ExcelHandler
from utils.request_sender.soap_action_enums import build_soap_action
from utils.env_vars import EnvVar


# ---------------------------------------------------------------------------
# Executor helper
# ---------------------------------------------------------------------------

class RequestGeneratorExecutor:
    def __init__(self):
        self.excel_handler = ExcelHandler()
        self.api_client = APIClient()

    def load_test_cases(self, excel_file, sheet_name):
        """Return a list of row dicts from the given sheet, annotated with _sheet_name."""
        rows = self.excel_handler.load_excel(excel_file, sheet_name=sheet_name)
        for row in rows:
            row['_sheet_name'] = sheet_name
        return rows


# ---------------------------------------------------------------------------
# Pytest parametrization hook
# ---------------------------------------------------------------------------

def pytest_generate_tests(metafunc):
    if "rg_test_case" not in metafunc.fixturenames:
        return

    excel_file   = os.environ.get(EnvVar.REQUEST_GEN_EXCEL_FILE)
    sheet_name   = os.environ.get(EnvVar.REQUEST_GEN_SHEET)

    if not excel_file or not sheet_name:
        pytest.skip("REQUEST_GEN_EXCEL_FILE or REQUEST_GEN_SHEET not set")
        return

    transaction_col = os.environ.get(EnvVar.REQUEST_GEN_TRANSACTION_COL, '')

    test_cases = RequestGeneratorExecutor().load_test_cases(excel_file, sheet_name)

    if not test_cases:
        pytest.skip("No rows found in the selected sheet")
        return

    ids = [str(row.get(transaction_col, i)) for i, row in enumerate(test_cases)]
    metafunc.parametrize("rg_test_case", test_cases, ids=ids)


# ---------------------------------------------------------------------------
# Test function
# ---------------------------------------------------------------------------

@allure.feature("Request Generator")
@allure.story("Environment Execution")
def test_request_generator(rg_test_case):
    """Execute a raw payload request and attach the response to the Allure report."""
    worker_id = os.environ.get(EnvVar.PYTEST_XDIST_WORKER, 'main')
    transaction_col = os.environ.get(EnvVar.REQUEST_GEN_TRANSACTION_COL, '')
    transaction_name = str(rg_test_case.get(transaction_col, ''))

    allure.dynamic.description(
        f"Transaction: {transaction_name}\n"
        f"Sheet: {rg_test_case.get('_sheet_name', '')}\n"
        f"Worker: {worker_id}"
    )
    allure.dynamic.parent_suite("Request Generator")
    allure.dynamic.suite(rg_test_case.get('_sheet_name', 'Sheet'))
    allure.dynamic.sub_suite("Environment Execution")

    try:
        _execute_on_environment(rg_test_case)
        print(f"Worker {worker_id}: Completed '{transaction_name}' - PASSED")
    except Exception as e:
        print(f"Worker {worker_id}: '{transaction_name}' FAILED: {e}")
        raise


# ---------------------------------------------------------------------------
# Core execution helper
# ---------------------------------------------------------------------------

def _execute_on_environment(test_case):
    """Send the row's payload to the configured URL and attach the response to Allure."""
    transaction_col = os.environ.get(EnvVar.REQUEST_GEN_TRANSACTION_COL, '')
    payload_col     = os.environ.get(EnvVar.REQUEST_GEN_PAYLOAD_COL, '')
    response_col    = os.environ.get(EnvVar.REQUEST_GEN_RESPONSE_COL, '')
    url             = os.environ.get(EnvVar.REQUEST_GEN_URL, '')

    transaction_name = str(test_case.get(transaction_col, ''))
    sheet_name       = test_case.get('_sheet_name', 'Unknown')

    allure.dynamic.tag(f"Transaction - {transaction_name}")
    allure.dynamic.tag(f"Sheet - {sheet_name}")

    payload = str(test_case.get(payload_col, '')).strip()

    if not payload:
        allure.attach(
            f"Row skipped — payload column '{payload_col}' is empty.",
            name="Skipped",
            attachment_type=allure.attachment_type.TEXT,
        )
        return

    try:
        soap_action = build_soap_action(transaction_name, payload)
        api_client = APIClient()
        result = api_client.send_request(
            url=url,
            xml_body=payload,
            soap_action=soap_action,
        )

        allure.attach(
            payload,
            name="Request Payload",
            attachment_type=allure.attachment_type.XML,
        )
        allure.attach(
            result['content'],
            name="Response",
            attachment_type=allure.attachment_type.XML,
        )
        allure.attach(
            f"Status: {result['status_code']}\n"
            f"Response time: {result['response_time']:.0f} ms\n"
            f"Timestamp: {result['timestamp']}\n"
            f"Response column: {response_col}",
            name="Request Summary",
            attachment_type=allure.attachment_type.TEXT,
        )

        if not result['success']:
            pytest.fail(
                f"Request returned non-200 status {result['status_code']} "
                f"for transaction '{transaction_name}'"
            )

    except Exception as e:
        worker_id = os.environ.get(EnvVar.PYTEST_XDIST_WORKER, 'main')
        print(f"Worker {worker_id}: Error executing '{transaction_name}': {e}")
        raise
