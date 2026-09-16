"""
Azure DevOps Reporting Utility
Scans allure-results for System 2 failures and reports them as bugs in Azure DevOps.
"""

import ast
import json
import base64
import requests
import os
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────
# Attachment IDs (partial name match used in allure result JSON)
# ──────────────────────────────────────────────────────────────────────────────
ATTACHMENT_IDS = {
    "request":          "98efcb",   # Request XML
    "old_response":     "33a829",   # Old system response
    "new_response":     "a4b5d4",   # New system response
    "assert_7efb21":    "7efb21",   # Assert attachment variant A
    "assert_35b0bf":    "35b0bf",   # Assert attachment variant B
    "assert_392130":    "392130",   # Assert attachment variant C (error text diff)
    "assert_3b4195":    "3b4195",   # Error text match across occurrences (asserter.py)
    "assert_76b634":    "76b634",   # Assert attachment variant D
    "assert_bedd20":    "bedd20",   # Assert attachment variant E
    "assert_bb87e7":    "bb87e7",   # Assert attachment variant F
    "assert_731468":    "731468",   # Assert attachment variant G
    "assert_ad668e":    "ad668e",   # Assert attachment variant H (no error report)
    "assert_979b2c":    "979b2c",   # Assert attachment variant I (response codes diff)
    "assert_d8b2e5":    "d8b2e5",   # Check error message (asserter.py)
    "assert_f3a1c9":    "f3a1c9",   # Check error code (asserter.py)
    "assert_a3f8b1":    "a3f8b1",   # Check error report (asserter.py)
    "assert_b5c3e7":    "b5c3e7",   # Response vs XML template (asserter.py)
    "assert_c4e2f1":    "c4e2f1",   # Assert no errors (custom_assert)
    "assert_c4f21a":    "c4f21a",   # Compare responses error fields (dual system)
    "assert_e8f3d2":    "e8f3d2",   # Dual system row comparison failure (XMLDualSingleRowAsserter)
    "assert_5e2a1f":    "5e2a1f",   # Rule presence check — no error report (presence comparison mode)
    "assert_9c4d83":    "9c4d83",   # Rule presence check — result per system (presence comparison mode)
    "assert_b7f041":    "b7f041",   # Rule presence matches between systems (presence comparison mode)
    "assert_3a8e6c":    "3a8e6c",   # Rule presence mismatch between systems (presence comparison mode)
    "assert_6f2c9a":    "6f2c9a",   # Occurrence count mismatch (asserter.py)
    "assert_1d7e4b":    "1d7e4b",   # Occurrence count matches (asserter.py)
    "assert_b3d91c":    "b3d91c",   # Object/Element mismatch across occurrences (asserter.py)
    "assert_a1c7d4":    "a1c7d4",   # Object/Element match across occurrences (asserter.py)
    "assert_c7e592":    "c7e592",   # Field/Additional mismatch across occurrences (asserter.py)
    "assert_6a3fd8":    "6a3fd8",   # Field/Additional match across occurrences (asserter.py)
}

# Attachment IDs for assertion testing (custom_requests_asserter.py)
ASSERTION_ATTACHMENT_IDS = {
    "request":          "98efcb",   # Request XML
    "old_response":     "33a829",   # Old system response
    "new_response":     "a4b5d4",   # New system response
    "assert_2ffe8e":    "2ffe8e",   # Check against transaction (not found)
    "assert_2ffvce":    "2ffvce",   # Unexpected transaction found (not_found)
    "assert_8b450b":    "8b450b",   # Check against transaction (found)
    "assert_d43b5a":    "d43b5a",   # Transaction FileID was found
    "assert_d56775a":   "d56775a",  # File name mismatch (found)
    "assert_d43we5a":   "d43we5a",  # File name mismatch (found_downloaded)
    "assert_d4ty5a":    "d4ty5a",   # Sender ID mismatch
    "assert_d4ml5a":    "d4ml5a",   # Receiver ID mismatch
    "assert_d4005a":    "d4005a",   # Record count mismatch
    "assert_d4ioo5a":   "d4ioo5a",  # Transaction date mismatch
    "assert_d4er05a":   "d4er05a",  # Transaction timestamp mismatch
    "assert_d4tto5a":   "d4tto5a",  # Is downloaded flag mismatch
    "assert_568d49":    "568d49",   # Check error message
    "assert_c67011":    "c67011",   # Compare template and downloaded file
    "assert_c67045":    "c67045",   # Check set downloaded code and error message
    "assert_c67048":    "c67048",   # Check error code
    "assert_c63496":    "c63496",   # Reconciliation check
    "assert_e4c52a":    "e4c52a",   # Element value verification
    "assert_f41a3b":    "f41a3b",   # File found check
    "assert_f17d8e":    "f17d8e",   # File not found check
    "assert_crrre96":   "crrre96",  # Check reconciliation code and error message
    "assert_d4w4nb5a":  "d4w4nb5a", # Transaction date match
    "assert_d4ezz5a":   "d4ezz5a",  # Transaction timestamp match
    "assert_d4jjj5a":   "d4jjj5a",  # Is downloaded flag match
    "assert_c6ggfr6":   "c6ggfr6",  # Download count not numeric
}

# Attachment IDs for E2E flows (e2e_flows_allure_wrapper.py)
E2E_ATTACHMENT_IDS = {
    "soap_action":         "e2ea01",
    "nested_xml":          "e2ea02",
    "request":             "e2ea03",
    "response":            "e2ea04",
    "summary":             "e2ea05",
    "extracted_variables": "e2ea06",
    "assertions":          "e2ea07",
}

# Tags that qualify a test case for ADO reporting (both_systems mode)
TARGET_TAGS = {"system 2 failure", "system 2 error text failure", "system 2 object/element failure", "system 2 field/additional failure", "dual system failure", "dual system error text failure", "dual system row failure"}

# Ordered display-name → allure tag value mapping (used by the UI) — both_systems mode
AVAILABLE_REPORT_TAGS = {
    "System 2 Failure":                    "system 2 failure",
    "System 2 Error Text Failure":         "system 2 error text failure",
    "System 2 Object/Element Failure":     "system 2 object/element failure",
    "System 2 Field/Additional Failure":   "system 2 field/additional failure",
    "Dual System Failure":                 "dual system failure",
    "Dual System Error Text Failure":      "dual system error text failure",
    "Dual System Row Failure":             "dual system row failure",
}

# Tags that qualify a test case for ADO reporting (system2_only mode)
SYSTEM1_TARGET_TAGS = {"system 1 failure", "system 1 error text failure", "system 1 object/element failure", "system 1 field/additional failure"}

# Ordered display-name → allure tag value mapping (used by the UI) — system2_only mode
SYSTEM1_AVAILABLE_REPORT_TAGS = {
    "System 1 Failure":                    "system 1 failure",
    "System 1 Error Text Failure":         "system 1 error text failure",
    "System 1 Object/Element Failure":     "system 1 object/element failure",
    "System 1 Field/Additional Failure":   "system 1 field/additional failure",
}


# ──────────────────────────────────────────────────────────────────────────────
# Allure scanning
# ──────────────────────────────────────────────────────────────────────────────

def _find_attachments_recursive(steps, target_id):
    """Recursively search steps for attachments whose name contains target_id."""
    found = []
    for step in steps:
        for att in step.get("attachments", []):
            if target_id in att.get("name", ""):
                found.append(att.get("source"))
        found.extend(_find_attachments_recursive(step.get("steps", []), target_id))
    return found


def _collect_attachment_sources(data, target_id):
    """Collect all attachment sources (step-level + top-level) for a given id."""
    sources = _find_attachments_recursive(data.get("steps", []), target_id)
    for att in data.get("attachments", []):
        if target_id in att.get("name", ""):
            sources.append(att.get("source"))
    return sources


_SEND_ATT_IDS = [
    ("Request URL and action", "Request URL and Action"),
    ("98efcb",                 "Request"),
    ("33a829",                 "Old Response"),
    ("a4b5d4",                 "New Response"),
]


def _collect_send_grouped(data, allure_results_dir):
    """
    Walk the step tree and return all send attachments grouped per step,
    in the order they appear: URL & action, request, response.
    """
    parts = []

    def _process_steps(steps):
        for step in steps:
            group = []
            for att_id, label in _SEND_ATT_IDS:
                for att in step.get("attachments", []):
                    if att_id in att.get("name", ""):
                        content = _read_attachment(allure_results_dir, att.get("source", ""))
                        if content:
                            group.append(f"--- {label} ---\n{content}")
                        break
            if group:
                step_name = step.get("name", "")
                header = f"{'='*60}\n{step_name}\n{'='*60}" if step_name else "=" * 60
                parts.append(header + "\n" + "\n\n".join(group))
            _process_steps(step.get("steps", []))

    _process_steps(data.get("steps", []))
    return "\n\n".join(parts)


