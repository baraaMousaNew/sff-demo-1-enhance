"""
E2E Flows Allure Wrapper - Executes end-to-end request chains from an Excel sheet
and reports each test case (group of steps) as a single Allure test.

Sheet structure:
  - TC_ID column identifies test cases.  A non-empty TC_ID starts a new test case;
    rows with an empty TC_ID are additional steps of the current test case.
  - Each step row may have a Main XML column, an optional Nested XML column, and an
    optional Extraction Rules column.

Environment variables read at runtime:
    E2E_EXCEL_FILE          Path to the Excel file
    E2E_SHEET               Sheet name to load
    E2E_URL                 Target endpoint URL
    E2E_MAIN_XML_COL        Column that holds the main SOAP/XML payload
    E2E_NESTED_XML_COL      Column that holds the inner XML to be encoded and substituted
                            in the main XML.  Use {{nested_xml}} for plain base64 encoding
                            or {{nested_xml_zip}} to zip (context.xml / ZIP_DEFLATED) then
                            base64-encode before substitution.
                            (leave empty or omit to disable)
    E2E_EXTRACT_RULES_COL   Column that holds extraction rules for the step response,
                            e.g.  claim_id=//ClaimID;status=Status
                            (leave empty or omit to disable)
    E2E_TRANSACTION_COL     Column that holds the transaction name used to resolve
                            the SOAPAction header (same lookup as Request Generator)
    E2E_ASSERT_COL          Column that holds assertion rules for the step response,
                            e.g.  Status==Active;ErrorCode==0;//ClaimID==12345
                            Format: selector==expected_value separated by semicolons.
                            Selector may be XPath (//...), regex (regex:...), EXTRACT.var,
                            or a plain element name.  Expected values support {{...}} variables.
                            (leave empty or omit to disable)
    E2E_ENV_LABEL           Human-readable label for the environment being tested
                            (e.g. "UAT", "Production").  Added as an Allure tag so
                            results from different environments are distinguishable
                            in the same report.  Set automatically by the GUI.
                            (leave empty or omit to skip the tag)
    E2E_TC_NAME_COL         Column that holds a human-readable test case name.
                            When set, the Allure report title uses this value instead
                            of TC_ID (falls back to TC_ID if the cell is empty).
                            (leave empty or omit to always use TC_ID)
    E2E_SPECIFIC_CASES      Comma-separated TC_ID values to run (omit to run all)
    E2E_SKIP_COL            Column that flags individual steps to skip.
                            A step is skipped when its cell is non-empty and not
                            one of: no, false, 0, n.  The step is recorded in
                            Allure as "Skipped" and execution continues normally.
                            (leave empty or omit to disable)
"""

import base64
import io
import os
import time
import zipfile

import allure
import pytest

from utils.api_client import APIClient
from utils.azure_reporting import E2E_ATTACHMENT_IDS
from utils.excel_handler import ExcelHandler
from utils.variable_processor import VariableProcessor
from utils.request_sender.soap_action_enums import build_soap_action
from utils.env_vars import EnvVar

TC_ID_COL = "TC_ID"
NESTED_XML_PLACEHOLDER     = "{{nested_xml}}"
NESTED_XML_ZIP_PLACEHOLDER = "{{nested_xml_zip}}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _b64_encode(xml_string: str) -> str:
    return base64.b64encode(xml_string.encode("utf-8")).decode("utf-8")


def _b64_zip_encode(xml_string: str) -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("context.xml", xml_string)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _get_worker_id() -> str:
    return os.environ.get(EnvVar.PYTEST_XDIST_WORKER, "main")


