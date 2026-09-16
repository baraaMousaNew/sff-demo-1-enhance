"""
Regression tests for the "Update QA Bugs" business logic in utils/azure_reporting.py.

Covers:
    - _failure_tag_outcome(): the hard/soft + Dual System chain reopen/close/skip rules.
    - match_bug_to_test_case(): field matching, the failure_tag integration, the
      reopen-beats-close multi-match priority rule, and bug_title matching.

These are pure functions (no network I/O), so no mocking is required.

Run with:
    python -m pytest tests/test_update_qa_bugs.py -v
        -> each case + its expected outcome is printed as its own test ID.
    python -m pytest tests/test_update_qa_bugs.py -v -s
        -> also prints the exact bug/test-case tags and the actual outcome for every case.
"""

import pytest

from utils.azure_reporting import (
    _failure_tag_outcome,
    match_bug_to_test_case,
    SYSTEM_FAILURE_FAMILIES,
    DUAL_SYSTEM_CHAIN,
    DUAL_SYSTEM_MISMATCH,
)


def tags(*values):
    """Build a lowercased tag set the way callers of _failure_tag_outcome expect."""
    return {v.lower() for v in values}


def make_bug(title="Bug Title", *tag_values):
    return {"id": 1, "title": title, "tags": {t.lower() for t in tag_values}}


def make_tc(name, status, *tag_values):
    return {"test_case_name": name, "status": status, "all_tags": list(tag_values)}


IDENT_TAGS = ("Transaction Type - X", "RuleID - 123", "Object - Foo", "Element - Bar")
FULL_IDENT_TAGS = IDENT_TAGS + ("Scenario Type - Baseline",)


# ──────────────────────────────────────────────────────────────────────────────
# _failure_tag_outcome — one case per row, test ID = "<scenario> -> <expected>"
# ──────────────────────────────────────────────────────────────────────────────

def _system_family_cases(system):
    hard = SYSTEM_FAILURE_FAMILIES[system]["hard"]
    soft = sorted(SYSTEM_FAILURE_FAMILIES[system]["soft"])
    other = 2 if system == 1 else 1
    other_hard = SYSTEM_FAILURE_FAMILIES[other]["hard"]
    label = f"system {system}"

    return [
        (f"{label}: tc has no known failure tag -> skip",
         tags(hard), tags("Some Unrelated Tag"), "skip"),

        (f"{label}: bug has no known failure tag -> skip",
         tags("Some Unrelated Tag"), tags(hard), "skip"),

        (f"{label}: same hard tag on both -> reopen",
         tags(hard), tags(hard), "reopen"),

        (f"{label}: same soft tag on both -> reopen",
         tags(soft[0]), tags(soft[0]), "reopen"),

        (f"{label}: tc's soft tag is inside bug's full 3-tag soft set -> reopen",
         tags(*soft), tags(soft[0]), "reopen"),

        (f"{label}: tc fails in the other system's family -> skip",
         tags(hard), tags(other_hard), "skip"),

        (f"{label}: bug=hard only, tc=different soft tag -> close (hard check passed)",
         tags(hard), tags(soft[1]), "close"),

        (f"{label}: bug=soft only, tc=hard tag -> skip (soft check never ran)",
         tags(soft[0]), tags(hard), "skip"),

        (f"{label}: bug=one soft tag, tc=a different soft tag -> close",
         tags(soft[0]), tags(soft[1]), "close"),
    ]