def _read_attachment(allure_dir, source):
    """Read the content of an allure attachment file."""
    if not source:
        return ""
    try:
        path = Path(allure_dir) / source
        if path.exists():
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
    except Exception:
        pass
    return ""


def _get_error_text(data):
    """Extract the 'Error Text' column value from allure result parameters."""
    params = data.get("parameters", [])
    if not params:
        return ""
    try:
        tc = ast.literal_eval(params[0].get("value", "{}"))
        return tc.get("Error Text", "")
    except Exception:
        return ""


def scan_failures_by_tag(allure_results_dir, tag_key, report_tags=None):
    """
    Scan allure-results and return failures that have the given tag_key.
    tag_key must be one of the keys in report_tags (defaults to AVAILABLE_REPORT_TAGS).
    Each returned dict contains: test_case_name, rule_id, failure_tags, attachments.
    """
    if report_tags is None:
        report_tags = AVAILABLE_REPORT_TAGS
    target_tag = report_tags.get(tag_key, "").lower()
    if not target_tag:
        return []

    failures = []
    allure_dir = Path(allure_results_dir)

    for file in allure_dir.glob("*-result.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        if data.get("status") != "failed":
            continue

        tags = [
            lbl.get("value", "")
            for lbl in data.get("labels", [])
            if lbl.get("name") == "tag" and lbl.get("value")
        ]
        tags_lower = {t.lower() for t in tags}

        if target_tag not in tags_lower:
            continue

        rule_id_tag = next((t for t in tags if t.startswith("RuleID - ")), None)
        rule_id = rule_id_tag[len("RuleID - "):].strip() if rule_id_tag else "Unknown"
        test_case_name = data.get("name", "Unknown")

        def _get(att_id):
            sources = _collect_attachment_sources(data, att_id)
            return _read_attachment(allure_results_dir, sources[-1]) if sources else ""

        assert_7efb21_content = _get(ATTACHMENT_IDS["assert_7efb21"])
        assert_35b0bf_content = _get(ATTACHMENT_IDS["assert_35b0bf"])
        assert_392130_content = _get(ATTACHMENT_IDS["assert_392130"])
        assert_3b4195_content = _get(ATTACHMENT_IDS["assert_3b4195"])
        assert_76b634_content = _get(ATTACHMENT_IDS["assert_76b634"])
        assert_bedd20_content = _get(ATTACHMENT_IDS["assert_bedd20"])
        assert_bb87e7_content = _get(ATTACHMENT_IDS["assert_bb87e7"])
        assert_731468_content = _get(ATTACHMENT_IDS["assert_731468"])
        assert_ad668e_content = _get(ATTACHMENT_IDS["assert_ad668e"])
        assert_979b2c_content = _get(ATTACHMENT_IDS["assert_979b2c"])
        assert_d8b2e5_content = _get(ATTACHMENT_IDS["assert_d8b2e5"])
        assert_f3a1c9_content = _get(ATTACHMENT_IDS["assert_f3a1c9"])
        assert_a3f8b1_content = _get(ATTACHMENT_IDS["assert_a3f8b1"])
        assert_b5c3e7_content = _get(ATTACHMENT_IDS["assert_b5c3e7"])
        assert_c4e2f1_content = _get(ATTACHMENT_IDS["assert_c4e2f1"])
        assert_c4f21a_content = _get(ATTACHMENT_IDS["assert_c4f21a"])
        assert_e8f3d2_content = _get(ATTACHMENT_IDS["assert_e8f3d2"])
        assert_5e2a1f_content = _get(ATTACHMENT_IDS["assert_5e2a1f"])
        assert_9c4d83_content = _get(ATTACHMENT_IDS["assert_9c4d83"])
        assert_b7f041_content = _get(ATTACHMENT_IDS["assert_b7f041"])
        assert_3a8e6c_content = _get(ATTACHMENT_IDS["assert_3a8e6c"])
        assert_6f2c9a_content = _get(ATTACHMENT_IDS["assert_6f2c9a"])
        assert_1d7e4b_content = _get(ATTACHMENT_IDS["assert_1d7e4b"])
        assert_b3d91c_content = _get(ATTACHMENT_IDS["assert_b3d91c"])
        assert_a1c7d4_content = _get(ATTACHMENT_IDS["assert_a1c7d4"])
        assert_c7e592_content = _get(ATTACHMENT_IDS["assert_c7e592"])
        assert_6a3fd8_content = _get(ATTACHMENT_IDS["assert_6a3fd8"])

        failures.append({
            "test_case_name": test_case_name,
            "rule_id":        rule_id,
            "failure_tags":   [tag_key],
            "all_tags":       list(set(tags)),
            "error_text":     _get_error_text(data),
            "attachments": {
                "send":          _collect_send_grouped(data, allure_results_dir),
                "request":       _get(ATTACHMENT_IDS["request"]),
                "old_response":  _get(ATTACHMENT_IDS["old_response"]),
                "new_response":  _get(ATTACHMENT_IDS["new_response"]),
                "assert_7efb21": assert_7efb21_content,
                "assert_35b0bf": assert_35b0bf_content,
                "assert_392130": assert_392130_content,
                "assert_3b4195": assert_3b4195_content,
                "assert_76b634": assert_76b634_content,
                "assert_bedd20": assert_bedd20_content,
                "assert_bb87e7": assert_bb87e7_content,
                "assert_731468": assert_731468_content,
                "assert_ad668e": assert_ad668e_content,
                "assert_979b2c": assert_979b2c_content,
                "assert_d8b2e5": assert_d8b2e5_content,
                "assert_f3a1c9": assert_f3a1c9_content,
                "assert_a3f8b1": assert_a3f8b1_content,
                "assert_b5c3e7": assert_b5c3e7_content,
                "assert_c4e2f1": assert_c4e2f1_content,
                "assert_c4f21a": assert_c4f21a_content,
                "assert_e8f3d2": assert_e8f3d2_content,
                "assert_5e2a1f": assert_5e2a1f_content,
                "assert_9c4d83": assert_9c4d83_content,
                "assert_b7f041": assert_b7f041_content,
                "assert_3a8e6c": assert_3a8e6c_content,
                "assert_6f2c9a": assert_6f2c9a_content,
                "assert_1d7e4b": assert_1d7e4b_content,
                "assert_b3d91c": assert_b3d91c_content,
                "assert_a1c7d4": assert_a1c7d4_content,
                "assert_c7e592": assert_c7e592_content,
                "assert_6a3fd8": assert_6a3fd8_content,
            },
        })

    return failures


def scan_assertion_failures_by_tag(allure_results_dir, tag_key, report_tags=None):
    """
    Scan allure-results for assertion testing failures (custom_requests_asserter.py).
    Uses ASSERTION_ATTACHMENT_IDS instead of ATTACHMENT_IDS.
    """
    if report_tags is None:
        report_tags = SYSTEM1_AVAILABLE_REPORT_TAGS
    target_tag = report_tags.get(tag_key, "").lower()
    if not target_tag:
        return []

    failures = []
    allure_dir = Path(allure_results_dir)

    for file in allure_dir.glob("*-result.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        if data.get("status") != "failed":
            continue

        tags = [
            lbl.get("value", "")
            for lbl in data.get("labels", [])
            if lbl.get("name") == "tag" and lbl.get("value")
        ]
        tags_lower = {t.lower() for t in tags}

        if target_tag not in tags_lower:
            continue

        rule_id_tag = next((t for t in tags if t.startswith("RuleID - ")), None)
        rule_id = rule_id_tag[len("RuleID - "):].strip() if rule_id_tag else "Unknown"
        test_case_name = data.get("name", "Unknown")

        def _get_all(att_id):
            sources = _collect_attachment_sources(data, att_id)
            return "\n\n".join(
                filter(None, (_read_attachment(allure_results_dir, s) for s in sources))
            )

        failures.append({
            "test_case_name": test_case_name,
            "rule_id":        rule_id,
            "failure_tags":   [tag_key],
            "all_tags":       [t for t in set(tags) if not t.lower().startswith("precondition -")],
            "error_text":     _get_error_text(data),
            "attachments": {
                "send":          _collect_send_grouped(data, allure_results_dir),
                "assert_2ffe8e":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_2ffe8e"]),
                "assert_2ffvce":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_2ffvce"]),
                "assert_8b450b":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_8b450b"]),
                "assert_d43b5a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_d43b5a"]),
                "assert_d56775a": _get_all(ASSERTION_ATTACHMENT_IDS["assert_d56775a"]),
                "assert_d43we5a": _get_all(ASSERTION_ATTACHMENT_IDS["assert_d43we5a"]),
                "assert_d4ty5a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4ty5a"]),
                "assert_d4ml5a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4ml5a"]),
                "assert_d4005a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4005a"]),
                "assert_d4ioo5a": _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4ioo5a"]),
                "assert_d4er05a": _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4er05a"]),
                "assert_d4tto5a": _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4tto5a"]),
                "assert_568d49":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_568d49"]),
                "assert_c67011":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_c67011"]),
                "assert_c67045":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_c67045"]),
                "assert_c67048":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_c67048"]),
                "assert_c63496":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_c63496"]),
                "assert_e4c52a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_e4c52a"]),
                "assert_f41a3b":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_f41a3b"]),
                "assert_f17d8e":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_f17d8e"]),
                "assert_crrre96":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_crrre96"]),
                "assert_d4w4nb5a": _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4w4nb5a"]),
                "assert_d4ezz5a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4ezz5a"]),
                "assert_d4jjj5a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4jjj5a"]),
                "assert_c6ggfr6":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_c6ggfr6"]),
            },
        })

    return failures


