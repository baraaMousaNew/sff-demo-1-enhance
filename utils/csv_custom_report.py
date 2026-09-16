import ast
import base64
import json
import pandas as pd
import os
import re
import warnings
from pathlib import Path
from openpyxl.comments import Comment
from utils.error_validator import ErrorValidator
from utils.env_vars import EnvVar
from utils.execution_mode import ExecutionMode


def _decode_error_report_from_response(response_content):
    """Extracts and decodes the base64 error report from a SOAP response XML string."""
    if not response_content:
        return ""
    try:
        ev = ErrorValidator()
        base64_report = ev.extract_error_report(response_content)
        if not base64_report:
            return ""
        decoded = ev.decode_and_parse_error_report(base64_report)
        return json.dumps(decoded, indent=2)
    except Exception:
        return ""

def _decode_inner_request_content(request_content):
    """Extracts and base64-decodes the fileContent payload embedded in the SOAP request XML."""
    if not request_content:
        return ""
    try:
        match = re.search(r'<(?:\w+:)?fileContent>(.*?)</(?:\w+:)?fileContent>', request_content, re.DOTALL)
        if not match:
            return ""
        return base64.b64decode(match.group(1).strip()).decode('utf-8')
    except Exception:
        return ""

def _extract_error_text_from_parameters(data):
    for param in data.get('parameters', []):
        if param.get('name') == 'soap_test_case':
            try:
                tc = ast.literal_eval(param['value'])
                return tc.get('Error Text', '')
            except Exception:
                pass
    return ''

def _extract_tc_id_from_parameters(data):
    for param in data.get('parameters', []):
        if param.get('name') == 'soap_test_case':
            try:
                tc = ast.literal_eval(param['value'])
                return tc.get('TC ID', '')
            except Exception:
                pass
    return ''

def get_available_rules_summary_columns(execution_mode, assert_error_text_enabled=False, assert_field_additional_enabled=False):
    """Returns the list of available columns based on execution mode and assertion settings"""
    
    s1_name = "System 1"
    s2_name = "System 2"
    
    if execution_mode == ExecutionMode.BOTH_SYSTEMS:
        s1_name = "Legacy System"
        s2_name = "System 2.0"
    elif execution_mode == ExecutionMode.SYSTEM1_BOTH_ENVS:
        s1_name = "Legacy System (Prod)"
        s2_name = "Legacy System (PTE)"
    elif execution_mode == ExecutionMode.SYSTEM1_ONLY:
        s1_name = "Legacy System"
    elif execution_mode == ExecutionMode.SYSTEM2_ONLY:
        s1_name = "System 2.0"

    display_columns = [
        'Rule ID',
        'TC ID',
        'Sheet Name',
        'Scenario Type',
        'Test Case Name',
        'Test Case Status',
        'Request Content',
        'Inner Request Content',
        'Error Text'
    ]
    
    if execution_mode in [ExecutionMode.BOTH_SYSTEMS, ExecutionMode.SYSTEM1_BOTH_ENVS]:
        display_columns.extend([
            f'Response Content {s1_name}',
            f'Response Content {s2_name}',
            f'Decoded Error Report [{s1_name}]',
            f'Decoded Error Report [{s2_name}]',
            f'Row Comparison Difference {s2_name}',
            'Rule Presence Mismatch',
            f'Object/Element Difference {s1_name}',
            f'Object/Element Difference {s2_name}',
        ])
        if assert_error_text_enabled:
            display_columns.extend([
                f'Error Text Difference {s1_name}',
                f'Error Text Difference {s2_name}'
            ])
        if assert_field_additional_enabled:
            display_columns.extend([
                f'Field/Additional Difference {s1_name}',
                f'Field/Additional Difference {s2_name}'
            ])
    else:
        display_columns.extend([
            'Response Content',
            'Decoded Error Report',
            'Object/Element Difference',
        ])
        if assert_error_text_enabled:
            display_columns.extend([
                'Error Text Difference'
            ])
        if assert_field_additional_enabled:
            display_columns.extend([
                'Field/Additional Difference'
            ])

    return display_columns