def _attach(name: str, content: str, attachment_type) -> None:
    allure.attach(content, name=name, attachment_type=attachment_type)


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class E2EFlowsExecutor:
    def __init__(self):
        self.excel_handler = ExcelHandler()
        self.api_client = APIClient()

    def load_test_cases(self, excel_file: str, sheet_name: str) -> list:
        """
        Load rows from the sheet and group them by TC_ID.
        Returns a list of dicts:
            {"tc_id": str, "steps": [row_dict, ...], "_sheet_name": str}
        """
        rows = self.excel_handler.load_excel(excel_file, sheet_name=sheet_name)
        groups = []
        current = None
        for row in rows:
            tc_id = str(row.get(TC_ID_COL, "") or "").strip()
            if tc_id:
                current = {"tc_id": tc_id, "steps": [row], "_sheet_name": sheet_name}
                groups.append(current)
            elif current is not None:
                current["steps"].append(row)
        return groups

    def build_payload(self, row: dict, processor: VariableProcessor) -> tuple:
        """
        Resolve variables in both nested and main XML for a single step row.
        Returns (final_main_xml, processed_nested_xml | None).

        If a nested XML column is configured and the cell has a value:
          1. Process {{...}} placeholders in nested XML.
          2. Base64-encode the result.
          3. Substitute {{nested_xml}} inside the main XML string.
        Then process {{...}} placeholders in the main XML.
        """
        main_col   = os.environ.get(EnvVar.E2E_MAIN_XML_COL, "").strip()
        nested_col = os.environ.get(EnvVar.E2E_NESTED_XML_COL, "").strip()

        main_xml       = str(row.get(main_col, "") or "").strip()
        processed_nested = None

        if nested_col:
            nested_xml = str(row.get(nested_col, "") or "").strip()
            if nested_xml:
                processed_nested = processor.process_variables(nested_xml, excel_row_data=row)
                if NESTED_XML_ZIP_PLACEHOLDER in main_xml:
                    encoded = _b64_zip_encode(processed_nested)
                    main_xml = main_xml.replace(NESTED_XML_ZIP_PLACEHOLDER, encoded)
                else:
                    encoded = _b64_encode(processed_nested)
                    main_xml = main_xml.replace(NESTED_XML_PLACEHOLDER, encoded)

        return processor.process_variables(main_xml, excel_row_data=row), processed_nested

    def run_assertions(
        self, response_content: str, row: dict, processor: VariableProcessor
    ) -> list:
        """
        Evaluate assertion rules for this step against the response.
        Returns the list of assertion result dicts (empty if no column configured).
        """
        assert_col = os.environ.get(EnvVar.E2E_ASSERT_COL, "").strip()
        if not assert_col:
            return []
        rules = str(row.get(assert_col, "") or "").strip()
        if not rules:
            return []
        return processor.evaluate_assertions(response_content, rules)

    def extract_from_response(
        self, response_content: str, row: dict, processor: VariableProcessor
    ) -> dict:
        """
        Apply the step's extraction rules to the response and store results in
        the processor so subsequent steps can use {{EXTRACT.var_name}}.
        """
        extract_col = os.environ.get(EnvVar.E2E_EXTRACT_RULES_COL, "").strip()
        if not extract_col:
            return {}
        rules = str(row.get(extract_col, "") or "").strip()
        if not rules:
            return {}
        return processor.extract_values_from_response(response_content, rules)


# ---------------------------------------------------------------------------
# Pytest parametrization hook
# ---------------------------------------------------------------------------

def pytest_generate_tests(metafunc):
    if "e2e_test_case" not in metafunc.fixturenames:
        return

    excel_file  = os.environ.get(EnvVar.E2E_EXCEL_FILE)
    sheet_name  = os.environ.get(EnvVar.E2E_SHEET)

    if not excel_file or not sheet_name:
        pytest.skip("E2E_EXCEL_FILE or E2E_SHEET not set")
        return

    test_cases = E2EFlowsExecutor().load_test_cases(excel_file, sheet_name)

    specific = os.environ.get(EnvVar.E2E_SPECIFIC_CASES, "").strip()
    if specific:
        allowed = {tc_id.strip() for tc_id in specific.split(",")}
        test_cases = [tc for tc in test_cases if tc["tc_id"] in allowed]

    if not test_cases:
        pytest.skip("No test cases found in the selected sheet")
        return

    ids = [tc["tc_id"] for tc in test_cases]
    metafunc.parametrize("e2e_test_case", test_cases, ids=ids)


# ---------------------------------------------------------------------------
# Test function
# ---------------------------------------------------------------------------

@allure.feature("E2E Flows")
@allure.story("End-to-End Chain Execution")
def test_e2e_flow(e2e_test_case):
    """Execute all steps of an E2E test case and report each step to Allure."""
    worker_id  = _get_worker_id()
    tc_id      = e2e_test_case["tc_id"]
    sheet_name = e2e_test_case["_sheet_name"]
    steps      = e2e_test_case["steps"]

    tc_name_col = os.environ.get(EnvVar.E2E_TC_NAME_COL, "").strip()
    tc_title = tc_id
    if tc_name_col and steps:
        name_from_col = str(steps[0].get(tc_name_col, "") or "").strip()
        if name_from_col:
            tc_title = name_from_col

    env_label = os.environ.get(EnvVar.E2E_ENV_LABEL, "").strip()

    allure.dynamic.parent_suite("E2E Flows")
    allure.dynamic.suite(sheet_name)
    allure.dynamic.sub_suite(f"Chain Execution [{env_label}]" if env_label else "Chain Execution")
    allure.dynamic.title(tc_title)
    allure.dynamic.tag(f"TC - {tc_id}")
    allure.dynamic.tag(f"Sheet - {sheet_name}")
    if env_label:
        allure.dynamic.tag(f"Env - {env_label}")
    allure.dynamic.description(
        f"Test Case: {tc_id}\n"
        f"Sheet: {sheet_name}\n"
        f"Steps: {len(steps)}\n"
        f"Worker: {worker_id}"
    )

    print(f"Worker {worker_id}: Starting E2E test case '{tc_id}' ({len(steps)} step(s))")

    executor    = E2EFlowsExecutor()
    processor   = VariableProcessor()  # shared across all steps of this test case
    failure_exc = None

    try:
        step_pause = max(0.0, float(os.environ.get(EnvVar.E2E_STEP_PAUSE, "0") or "0"))
    except ValueError:
        step_pause = 0.0

    transaction_col = os.environ.get(EnvVar.E2E_TRANSACTION_COL, "").strip()
    for step_index, row in enumerate(steps, start=1):
        if step_index > 1 and step_pause > 0:
            time.sleep(step_pause)
        transaction_name = str(row.get(transaction_col, "") or "").strip() if transaction_col else ""
        step_label = transaction_name if transaction_name else f"Step {step_index} of {len(steps)}"
        try:
            with allure.step(step_label):
                _execute_step(executor, processor, row, step_index, step_label, tc_id, worker_id)
        except Exception as exc:
            failure_exc = exc
            break

    if failure_exc is not None:
        raise failure_exc

    print(f"Worker {worker_id}: Completed E2E test case '{tc_id}' - PASSED")


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------