# ──────────────────────────────────────────────────────────────────────────────
# Bug HTML description builder
# ──────────────────────────────────────────────────────────────────────────────

def _escape_html(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_bug_description(failure):
    """Build an HTML description for the ADO bug from a failure dict."""
    tc     = _escape_html(failure["test_case_name"])
    rid    = _escape_html(failure["rule_id"])
    ftags  = ", ".join(_escape_html(t) for t in failure["failure_tags"])
    atts   = failure["attachments"]
    inc    = failure.get("include_attachments", {})
    include_assertions = inc.get("include_assertions", True)

    def _section(title, content, key_name=None):
        if not content:
            return ""
        if key_name and not inc.get(key_name, True):
            return ""
        escaped = _escape_html(content)
        return (
            f"<h3>{title}</h3>"
            f'<pre style="background:#f5f5f5;padding:8px;font-size:12px;'
            f'white-space:pre-wrap;word-break:break-all;">{escaped}</pre>'
        )

    _ASSERTION_SECTIONS = [
        # Batch testing assertions (asserter.py)
        ("\u26a0\ufe0f Assertion Details (A)",   "assert_7efb21"),
        ("\u26a0\ufe0f Assertion Details (B)",   "assert_35b0bf"),
        ("\u26a0\ufe0f Error Text Diff (C)",     "assert_392130"),
        ("\u26a0\ufe0f Error Text Match",         "assert_3b4195"),
        ("\u26a0\ufe0f Assertion Details (D)",   "assert_76b634"),
        ("\u26a0\ufe0f Assertion Details (E)",   "assert_bedd20"),
        ("\u26a0\ufe0f Assertion Details (F)",   "assert_bb87e7"),
        ("\u26a0\ufe0f Assertion Details (G)",   "assert_731468"),
        ("\u26a0\ufe0f No Error Report (H)",     "assert_ad668e"),
        ("\u26a0\ufe0f Response Codes Diff (I)", "assert_979b2c"),
        ("\u26a0\ufe0f Check Error Message",     "assert_d8b2e5"),
        ("\u26a0\ufe0f Check Error Code",        "assert_f3a1c9"),
        ("\u26a0\ufe0f Check Error Report",      "assert_a3f8b1"),
        ("\u26a0\ufe0f Response vs XML Template", "assert_b5c3e7"),
        ("\u26a0\ufe0f Assert No Errors",         "assert_c4e2f1"),
        ("\u26a0\ufe0f Error Fields Diff",         "assert_c4f21a"),
        ("\u26a0\ufe0f Row Comparison (Dual System)", "assert_e8f3d2"),
        ("\u26a0\ufe0f Rule Presence Mismatch (Dual System)", "assert_3a8e6c"),
        ("\u26a0\ufe0f Occurrence Count Mismatch",     "assert_6f2c9a"),
        ("\u26a0\ufe0f Occurrence Count Matches",       "assert_1d7e4b"),
        ("\u26a0\ufe0f Object/Element Mismatch (Occurrences)", "assert_b3d91c"),
        ("\u26a0\ufe0f Object/Element Match (Occurrences)",    "assert_a1c7d4"),
        ("\u26a0\ufe0f Field/Additional Mismatch (Occurrences)", "assert_c7e592"),
        ("\u26a0\ufe0f Field/Additional Match (Occurrences)",    "assert_6a3fd8"),
        # Assertion testing assertions (custom_requests_asserter.py)
        ("\u26a0\ufe0f Check Against Transaction (Not Found)", "assert_2ffe8e"),
        ("\u26a0\ufe0f Unexpected Transaction Found",          "assert_2ffvce"),
        ("\u26a0\ufe0f Check Against Transaction (Found)",     "assert_8b450b"),
        ("\u26a0\ufe0f Transaction FileID Found",              "assert_d43b5a"),
        ("\u26a0\ufe0f File Name Mismatch (found)",            "assert_d56775a"),
        ("\u26a0\ufe0f File Name Mismatch (found_downloaded)", "assert_d43we5a"),
        ("\u26a0\ufe0f Sender ID Mismatch",                    "assert_d4ty5a"),
        ("\u26a0\ufe0f Receiver ID Mismatch",                  "assert_d4ml5a"),
        ("\u26a0\ufe0f Record Count Mismatch",                 "assert_d4005a"),
        ("\u26a0\ufe0f Transaction Date Mismatch",             "assert_d4ioo5a"),
        ("\u26a0\ufe0f Transaction Timestamp Mismatch",        "assert_d4er05a"),
        ("\u26a0\ufe0f Is Downloaded Flag Mismatch",           "assert_d4tto5a"),
        ("\u26a0\ufe0f Check Error Message",                   "assert_568d49"),
        ("\u26a0\ufe0f Compare Template & Downloaded File",    "assert_c67011"),
        ("\u26a0\ufe0f Check Set Downloaded",                  "assert_c67045"),
        ("\u26a0\ufe0f Check Error Code",                      "assert_c67048"),
        ("\u26a0\ufe0f Reconciliation Check",                  "assert_c63496"),
        ("\u26a0\ufe0f Element Value Verification",            "assert_e4c52a"),
        ("\u26a0\ufe0f File Found Check",                      "assert_f41a3b"),
        ("\u26a0\ufe0f File Not Found Check",                  "assert_f17d8e"),
        ("\u26a0\ufe0f Check Reconciliation Code & Error Message", "assert_crrre96"),
        ("\u26a0\ufe0f Transaction Date Match",                    "assert_d4w4nb5a"),
        ("\u26a0\ufe0f Transaction Timestamp Match",               "assert_d4ezz5a"),
        ("\u26a0\ufe0f Is Downloaded Flag Match",                  "assert_d4jjj5a"),
        ("\u26a0\ufe0f Download Count Not Numeric",                "assert_c6ggfr6"),
    ]

    error_text = failure.get("error_text", "")

    html = (
        f"<h2>Bug Report: {tc}</h2>"
        f"<p><strong>Rule ID:</strong> {rid}</p>"
        f"<p><strong>Failure Type(s):</strong> {ftags}</p>"
        + (f"<p><strong>Expected Error Text:</strong> {_escape_html(error_text)}</p>" if error_text else "")
        + f"<hr/>"
    )

    if atts.get("send"):
        html += _section("\U0001f4e4 Send Requests", atts.get("send"), "send")
    else:
        html += _section("\U0001f4e4 Request",      atts.get("request"),      "request")
        html += _section("\U0001f4e4 Old Response", atts.get("old_response"), "old_response")
        html += _section("\U0001f4e4 New Response", atts.get("new_response"), "new_response")

    if include_assertions:
        for title, key in _ASSERTION_SECTIONS:
            html += _section(title, atts.get(key))

    return html


# ──────────────────────────────────────────────────────────────────────────────
# Azure DevOps API helpers
# ──────────────────────────────────────────────────────────────────────────────

def _ado_headers(pat):
    token = base64.b64encode(f":{pat}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
    }


def test_ado_connection(url, pat):
    """
    Test connection to ADO and return a list of projects.
    Expected URL: e.g., https://dev.azure.com/Organization or http://server:8080/tfs/DefaultCollection
    """
    base_url = url.rstrip('/')
    api_url = f"{base_url}/_apis/projects?api-version=7.1"
    
    headers = _ado_headers(pat)
    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        # fallback to older api-version if 7.1 fails on older servers
        if resp.status_code == 400:
            api_url = f"{base_url}/_apis/projects?api-version=6.0"
            resp = requests.get(api_url, headers=headers, timeout=10)
            
        if resp.status_code == 200:
            data = resp.json()
            projects = [p.get("name") for p in data.get("value", [])]
            return True, "Connected successfully.", projects
        else:
            try:
                msg = resp.json().get("message", resp.text)
            except:
                msg = resp.text
            return False, f"HTTP {resp.status_code}: {msg}", []
    except Exception as e:
        return False, f"Connection error: {str(e)}", []


def get_pbi_details(url, project, pbi_id, pat):
    """
    Fetch PBI details to confirm it exists and return its title.
    """
    base_url = url.rstrip('/')
    api_url = f"{base_url}/{project}/_apis/wit/workitems/{pbi_id}?api-version=7.1"
    
    headers = _ado_headers(pat)
    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        if resp.status_code == 400:
            api_url = f"{base_url}/{project}/_apis/wit/workitems/{pbi_id}?api-version=6.0"
            resp = requests.get(api_url, headers=headers, timeout=10)
            
        if resp.status_code == 200:
            data = resp.json()
            fields = data.get("fields", {})
            title = fields.get("System.Title", "Unknown Title")
            work_item_type = fields.get("System.WorkItemType", "Work Item")
            return True, f"[{work_item_type} {pbi_id}] {title}"
        else:
            try:
                msg = resp.json().get("message", resp.text)
            except:
                msg = resp.text
            return False, f"Could not find PBI. HTTP {resp.status_code}: {msg}"
    except Exception as e:
        return False, f"Error finding PBI: {str(e)}"


def get_current_user_descriptor(url, pat):
    """
    Resolve the identity of the user so we can assign bugs to ourselves.
    Uses the Azure DevOps profile endpoint.
    Returns a dict with 'id' and 'displayName', or None on failure.
    """
    try:
        headers = _ado_headers(pat)
        api_url = f"{url.rstrip('/')}/_apis/connectionData"
        resp = requests.get(api_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            auth_user = data.get("authenticatedUser", {})
            return {
                "id": auth_user.get("id"),
                "displayName": auth_user.get("providerDisplayName", ""),
                "uniqueName": auth_user.get("subjectDescriptor", ""),
            }
    except Exception:
        pass
    return None


def create_ado_bug(url, project, pat, pbi_id, failure):
    """
    Create a Bug work item in Azure DevOps and link it as 'Related' to the given PBI.
    Returns (success: bool, message: str, work_item_id: int|None)
    """
    base_url = url.rstrip('/')
    # To create a bug, we POST a JSON Patch
    api_url = f"{base_url}/{project}/_apis/wit/workitems/$Bug?api-version=7.1"
    
    headers = _ado_headers(pat)
    headers["Content-Type"] = "application/json-patch+json"
    
    title       = failure["test_case_name"]
    description = failure.get("description_html") or build_bug_description(failure)

    patch_document = [
        {
            "op": "add",
            "path": "/fields/System.Title",
            "value": title,
        },
        {
            "op": "add",
            "path": "/fields/System.Description",
            "value": description,
        },
        {
            "op": "add",
            "path": "/fields/Microsoft.VSTS.TCM.ReproSteps",
            "value": description,
        },
    ]

    # Add custom tags and all test case tags
    custom_tags = failure.get("custom_tags", [])
    all_tags = failure.get("all_tags", [])
    
    # Combine tags and eliminate duplicates
    combined_tags = []
    for tag in all_tags + custom_tags:
        if tag and tag not in combined_tags:
            combined_tags.append(tag)
            
    if combined_tags:
        tags_str = "; ".join(combined_tags)
        patch_document.append({
            "op": "add",
            "path": "/fields/System.Tags",
            "value": tags_str
        })

    # Priority (1=highest, 4=lowest)
    priority = failure.get("priority")
    if priority:
        patch_document.append({
            "op": "add",
            "path": "/fields/Microsoft.VSTS.Common.Priority",
            "value": int(priority),
        })

    # Severity e.g. "1 - Critical", "2 - High", "3 - Medium", "4 - Low"
    severity = failure.get("severity")
    if severity:
        patch_document.append({
            "op": "add",
            "path": "/fields/Microsoft.VSTS.Common.Severity",
            "value": severity,
        })

    # Assignee: use provided value or fall back to auto-detected current user
    assignee = failure.get("assignee")
    if assignee:
        patch_document.append({
            "op": "add",
            "path": "/fields/System.AssignedTo",
            "value": assignee,
        })
    else:
        current_user = get_current_user_descriptor(base_url, pat)
        if current_user and current_user.get("id"):
            patch_document.append({
                "op": "add",
                "path": "/fields/System.AssignedTo",
                "value": {"id": current_user["id"]},
            })

    # Add 'Related' relation to PBI
    pbi_url = f"{base_url}/{project}/_apis/wit/workItems/{pbi_id}"
    patch_document.append({
        "op": "add",
        "path": "/relations/-",
        "value": {
            "rel": "System.LinkTypes.Related",
            "url": pbi_url,
            "attributes": {
                "comment": f"Related to PBI #{pbi_id}",
            },
        },
    })

    try:
        # If API 7.1 post fails on an older server, it might still create it, but let's just stick to 7.1
        resp = requests.post(api_url, json=patch_document, headers=headers, timeout=30)
        
        if resp.status_code in (200, 201):
            wi_id = resp.json().get("id")
            return True, f"Bug #{wi_id} created successfully.", wi_id
        else:
            try:
                err_msg = resp.json().get("message", resp.text)
            except Exception:
                err_msg = resp.text
            return False, f"ADO API error {resp.status_code}: {err_msg}", None
    except requests.exceptions.ConnectionError:
        return False, "Connection error: could not reach Azure DevOps server.", None
    except requests.exceptions.Timeout:
        return False, "Request timed out while connecting to Azure DevOps.", None
    except Exception as e:
        return False, f"Unexpected error: {str(e)}", None


def check_existing_bug(url, project, pat, failure, target_tags=None, fp_criteria=None):
    """
    Check if a Bug already exists in ADO matching the active fp_criteria fields.
    fp_criteria is a dict of booleans keyed by:
      transaction_type, rule_id, scenario_type, object, element, failure_reason, error_text, bug_title
    When fp_criteria is None all tag-based fields are used (backwards-compatible default).
    State is NOT 'Closed' or 'Deferred'.
    Returns: (exists: bool, message: str)
    """
    if target_tags is None:
        target_tags = TARGET_TAGS

    # When no criteria dict supplied fall back to checking all tag fields
    if fp_criteria is None:
        fp_criteria = {
            "transaction_type": True,
            "rule_id":          True,
            "scenario_type":    True,
            "object":           True,
            "element":          True,
            "failure_reason":   True,
            "error_text":       False,
            "bug_title":        False,
            "sheet_name":       False,
        }

    base_url = url.rstrip('/')
    api_url = f"{base_url}/{project}/_apis/wit/wiql?api-version=7.1"

    all_tags = failure.get("all_tags", [])

    transaction_type = next((t for t in all_tags if t.lower().startswith("transaction type - ")), None)
    rule_id          = next((t for t in all_tags if t.lower().startswith("ruleid - ")), None)
    scenario_type    = next((t for t in all_tags if t.lower().startswith("scenario type - ")), None)
    object_tag       = next((t for t in all_tags if t.lower().startswith("object - ")), None)
    element_tag      = next((t for t in all_tags if t.lower().startswith("element - ")), None)
    sheet_tag        = next((t for t in all_tags if t.lower().startswith("sheet - ")), None)
    failure_reasons  = [t for t in all_tags if t.lower() in target_tags]

    tags_to_check = []
    if fp_criteria.get("transaction_type") and transaction_type:
        tags_to_check.append(transaction_type)
    if fp_criteria.get("rule_id") and rule_id:
        tags_to_check.append(rule_id)
    if fp_criteria.get("scenario_type") and scenario_type:
        tags_to_check.append(scenario_type)
    if fp_criteria.get("object") and object_tag:
        tags_to_check.append(object_tag)
    if fp_criteria.get("element") and element_tag:
        tags_to_check.append(element_tag)
    if fp_criteria.get("sheet_name") and sheet_tag:
        tags_to_check.append(sheet_tag)
    if fp_criteria.get("failure_reason"):
        tags_to_check.extend(failure_reasons)

    if not tags_to_check and not fp_criteria.get("error_text") and not fp_criteria.get("bug_title"):
        return False, ""

    conditions = [
        "[System.WorkItemType] = 'Bug'",
        "[System.State] <> 'Closed'",
        "[System.State] <> 'Deferred'",
        "[System.State] <> 'Rejected'",
        "[System.State] <> 'Ready for Release'",
    ]

    for tag in tags_to_check:
        tag_escaped = tag.replace("'", "''")
        conditions.append(f"[System.Tags] CONTAINS '{tag_escaped}'")

    if fp_criteria.get("error_text"):
        error_text = failure.get("error_text", "")
        if error_text:
            error_text_escaped = f"Expected Error Text: {error_text}".replace("'", "''")
            conditions.append(f"[System.Description] CONTAINS '{error_text_escaped}'")

    if fp_criteria.get("bug_title"):
        bug_title = failure.get("test_case_name", "")
        if bug_title:
            bug_title_escaped = bug_title.replace("'", "''")
            conditions.append(f"[System.Title] = '{bug_title_escaped}'")
        
    where_clause = " AND ".join(conditions)
    wiql_query = f"SELECT [System.Id] FROM WorkItems WHERE {where_clause}"
    
    headers = _ado_headers(pat)
    try:
        resp = requests.post(api_url, json={"query": wiql_query}, headers=headers, timeout=10)
        if resp.status_code == 400:
            api_url = f"{base_url}/{project}/_apis/wit/wiql?api-version=6.0"
            resp = requests.post(api_url, json={"query": wiql_query}, headers=headers, timeout=10)
            
        if resp.status_code == 200:
            data = resp.json()
            work_items = data.get("workItems", [])
            if work_items:
                ids = [str(wi["id"]) for wi in work_items]
                return True, f"Skipped: Existing bug(s) found ({', '.join(ids)})"
            return False, ""
        else:
            return False, f"WIQL HTTP {resp.status_code}"
    except Exception as e:
        return False, f"WIQL Error: {str(e)}"


# ──────────────────────────────────────────────────────────────────────────────
# Ready-for-QA bug update helpers
# ──────────────────────────────────────────────────────────────────────────────

def scan_all_results(allure_results_dir):
    """
    Scan allure-results and return a list of dicts for every test case result.

    Each dict contains:
        - test_case_name  (str)
        - status          (str)  – 'passed' | 'failed' | 'broken' | 'skipped'
        - all_tags        (list[str])
        - attachments     (dict)  – keyed by role: request, old_response, new_response, assert
    """
    results = []
    allure_dir = Path(allure_results_dir)

    for file in allure_dir.glob("*-result.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        status = data.get("status", "")
        if not status:
            continue

        tags = [
            lbl.get("value", "")
            for lbl in data.get("labels", [])
            if lbl.get("name") == "tag" and lbl.get("value")
        ]

        def _get(att_id):
            sources = _collect_attachment_sources(data, att_id)
            return _read_attachment(allure_results_dir, sources[-1]) if sources else ""

        rule_id_tag = next((t for t in tags if t.startswith("RuleID - ")), None)
        rule_id = rule_id_tag[len("RuleID - "):].strip() if rule_id_tag else "Unknown"

        results.append({
            "test_case_name": data.get("name", "Unknown"),
            "rule_id": rule_id,
            "status": status,
            "all_tags": list(set(tags)),
            "attachments": {
                "request":       _get(ATTACHMENT_IDS["request"]),
                "old_response":  _get(ATTACHMENT_IDS["old_response"]),
                "new_response":  _get(ATTACHMENT_IDS["new_response"]),
                "assert_7efb21": _get(ATTACHMENT_IDS["assert_7efb21"]),
                "assert_35b0bf": _get(ATTACHMENT_IDS["assert_35b0bf"]),
                "assert_392130": _get(ATTACHMENT_IDS["assert_392130"]),
                "assert_3b4195": _get(ATTACHMENT_IDS["assert_3b4195"]),
                "assert_76b634": _get(ATTACHMENT_IDS["assert_76b634"]),
                "assert_bedd20": _get(ATTACHMENT_IDS["assert_bedd20"]),
                "assert_bb87e7": _get(ATTACHMENT_IDS["assert_bb87e7"]),
                "assert_731468": _get(ATTACHMENT_IDS["assert_731468"]),
                "assert_ad668e": _get(ATTACHMENT_IDS["assert_ad668e"]),
                "assert_979b2c": _get(ATTACHMENT_IDS["assert_979b2c"]),
                "assert_d8b2e5": _get(ATTACHMENT_IDS["assert_d8b2e5"]),
                "assert_f3a1c9": _get(ATTACHMENT_IDS["assert_f3a1c9"]),
                "assert_a3f8b1": _get(ATTACHMENT_IDS["assert_a3f8b1"]),
                "assert_b5c3e7": _get(ATTACHMENT_IDS["assert_b5c3e7"]),
                "assert_c4e2f1": _get(ATTACHMENT_IDS["assert_c4e2f1"]),
                "assert_c4f21a": _get(ATTACHMENT_IDS["assert_c4f21a"]),
                "assert_c7e592": _get(ATTACHMENT_IDS["assert_c7e592"]),
                "assert_6a3fd8": _get(ATTACHMENT_IDS["assert_6a3fd8"]),
            },
        })

    return results


def scan_all_batch_results(allure_results_dir):
    """
    Scan allure-results and return a list of dicts for every test case result,
    using ATTACHMENT_IDS (for batch testing / asserter.py).

    Uses the last occurrence of each attachment (same as scan_failures_by_tag):
        - request      → last '98efcb - Request'
        - old_response → last '33a829 - Response'
        - new_response → last 'a4b5d4 - Response'
        - assert_*     → last of each asserter.py attachment variant

    Each dict contains:
        - test_case_name  (str)
        - rule_id         (str)
        - status          (str)  – 'passed' | 'failed' | 'broken' | 'skipped'
        - all_tags        (list[str])
        - error_text      (str)
        - attachments     (dict)  – keyed by batch attachment IDs
    """
    results = []
    allure_dir = Path(allure_results_dir)

    for file in allure_dir.glob("*-result.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        status = data.get("status", "")
        if not status:
            continue

        tags = [
            lbl.get("value", "")
            for lbl in data.get("labels", [])
            if lbl.get("name") == "tag" and lbl.get("value")
        ]

        def _get(att_id):
            sources = _collect_attachment_sources(data, att_id)
            return _read_attachment(allure_results_dir, sources[-1]) if sources else ""

        rule_id_tag = next((t for t in tags if t.startswith("RuleID - ")), None)
        rule_id = rule_id_tag[len("RuleID - "):].strip() if rule_id_tag else "Unknown"

        results.append({
            "test_case_name": data.get("name", "Unknown"),
            "rule_id":        rule_id,
            "status":         status,
            "all_tags":       list(set(tags)),
            "error_text":     _get_error_text(data),
            "attachments": {
                "send":          _collect_send_grouped(data, allure_results_dir),
                "request":       _get(ATTACHMENT_IDS["request"]),
                "old_response":  _get(ATTACHMENT_IDS["old_response"]),
                "new_response":  _get(ATTACHMENT_IDS["new_response"]),
                "assert_7efb21": _get(ATTACHMENT_IDS["assert_7efb21"]),
                "assert_35b0bf": _get(ATTACHMENT_IDS["assert_35b0bf"]),
                "assert_392130": _get(ATTACHMENT_IDS["assert_392130"]),
                "assert_3b4195": _get(ATTACHMENT_IDS["assert_3b4195"]),
                "assert_76b634": _get(ATTACHMENT_IDS["assert_76b634"]),
                "assert_bedd20": _get(ATTACHMENT_IDS["assert_bedd20"]),
                "assert_bb87e7": _get(ATTACHMENT_IDS["assert_bb87e7"]),
                "assert_731468": _get(ATTACHMENT_IDS["assert_731468"]),
                "assert_ad668e": _get(ATTACHMENT_IDS["assert_ad668e"]),
                "assert_979b2c": _get(ATTACHMENT_IDS["assert_979b2c"]),
                "assert_d8b2e5": _get(ATTACHMENT_IDS["assert_d8b2e5"]),
                "assert_f3a1c9": _get(ATTACHMENT_IDS["assert_f3a1c9"]),
                "assert_a3f8b1": _get(ATTACHMENT_IDS["assert_a3f8b1"]),
                "assert_b5c3e7": _get(ATTACHMENT_IDS["assert_b5c3e7"]),
                "assert_c4e2f1": _get(ATTACHMENT_IDS["assert_c4e2f1"]),
                "assert_c4f21a": _get(ATTACHMENT_IDS["assert_c4f21a"]),
                "assert_e8f3d2": _get(ATTACHMENT_IDS["assert_e8f3d2"]),
                "assert_5e2a1f": _get(ATTACHMENT_IDS["assert_5e2a1f"]),
                "assert_9c4d83": _get(ATTACHMENT_IDS["assert_9c4d83"]),
                "assert_b7f041": _get(ATTACHMENT_IDS["assert_b7f041"]),
                "assert_3a8e6c": _get(ATTACHMENT_IDS["assert_3a8e6c"]),
                "assert_6f2c9a": _get(ATTACHMENT_IDS["assert_6f2c9a"]),
                "assert_1d7e4b": _get(ATTACHMENT_IDS["assert_1d7e4b"]),
                "assert_b3d91c": _get(ATTACHMENT_IDS["assert_b3d91c"]),
                "assert_a1c7d4": _get(ATTACHMENT_IDS["assert_a1c7d4"]),
                "assert_c7e592": _get(ATTACHMENT_IDS["assert_c7e592"]),
                "assert_6a3fd8": _get(ATTACHMENT_IDS["assert_6a3fd8"]),
            },
        })

    return results


def scan_all_assertion_results(allure_results_dir):
    """
    Scan allure-results and return a list of dicts for every test case result,
    using ASSERTION_ATTACHMENT_IDS (for assertion testing / custom_requests_asserter.py).

    Mirrors scan_all_results but reads the assertion-specific attachment slots so
    that build_bug_description produces the same content as the initial failure report.

    Each dict contains:
        - test_case_name  (str)
        - rule_id         (str)
        - status          (str)  – 'passed' | 'failed' | 'broken' | 'skipped'
        - all_tags        (list[str])
        - error_text      (str)
        - attachments     (dict)  – keyed by assertion attachment IDs + 'send'
    """
    results = []
    allure_dir = Path(allure_results_dir)

    for file in allure_dir.glob("*-result.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        status = data.get("status", "")
        if not status:
            continue

        tags = [
            lbl.get("value", "")
            for lbl in data.get("labels", [])
            if lbl.get("name") == "tag" and lbl.get("value")
        ]

        def _get_all(att_id):
            sources = _collect_attachment_sources(data, att_id)
            return "\n\n".join(
                filter(None, (_read_attachment(allure_results_dir, s) for s in sources))
            )

        rule_id_tag = next((t for t in tags if t.startswith("RuleID - ")), None)
        rule_id = rule_id_tag[len("RuleID - "):].strip() if rule_id_tag else "Unknown"

        results.append({
            "test_case_name": data.get("name", "Unknown"),
            "rule_id":        rule_id,
            "status":         status,
            "all_tags":       [t for t in set(tags) if not t.lower().startswith("precondition -")],
            "error_text":     _get_error_text(data),
            "attachments": {
                "send":          _collect_send_grouped(data, allure_results_dir),
                "assert_2ffe8e":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_2ffe8e"]),
                "assert_2ffvce":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_2ffvce"]),
                "assert_8b450b":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_8b450b"]),
                "assert_d43b5a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_d43b5a"]),
                "assert_d56775a": _get_all(ASSERTION_ATTACHMENT_IDS["assert_d56775a"]),
                "assert_d43we5a": _get_all(ASSERTION_ATTACHMENT_IDS["assert_d43we5a"]),
                "assert_d4ty5a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4ty5a"]),
                "assert_d4ml5a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4ml5a"]),
                "assert_d4005a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4005a"]),
                "assert_d4ioo5a": _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4ioo5a"]),
                "assert_d4er05a": _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4er05a"]),
                "assert_d4tto5a": _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4tto5a"]),
                "assert_568d49":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_568d49"]),
                "assert_c67011":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_c67011"]),
                "assert_c67045":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_c67045"]),
                "assert_c67048":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_c67048"]),
                "assert_c63496":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_c63496"]),
                "assert_e4c52a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_e4c52a"]),
                "assert_f41a3b":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_f41a3b"]),
                "assert_f17d8e":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_f17d8e"]),
                "assert_crrre96":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_crrre96"]),
                "assert_d4w4nb5a": _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4w4nb5a"]),
                "assert_d4ezz5a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4ezz5a"]),
                "assert_d4jjj5a":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_d4jjj5a"]),
                "assert_c6ggfr6":  _get_all(ASSERTION_ATTACHMENT_IDS["assert_c6ggfr6"]),
            },
        })

    return results


