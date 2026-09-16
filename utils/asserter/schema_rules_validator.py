import csv
import io

from utils.asserter.report_row_type import ReportRowType
from utils.common_variables import tc_object, tc_element, tc_error_text, tc_field_value, tc_additional_reference


CRITERIA_COLUMNS = (tc_error_text, tc_object, tc_element, tc_field_value, tc_additional_reference)

REPORT_FIELD_BY_COLUMN = {
    tc_error_text: "Error Text",
    tc_object: "Object Name",
    tc_element: "HAAD Field",
    tc_field_value: "Field Value",
    tc_additional_reference: "Additional Reference",
}


def build_match_grid(report_file, rule_id, expected_type, expected):
    """
    Rows of report_file whose Type matches expected_type and whose RuleID matches,
    each scored against `expected` — a dict of column (a common_variables tc_*
    constant) -> expected value.

    expected_type may be a single ReportRowType, an iterable of them, or None to
    match a row of any type (ERROR/WARNING/NOTIFICATION) — used by "doesn't
    exist" checks, where the rule must be absent regardless of the severity it
    would have fired under.

    A column left blank/None in `expected` is not enforced and defaults to
    matched=True — the same rule whether it's blank because the caller's checkbox
    was off or because the test case's own value was blank.
    """
    if expected_type is None:
        allowed_types = None
    elif isinstance(expected_type, (list, tuple, set, frozenset)):
        allowed_types = expected_type
    else:
        allowed_types = (expected_type,)

    rows = []
    for row_num, element in enumerate(report_file):
        if allowed_types is not None and element.get("Type") not in allowed_types:
            continue
        if str(element.get("RuleID")) != str(rule_id):
            continue

        columns = {}
        for name in CRITERIA_COLUMNS:
            exp = expected.get(name)
            actual = element.get(REPORT_FIELD_BY_COLUMN[name])
            columns[name] = {
                "actual": actual,
                "expected": exp,
                "matched": True if not exp else str(actual) == str(exp),
            }

        rows.append({
            "row_num": row_num,
            "rule_id": element.get("RuleID"),
            "type": element.get("Type"),
            "columns": columns,
            "all_matched": all(c["matched"] for c in columns.values()),
        })
    return rows


def _single_row_grid(found, row_num, row_type, error_text, expected_error_text=None):
    if not found:
        return []
    return [{
        "row_num": row_num,
        "rule_id": None,
        "type": row_type,
        "columns": {tc_error_text: {"actual": error_text, "expected": expected_error_text, "matched": True}},
        "all_matched": True,
    }]


def render_grid_csv(rows):
    """CSV rendering of grid rows, for surfacing the match grid as an Allure attachment."""
    columns_present = [name for name in CRITERIA_COLUMNS if any(name in r["columns"] for r in rows)]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Row#", "RuleID", "Type", "All Matched"] + columns_present)
    for row in rows:
        cells = []
        for name in columns_present:
            col = row["columns"].get(name)
            if col is None:
                cells.append('')
            elif not col['expected']:
                cells.append(f"(actual: {col['actual']}) (not checked)")
            else:
                cells.append(f"(actual: {col['actual']}) (expected: {col['expected']}) {'MATCH' if col['matched'] else 'MISMATCH'}")
        writer.writerow([row["row_num"], row["rule_id"], row["type"], row["all_matched"]] + cells)
    return buf.getvalue()


class RuleMatchGrid:
    """Query surface over the rows build_match_grid (or a special-rule-type validator) produced."""

    def __init__(self, rows):
        self.rows = rows

    def exists(self):
        return any(r["all_matched"] for r in self.rows)

    def matched_rows(self):
        return [r for r in self.rows if r["all_matched"]]

    def count(self):
        return len(self.matched_rows())

    def best_row(self):
        """The row to report/soft-check against: the first full match, or — when
        nothing fully matches — the row closest to matching, so callers still have
        something concrete to compare against and report on."""
        if not self.rows:
            return None
        matched = self.matched_rows()
        if matched:
            return matched[0]
        return max(self.rows, key=lambda r: sum(c["matched"] for c in r["columns"].values()))


class SchemaRulesValidator:

    def __init__(self, rule_id, expected_type, expected):
        self.rule_id = rule_id
        self.expected_type = expected_type
        self.expected = expected

    def validate_strategy(self, report_file) -> RuleMatchGrid:
        rule_type = str(self.rule_id).lower().strip()
        if rule_type == 'schema validation':
            rows = self._validate_schema_in_report(report_file)
        elif rule_type == 'common types':
            rows = self._validate_common_types_in_report(report_file)
        elif rule_type == 'routine reporting':
            # if self.expected.get(tc_error_text) is None:
            #     raise Exception("Error text is None while rule is routine reporting")
            rows = build_match_grid(report_file, '82', ReportRowType.ERROR, self.expected)
        else:
            rows = build_match_grid(report_file, self.rule_id, self.expected_type, self.expected)
        return RuleMatchGrid(rows)

    def _validate_schema_in_report(self, report_file):
        found = False
        error_text = ''
        row_num = -1
        for i, element in enumerate(report_file):
            if element.get("Type") == 'ERROR':
                if str(element.get("Object Name")) == str(self.rule_id):
                    if str(element.get("Transaction")) == str(self.rule_id):
                        if str(element.get("HAAD Field")) == '':
                            found = True
                            error_text = element["Error Text"]
                            row_num = i
                elif str(element.get("Object Name")) != str(self.rule_id) and str(element.get("RuleID")) == '':
                    return []
        return _single_row_grid(found, row_num, 'ERROR', error_text)

    def _validate_common_types_in_report(self, report_file):
        for i, element in enumerate(report_file):
            if element.get("Type") == 'ERROR' and str(element.get("RuleID")) == '':
                if str(element.get("Object Name")) == 'Schema Validation':
                    return []
                return _single_row_grid(True, i, 'ERROR', element["Error Text"])
        return []