def _execute_step(
    executor:   E2EFlowsExecutor,
    processor:  VariableProcessor,
    row:        dict,
    step_index: int,
    step_label: str,
    tc_id:      str,
    worker_id:  str,
):
    skip_col = os.environ.get(EnvVar.E2E_SKIP_COL, "").strip()
    if skip_col:
        skip_val = str(row.get(skip_col, "") or "").strip().lower()
        if skip_val and skip_val not in ("no", "false", "0", "n"):
            allure.attach(
                f"Step {step_index} skipped — {skip_col} = '{skip_val}'.",
                name="Skipped",
                attachment_type=allure.attachment_type.TEXT,
            )
            return

    url = os.environ.get(EnvVar.E2E_URL, "").strip()
    if not url:
        pytest.fail("E2E_URL environment variable is not set")

    transaction_col  = os.environ.get(EnvVar.E2E_TRANSACTION_COL, "").strip()
    transaction_name = str(row.get(transaction_col, "") or "").strip() if transaction_col else ""

    payload, processed_nested = executor.build_payload(row, processor)

    if processed_nested:
        main_col = os.environ.get(EnvVar.E2E_MAIN_XML_COL, "").strip()
        raw_main = str(row.get(main_col, "") or "")
        encode_fn = _b64_zip_encode if NESTED_XML_ZIP_PLACEHOLDER in raw_main else _b64_encode
        processor.declared_variables[f"nested_xml_{step_index}"] = encode_fn(processed_nested)

    if not payload:
        allure.attach(
            f"Step {step_index} skipped — Main XML column is empty.",
            name="Skipped",
            attachment_type=allure.attachment_type.TEXT,
        )
        return

    soap_action = build_soap_action(transaction_name, payload) if transaction_name else None

    if transaction_name:
        allure.dynamic.tag(f"Transaction - {transaction_name}")
        _attach(
            f"{E2E_ATTACHMENT_IDS['soap_action']} - [{step_label}] SOAPAction",
            soap_action or "(not resolved — transaction name not in mapping)",
            allure.attachment_type.TEXT,
        )

    try:
        result = executor.api_client.send_request(
            url=url, xml_body=payload, soap_action=soap_action,
        )

        if processed_nested:
            _attach(
                f"{E2E_ATTACHMENT_IDS['nested_xml']} - [{step_label}] Nested XML (processed)",
                processed_nested,
                allure.attachment_type.XML,
            )
        _attach(f"{E2E_ATTACHMENT_IDS['request']} - [{step_label}] Request",   payload,           allure.attachment_type.XML)
        _attach(f"{E2E_ATTACHMENT_IDS['response']} - [{step_label}] Response", result["content"], allure.attachment_type.XML)
        _attach(
            f"{E2E_ATTACHMENT_IDS['summary']} - [{step_label}] Summary",
            f"HTTP {result['status_code']}  |  {result['response_time']:.0f} ms  |  {result['timestamp']}",
            allure.attachment_type.TEXT,
        )

        extracted = executor.extract_from_response(result["content"], row, processor)
        if extracted:
            _attach(
                f"{E2E_ATTACHMENT_IDS['extracted_variables']} - [{step_label}] Extracted Variables",
                "\n".join(f"{k} = {v}" for k, v in extracted.items()),
                allure.attachment_type.TEXT,
            )

        assertions = executor.run_assertions(result["content"], row, processor)
        if assertions:
            assertion_lines = []
            for a in assertions:
                status = "PASS" if a["passed"] else "FAIL"
                line   = f"{status}  {a['selector']} == {a['expected']}"
                if not a["passed"]:
                    line += f"  (actual: {a['actual']})"
                assertion_lines.append(line)
            _attach(
                f"{E2E_ATTACHMENT_IDS['assertions']} - [{step_label}] Assertions",
                "\n".join(assertion_lines),
                allure.attachment_type.TEXT,
            )
            failures = [a for a in assertions if not a["passed"]]
            if failures:
                failure_detail = "\n".join(
                    f"  {a['selector']}: expected '{a['expected']}', got '{a['actual']}'"
                    for a in failures
                )
                pytest.fail(f"[{tc_id}] {step_label} assertion(s) failed:\n{failure_detail}")

        if not result["success"]:
            pytest.fail(f"[{tc_id}] {step_label} returned HTTP {result['status_code']}")

    except Exception as exc:
        print(f"Worker {worker_id}: [{tc_id}] {step_label} FAILED: {exc}")
        raise
