"""
Regression tests for SchemaRulesValidator's grid-based rule matching, used by
XMLSingleAsserter.assert_error_doesnt_exist and assert_error_exists
(utils/asserter/asserter.py).

The bug being fixed:
    Presence-only callers have no downstream soft-check stage (unlike
    assert_error_exists, which tags mismatches as soft failures — see
    tests/test_soft_assertions.py). Before this fix, rule matching decided
    "found" purely from RuleID+Type, ignoring Object/Element/Error Text/Field
    Value/Additional Reference entirely for that decision — so if the same
    RuleID fired on a different occurrence (e.g. a different HAAD Field), a
    "doesn't exist" check for the *other* occurrence would still see
    found=True and incorrectly fail.

    build_match_grid/RuleMatchGrid fixes this: every report row matching
    RuleID(+Type) is scored, column by column, against whatever criteria the
    caller actually supplied (object/element/error text/field value/additional
    reference) — with any criterion left blank on the test case simply
    ignored, not treated as "must also be blank in the report". A row counts
    as a full match (RuleMatchGrid.exists()/matched_rows()) only when every
    supplied criterion matches on that row.

assert_error_exists uses the grid's loose sense of "found" (any RuleID+Type
row at all, via `bool(grid.rows)`) so its soft-check stage can still run and
tag the specific mismatch reason — see tests/test_soft_assertions.py.
"""

import base64
import csv
import io

import pytest

from utils.asserter.asserter import XMLSingleAsserter
from utils.asserter.schema_rules_validator import SchemaRulesValidator
from utils.asserter.report_row_type import ReportRowType
from utils.common_variables import tc_rule_id, tc_object, tc_element, tc_error_text


def _report_row(rule_id="500", object_name="Claim", haad_field="A",
                 error_text="dup", field_value="", additional_reference=""):
    return {
        "Type": "ERROR",
        "RuleID": rule_id,
        "Object Name": object_name,
        "HAAD Field": haad_field,
        "Error Text": error_text,
        "Field Value": field_value,
        "Additional Reference": additional_reference,
    }


CSV_HEADER = (
    "Transaction", "Type", "RuleID", "Object Name", "HAAD Field",
    "Field Value", "Additional Reference", "Error Text",
)


def _make_soap_response(rows, row_type="ERROR"):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)
    for object_name, haad_field in rows:
        writer.writerow(("TX1", row_type, "500", object_name, haad_field, "", "", "dup"))
    report_b64 = base64.b64encode(buf.getvalue().encode("utf-8")).decode("ascii")
    return {"content": (
        "<Envelope><Body><SubmitResponse>"
        "<SubmitResult>-2</SubmitResult>"
        f"<errorReport>{report_b64}</errorReport>"
        "</SubmitResponse></Body></Envelope>"
    )}


def test_exact_match_correctly_reports_absent_when_only_a_different_occurrence_fired():
    """Only field A fired. A doesn't-exist check for field B must find nothing."""
    report = [_report_row(haad_field="A")]

    grid = SchemaRulesValidator("500", ReportRowType.ERROR, {tc_object: "Claim", tc_element: "B"}).validate_strategy(report)

    assert grid.exists() is False


def test_exact_match_correctly_reports_present_when_that_exact_occurrence_fired():
    report = [_report_row(haad_field="A"), _report_row(haad_field="B")]

    grid = SchemaRulesValidator("500", ReportRowType.ERROR, {tc_object: "Claim", tc_element: "B"}).validate_strategy(report)

    assert grid.exists() is True


def test_exact_match_with_only_error_text_supplied_ignores_the_other_occurrence():
    report = [_report_row(haad_field="A", error_text="foo")]

    grid = SchemaRulesValidator("500", ReportRowType.ERROR, {tc_error_text: "bar"}).validate_strategy(report)

    assert grid.exists() is False