def generate_all_cases_flat(allure_results_dir):
    """
    Returns a flat DataFrame with one row per test case across ALL statuses.
    Used when no failure-filter criteria are selected (show everything).
    """
    execution_mode = os.environ.get(EnvVar.SOAP_EXECUTION_MODE, ExecutionMode.UNKNOWN)

    s1_name = "System 1"
    s2_name = "System 2"
    if execution_mode == ExecutionMode.BOTH_SYSTEMS:
        s1_name = "Legacy System"
        s2_name = "System 2.0"
    elif execution_mode == ExecutionMode.SYSTEM1_BOTH_ENVS:
        s1_name = "Legacy System (Prod)"
        s2_name = "Legacy System (PTE)"
    elif execution_mode == ExecutionMode.SYSTEM1_ONLY:
        s1_name = "Legacy System"
    elif execution_mode == ExecutionMode.SYSTEM2_ONLY:
        s1_name = "System 2.0"

    results = []
    for file in Path(allure_results_dir).glob('*-result.json'):
        with open(file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue

        tags = [l.get('value', '') for l in data.get('labels', []) if l.get('name') == 'tag' and l.get('value')]
        tags_lower = [t.lower() for t in tags]

        rule_id_tag = next((t for t in tags if t.startswith('RuleID - ')), None)
        rule_id = rule_id_tag[len('RuleID - '):].strip() if rule_id_tag else 'Unknown'

        sheet_tag = next((t for t in tags if t.startswith('Sheet - ')), None)
        sheet_name = sheet_tag[len('Sheet - '):].strip() if sheet_tag else ''

        scenario_type_tag = next((t for t in tags if t.startswith('Scenario Type - ')), None)
        scenario_type = scenario_type_tag[len('Scenario Type - '):].strip().lower() if scenario_type_tag else ''

        is_positive = (scenario_type == 'positive')
        is_negative = (scenario_type == 'negative')

        test_case_name = data.get('name', 'Unknown')
        status = data.get('status', 'unknown')
        tc_id = _extract_tc_id_from_parameters(data)

        is_s1_trigger_failure          = 'system 1 failure' in tags_lower
        is_s2_trigger_failure          = 'system 2 failure' in tags_lower
        is_s1_error_text_failure       = 'system 1 error text failure' in tags_lower
        is_s2_error_text_failure       = 'system 2 error text failure' in tags_lower
        is_s1_object_element_failure   = 'system 1 object/element failure' in tags_lower
        is_s2_object_element_failure   = 'system 2 object/element failure' in tags_lower
        is_s1_field_additional_failure = 'system 1 field/additional failure' in tags_lower
        is_s2_field_additional_failure = 'system 2 field/additional failure' in tags_lower
        is_dual_system_failure         = 'dual system failure' in tags_lower
        is_dual_error_text_failure     = 'dual system error text failure' in tags_lower
        is_dual_row_failure            = 'dual system row failure' in tags_lower
        is_dual_mismatch_failure       = 'dual system mismatch failure' in tags_lower

        def find_attachments_recursive(steps, target_name_part):
            found = []
            for step in steps:
                for att in step.get('attachments', []):
                    if target_name_part in att.get('name', ''):
                        found.append(att.get('source'))
                found.extend(find_attachments_recursive(step.get('steps', []), target_name_part))
            return found

        req_sources = find_attachments_recursive(data.get('steps', []), 'e86ab1')
        for att in data.get('attachments', []):
            if 'e86ab1' in att.get('name', ''):
                req_sources.append(att.get('source'))
        request_content = get_attachment_content(allure_results_dir, req_sources[-1]) if req_sources else ""
        inner_request_content = _decode_inner_request_content(request_content)

        resp_s1_sources = find_attachments_recursive(data.get('steps', []), '33a829')
        for att in data.get('attachments', []):
            if '33a829' in att.get('name', ''):
                resp_s1_sources.append(att.get('source'))
        response_s1_content = get_attachment_content(allure_results_dir, resp_s1_sources[-1]) if resp_s1_sources else ""

        resp_s2_sources = find_attachments_recursive(data.get('steps', []), 'a4b5d4')
        for att in data.get('attachments', []):
            if 'a4b5d4' in att.get('name', ''):
                resp_s2_sources.append(att.get('source'))
        response_s2_content = get_attachment_content(allure_results_dir, resp_s2_sources[-1]) if resp_s2_sources else ""

        decoded_s1_error_report = _decode_error_report_from_response(response_s1_content)
        decoded_s2_error_report = _decode_error_report_from_response(response_s2_content)

        row_diff_sources = find_attachments_recursive(data.get('steps', []), 'e8f3d2')
        for att in data.get('attachments', []):
            if 'e8f3d2' in att.get('name', ''):
                row_diff_sources.append(att.get('source'))
        row_comparison_diff = "\n----------------------------------------\n".join(
            get_attachment_content(allure_results_dir, s) for s in row_diff_sources if s
        )

        presence_mismatch_sources = find_attachments_recursive(data.get('steps', []), '3a8e6c')
        for att in data.get('attachments', []):
            if '3a8e6c' in att.get('name', ''):
                presence_mismatch_sources.append(att.get('source'))
        presence_mismatch_content = "\n----------------------------------------\n".join(
            get_attachment_content(allure_results_dir, s) for s in presence_mismatch_sources if s
        )

        # Object/Element diff - b3d91c
        # Route by attachment name ("system 1" / "system 2") so dual-system cases are split correctly.
        def _collect_obj_diffs(steps):
            s1, s2 = [], []
            for step in steps:
                for att in step.get('attachments', []):
                    if 'b3d91c' in att.get('name', ''):
                        bucket = s1 if 'system 1' in att.get('name', '').lower() else s2
                        bucket.append(att.get('source'))
                sub1, sub2 = _collect_obj_diffs(step.get('steps', []))
                s1.extend(sub1); s2.extend(sub2)
            return s1, s2

        _obj_s1_srcs, _obj_s2_srcs = _collect_obj_diffs(data.get('steps', []))
        for att in data.get('attachments', []):
            if 'b3d91c' in att.get('name', ''):
                ((_obj_s1_srcs if 'system 1' in att.get('name', '').lower() else _obj_s2_srcs)
                 .append(att.get('source')))

        SEP = "\n----------------------------------------\n"
        obj_s1_diff = SEP.join(get_attachment_content(allure_results_dir, s) for s in _obj_s1_srcs if s)
        obj_s2_diff = SEP.join(get_attachment_content(allure_results_dir, s) for s in _obj_s2_srcs if s)

        # Field/Additional diff - c7e592
        # Route by attachment name ("system 1" / "system 2") so dual-system cases are split correctly.
        def _collect_field_additional_diffs(steps):
            s1, s2 = [], []
            for step in steps:
                for att in step.get('attachments', []):
                    if 'c7e592' in att.get('name', ''):
                        bucket = s1 if 'system 1' in att.get('name', '').lower() else s2
                        bucket.append(att.get('source'))
                sub1, sub2 = _collect_field_additional_diffs(step.get('steps', []))
                s1.extend(sub1); s2.extend(sub2)
            return s1, s2

        _fa_s1_srcs, _fa_s2_srcs = _collect_field_additional_diffs(data.get('steps', []))
        for att in data.get('attachments', []):
            if 'c7e592' in att.get('name', ''):
                ((_fa_s1_srcs if 'system 1' in att.get('name', '').lower() else _fa_s2_srcs)
                 .append(att.get('source')))

        field_additional_s1_diff = SEP.join(get_attachment_content(allure_results_dir, s) for s in _fa_s1_srcs if s)
        field_additional_s2_diff = SEP.join(get_attachment_content(allure_results_dir, s) for s in _fa_s2_srcs if s)

        error_text_content = _extract_error_text_from_parameters(data)

        single_response = response_s2_content if execution_mode == ExecutionMode.SYSTEM2_ONLY else response_s1_content
        single_decoded = decoded_s2_error_report if execution_mode == ExecutionMode.SYSTEM2_ONLY else decoded_s1_error_report

        results.append({
            'Rule ID': rule_id,
            'TC ID': tc_id,
            'Sheet Name': sheet_name,
            'Scenario Type': scenario_type,
            'Test Case Name': test_case_name,
            'Test Case Status': status,
            'Request Content': request_content,
            'Inner Request Content': inner_request_content,
            'Error Text': error_text_content,
            'Response Content': single_response,
            f'Response Content {s1_name}': response_s1_content,
            f'Response Content {s2_name}': response_s2_content,
            'Decoded Error Report': single_decoded,
            f'Decoded Error Report [{s1_name}]': decoded_s1_error_report,
            f'Decoded Error Report [{s2_name}]': decoded_s2_error_report,
            f'Row Comparison Difference {s2_name}': row_comparison_diff,
            'Rule Presence Mismatch': presence_mismatch_content,
            'Object/Element Difference': obj_s1_diff,
            f'Object/Element Difference {s1_name}': obj_s1_diff,
            f'Object/Element Difference {s2_name}': obj_s2_diff,
            'Field/Additional Difference': field_additional_s1_diff,
            f'Field/Additional Difference {s1_name}': field_additional_s1_diff,
            f'Field/Additional Difference {s2_name}': field_additional_s2_diff,
            'status': status,
            'is_s1_trigger_failure': is_s1_trigger_failure,
            'is_s2_trigger_failure': is_s2_trigger_failure,
            'is_s1_error_text_failure': is_s1_error_text_failure,
            'is_s2_error_text_failure': is_s2_error_text_failure,
            'is_s1_object_element_failure': is_s1_object_element_failure,
            'is_s2_object_element_failure': is_s2_object_element_failure,
            'is_s1_field_additional_failure': is_s1_field_additional_failure,
            'is_s2_field_additional_failure': is_s2_field_additional_failure,
            'is_dual_system_failure': is_dual_system_failure,
            'is_dual_error_text_failure': is_dual_error_text_failure,
            'is_dual_row_failure': is_dual_row_failure,
            'is_dual_mismatch_failure': is_dual_mismatch_failure,
        })

    return pd.DataFrame(results) if results else pd.DataFrame()

def generate_default_statistics(allure_results_dir):
    """
    Generates a DataFrame with one row per Rule ID containing:
    Rule ID, Total Cases, Pass Cases, Fail Cases on Old System,
    Fail Cases on New System, Completion %

    Failure attribution:
    - Old System: system 1 failure OR system 1 error text failure (excluding dual)
    - New System: system 2 failure OR system 2 error text failure
                  OR dual system failure OR dual system error text failure
    """
    results = []
    for file in Path(allure_results_dir).glob('*-result.json'):
        with open(file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue

        tags = [l.get('value', '') for l in data.get('labels', []) if l.get('name') == 'tag' and l.get('value')]
        tags_lower = [t.lower() for t in tags]

        rule_id_tag = next((t for t in tags if t.startswith('RuleID - ')), None)
        rule_id = rule_id_tag[len('RuleID - '):].strip() if rule_id_tag else 'Unknown'
        status = data.get('status', 'unknown')

        is_dual              = 'dual system failure' in tags_lower or 'dual system error text failure' in tags_lower
        is_s1_failure        = ('system 1 failure' in tags_lower or 'system 1 error text failure' in tags_lower or 'system 1 object/element failure' in tags_lower or 'system 1 field/additional failure' in tags_lower) and not is_dual
        is_s2_failure        = 'system 2 failure' in tags_lower or 'system 2 error text failure' in tags_lower or 'system 2 object/element failure' in tags_lower or 'system 2 field/additional failure' in tags_lower or is_dual \
                               or 'dual system row failure' in tags_lower \
                               or 'dual system mismatch failure' in tags_lower

        results.append({
            'Rule ID': rule_id,
            'status': status,
            'is_s1_failure': is_s1_failure,
            'is_s2_failure': is_s2_failure,
        })

    if not results:
        return pd.DataFrame(columns=[
            'Rule ID', 'Total Cases', 'Pass Cases',
            'Fail Cases on Old System', 'Fail Cases on New System', 'Completion %'
        ])

    df = pd.DataFrame(results)
    grouped = df.groupby('Rule ID')

    rows = []
    for rule_id, group in grouped:
        total   = len(group)
        passed  = len(group[group['status'] == 'passed'])
        failed  = group[group['status'] == 'failed']

        fail_old = len(failed[failed['is_s1_failure']])
        fail_new = len(failed[failed['is_s2_failure']])
        completion = round((passed / total) * 100, 2) if total > 0 else 0.0

        rows.append({
            'Rule ID': rule_id,
            'Total Cases': total,
            'Pass Cases': passed,
            'Fail Cases on Old System': fail_old,
            'Fail Cases on New System': fail_new,
            'Completion %': completion
        })

    return pd.DataFrame(rows, columns=[
        'Rule ID', 'Total Cases', 'Pass Cases',
        'Fail Cases on Old System', 'Fail Cases on New System', 'Completion %'
    ])


def generate_transactions_default_statistics(allure_results_dir):
    """
    Generates a DataFrame with one row per Transaction Type containing:
    Transaction Type, Total Cases, Pass Cases, Fail Cases on Old System,
    Fail Cases on New System, Completion %

    Failure attribution mirrors generate_default_statistics:
    - Old System: system 1 failure OR system 1 error text failure (excluding dual)
    - New System: system 2 failure OR system 2 error text failure
                  OR dual system failure OR dual system error text failure
    """
    results = []
    for file in Path(allure_results_dir).glob('*-result.json'):
        with open(file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue

        tags = [l.get('value', '') for l in data.get('labels', []) if l.get('name') == 'tag' and l.get('value')]
        tags_lower = [t.lower() for t in tags]

        txn_type_tag = next((t for t in tags if t.lower().startswith('sheet - ')), None)
        txn_type = txn_type_tag[8:].strip() if txn_type_tag else 'Unknown'

        status = data.get('status', 'unknown')

        is_dual       = 'dual system failure' in tags_lower or 'dual system error text failure' in tags_lower
        is_s1_failure = ('system 1 failure' in tags_lower or 'system 1 error text failure' in tags_lower) and not is_dual
        is_s2_failure = 'system 2 failure' in tags_lower or 'system 2 error text failure' in tags_lower or is_dual \
                        or 'dual system row failure' in tags_lower \
                        or 'dual system mismatch failure' in tags_lower

        results.append({
            'Transaction Type': txn_type,
            'status': status,
            'is_s1_failure': is_s1_failure,
            'is_s2_failure': is_s2_failure,
        })

    if not results:
        return pd.DataFrame(columns=[
            'Transaction Type', 'Total Cases', 'Pass Cases',
            'Fail Cases on Old System', 'Fail Cases on New System', 'Completion %'
        ])

    df = pd.DataFrame(results)
    grouped = df.groupby('Transaction Type')

    rows = []
    for txn_type, group in grouped:
        total   = len(group)
        passed  = len(group[group['status'] == 'passed'])
        failed  = group[group['status'] == 'failed']

        fail_old = len(failed[failed['is_s1_failure']])
        fail_new = len(failed[failed['is_s2_failure']])
        completion = round((passed / total) * 100, 2) if total > 0 else 0.0

        rows.append({
            'Transaction Type': txn_type,
            'Total Cases': total,
            'Pass Cases': passed,
            'Fail Cases on Old System': fail_old,
            'Fail Cases on New System': fail_new,
            'Completion %': completion
        })

    return pd.DataFrame(rows, columns=[
        'Transaction Type', 'Total Cases', 'Pass Cases',
        'Fail Cases on Old System', 'Fail Cases on New System', 'Completion %'
    ])


def generate_custom_combined_report(allure_results_dir, output_excel, sheets_config, assert_error_text_enabled=False, assert_field_additional_enabled=False):
    """
    Generates a combined custom report based on user configuration.
    """
    print(f"Generating custom report with config: {sheets_config}")
    
    # Generate both views once:
    # - full_df: aggregated failure view (used when failure criteria are selected)
    # - flat_df: one row per test case, all statuses (used when no failure criteria)
    full_df = generate_rules_summary(allure_results_dir)
    flat_df = generate_all_cases_flat(allure_results_dir)
    
    execution_mode = os.environ.get(EnvVar.SOAP_EXECUTION_MODE, ExecutionMode.SYSTEM1_ONLY)
    
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        if not sheets_config:
            # Fallback if empty config
            full_df_clean = full_df.drop(columns=['status', 'is_s1_error_text_failure', 'is_s2_error_text_failure', 'is_s1_object_element_failure', 'is_s2_object_element_failure', 'is_s1_field_additional_failure', 'is_s2_field_additional_failure'], errors='ignore')
            full_df_clean.to_excel(writer, sheet_name='Rules Summary', index=False)
        else:
            for sheet_conf in sheets_config:
                sheet_name = sheet_conf.get('name', 'Sheet')
                selected_columns = sheet_conf.get('columns', [])
                criteria = sheet_conf.get('criteria', [])

                # ── Default Statistics: special exclusive criteria ──────────────
                if 'Default Statistics' in criteria:
                    stats_df = generate_default_statistics(allure_results_dir)
                    if not stats_df.empty:
                        stats_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    else:
                        pd.DataFrame(columns=['Rule ID', 'Total Cases', 'Pass Cases', 'Fail Cases on Old System', 'Fail Cases on New System', 'Completion %']).to_excel(
                            writer, sheet_name=sheet_name, index=False
                        )
                    try:
                        workbook = writer.book
                        if sheet_name in workbook.sheetnames:
                            worksheet = workbook[sheet_name]
                            worksheet['A1'].comment = Comment("Default Statistics Report", "System")
                    except Exception as e:
                        print(f"Warning: Could not add comment to {sheet_name}: {e}")
                    continue  # skip all other column/criteria logic for this sheet

                # ── Transactions Default Statistics ────────────────────────────
                if 'Transactions Default Statistics' in criteria:
                    stats_df = generate_transactions_default_statistics(allure_results_dir)
                    if not stats_df.empty:
                        stats_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    else:
                        pd.DataFrame(columns=['Transaction Type', 'Total Cases', 'Pass Cases', 'Fail Cases on Old System', 'Fail Cases on New System', 'Completion %']).to_excel(
                            writer, sheet_name=sheet_name, index=False
                        )
                    try:
                        workbook = writer.book
                        if sheet_name in workbook.sheetnames:
                            worksheet = workbook[sheet_name]
                            worksheet['A1'].comment = Comment("Transactions Default Statistics Report", "System")
                    except Exception as e:
                        print(f"Warning: Could not add comment to {sheet_name}: {e}")
                    continue  # skip all other column/criteria logic for this sheet
                # ──────────────────────────────────────────────────────────────

                # Row Filtering Logic based on criteria
                # Separate modifier criteria from standard failure-filter criteria
                apply_group_by = 'Group By Criteria' in criteria
                apply_no_failure = 'No Failure' in criteria
                apply_broken = 'Broken' in criteria
                old_criteria = [c for c in criteria if c not in ('Group By Criteria', 'No Failure', 'Broken')]

                if old_criteria or apply_no_failure or apply_broken:
                    # Use flat_df when 'No Failure' or 'Broken' is selected so all statuses
                    # are available in the same source. Otherwise use the aggregated full_df.
                    source_df = flat_df if (apply_no_failure or apply_broken) else full_df
                    criteria_mask = pd.Series([False] * len(source_df), dtype=bool)

                    s1_name = "System 1"
                    s2_name = "System 2"
                    if execution_mode == ExecutionMode.BOTH_SYSTEMS:
                        s1_name = "Legacy System"
                        s2_name = "System 2.0"
                    elif execution_mode == ExecutionMode.SYSTEM1_BOTH_ENVS:
                        s1_name = "Legacy System (Prod)"
                        s2_name = "Legacy System (PTE)"
                    elif execution_mode == ExecutionMode.SYSTEM1_ONLY:
                        s1_name = "Legacy System"
                    elif execution_mode == ExecutionMode.SYSTEM2_ONLY:
                        s1_name = "System 2.0"

                    if f'{s1_name} Failure' in old_criteria:
                        criteria_mask |= source_df['is_s1_trigger_failure']
                    if f'{s2_name} Failure' in old_criteria:
                        criteria_mask |= source_df['is_s2_trigger_failure']
                    if f'{s1_name} Error Text Failure' in old_criteria:
                        criteria_mask |= source_df['is_s1_error_text_failure']
                    if f'{s2_name} Error Text Failure' in old_criteria:
                        criteria_mask |= source_df['is_s2_error_text_failure']
                    if f'{s1_name} Object/Element Failure' in old_criteria:
                        criteria_mask |= source_df['is_s1_object_element_failure']
                    if f'{s2_name} Object/Element Failure' in old_criteria:
                        criteria_mask |= source_df['is_s2_object_element_failure']
                    if f'{s1_name} Field/Additional Failure' in old_criteria:
                        criteria_mask |= source_df['is_s1_field_additional_failure']
                    if f'{s2_name} Field/Additional Failure' in old_criteria:
                        criteria_mask |= source_df['is_s2_field_additional_failure']
                    if 'System Comparison Failure' in old_criteria:
                        criteria_mask |= source_df['is_dual_system_failure']
                    if 'System Comparison Error Text Failure' in old_criteria:
                        criteria_mask |= source_df['is_dual_error_text_failure']
                    if 'System Row Comparison Failure' in old_criteria:
                        criteria_mask |= source_df['is_dual_row_failure']
                    if 'System Mismatch Failure' in old_criteria:
                        criteria_mask |= source_df['is_dual_mismatch_failure']

                    failure_mask = criteria_mask & (source_df['status'] == 'failed')
                    pass_mask = (source_df['status'] == 'passed') if apply_no_failure else pd.Series([False] * len(source_df), dtype=bool)
                    broken_mask = (source_df['status'] == 'broken') if apply_broken else pd.Series([False] * len(source_df), dtype=bool)
                    keep_mask = failure_mask | pass_mask | broken_mask
                else:
                    # No failure criteria and no 'No Failure' → show ALL executed cases (flat view)
                    source_df = flat_df
                    keep_mask = pd.Series([True] * len(source_df))

                # Filter columns against the chosen source
                valid_columns = [col for col in selected_columns if col in source_df.columns]
                filtered_df = source_df[keep_mask]
                
                if not valid_columns:
                    # Fallback if no columns matched
                    valid_columns = ['Rule ID', 'Test Case Name', 'Test Case Status']
                    available_fallback = [c for c in valid_columns if c in filtered_df.columns]
                    if available_fallback:
                        sheet_df = filtered_df[available_fallback]
                    else:
                        sheet_df = pd.DataFrame(columns=available_fallback)
                elif apply_group_by:
                    # Group By Criteria: group filtered rows by selected columns, prepend Count
                    group_cols = [col for col in valid_columns if col in filtered_df.columns]
                    if group_cols and not filtered_df.empty:
                        grouped = (
                            filtered_df
                            .groupby(group_cols)
                            .size()
                            .reset_index(name='Count')
                        )
                        sheet_df = grouped[['Count'] + group_cols]
                    else:
                        sheet_df = pd.DataFrame(columns=['Count'] + valid_columns)
                else:
                    sheet_df = filtered_df[valid_columns]
                
                # Write to Excel
                if not sheet_df.empty:
                    sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
                else:
                    # Create empty df with columns to ensure sheet exists
                    fallback_cols = (['Count'] + valid_columns) if apply_group_by else valid_columns
                    pd.DataFrame(columns=fallback_cols).to_excel(writer, sheet_name=sheet_name, index=False)

                # Add tooltip (comment)
                try:
                    workbook = writer.book
                    if sheet_name in workbook.sheetnames:
                        worksheet = workbook[sheet_name]
                        comment_text = "Custom Generated Report"
                        if 'Rule ID' in valid_columns:
                            comment_text += "\nIncludes Rule Validation Data."
                        worksheet['A1'].comment = Comment(comment_text, "System")
                except Exception as e:
                    print(f"Warning: Could not add comment to {sheet_name}: {e}")
        
        # Safety check: Ensure at least one sheet exists and is visible
        if not writer.book.sheetnames:
             print("WARNING: No sheets found in workbook. Creating fallback sheet.")
             pd.DataFrame({'Info': ['No data generated for the selected criteria and columns.']}).to_excel(writer, sheet_name='Rules Summary', index=False)
        
        # Ensure at least one sheet is visible
        visible_sheets = [s for s in writer.book.worksheets if s.sheet_state == 'visible']
        if not visible_sheets:
            print("WARNING: No visible sheets found. Forcing visibility on the first sheet.")
            if writer.book.worksheets:
                writer.book.worksheets[0].sheet_state = 'visible'

    print(f"Combined custom report generated at {output_excel}")

def get_attachment_content(allure_results_dir, source_file):
    """Reads attachment content from source file"""
    try:
        path = Path(allure_results_dir) / source_file
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception:
        pass
    return ""

def generate_rules_summary(allure_results_dir):
    execution_mode = os.environ.get(EnvVar.SOAP_EXECUTION_MODE, ExecutionMode.UNKNOWN)
    
    s1_name = "System 1"
    s2_name = "System 2"
    
    if execution_mode == ExecutionMode.BOTH_SYSTEMS:
        s1_name = "Legacy System"
        s2_name = "System 2.0"
    elif execution_mode == ExecutionMode.SYSTEM1_BOTH_ENVS:
        s1_name = "Legacy System (Prod)"
        s2_name = "Legacy System (PTE)"
    elif execution_mode == ExecutionMode.SYSTEM1_ONLY:
        s1_name = "Legacy System"
    elif execution_mode == ExecutionMode.SYSTEM2_ONLY:
        s1_name = "System 2.0"
        
    results = []
    
    # Iterate over all JSON files in the allure results directory
    for file in Path(allure_results_dir).glob('*-result.json'):
        with open(file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue
                
        # Extract tags
        tags = [l.get('value', '') for l in data.get('labels', []) if l.get('name') == 'tag' and l.get('value')]
        tags_lower = [t.lower() for t in tags]
        
        # Determine Rule ID from explicit prefix tag
        rule_id_tag = next((t for t in tags if t.startswith('RuleID - ')), None)
        rule_id = rule_id_tag[len('RuleID - '):].strip() if rule_id_tag else 'Unknown'

        sheet_tag = next((t for t in tags if t.startswith('Sheet - ')), None)
        sheet_name = sheet_tag[len('Sheet - '):].strip() if sheet_tag else ''

        # Determine scenario type from explicit prefix tag
        scenario_type_tag = next((t for t in tags if t.startswith('Scenario Type - ')), None)
        scenario_type = scenario_type_tag[len('Scenario Type - '):].strip().lower() if scenario_type_tag else ''
        
        is_positive = (scenario_type == 'positive')
        is_negative = (scenario_type == 'negative')

        test_case_name = data.get('name', 'Unknown')
        status = data.get('status', 'unknown')
        error_text = _extract_error_text_from_parameters(data)
        tc_id = _extract_tc_id_from_parameters(data)

        # Specific failure checks
        is_s1_error_text_failure     = 'system 1 error text failure' in tags_lower
        is_s2_error_text_failure     = 'system 2 error text failure' in tags_lower
        is_s1_object_element_failure = 'system 1 object/element failure' in tags_lower
        is_s2_object_element_failure = 'system 2 object/element failure' in tags_lower
        is_s1_field_additional_failure = 'system 1 field/additional failure' in tags_lower
        is_s2_field_additional_failure = 'system 2 field/additional failure' in tags_lower
        is_s1_trigger_failure        = 'system 1 failure' in tags_lower
        is_s2_trigger_failure        = 'system 2 failure' in tags_lower
        is_dual_system_failure       = 'dual system failure' in tags_lower
        is_dual_error_text_failure   = 'dual system error text failure' in tags_lower
        is_dual_row_failure          = 'dual system row failure' in tags_lower
        is_dual_mismatch_failure     = 'dual system mismatch failure' in tags_lower

        # --- Attachment Extraction Logic ---
        
        def find_attachments_recursive(steps, target_name_part):
            found = []
            for step in steps:
                for att in step.get('attachments', []):
                    if target_name_part in att.get('name', ''):
                        found.append(att.get('source'))
                found.extend(find_attachments_recursive(step.get('steps', []), target_name_part))
            return found

        # 1. Error Text Diffs (392130)
        s1_diffs = []
        s2_diffs = []
        generic_diffs = []
        
        diff_sources = find_attachments_recursive(data.get('steps', []), '392130')
        for att in data.get('attachments', []):
             if '392130' in att.get('name', ''):
                 diff_sources.append(att.get('source'))
        
        for src in list(set(diff_sources)):
            content = get_attachment_content(allure_results_dir, src)
            if not content: continue
            
            assigned = False
            if is_s1_error_text_failure:
                s1_diffs.append(content)
                assigned = True
            
            if is_s2_error_text_failure:
                s2_diffs.append(content)
                assigned = True
                
            if not assigned:
                generic_diffs.append(content)

        # 2. Request XML (e86ab1)
        req_sources = find_attachments_recursive(data.get('steps', []), 'e86ab1')
        for att in data.get('attachments', []):
             if 'e86ab1' in att.get('name', ''):
                 req_sources.append(att.get('source'))
        request_content = get_attachment_content(allure_results_dir, req_sources[-1]) if req_sources else ""
        inner_request_content = _decode_inner_request_content(request_content)

        # 3. Response (33a829)
        resp_sources = find_attachments_recursive(data.get('steps', []), '33a829')
        for att in data.get('attachments', []):
             if '33a829' in att.get('name', ''):
                 resp_sources.append(att.get('source'))
        response_content = get_attachment_content(allure_results_dir, resp_sources[-1]) if resp_sources else ""
        


        # 5. Response Split (33a829, a4b5d4)
        # System 1 - 33a829
        resp_s1_sources = find_attachments_recursive(data.get('steps', []), '33a829')
        for att in data.get('attachments', []):
             if '33a829' in att.get('name', ''):
                 resp_s1_sources.append(att.get('source'))
        response_s1_content = get_attachment_content(allure_results_dir, resp_s1_sources[-1]) if resp_s1_sources else ""

        # System 2 - a4b5d4
        resp_s2_sources = find_attachments_recursive(data.get('steps', []), 'a4b5d4')
        for att in data.get('attachments', []):
             if 'a4b5d4' in att.get('name', ''):
                 resp_s2_sources.append(att.get('source'))
        response_s2_content = get_attachment_content(allure_results_dir, resp_s2_sources[-1]) if resp_s2_sources else ""

        decoded_s1_error_report = _decode_error_report_from_response(response_s1_content)
        decoded_s2_error_report = _decode_error_report_from_response(response_s2_content)

        single_rs_response = response_s2_content if execution_mode == ExecutionMode.SYSTEM2_ONLY else response_s1_content
        single_rs_decoded = decoded_s2_error_report if execution_mode == ExecutionMode.SYSTEM2_ONLY else decoded_s1_error_report

        # Row comparison diff - e8f3d2
        row_diff_sources = find_attachments_recursive(data.get('steps', []), 'e8f3d2')
        for att in data.get('attachments', []):
            if 'e8f3d2' in att.get('name', ''):
                row_diff_sources.append(att.get('source'))
        row_comparison_diff = "\n----------------------------------------\n".join(
            get_attachment_content(allure_results_dir, s) for s in row_diff_sources if s
        )

        # Rule presence mismatch - 3a8e6c
        presence_mismatch_sources = find_attachments_recursive(data.get('steps', []), '3a8e6c')
        for att in data.get('attachments', []):
            if '3a8e6c' in att.get('name', ''):
                presence_mismatch_sources.append(att.get('source'))
        presence_mismatch_content = "\n----------------------------------------\n".join(
            get_attachment_content(allure_results_dir, s) for s in presence_mismatch_sources if s
        )

        # Object/Element diff - b3d91c
        # Route by attachment name so System 1 and System 2 diffs are kept separate.
        def _collect_obj_diffs_rs(steps):
            s1, s2 = [], []
            for step in steps:
                for att in step.get('attachments', []):
                    if 'b3d91c' in att.get('name', ''):
                        bucket = s1 if 'system 1' in att.get('name', '').lower() else s2
                        bucket.append(att.get('source'))
                sub1, sub2 = _collect_obj_diffs_rs(step.get('steps', []))
                s1.extend(sub1); s2.extend(sub2)
            return s1, s2

        _obj_s1_srcs, _obj_s2_srcs = _collect_obj_diffs_rs(data.get('steps', []))
        for att in data.get('attachments', []):
            if 'b3d91c' in att.get('name', ''):
                ((_obj_s1_srcs if 'system 1' in att.get('name', '').lower() else _obj_s2_srcs)
                 .append(att.get('source')))

        # Field/Additional diff - c7e592
        # Route by attachment name so System 1 and System 2 diffs are kept separate.
        def _collect_field_additional_diffs_rs(steps):
            s1, s2 = [], []
            for step in steps:
                for att in step.get('attachments', []):
                    if 'c7e592' in att.get('name', ''):
                        bucket = s1 if 'system 1' in att.get('name', '').lower() else s2
                        bucket.append(att.get('source'))
                sub1, sub2 = _collect_field_additional_diffs_rs(step.get('steps', []))
                s1.extend(sub1); s2.extend(sub2)
            return s1, s2

        _fa_s1_srcs, _fa_s2_srcs = _collect_field_additional_diffs_rs(data.get('steps', []))
        for att in data.get('attachments', []):
            if 'c7e592' in att.get('name', ''):
                ((_fa_s1_srcs if 'system 1' in att.get('name', '').lower() else _fa_s2_srcs)
                 .append(att.get('source')))

        results.append({
            'rule_id': rule_id,
            'tc_id': tc_id,
            'sheet_name': sheet_name,
            'scenario_type': scenario_type,
            'test_case_name': test_case_name,
            'status': status,
            'error_text': error_text,
            'is_positive': is_positive,
            'is_negative': is_negative,
            'is_s1_error_text_failure': is_s1_error_text_failure,
            'is_s2_error_text_failure': is_s2_error_text_failure,
            'is_s1_object_element_failure': is_s1_object_element_failure,
            'is_s2_object_element_failure': is_s2_object_element_failure,
            'is_s1_field_additional_failure': is_s1_field_additional_failure,
            'is_s2_field_additional_failure': is_s2_field_additional_failure,
            'is_s1_trigger_failure': is_s1_trigger_failure,
            'is_s2_trigger_failure': is_s2_trigger_failure,
            'is_dual_system_failure': is_dual_system_failure,
            'is_dual_error_text_failure': is_dual_error_text_failure,
            'is_dual_row_failure': is_dual_row_failure,
            'is_dual_mismatch_failure': is_dual_mismatch_failure,
            's1_diffs': s1_diffs,
            's2_diffs': s2_diffs,
            'generic_diffs': generic_diffs,
            'obj_s1_diffs': _obj_s1_srcs,
            'obj_s2_diffs': _obj_s2_srcs,
            'field_additional_s1_diffs': _fa_s1_srcs,
            'field_additional_s2_diffs': _fa_s2_srcs,
            'request_content': request_content,
            'inner_request_content': inner_request_content,
            'response_content': single_rs_response,
            'response_s1_content': response_s1_content,
            'response_s2_content': response_s2_content,
            'decoded_s1_error_report': decoded_s1_error_report,
            'decoded_s2_error_report': decoded_s2_error_report,
            'row_comparison_diff': row_comparison_diff,
            'presence_mismatch': presence_mismatch_content,
            'count': 1
        })
        
    df = pd.DataFrame(results)
    
    _FLAG_COLUMNS = [
        'status', 'is_s1_error_text_failure', 'is_s2_error_text_failure',
        'is_s1_object_element_failure', 'is_s2_object_element_failure',
        'is_s1_field_additional_failure', 'is_s2_field_additional_failure',
        'is_s1_trigger_failure', 'is_s2_trigger_failure',
        'is_dual_system_failure', 'is_dual_error_text_failure',
        'is_dual_row_failure', 'is_dual_mismatch_failure',
    ]

    if df.empty:
        empty = pd.DataFrame(columns=get_available_rules_summary_columns(execution_mode) + _FLAG_COLUMNS)
        for col in _FLAG_COLUMNS:
            empty[col] = pd.Series(dtype=bool)
        return empty

    # Aggregation
    def aggregate_rule(x):
        total_positive = x['is_positive'].sum()
        passed_positive = len(x[(x['status'] == 'passed') & (x['is_positive'])])
        
        total_negative = x['is_negative'].sum()
        passed_negative = len(x[(x['status'] == 'passed') & (x['is_negative'])])
        
        common_data = {
            'Total Cases': len(x),
            'Total Positive Cases Passed': f"{passed_positive}/{total_positive}",
            'Total Negative Cases Passed': f"{passed_negative}/{total_negative}",
            'Total Broken Cases': len(x[x['status'] == 'broken']),
            'Cases Failed for Error Text Issues on System 1': len(x[(x['status'] == 'failed') & (x['is_s1_error_text_failure'])]),
            'Cases Failed for Error Text Issues on System 2': len(x[(x['status'] == 'failed') & (x['is_s2_error_text_failure'])]),
            'Cases Failed for Object/Element Issues on System 1': len(x[(x['status'] == 'failed') & (x['is_s1_object_element_failure'])]),
            'Cases Failed for Object/Element Issues on System 2': len(x[(x['status'] == 'failed') & (x['is_s2_object_element_failure'])]),
            'Cases Failed for Field/Additional Issues on System 1': len(x[(x['status'] == 'failed') & (x['is_s1_field_additional_failure'])]),
            'Cases Failed for Field/Additional Issues on System 2': len(x[(x['status'] == 'failed') & (x['is_s2_field_additional_failure'])]),
            'Cases Failed for Rule Triggering Issues on System 1': len(x[(x['status'] == 'failed') & (x['is_s1_trigger_failure'])]),
            'Cases Failed for Rule Triggering Issues on System 2': len(x[(x['status'] == 'failed') & (x['is_s2_trigger_failure'])]),
            'Cases Failed for Systems Comparison': len(x[(x['status'] == 'failed') & (x['is_dual_system_failure'])]),
            'Cases Failed for Error Text Issues': len(x[(x['status'] == 'failed') & (x['is_s1_error_text_failure'] | x['is_s2_error_text_failure'])]),
            'Cases Failed for Object/Element Issues': len(x[(x['status'] == 'failed') & (x['is_s1_object_element_failure'] | x['is_s2_object_element_failure'])]),
            'Cases Failed for Field/Additional Issues': len(x[(x['status'] == 'failed') & (x['is_s1_field_additional_failure'] | x['is_s2_field_additional_failure'])]),
            'Cases Failed for Rule Triggering Issues': len(x[(x['status'] == 'failed') & (x['is_s1_trigger_failure'] | x['is_s2_trigger_failure'])])
        }

        rows = []
        failed_cases = x[x['status'] == 'failed']
        
        if failed_cases.empty:
            # Add one summary row if no failures
            row = common_data.copy()
            row['TC ID'] = ""
            row['Sheet Name'] = ""
            row['Scenario Type'] = ""
            row['Test Case Name'] = ""
            row['Test Case Status'] = ""
            row['Request Content'] = ""
            row['Inner Request Content'] = ""
            row['Error Text'] = ""
            row['Response Content'] = ""
            row[f'Response Content {s1_name}'] = ""
            row[f'Response Content {s2_name}'] = ""
            row['Decoded Error Report'] = ""
            row[f'Decoded Error Report [{s1_name}]'] = ""
            row[f'Decoded Error Report [{s2_name}]'] = ""
            row[f'Row Comparison Difference {s2_name}'] = ""
            row['Rule Presence Mismatch'] = ""
            row[f'Object/Element Difference {s1_name}'] = ""
            row[f'Object/Element Difference {s2_name}'] = ""
            row['Object/Element Difference'] = ""
            row[f'Error Text Difference {s1_name}'] = ""
            row[f'Error Text Difference {s2_name}'] = ""
            row['Error Text Difference'] = ""
            row[f'Field/Additional Difference {s1_name}'] = ""
            row[f'Field/Additional Difference {s2_name}'] = ""
            row['Field/Additional Difference'] = ""

            # Flags for filtering
            row['status'] = 'passed' # Approximation for summary row
            row['is_s1_error_text_failure'] = False
            row['is_s2_error_text_failure'] = False
            row['is_s1_object_element_failure'] = False
            row['is_s2_object_element_failure'] = False
            row['is_s1_field_additional_failure'] = False
            row['is_s2_field_additional_failure'] = False
            row['is_s1_trigger_failure'] = False
            row['is_s2_trigger_failure'] = False
            row['is_dual_system_failure'] = False
            row['is_dual_error_text_failure'] = False
            row['is_dual_row_failure'] = False
            row['is_dual_mismatch_failure'] = False

            rows.append(row)
        else:
            for idx, case in failed_cases.iterrows():
                row = common_data.copy()
                row['TC ID'] = case['tc_id']
                row['Sheet Name'] = case['sheet_name']
                row['Scenario Type'] = case['scenario_type']
                row['Test Case Name'] = case['test_case_name']
                row['Test Case Status'] = case['status']
                row['Request Content'] = case['request_content']
                row['Inner Request Content'] = case['inner_request_content']

                # Use same content for Content/XML for now unless separate source exists
                row['Response Content'] = case['response_content']
                
                row[f'Response Content {s1_name}'] = case['response_s1_content']
                row[f'Response Content {s2_name}'] = case['response_s2_content']
                _single_decoded = case['decoded_s2_error_report'] if execution_mode == ExecutionMode.SYSTEM2_ONLY else case['decoded_s1_error_report']
                row['Decoded Error Report'] = _single_decoded
                row[f'Decoded Error Report [{s1_name}]'] = case['decoded_s1_error_report']
                row[f'Decoded Error Report [{s2_name}]'] = case['decoded_s2_error_report']
                row[f'Row Comparison Difference {s2_name}'] = case['row_comparison_diff']
                row['Rule Presence Mismatch'] = case['presence_mismatch']

                # Flags for filtering
                row['status'] = case['status']
                row['is_s1_error_text_failure'] = case['is_s1_error_text_failure']
                row['is_s2_error_text_failure'] = case['is_s2_error_text_failure']
                row['is_s1_object_element_failure'] = case['is_s1_object_element_failure']
                row['is_s2_object_element_failure'] = case['is_s2_object_element_failure']
                row['is_s1_field_additional_failure'] = case['is_s1_field_additional_failure']
                row['is_s2_field_additional_failure'] = case['is_s2_field_additional_failure']
                row['is_s1_trigger_failure'] = case['is_s1_trigger_failure']
                row['is_s2_trigger_failure'] = case['is_s2_trigger_failure']
                row['is_dual_system_failure'] = case['is_dual_system_failure']
                row['is_dual_error_text_failure'] = case['is_dual_error_text_failure']
                row['is_dual_row_failure'] = case['is_dual_row_failure']
                row['is_dual_mismatch_failure'] = case['is_dual_mismatch_failure']

                # Combine diffs for this case
                s1_t = "\n----------------------------------------\n".join(case['s1_diffs'])
                s2_t = "\n----------------------------------------\n".join(case['s2_diffs'])
                gen_t = "\n----------------------------------------\n".join(case['generic_diffs'])

                SEP = "\n----------------------------------------\n"
                obj_s1_t = SEP.join(
                    get_attachment_content(allure_results_dir, s) for s in case['obj_s1_diffs'] if s
                )
                obj_s2_t = SEP.join(
                    get_attachment_content(allure_results_dir, s) for s in case['obj_s2_diffs'] if s
                )
                fa_s1_t = SEP.join(
                    get_attachment_content(allure_results_dir, s) for s in case['field_additional_s1_diffs'] if s
                )
                fa_s2_t = SEP.join(
                    get_attachment_content(allure_results_dir, s) for s in case['field_additional_s2_diffs'] if s
                )

                row['Error Text'] = case['error_text']

                if execution_mode in [ExecutionMode.BOTH_SYSTEMS, ExecutionMode.SYSTEM1_BOTH_ENVS]:
                    row[f'Object/Element Difference {s1_name}'] = obj_s1_t
                    row[f'Object/Element Difference {s2_name}'] = obj_s2_t
                    row[f'Error Text Difference {s1_name}'] = s1_t
                    row[f'Error Text Difference {s2_name}'] = s2_t
                    row[f'Field/Additional Difference {s1_name}'] = fa_s1_t
                    row[f'Field/Additional Difference {s2_name}'] = fa_s2_t
                else:
                    row['Object/Element Difference'] = obj_s1_t or obj_s2_t
                    row['Field/Additional Difference'] = fa_s1_t or fa_s2_t
                    combined_t = s1_t
                    if s2_t: combined_t += ("\n---\n" + s2_t) if combined_t else s2_t
                    if gen_t: combined_t += ("\n---\n" + gen_t) if combined_t else gen_t
                    row['Error Text Difference'] = combined_t
                
                rows.append(row)
            
        return pd.DataFrame(rows)

    if 'rule_id' not in df.columns:
        return pd.DataFrame(columns=get_available_rules_summary_columns(execution_mode, assert_error_text_enabled=True, assert_field_additional_enabled=True))

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', FutureWarning)
        summary_df = df.groupby('rule_id').apply(aggregate_rule).reset_index()
    summary_df = summary_df.rename(columns={'rule_id': 'Rule ID'})
    
    # Ensure all expected columns are present
    expected_cols = get_available_rules_summary_columns(execution_mode, assert_error_text_enabled=True, assert_field_additional_enabled=True)
    for col in expected_cols:
        if col not in summary_df.columns:
            if 'Cases' in col or 'Total' in col:
                summary_df[col] = 0
            else:
                summary_df[col] = "" 
            
    # Ensure every flag column is always present (False if not produced by aggregation)
    for col in _FLAG_COLUMNS:
        if col not in summary_df.columns:
            summary_df[col] = False

    cols_to_keep = expected_cols + [c for c in _FLAG_COLUMNS if c in summary_df.columns]
    summary_df = summary_df[cols_to_keep]

    return summary_df