# ──────────────────────────────────────────────────────────────────────────────
# E2E Flows ADO helpers
# ──────────────────────────────────────────────────────────────────────────────

def _collect_e2e_steps_content(data, allure_results_dir):
    """Walk the Allure step tree and return all E2E step attachments as a single text block."""
    _ORDER = [
        (E2E_ATTACHMENT_IDS["soap_action"],         "SOAPAction"),
        (E2E_ATTACHMENT_IDS["nested_xml"],           "Nested XML"),
        (E2E_ATTACHMENT_IDS["request"],              "Request"),
        (E2E_ATTACHMENT_IDS["response"],             "Response"),
        (E2E_ATTACHMENT_IDS["summary"],              "Summary"),
        (E2E_ATTACHMENT_IDS["extracted_variables"],  "Extracted Variables"),
        (E2E_ATTACHMENT_IDS["assertions"],           "Assertions"),
    ]
    parts = []

    def _process(steps):
        for step in steps:
            group = []
            for att_id, label in _ORDER:
                for att in step.get("attachments", []):
                    if att_id in att.get("name", ""):
                        content = _read_attachment(allure_results_dir, att.get("source", ""))
                        if content:
                            group.append(f"--- {label} ---\n{content}")
                        break
            if group:
                name = step.get("name", "")
                header = f"{'='*60}\n{name}\n{'='*60}" if name else "=" * 60
                parts.append(header + "\n" + "\n\n".join(group))
            _process(step.get("steps", []))

    _process(data.get("steps", []))
    return "\n\n".join(parts)