DUAL_SYSTEM_CASES = [
    ("dual chain: bug=tc=Dual System Failure -> reopen",
     tags(DUAL_SYSTEM_CHAIN[0]), tags(DUAL_SYSTEM_CHAIN[0]), "reopen"),

    ("dual chain: bug=tc=Dual System Error Text Failure -> reopen",
     tags(DUAL_SYSTEM_CHAIN[1]), tags(DUAL_SYSTEM_CHAIN[1]), "reopen"),

    ("dual chain: bug=tc=Dual System Row Failure -> reopen",
     tags(DUAL_SYSTEM_CHAIN[2]), tags(DUAL_SYSTEM_CHAIN[2]), "reopen"),

    ("dual chain: bug=Failure, tc=Error Text Failure (downstream) -> close",
     tags(DUAL_SYSTEM_CHAIN[0]), tags(DUAL_SYSTEM_CHAIN[1]), "close"),

    ("dual chain: bug=Failure, tc=Row Failure (downstream) -> close",
     tags(DUAL_SYSTEM_CHAIN[0]), tags(DUAL_SYSTEM_CHAIN[2]), "close"),

    ("dual chain: bug=Row Failure, tc=Failure (upstream) -> skip (Row check never ran)",
     tags(DUAL_SYSTEM_CHAIN[2]), tags(DUAL_SYSTEM_CHAIN[0]), "skip"),

    ("dual chain: bug=Failure, tc=Mismatch (unrelated assertion mode) -> skip",
     tags(DUAL_SYSTEM_CHAIN[0]), tags(DUAL_SYSTEM_MISMATCH), "skip"),

    ("dual mismatch: bug=tc=Dual System Mismatch Failure -> reopen",
     tags(DUAL_SYSTEM_MISMATCH), tags(DUAL_SYSTEM_MISMATCH), "reopen"),

    ("dual mismatch: bug=Mismatch, tc=Failure -> skip (no provable relationship)",
     tags(DUAL_SYSTEM_MISMATCH), tags(DUAL_SYSTEM_CHAIN[0]), "skip"),

    ("dual mismatch: bug=Mismatch, tc=Error Text Failure -> skip (no provable relationship)",
     tags(DUAL_SYSTEM_MISMATCH), tags(DUAL_SYSTEM_CHAIN[1]), "skip"),

    ("dual mismatch: bug=Mismatch, tc=Row Failure -> skip (no provable relationship)",
     tags(DUAL_SYSTEM_MISMATCH), tags(DUAL_SYSTEM_CHAIN[2]), "skip"),
]

OUTCOME_CASES = _system_family_cases(1) + _system_family_cases(2) + DUAL_SYSTEM_CASES


@pytest.mark.parametrize(
    "bug_tags, tc_tags, expected",
    [case[1:] for case in OUTCOME_CASES],
    ids=[case[0] for case in OUTCOME_CASES],
)
def test_failure_tag_outcome(bug_tags, tc_tags, expected):
    actual = _failure_tag_outcome(bug_tags, tc_tags)
    print(f"\n  bug tags : {sorted(bug_tags)}")
    print(f"  tc tags  : {sorted(tc_tags)}")
    print(f"  expected : {expected}")
    print(f"  actual   : {actual}")
    assert actual == expected


# ──────────────────────────────────────────────────────────────────────────────
# match_bug_to_test_case — one case per row, test ID = scenario description
# ──────────────────────────────────────────────────────────────────────────────

HARD1 = SYSTEM_FAILURE_FAMILIES[1]["hard"]
SOFT1 = sorted(SYSTEM_FAILURE_FAMILIES[1]["soft"])

ALL_IDENT_FIELDS = {"transaction_type", "rule_id", "object", "element"}
ALL_IDENT_PLUS_TAG_FIELDS = ALL_IDENT_FIELDS | {"failure_tag"}


def _match_case(case_id, bug, test_cases, match_fields, expected_outcome, expected_tc_name=None):
    return pytest.param(bug, test_cases, match_fields, expected_outcome, expected_tc_name, id=case_id)


