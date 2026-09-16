"""
Regression tests for the soft-assertion contract in
utils/asserter/asserter.py::XMLSingleAsserter.assert_error_exists().

The behaviour being locked down:
    When assert_text / assert_object_element / assert_field_additional are all
    enabled, a mismatch in one check must NOT short-circuit the others — every
    enabled check runs, and assert_error_exists fails exactly once at the end,
    tagging the Allure result with EVERY failure reason that actually mismatched
    (not just the first one it hit).

This matters beyond the assertion itself: utils/azure_reporting.py's ADO dedup
logic (see tests/test_ado_dedup.py) relies on a single failed test case carrying
every applicable "System N ... Failure" tag at once. If assert_error_exists ever
regressed to stopping at the first mismatch, that dedup guarantee would silently
break too.

Uses the real ErrorValidator / SchemaRulesValidator / ErrorTextProcessor classes
against a hand-built SOAP response — no mocking of business logic. Only
allure.dynamic.tag/label are spied on, purely to observe what gets tagged.
"""

import base64
import csv
import io

import allure
import pytest

from utils.asserter.asserter import XMLSingleAsserter
from utils.common_variables import (
    tc_rule_id,
    tc_object,
    tc_element,
    tc_error_text,
    tc_field_value,
    tc_additional_reference,
)

REPORT_HEADER = (
    "Transaction", "Type", "RuleID", "Object Name", "HAAD Field",
    "Field Value", "Additional Reference", "Error Text",
)