def test_exact_match_ignores_blank_criteria_on_the_test_case():
    """Object/element/error text/field value/additional reference left blank on the
    test case must not be forced to also be blank in the matched report row."""
    report = [_report_row(
        haad_field="A", error_text="some error", field_value="X", additional_reference="Y"
    )]

    grid = SchemaRulesValidator("500", ReportRowType.ERROR, {
        tc_object: "Claim", tc_element: "A",
        tc_error_text: None,  # not supplied — must be ignored, not compared against ''
    }).validate_strategy(report)

    assert grid.exists() is True


def test_exact_match_falls_back_to_plain_ruleid_presence_when_no_criteria_supplied():
    report = [_report_row(haad_field="A")]

    grid = SchemaRulesValidator("500", ReportRowType.ERROR, {}).validate_strategy(report)

    assert grid.exists() is True


def test_loose_found_is_true_even_on_a_wrong_occurrence():
    """assert_error_exists's behaviour: `bool(grid.rows)` stays True even on a wrong
    occurrence, so the soft-check stage can run and tag the specific mismatch reason.
    grid.exists() correctly stays False for that same wrong occurrence."""
    report = [_report_row(haad_field="A")]

    grid = SchemaRulesValidator("500", ReportRowType.ERROR, {tc_object: "Claim", tc_element: "B"}).validate_strategy(report)

    assert bool(grid.rows) is True
    assert grid.exists() is False


def _doesnt_exist_test_case(element="B"):
    return {
        tc_rule_id: "500",
        tc_object: "Claim",
        tc_element: element,
        tc_error_text: "dup",
    }


def test_assert_error_doesnt_exist_passes_for_a_different_field_when_object_element_is_checked():
    """Only field A fired. assert_object_element=True must let a doesn't-exist
    check for field B pass, since that specific occurrence never showed up."""
    response = _make_soap_response([("Claim", "A")])

    found, row_num = XMLSingleAsserter(response).assert_error_doesnt_exist(
        _doesnt_exist_test_case(element="B"), request_template=None, system_index=1,
        assert_object_element=True,
    )

    assert found is False


def test_assert_error_doesnt_exist_still_fails_when_object_element_is_unchecked():
    """Without the checkbox on, presence falls back to plain RuleID — matching
    the pre-fix behaviour when no disambiguating criteria are requested at all."""
    response = _make_soap_response([("Claim", "A")])

    with pytest.raises(pytest.fail.Exception):
        XMLSingleAsserter(response).assert_error_doesnt_exist(
            _doesnt_exist_test_case(element="B"), request_template=None, system_index=1,
            assert_object_element=False,
        )


def test_assert_error_doesnt_exist_fails_when_the_exact_field_did_fire():
    """Both fields fired. A doesn't-exist check for field B must correctly fail,
    since that specific occurrence is genuinely present."""
    response = _make_soap_response([("Claim", "A"), ("Claim", "B")])

    with pytest.raises(pytest.fail.Exception):
        XMLSingleAsserter(response).assert_error_doesnt_exist(
            _doesnt_exist_test_case(element="B"), request_template=None, system_index=1,
            assert_object_element=True,
        )


def test_assert_error_doesnt_exist_catches_the_rule_firing_as_a_warning():
    """Bug: a "Pass" objective only checked expected_type=ERROR by default, so a
    rule that actually fires as a WARNING (or NOTIFICATION) was invisible to the
    doesn't-exist check and the assertion passed trivially. It must now be caught
    regardless of the row's Type."""
    response = _make_soap_response([("Claim", "B")], row_type="WARNING")

    with pytest.raises(pytest.fail.Exception):
        XMLSingleAsserter(response).assert_error_doesnt_exist(
            _doesnt_exist_test_case(element="B"), request_template=None, system_index=1,
            assert_object_element=True,
        )


def test_assert_error_doesnt_exist_catches_the_rule_firing_as_a_notification():
    response = _make_soap_response([("Claim", "B")], row_type="NOTIFICATION")

    with pytest.raises(pytest.fail.Exception):
        XMLSingleAsserter(response).assert_error_doesnt_exist(
            _doesnt_exist_test_case(element="B"), request_template=None, system_index=1,
            assert_object_element=True,
        )