MATCH_CASES = [
    _match_case(
        "field matching: no test cases at all -> no match",
        make_bug("Bug", *IDENT_TAGS), [], ALL_IDENT_FIELDS,
        None,
    ),
    _match_case(
        "field matching: a selected identifying field differs -> tc excluded",
        make_bug("Bug", "Transaction Type - X", "RuleID - 123"),
        [make_tc("TC", "passed", "Transaction Type - Y", "RuleID - 123")],
        {"transaction_type", "rule_id"},
        None,
    ),
    _match_case(
        "field matching: 'broken' status tc is always ignored",
        make_bug("Bug", *IDENT_TAGS),
        [make_tc("TC", "broken", *IDENT_TAGS)],
        ALL_IDENT_FIELDS,
        None,
    ),
    _match_case(
        "field matching: 'skipped' status tc is always ignored",
        make_bug("Bug", *IDENT_TAGS),
        [make_tc("TC", "skipped", *IDENT_TAGS)],
        ALL_IDENT_FIELDS,
        None,
    ),
    _match_case(
        "bug_title field: title differs -> tc excluded",
        make_bug("Exact Name", *IDENT_TAGS),
        [make_tc("Different Name", "passed", *IDENT_TAGS)],
        {"bug_title"},
        None,
    ),
    _match_case(
        "bug_title field: exact title match -> passed tc closes",
        make_bug("Exact Name", *IDENT_TAGS),
        [make_tc("Exact Name", "passed", *IDENT_TAGS)],
        {"bug_title"},
        "close", "Exact Name",
    ),
    _match_case(
        "default match_fields (None): full tag + title match -> closes",
        make_bug("TC Name", *FULL_IDENT_TAGS),
        [make_tc("TC Name", "passed", *FULL_IDENT_TAGS)],
        None,
        "close", "TC Name",
    ),
    _match_case(
        "legacy (failure_tag not selected): passed tc -> close",
        make_bug("Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC", "passed", *IDENT_TAGS)],
        ALL_IDENT_FIELDS,
        "close", "TC",
    ),
    _match_case(
        "legacy (failure_tag not selected): any failed tc -> reopen, tag ignored",
        make_bug("Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC", "failed", *IDENT_TAGS, SOFT1[0])],
        ALL_IDENT_FIELDS,
        "reopen", "TC",
    ),
    _match_case(
        "failure_tag-aware: passed tc -> close",
        make_bug("Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC", "passed", *IDENT_TAGS)],
        ALL_IDENT_PLUS_TAG_FIELDS,
        "close", "TC",
    ),
    _match_case(
        "failure_tag-aware: failed tc with no recognized failure tag -> excluded",
        make_bug("Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC", "failed", *IDENT_TAGS)],
        ALL_IDENT_PLUS_TAG_FIELDS,
        None,
    ),
    _match_case(
        "failure_tag-aware: failed tc reproduces the bug's own tag -> reopen",
        make_bug("Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC", "failed", *IDENT_TAGS, HARD1)],
        ALL_IDENT_PLUS_TAG_FIELDS,
        "reopen", "TC",
    ),
    _match_case(
        "failure_tag-aware: failed tc on a provably-downstream tag -> close",
        make_bug("Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC", "failed", *IDENT_TAGS, SOFT1[0])],
        ALL_IDENT_PLUS_TAG_FIELDS,
        "close", "TC",
    ),
    _match_case(
        "failure_tag-aware: failed tc on an unprovable differing tag -> excluded",
        make_bug("Bug", *IDENT_TAGS, SOFT1[0]),
        [make_tc("TC", "failed", *IDENT_TAGS, HARD1)],
        ALL_IDENT_PLUS_TAG_FIELDS,
        None,
    ),
    _match_case(
        "priority: reopen beats close when the reopen match is listed second",
        make_bug("Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC-Close", "failed", *IDENT_TAGS, SOFT1[0]),
         make_tc("TC-Reopen", "failed", *IDENT_TAGS, HARD1)],
        ALL_IDENT_PLUS_TAG_FIELDS,
        "reopen", "TC-Reopen",
    ),
    _match_case(
        "priority: reopen beats close when the reopen match is listed first",
        make_bug("Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC-Reopen", "failed", *IDENT_TAGS, HARD1),
         make_tc("TC-Close", "failed", *IDENT_TAGS, SOFT1[0])],
        ALL_IDENT_PLUS_TAG_FIELDS,
        "reopen", "TC-Reopen",
    ),
    _match_case(
        "priority (legacy): a failed match beats a passed match",
        make_bug("Bug", *IDENT_TAGS),
        [make_tc("TC-Passed", "passed", *IDENT_TAGS),
         make_tc("TC-Failed", "failed", *IDENT_TAGS)],
        ALL_IDENT_FIELDS,
        "reopen", "TC-Failed",
    ),
    _match_case(
        "priority: close is returned when no match reopens",
        make_bug("Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC-A", "passed", *IDENT_TAGS),
         make_tc("TC-B", "failed", *IDENT_TAGS, SOFT1[0])],
        ALL_IDENT_PLUS_TAG_FIELDS,
        "close", "TC-A",
    ),
    # Mirrors the 5-row "EXAMPLE SCENARIOS" table in the Update QA Bugs help tab
    # (gui/help_tab.py) — keeps the shipped documentation and the real behaviour in sync.
    _match_case(
        "doc example TC-1: failed with no failure tag -> no match (unsafe to touch the bug)",
        make_bug("Example Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC-1", "failed", *IDENT_TAGS)],
        ALL_IDENT_PLUS_TAG_FIELDS,
        None,
    ),
    _match_case(
        "doc example TC-2: failed but Element tag differs -> excluded (not the same bug)",
        make_bug("Example Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC-2", "failed", "Transaction Type - X", "RuleID - 123",
                 "Object - Foo", "Element - DIFFERENT", HARD1)],
        ALL_IDENT_PLUS_TAG_FIELDS,
        None,
    ),
    _match_case(
        "doc example TC-3: failed with the bug's own tag -> reopen",
        make_bug("Example Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC-3", "failed", *IDENT_TAGS, HARD1)],
        ALL_IDENT_PLUS_TAG_FIELDS,
        "reopen", "TC-3",
    ),
    _match_case(
        "doc example TC-4: failed with a different, provably-safe tag -> close",
        make_bug("Example Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC-4", "failed", *IDENT_TAGS, SOFT1[0])],
        ALL_IDENT_PLUS_TAG_FIELDS,
        "close", "TC-4",
    ),
    _match_case(
        "doc example TC-5: passed -> close",
        make_bug("Example Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC-5", "passed", *IDENT_TAGS)],
        ALL_IDENT_PLUS_TAG_FIELDS,
        "close", "TC-5",
    ),
    _match_case(
        "doc example TC-3+4+5 together: TC-3's reopen wins over TC-4/TC-5's close",
        make_bug("Example Bug", *IDENT_TAGS, HARD1),
        [make_tc("TC-3", "failed", *IDENT_TAGS, HARD1),
         make_tc("TC-4", "failed", *IDENT_TAGS, SOFT1[0]),
         make_tc("TC-5", "passed", *IDENT_TAGS)],
        ALL_IDENT_PLUS_TAG_FIELDS,
        "reopen", "TC-3",
    ),
]


@pytest.mark.parametrize(
    "bug, test_cases, match_fields, expected_outcome, expected_tc_name",
    MATCH_CASES,
)
def test_match_bug_to_test_case(bug, test_cases, match_fields, expected_outcome, expected_tc_name):
    result = match_bug_to_test_case(bug, test_cases, match_fields=match_fields)
    actual_outcome = result["qa_outcome"] if result else None
    actual_tc_name = result["test_case_name"] if result else None

    print(f"\n  bug          : title={bug['title']!r} tags={sorted(bug['tags'])}")
    for tc in test_cases:
        print(f"  test case    : name={tc['test_case_name']!r} status={tc['status']} tags={tc['all_tags']}")
    print(f"  match_fields : {match_fields}")
    print(f"  expected     : outcome={expected_outcome!r} matched_tc={expected_tc_name!r}")
    print(f"  actual       : outcome={actual_outcome!r} matched_tc={actual_tc_name!r}")

    assert actual_outcome == expected_outcome, (
        f"expected qa_outcome={expected_outcome!r}, got {actual_outcome!r}"
    )
    if expected_tc_name is not None:
        assert actual_tc_name == expected_tc_name, (
            f"expected matched test case {expected_tc_name!r}, got {actual_tc_name!r}"
        )