def build_e2e_bug_description(tc_id, test_case_name, sheet_name, env_label, steps_content):
    """Build an HTML description for a failed E2E flow test case."""
    def _e(v): return _escape_html(str(v))
    html = (
        f"<h2>E2E Failure: {_e(test_case_name)}</h2>"
        f"<p><strong>TC ID:</strong> {_e(tc_id)}</p>"
        f"<p><strong>Sheet:</strong> {_e(sheet_name)}</p>"
    )
    if env_label:
        html += f"<p><strong>Environment:</strong> {_e(env_label)}</p>"
    html += "<hr/>"
    if steps_content:
        html += (
            "<h3>Step Details</h3>"
            '<pre style="background:#f5f5f5;padding:8px;font-size:11px;'
            f'white-space:pre-wrap;word-break:break-all;">{_e(steps_content)}</pre>'
        )
    return html


def scan_e2e_failures(allure_results_dir):
    """
    Scan allure-results for failed E2E flow tests (identified by a 'TC - ...' tag).
    Returns failure dicts compatible with create_ado_bug.
    """
    failures = []
    allure_dir = Path(allure_results_dir)

    for file in allure_dir.glob("*-result.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        if data.get("status") != "failed":
            continue

        tags = [
            lbl.get("value", "")
            for lbl in data.get("labels", [])
            if lbl.get("name") == "tag" and lbl.get("value")
        ]

        tc_tag = next((t for t in tags if t.startswith("TC - ")), None)
        if not tc_tag:
            continue

        tc_id      = tc_tag[len("TC - "):].strip()
        sheet_tag  = next((t for t in tags if t.startswith("Sheet - ")), None)
        env_tag    = next((t for t in tags if t.startswith("Env - ")), None)
        sheet_name = sheet_tag[len("Sheet - "):].strip() if sheet_tag else ""
        env_label  = env_tag[len("Env - "):].strip() if env_tag else ""

        test_case_name = data.get("name", tc_id)
        steps_content  = _collect_e2e_steps_content(data, allure_results_dir)
        description_html = build_e2e_bug_description(
            tc_id, test_case_name, sheet_name, env_label, steps_content
        )

        custom_tags = ["E2E"]
        if env_label:
            custom_tags.append(env_label)

        failures.append({
            "test_case_name":  test_case_name,
            "rule_id":         tc_id,
            "failure_tags":    [tc_tag],
            "all_tags":        list(set(tags)),
            "error_text":      "",
            "description_html": description_html,
            "attachments":     {},
            "custom_tags":     custom_tags,
        })

    return failures


def scan_all_e2e_results(allure_results_dir):
    """
    Scan allure-results and return a list of dicts for every E2E test case result.
    Only includes results that carry a 'TC - ...' tag (E2E flow results).

    Each dict contains:
        - test_case_name  (str)
        - tc_id           (str)
        - rule_id         (str)  – same as tc_id for compatibility with match helpers
        - status          (str)  – 'passed' | 'failed' | 'broken' | 'skipped'
        - all_tags        (list[str])
        - attachments     (dict)  – empty; E2E bugs use description_html
    """
    results = []
    allure_dir = Path(allure_results_dir)

    for file in allure_dir.glob("*-result.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        status = data.get("status", "")
        if not status:
            continue

        tags = [
            lbl.get("value", "")
            for lbl in data.get("labels", [])
            if lbl.get("name") == "tag" and lbl.get("value")
        ]

        tc_tag = next((t for t in tags if t.startswith("TC - ")), None)
        if not tc_tag:
            continue

        tc_id      = tc_tag[len("TC - "):].strip()
        sheet_tag  = next((t for t in tags if t.startswith("Sheet - ")), None)
        env_tag    = next((t for t in tags if t.startswith("Env - ")), None)
        sheet_name = sheet_tag[len("Sheet - "):].strip() if sheet_tag else ""
        env_label  = env_tag[len("Env - "):].strip() if env_tag else ""

        test_case_name   = data.get("name", tc_id)
        steps_content    = _collect_e2e_steps_content(data, allure_results_dir)
        description_html = build_e2e_bug_description(
            tc_id, test_case_name, sheet_name, env_label, steps_content
        )

        results.append({
            "test_case_name":  test_case_name,
            "tc_id":           tc_id,
            "rule_id":         tc_id,
            "status":          status,
            "all_tags":        list(set(tags)),
            "error_text":      "",
            "description_html": description_html,
            "attachments":     {},
        })

    return results


def scan_e2e_failed_tc_ids(allure_results_dir: str) -> set:
    """Return the set of TC_IDs whose status is 'failed' in the given allure-results directory."""
    failed = set()
    for file in Path(allure_results_dir).glob("*-result.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("status") != "failed":
            continue
        for lbl in data.get("labels", []):
            if lbl.get("name") == "tag":
                val = lbl.get("value", "")
                if val.startswith("TC - "):
                    failed.add(val[len("TC - "):].strip())
                    break
    return failed


def find_ready_for_qa_bug(url, project, pat, test_case, match_fields=None):
    """
    Search ADO for a Bug with State = 'Ready for QA' that matches the test case.

    match_fields: set of field keys to match on. Supported values:
        'transaction_type', 'rule_id', 'scenario_type', 'object', 'element', 'bug_title'
    Defaults to all fields when None.

    Returns (found: bool, work_item_id: int|None, message: str)
    """
    all_fields = {"transaction_type", "rule_id", "scenario_type", "object", "element", "failure_tag", "bug_title"}
    if match_fields is None:
        match_fields = all_fields

    base_url = url.rstrip('/')
    api_url = f"{base_url}/{project}/_apis/wit/wiql?api-version=7.1"

    all_tags = test_case.get("all_tags", [])

    transaction_type = next((t for t in all_tags if t.lower().startswith("transaction type - ")), None)
    rule_id          = next((t for t in all_tags if t.lower().startswith("ruleid - ")), None)
    scenario_type    = next((t for t in all_tags if t.lower().startswith("scenario type - ")), None)
    object_tag       = next((t for t in all_tags if t.lower().startswith("object - ")), None)
    element_tag      = next((t for t in all_tags if t.lower().startswith("element - ")), None)

    all_known_failure_tags = TARGET_TAGS | SYSTEM1_TARGET_TAGS
    failure_tag = next((t for t in all_tags if t.lower() in all_known_failure_tags), None)
    # Passed test cases have no failure tag — skip that condition even if selected,
    # and signal to the caller that it was dropped.
    failure_tag_skipped = "failure_tag" in match_fields and failure_tag is None

    tag_field_map = {
        "transaction_type": transaction_type,
        "rule_id":          rule_id,
        "scenario_type":    scenario_type,
        "object":           object_tag,
        "element":          element_tag,
        "failure_tag":      failure_tag,
    }

    conditions = [
        "[System.WorkItemType] = 'Bug'",
        "[System.State] = 'Ready for QA'",
    ]

    for field_key, tag_value in tag_field_map.items():
        if field_key in match_fields and tag_value:
            tag_escaped = tag_value.replace("'", "''")
            conditions.append(f"[System.Tags] CONTAINS '{tag_escaped}'")

    if "bug_title" in match_fields:
        title_escaped = test_case.get("test_case_name", "").replace("'", "''")
        if title_escaped:
            conditions.append(f"[System.Title] = '{title_escaped}'")

    if len(conditions) == 2:
        return False, None, "No identifying fields selected or found on test case"

    wiql_query = f"SELECT [System.Id] FROM WorkItems WHERE {' AND '.join(conditions)}"

    headers = _ado_headers(pat)
    try:
        resp = requests.post(api_url, json={"query": wiql_query}, headers=headers, timeout=10)
        if resp.status_code == 400:
            api_url = f"{base_url}/{project}/_apis/wit/wiql?api-version=6.0"
            resp = requests.post(api_url, json={"query": wiql_query}, headers=headers, timeout=10)

        if resp.status_code == 200:
            work_items = resp.json().get("workItems", [])
            if work_items:
                wi_id = work_items[0]["id"]
                return True, wi_id, f"Found Bug #{wi_id}", failure_tag_skipped
            return False, None, "No matching 'Ready for QA' bug found", failure_tag_skipped
        else:
            try:
                msg = resp.json().get("message", resp.text)
            except Exception:
                msg = resp.text
            return False, None, f"WIQL HTTP {resp.status_code}: {msg}", failure_tag_skipped
    except Exception as e:
        return False, None, f"WIQL Error: {str(e)}", failure_tag_skipped


def update_bug_for_qa_result(url, project, pat, work_item_id, test_case, new_state):
    """
    Update an ADO bug state and add a comment based on the test result.

    new_state: 'Ready for Release' (test passed) or 'Reopened' (test failed)
    Returns (success: bool, message: str)
    """
    base_url = url.rstrip('/')

    # Build comment HTML.
    # For E2E test cases, description_html already contains the step attachments.
    # For batch/assertion test cases, fall back to build_bug_description.
    if test_case.get("description_html"):
        comment_html = test_case["description_html"]
    else:
        all_known = TARGET_TAGS | SYSTEM1_TARGET_TAGS
        tc_for_desc = dict(test_case)
        tc_for_desc.setdefault(
            "failure_tags",
            [t for t in tc_for_desc.get("all_tags", []) if t.lower() in all_known]
        )
        comment_html = build_bug_description(tc_for_desc)

    # 1. Update state via PATCH on the work item
    patch_url = f"{base_url}/{project}/_apis/wit/workitems/{work_item_id}?api-version=7.1"
    headers_patch = _ado_headers(pat)
    headers_patch["Content-Type"] = "application/json-patch+json"

    patch_document = [
        {"op": "add", "path": "/fields/System.State", "value": new_state},
    ]

    try:
        resp = requests.patch(patch_url, json=patch_document, headers=headers_patch, timeout=15)
        if resp.status_code not in (200, 201):
            try:
                err_msg = resp.json().get("message", resp.text)
            except Exception:
                err_msg = resp.text
            return False, f"State update failed HTTP {resp.status_code}: {err_msg}"
    except Exception as e:
        return False, f"State update error: {str(e)}"

    # 2. Add comment via the comments endpoint
    comments_url = f"{base_url}/{project}/_apis/wit/workitems/{work_item_id}/comments?api-version=7.1-preview.3"
    headers_comment = _ado_headers(pat)
    headers_comment["Content-Type"] = "application/json"

    try:
        resp = requests.post(comments_url, json={"text": comment_html}, headers=headers_comment, timeout=15)
        if resp.status_code not in (200, 201):
            # Comment failed but state was already updated — report partial success
            try:
                err_msg = resp.json().get("message", resp.text)
            except Exception:
                err_msg = resp.text
            return True, f"State updated to '{new_state}' but comment failed: {err_msg}"
    except Exception as e:
        return True, f"State updated to '{new_state}' but comment error: {str(e)}"

    return True, f"Bug #{work_item_id} → '{new_state}' and comment added."


def _get_all_bugs_with_state(url, project, pat, state):
    """
    Fetch all ADO Bugs matching a given state.
    Returns (list of dicts, error_message|None).
    Each dict: {id, title, tags} where tags is a set of lowercased, stripped tag strings.
    """
    base_url = url.rstrip('/')
    api_url = f"{base_url}/{project}/_apis/wit/wiql?api-version=7.1"

    state_escaped = state.replace("'", "''")
    wiql_query = (
        "SELECT [System.Id] FROM WorkItems "
        f"WHERE [System.WorkItemType] = 'Bug' AND [System.State] = '{state_escaped}'"
    )

    headers = _ado_headers(pat)
    try:
        resp = requests.post(api_url, json={"query": wiql_query}, headers=headers, timeout=30)
        if resp.status_code == 400:
            api_url = f"{base_url}/{project}/_apis/wit/wiql?api-version=6.0"
            resp = requests.post(api_url, json={"query": wiql_query}, headers=headers, timeout=30)

        if resp.status_code != 200:
            try:
                msg = resp.json().get("message", resp.text)
            except Exception:
                msg = resp.text
            return [], f"WIQL HTTP {resp.status_code}: {msg}"

        work_items = resp.json().get("workItems", [])
        if not work_items:
            return [], None

        ids = [wi["id"] for wi in work_items]
        bugs = []
        batch_size = 200
        fields_param = "System.Id,System.Title,System.Tags"

        for start in range(0, len(ids), batch_size):
            batch_ids = ids[start:start + batch_size]
            ids_str = ",".join(str(i) for i in batch_ids)
            batch_url = (
                f"{base_url}/{project}/_apis/wit/workitems"
                f"?ids={ids_str}&fields={fields_param}&api-version=7.1"
            )
            try:
                r = requests.get(batch_url, headers=headers, timeout=30)
                if r.status_code != 200:
                    continue
                for item in r.json().get("value", []):
                    f = item.get("fields", {})
                    raw_tags = f.get("System.Tags", "") or ""
                    tags_set = {t.strip().lower() for t in raw_tags.split(";") if t.strip()}
                    bugs.append({
                        "id":    item["id"],
                        "title": f.get("System.Title", ""),
                        "tags":  tags_set,
                    })
            except Exception:
                continue

        return bugs, None
    except Exception as e:
        return [], f"Error: {str(e)}"


def get_all_ready_for_qa_bugs(url, project, pat):
    """Fetch all ADO Bugs with State = 'Ready for QA'. See _get_all_bugs_with_state."""
    return _get_all_bugs_with_state(url, project, pat, "Ready for QA")


def get_all_closed_bugs(url, project, pat):
    """Fetch all ADO Bugs with State = 'Closed'. See _get_all_bugs_with_state."""
    return _get_all_bugs_with_state(url, project, pat, "Closed")


# ──────────────────────────────────────────────────────────────────────────────
# Failure-tag hierarchies for "Update QA Bugs".
#
# A failed test case's failure tag(s) can differ from the tag(s) already on a
# 'Ready for QA' bug. Whether that's safe grounds to close the bug (the check
# it tracks ran and passed this time) or must be skipped (the check never ran,
# so nothing is proven) depends on execution order in the asserter:
#
# - System 1 / System 2: one hard tag ("System N Failure") that short-circuits
#   via pytest.fail() before the 3 soft checks (error text / object-element /
#   field-additional) ever run (utils/asserter/asserter.py). Reaching any soft
#   tag proves the hard tag passed; reaching a *different* soft tag proves the
#   other soft checks ran together and passed (they're not short-circuited
#   from each other — see the soft_failures list in assert_error_exists).
# - Dual System: an ordered 3-step chain, Failure -> Error Text -> Row
#   (XMLDualAsserter.assert_responses_errors / XMLDualSingleRowAsserter) where
#   each stage only runs if the earlier one(s) completed without failing.
# - Dual System Mismatch Failure comes from an unrelated assertion mode
#   (presence comparison) with no code path connecting it to the chain above,
#   so no ordering can be proven against it either way.
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_FAILURE_FAMILIES = {
    1: {
        "hard": "system 1 failure",
        "soft": {
            "system 1 error text failure",
            "system 1 object/element failure",
            "system 1 field/additional failure",
        },
    },
    2: {
        "hard": "system 2 failure",
        "soft": {
            "system 2 error text failure",
            "system 2 object/element failure",
            "system 2 field/additional failure",
        },
    },
}

DUAL_SYSTEM_CHAIN = ["dual system failure", "dual system error text failure", "dual system row failure"]
DUAL_SYSTEM_MISMATCH = "dual system mismatch failure"

ALL_KNOWN_FAILURE_TAGS = (
    {SYSTEM_FAILURE_FAMILIES[1]["hard"]} | SYSTEM_FAILURE_FAMILIES[1]["soft"]
    | {SYSTEM_FAILURE_FAMILIES[2]["hard"]} | SYSTEM_FAILURE_FAMILIES[2]["soft"]
    | set(DUAL_SYSTEM_CHAIN) | {DUAL_SYSTEM_MISMATCH}
)


def _failure_tag_outcome(bug_tags, tc_tags):
    """
    Compare a 'Ready for QA' bug's failure tag(s) against a FAILED test case's
    failure tag(s) and decide the QA-bug outcome.

    bug_tags / tc_tags: sets of lowercased tag strings.

    Returns:
        'reopen' - the test case reproduces (one of) the bug's own failure tag(s).
        'close'  - the test case fails with a different tag that is provably
                   downstream of every one of the bug's tag(s) in the same
                   family, meaning the bug's tracked check ran and passed.
        'skip'   - no safe conclusion can be drawn: the test case has no
                   recognized failure tag, its tag(s) belong to a different
                   family than the bug's, or the differing tag can't be proven
                   to run after the bug's tracked check.
    """
    tc_known = tc_tags & ALL_KNOWN_FAILURE_TAGS
    if not tc_known:
        return "skip"

    bug_known = bug_tags & ALL_KNOWN_FAILURE_TAGS
    if not bug_known:
        return "skip"

    for family in SYSTEM_FAILURE_FAMILIES.values():
        family_tags = {family["hard"]} | family["soft"]
        if not (bug_known & family_tags):
            continue

        tc_family = tc_known & family_tags
        if not tc_family:
            return "skip"  # tc's failure tag(s) belong to a different family

        if tc_family & bug_known:
            return "reopen"

        bug_is_hard_only = (bug_known & family_tags) == {family["hard"]}
        tc_is_hard_only = tc_family == {family["hard"]}
        if tc_is_hard_only and not bug_is_hard_only:
            return "skip"  # bug tracks a soft check that never ran this time
        return "close"

    dual_chain_set = set(DUAL_SYSTEM_CHAIN)
    if bug_known & dual_chain_set:
        tc_chain = tc_known & dual_chain_set
        if not tc_chain:
            return "skip"  # e.g. tc's only dual tag is Mismatch (different mode)

        if tc_chain & bug_known:
            return "reopen"

        bug_idx = max(DUAL_SYSTEM_CHAIN.index(t) for t in bug_known & dual_chain_set)
        tc_idx = min(DUAL_SYSTEM_CHAIN.index(t) for t in tc_chain)
        return "close" if tc_idx > bug_idx else "skip"

    if DUAL_SYSTEM_MISMATCH in bug_known:
        return "reopen" if DUAL_SYSTEM_MISMATCH in tc_known else "skip"

    return "skip"


def match_bug_to_test_case(bug, test_cases, match_fields=None):
    """
    Find the best matching test case for a bug across all executed test cases.

    When multiple test cases match, a 'reopen' outcome takes priority over a
    'close' outcome — so a bug is only closed when no matching execution still
    reproduces it.

    match_fields: set of field keys to match on. Supported values:
        'transaction_type', 'rule_id', 'scenario_type', 'object', 'element', 'failure_tag', 'bug_title'
    Defaults to all fields when None.

    For 'failure_tag': skipped for passed test cases (they have no failure tag
    by definition — always a 'close'-type match). For failed test cases, see
    _failure_tag_outcome() — a differing tag can mean 'reopen', 'close', or
    'skip' (excluded from matches) depending on whether it's safe to conclude
    the bug's tracked check actually ran and passed.

    Returns the matching test_case dict (with an added 'qa_outcome' key set to
    'reopen' or 'close') or None.
    """
    all_fields = {"transaction_type", "rule_id", "scenario_type", "object", "element", "failure_tag", "bug_title"}
    if match_fields is None:
        match_fields = all_fields

    bug_tags        = bug["tags"]           # set of lowercased strings
    bug_title_lower = bug["title"].lower()

    matches = []  # list of (tc, outcome) tuples
    for tc in test_cases:
        if tc.get("status") not in ("passed", "failed"):
            continue

        tc_tags = tc.get("all_tags", [])
        tc_tags_lower = {t.lower() for t in tc_tags}

        transaction_type = next((t for t in tc_tags if t.lower().startswith("transaction type - ")), None)
        rule_id          = next((t for t in tc_tags if t.lower().startswith("ruleid - ")), None)
        scenario_type    = next((t for t in tc_tags if t.lower().startswith("scenario type - ")), None)
        object_tag       = next((t for t in tc_tags if t.lower().startswith("object - ")), None)
        element_tag      = next((t for t in tc_tags if t.lower().startswith("element - ")), None)

        tag_field_map = {
            "transaction_type": transaction_type,
            "rule_id":          rule_id,
            "scenario_type":    scenario_type,
            "object":           object_tag,
            "element":          element_tag,
        }

        matched = True
        for field_key, tc_tag in tag_field_map.items():
            if field_key not in match_fields:
                continue
            if not tc_tag or tc_tag.lower() not in bug_tags:
                matched = False
                break

        if not matched:
            continue

        is_passed = tc.get("status") == "passed"
        if "failure_tag" in match_fields:
            if is_passed:
                outcome = "close"
            else:
                outcome = _failure_tag_outcome(bug_tags, tc_tags_lower)
                if outcome == "skip":
                    continue
        else:
            outcome = "close" if is_passed else "reopen"

        if "bug_title" in match_fields:
            tc_name = tc.get("test_case_name", "").lower()
            if tc_name and tc_name != bug_title_lower:
                continue

        matches.append((tc, outcome))

    if not matches:
        return None

    # Prioritize 'reopen': any matching execution that still reproduces the
    # bug's own failure tag means it's not actually fixed, regardless of other
    # matches that would otherwise close it.
    for tc, outcome in matches:
        if outcome == "reopen":
            result = dict(tc)
            result["qa_outcome"] = "reopen"
            return result

    tc, outcome = matches[0]
    result = dict(tc)
    result["qa_outcome"] = outcome
    return result


def add_failure_comment(url, project, pat, work_item_id, failure, prefix_text=None):
    """Post a failure's full description as a comment on an existing ADO work item."""
    base_url = url.rstrip("/")
    comments_url = (
        f"{base_url}/{project}/_apis/wit/workitems/{work_item_id}/comments"
        f"?api-version=7.1-preview.3"
    )
    headers = _ado_headers(pat)
    headers["Content-Type"] = "application/json"
    comment_html = build_bug_description(failure)
    if prefix_text:
        comment_html = f"<p>{prefix_text}</p>" + comment_html
    try:
        resp = requests.post(
            comments_url,
            json={"text": comment_html},
            headers=headers,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            return True, f"Comment added for: {failure['test_case_name']}"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)
