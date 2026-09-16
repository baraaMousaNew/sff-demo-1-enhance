"""
Regression tests for the ADO existing-bug dedup logic in utils/azure_reporting.py
(create_ado_bug + check_existing_bug).

The behaviour being locked down:
    A single failed test case can carry every applicable "System N ... Failure"
    tag at once (see tests/test_soft_assertions.py for why). Because of that,
    reporting the SAME test case a second time under a DIFFERENT failure-reason
    tag must be recognized as an existing bug rather than filed as a duplicate —
    check_existing_bug's WIQL query is built from every failure-reason tag
    present on the test case's all_tags, not just the one currently selected,
    and create_ado_bug stores that same full tag set on the bug it creates.

A fake ADO backend is used (no real network calls): it stores created bugs'
System.Tags strings and answers WIQL queries by re-checking the `CONTAINS`
conditions against those strings and the `<> 'Closed'` etc. state filters,
which is a faithful emulation of what the real WIQL query does.
"""

import re

from utils import azure_reporting as ar


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


class FakeAdoServer:
    """Minimal ADO emulation: create-bug + WIQL tag/state matching."""

    EXCLUDED_STATES = {"Closed", "Deferred", "Rejected", "Ready for Release"}

    def __init__(self):
        self.bugs = []  # each: {"id": int, "tags": str, "state": str}

    def post(self, url, json=None, headers=None, timeout=None):
        if "/wit/workitems/$Bug" in url:
            tags_value = next(
                (op["value"] for op in json if op["path"] == "/fields/System.Tags"), ""
            )
            wi_id = len(self.bugs) + 1
            self.bugs.append({"id": wi_id, "tags": tags_value, "state": "New"})
            return _FakeResponse(201, {"id": wi_id})

        if "/wiql" in url:
            query = json["query"]
            conditions = [c.replace("''", "'") for c in re.findall(r"CONTAINS '([^']*)'", query)]
            matches = [
                b for b in self.bugs
                if b["state"] not in self.EXCLUDED_STATES
                and all(cond in b["tags"] for cond in conditions)
            ]
            return _FakeResponse(200, {"workItems": [{"id": b["id"]} for b in matches]})

        raise AssertionError(f"Unexpected ADO URL in test: {url}")


IDENT_TAGS = ["RuleID - 123", "Object - Foo", "Element - Bar", "Transaction Type - Submit"]
ALL_SYSTEM1_FAILURE_TAGS = [
    "System 1 Error Text Failure",
    "System 1 Object/Element Failure",
    "System 1 Field/Additional Failure",
]


def _make_failure(name, all_tags, failure_tag_key):
    return {
        "test_case_name": name,
        "rule_id": "123",
        "failure_tags": [failure_tag_key],
        "all_tags": list(all_tags),
        "error_text": "",
        "attachments": {},
        "assignee": "tester@example.com",  # skips the current-user lookup network call
    }


def _create(server, name, all_tags, failure_tag_key):
    return ar.create_ado_bug(
        url="https://dev.azure.com/org", project="proj", pat="x", pbi_id=1,
        failure=_make_failure(name, all_tags, failure_tag_key),
    )


def _check(server, name, all_tags, failure_tag_key, **kwargs):
    return ar.check_existing_bug(
        url="https://dev.azure.com/org", project="proj", pat="x",
        failure=_make_failure(name, all_tags, failure_tag_key),
        target_tags=ar.SYSTEM1_TARGET_TAGS,
        **kwargs,
    )


def test_created_bug_tags_include_every_failure_reason_present_on_the_case(monkeypatch):
    server = FakeAdoServer()
    monkeypatch.setattr(ar.requests, "post", server.post)

    all_tags = IDENT_TAGS + ALL_SYSTEM1_FAILURE_TAGS
    ok, msg, wi_id = _create(server, "TC-1", all_tags, "System 1 Error Text Failure")

    assert ok, msg
    assert len(server.bugs) == 1
    stored_tags = server.bugs[0]["tags"]
    for tag in ALL_SYSTEM1_FAILURE_TAGS:
        assert tag in stored_tags


def test_bug_reported_under_one_failure_reason_is_found_as_duplicate_under_another(monkeypatch):
    server = FakeAdoServer()
    monkeypatch.setattr(ar.requests, "post", server.post)

    all_tags = IDENT_TAGS + ALL_SYSTEM1_FAILURE_TAGS
    ok, msg, wi_id = _create(server, "TC-1", all_tags, "System 1 Error Text Failure")
    assert ok, msg
    assert wi_id == 1

    exists, skip_msg = _check(server, "TC-1", all_tags, "System 1 Object/Element Failure")

    assert exists is True
    assert "1" in skip_msg


def test_third_failure_reason_on_the_same_case_is_also_recognized(monkeypatch):
    """Any of the 3 tags a soft-assertion failure carries must dedupe against the others."""
    server = FakeAdoServer()
    monkeypatch.setattr(ar.requests, "post", server.post)

    all_tags = IDENT_TAGS + ALL_SYSTEM1_FAILURE_TAGS
    _create(server, "TC-1", all_tags, "System 1 Object/Element Failure")

    exists, skip_msg = _check(server, "TC-1", all_tags, "System 1 Field/Additional Failure")

    assert exists is True


def test_unrelated_test_case_is_not_treated_as_a_duplicate(monkeypatch):
    server = FakeAdoServer()
    monkeypatch.setattr(ar.requests, "post", server.post)

    all_tags = IDENT_TAGS + ALL_SYSTEM1_FAILURE_TAGS
    _create(server, "TC-1", all_tags, "System 1 Error Text Failure")

    other_tags = [
        "RuleID - 999", "Object - Other", "Element - Different", "Transaction Type - Submit",
        "System 1 Object/Element Failure",
    ]
    exists, skip_msg = _check(server, "TC-2", other_tags, "System 1 Object/Element Failure")

    assert exists is False
    assert skip_msg == ""


def test_closed_bug_is_not_treated_as_an_existing_duplicate(monkeypatch):
    server = FakeAdoServer()
    monkeypatch.setattr(ar.requests, "post", server.post)

    all_tags = IDENT_TAGS + ALL_SYSTEM1_FAILURE_TAGS
    _create(server, "TC-1", all_tags, "System 1 Error Text Failure")
    server.bugs[0]["state"] = "Closed"

    exists, skip_msg = _check(server, "TC-1", all_tags, "System 1 Object/Element Failure")

    assert exists is False


def test_check_existing_bug_with_no_criteria_enabled_never_matches(monkeypatch):
    server = FakeAdoServer()
    monkeypatch.setattr(ar.requests, "post", server.post)

    all_tags = IDENT_TAGS + ALL_SYSTEM1_FAILURE_TAGS
    _create(server, "TC-1", all_tags, "System 1 Error Text Failure")

    no_criteria = {
        "transaction_type": False, "rule_id": False, "scenario_type": False,
        "object": False, "element": False, "failure_reason": False,
        "error_text": False, "bug_title": False,
    }
    exists, skip_msg = _check(server, "TC-1", all_tags, "System 1 Object/Element Failure",
                               fp_criteria=no_criteria)

    assert exists is False
    assert skip_msg == ""