def _make_report_b64(rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(REPORT_HEADER)
    for row in rows:
        writer.writerow(row)
    return base64.b64encode(buf.getvalue().encode("utf-8")).decode("ascii")


def _make_soap_response(response_code, report_b64):
    return (
        "<Envelope><Body><SubmitResponse>"
        f"<SubmitResult>{response_code}</SubmitResult>"
        f"<errorReport>{report_b64}</errorReport>"
        "</SubmitResponse></Body></Envelope>"
    )


@pytest.fixture
def tag_spy(monkeypatch):
    tagged = []
    monkeypatch.setattr(allure.dynamic, "tag", lambda t: tagged.append(t))
    monkeypatch.setattr(allure.dynamic, "label", lambda *a, **k: None)
    return tagged


def _base_test_case(**overrides):
    test_case = {
        tc_rule_id: "123",
        tc_object: "ExpectedObj",
        tc_element: "ExpectedField",
        tc_error_text: "Expected error text",
        tc_field_value: "ExpectedFieldVal",
        tc_additional_reference: "ExpectedAddRef",
    }
    test_case.update(overrides)
    return test_case


def test_all_three_soft_checks_mismatching_are_all_reported_and_tagged_together(tag_spy):
    report_b64 = _make_report_b64([
        ("TX1", "ERROR", "123", "ActualObj", "ActualField", "ActualFieldVal", "ActualAddRef", "Actual error text"),
    ])
    response = {"content": _make_soap_response("-2", report_b64)}

    with pytest.raises(pytest.fail.Exception) as excinfo:
        XMLSingleAsserter(response).assert_error_exists(
            _base_test_case(), request_template=None, assert_text=True, system_index=1,
            assert_object_element=True, assert_field_additional=True,
        )

    assert tag_spy == [
        "System 1 Error Text Failure",
        "System 1 Object/Element Failure",
        "System 1 Field/Additional Failure",
    ]
    # All three mismatch messages must be present, not just the first one hit.
    message = str(excinfo.value)
    assert "Error report doesn't contain the error text" in message
    assert "Object Name or HAAD Field does not match" in message
    assert "Field Value or Additional Reference does not match" in message


def test_only_the_mismatching_check_is_tagged_when_others_are_disabled(tag_spy):
    """Object/element and field/additional also mismatch here, but since they
    aren't requested only the error-text tag must show up."""
    report_b64 = _make_report_b64([
        ("TX1", "ERROR", "123", "ActualObj", "ActualField", "ActualFieldVal", "ActualAddRef", "Actual error text"),
    ])
    response = {"content": _make_soap_response("-2", report_b64)}

    with pytest.raises(pytest.fail.Exception):
        XMLSingleAsserter(response).assert_error_exists(
            _base_test_case(), request_template=None, assert_text=True, system_index=1,
            assert_object_element=False, assert_field_additional=False,
        )

    assert tag_spy == ["System 1 Error Text Failure"]


def test_assert_text_only_matching_passes_and_tags_nothing(tag_spy):
    """Object/element and field/additional also mismatch here, but since only
    assert_text is enabled and the error text matches, nothing should fail."""
    report_b64 = _make_report_b64([
        ("TX1", "ERROR", "123", "ActualObj", "ActualField", "ActualFieldVal", "ActualAddRef", "Expected error text"),
    ])
    response = {"content": _make_soap_response("-2", report_b64)}

    found, row_num = XMLSingleAsserter(response).assert_error_exists(
        _base_test_case(), request_template=None, assert_text=True, system_index=1,
        assert_object_element=False, assert_field_additional=False,
    )

    assert found is True
    assert tag_spy == []


def test_assert_text_only_with_blank_error_text_is_skipped(tag_spy):
    """A blank error text on the test case must be treated like every other blank
    criterion — not enforced — even though assert_text is enabled."""
    report_b64 = _make_report_b64([
        ("TX1", "ERROR", "123", "ActualObj", "ActualField", "ActualFieldVal", "ActualAddRef", "Some actual error text"),
    ])
    response = {"content": _make_soap_response("-2", report_b64)}

    found, row_num = XMLSingleAsserter(response).assert_error_exists(
        _base_test_case(**{tc_error_text: ""}), request_template=None, assert_text=True, system_index=1,
        assert_object_element=False, assert_field_additional=False,
    )

    assert found is True
    assert tag_spy == []


def test_only_object_element_mismatching_tags_only_that_reason(tag_spy):
    report_b64 = _make_report_b64([
        ("TX1", "ERROR", "123", "ActualObj", "ActualField", "ExpectedFieldVal", "ExpectedAddRef", "Expected error text"),
    ])
    response = {"content": _make_soap_response("-2", report_b64)}

    with pytest.raises(pytest.fail.Exception):
        XMLSingleAsserter(response).assert_error_exists(
            _base_test_case(), request_template=None, assert_text=True, system_index=1,
            assert_object_element=True, assert_field_additional=True,
        )

    assert tag_spy == ["System 1 Object/Element Failure"]


def test_fully_matching_report_does_not_fail_or_tag_anything(tag_spy):
    report_b64 = _make_report_b64([
        ("TX1", "ERROR", "123", "ExpectedObj", "ExpectedField", "ExpectedFieldVal", "ExpectedAddRef", "Expected error text"),
    ])
    response = {"content": _make_soap_response("-2", report_b64)}

    found, row_num = XMLSingleAsserter(response).assert_error_exists(
        _base_test_case(), request_template=None, assert_text=True, system_index=1,
        assert_object_element=True, assert_field_additional=True,
    )

    assert found is True
    assert row_num == 0
    assert tag_spy == []


def test_system_index_is_reflected_in_every_tag(tag_spy):
    report_b64 = _make_report_b64([
        ("TX1", "ERROR", "123", "ActualObj", "ActualField", "ActualFieldVal", "ActualAddRef", "Actual error text"),
    ])
    response = {"content": _make_soap_response("-2", report_b64)}

    with pytest.raises(pytest.fail.Exception):
        XMLSingleAsserter(response).assert_error_exists(
            _base_test_case(), request_template=None, assert_text=True, system_index=2,
            assert_object_element=True, assert_field_additional=True,
        )

    assert tag_spy == [
        "System 2 Error Text Failure",
        "System 2 Object/Element Failure",
        "System 2 Field/Additional Failure",
    ]
