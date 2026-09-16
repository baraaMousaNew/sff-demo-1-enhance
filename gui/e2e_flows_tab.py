"""
E2E Flows Tab - Load an Excel sheet to define and run end-to-end request chains.

Sheet structure:
  - TC_ID column identifies test cases.
  - The first row of a test case has a value in TC_ID; subsequent steps leave it empty.
  - Each step row has a Main XML column (SOAP envelope) and optionally a Nested XML
    column. When Nested XML is present its value is base64-encoded and substituted
    wherever {{nested_xml}} appears in the Main XML before sending.
"""

import base64
import io
import json
import os
import tempfile
import zipfile
import pathlib
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, filedialog, messagebox, simpledialog
import customtkinter as ctk

from utils.azure_reporting import (
    scan_e2e_failures, scan_e2e_failed_tc_ids, scan_all_e2e_results,
    create_ado_bug, test_ado_connection, get_pbi_details,
    get_all_ready_for_qa_bugs, match_bug_to_test_case, update_bug_for_qa_result,
)
from utils.excel_handler import ExcelHandler
from utils.variable_processor import VariableProcessor
from .theme import FONTS

_PROJECT_ROOT = str(
    pathlib.Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else pathlib.Path(__file__).parent.parent
)
_SYSTEM_DEFAULTS_PATH = pathlib.Path(_PROJECT_ROOT) / "resources" / "system_defaults.json"


def _load_url_options() -> list:
    """Return [{"label": "system › env", "url": "..."}, ...] from system_defaults.json."""
    try:
        import json
        with open(_SYSTEM_DEFAULTS_PATH, "r") as f:
            data = json.load(f)
        options = []
        for system, envs in data.items():
            for env_name, url in envs.items():
                options.append({"label": f"{system}  ›  {env_name}", "url": url})
        return options
    except Exception:
        return []

TC_ID_COL = "TC_ID"
NESTED_XML_PLACEHOLDER     = "{{nested_xml}}"
NESTED_XML_ZIP_PLACEHOLDER = "{{nested_xml_zip}}"


def _b64_encode(xml_string: str) -> str:
    return base64.b64encode(xml_string.encode("utf-8")).decode("utf-8")


def _b64_zip_encode(xml_string: str) -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("context.xml", xml_string)
    return base64.b64encode(buf.getvalue()).decode("utf-8")



def _copy_preverify_results(preverify_dir: str, results_dir: str) -> int:
    """Copy all pre-verify results and their attachments into results_dir as-is."""
    def _copy_attachments(steps, src, dst):
        for step in steps:
            for att in step.get("attachments", []):
                s = src / att.get("source", "")
                if s.exists():
                    shutil.copy2(s, dst / s.name)
            _copy_attachments(step.get("steps", []), src, dst)

    src_path = pathlib.Path(preverify_dir)
    dst_path = pathlib.Path(results_dir)
    count = 0
    for file in src_path.glob("*-result.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        shutil.copy2(file, dst_path / file.name)
        for att in data.get("attachments", []):
            s = src_path / att.get("source", "")
            if s.exists():
                shutil.copy2(s, dst_path / s.name)
        _copy_attachments(data.get("steps", []), src_path, dst_path)
        count += 1
    return count


class E2EFlowsTab:
    def __init__(self, parent):
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.pack(fill="both", expand=True)

        self.excel_handler = ExcelHandler()

        self.sheet_names = []
        self.current_sheet = None
        self.all_data = []        # flat list of row dicts from Excel
        self.test_cases = []      # list of {"tc_id": str, "steps": [row_dict, ...]}
        self.columns = []
        self._process = None      # running subprocess
        self._allure_serve_process = None  # running allure serve subprocess
        self.allure_report_generated = False

        self.create_widgets()

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def create_widgets(self):
        main_frame = ctk.CTkScrollableFrame(self.frame)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ── 1. File selection ──────────────────────────────────────────
        self.file_frame = ctk.CTkFrame(main_frame)
        self.file_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(self.file_frame, text="Excel File:", font=FONTS["main_bold"]).pack(side="left", padx=10)
        self.file_path_var = tk.StringVar()
        ctk.CTkEntry(
            self.file_frame, textvariable=self.file_path_var, width=400, font=FONTS["main"]
        ).pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(
            self.file_frame, text="Browse", command=self.browse_file,
            width=80, fg_color="gray", hover_color="#404040", font=FONTS["button"]
        ).pack(side="left", padx=(0, 5))
        ctk.CTkButton(
            self.file_frame, text="Load", command=self.load_file,
            width=80, font=FONTS["button"]
        ).pack(side="left", padx=5)

        # ── 2. Sheet selector (shown only for multi-sheet files) ───────
        self.sheet_frame = ctk.CTkFrame(main_frame)
        ctk.CTkLabel(self.sheet_frame, text="Sheet:", font=FONTS["main_bold"]).pack(side="left", padx=10)
        self.sheet_var = tk.StringVar()
        self.sheet_combo = ctk.CTkComboBox(
            self.sheet_frame, variable=self.sheet_var, values=[],
            width=200, font=FONTS["main"], command=self.on_sheet_changed,
        )
        self.sheet_combo.pack(side="left", padx=5)

        # ── 3. URL ────────────────────────────────────────────────────────
        url_frame = ctk.CTkFrame(main_frame)
        url_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(url_frame, text="Environment:", font=FONTS["main_bold"]).pack(side="left", padx=10)
        self._url_options = _load_url_options()
        env_labels = [o["label"] for o in self._url_options]
        self._env_var = tk.StringVar()
        self._env_combo = ctk.CTkComboBox(
            url_frame, variable=self._env_var, values=env_labels,
            width=260, font=FONTS["main"], command=self._on_env_selected,
        )
        self._env_combo.pack(side="left", padx=5)
        if env_labels:
            self._env_combo.set(env_labels[0])

        ctk.CTkLabel(url_frame, text="URL:", font=FONTS["main_bold"]).pack(side="left", padx=(12, 4))
        self.url_var = tk.StringVar()
        ctk.CTkEntry(
            url_frame, textvariable=self.url_var, width=420,
            placeholder_text="https://...", font=FONTS["main"]
        ).pack(side="left", fill="x", expand=True, padx=5)

        # Pre-fill URL from first option
        if self._url_options:
            self.url_var.set(self._url_options[0]["url"])

        # ── 3b. Pre-verification (optional) ──────────────────────────────
        self._preverify_toggle_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self._preverify_toggle_frame.pack(fill="x", pady=(0, 4))

        self._preverify_enabled_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self._preverify_toggle_frame,
            text="Pre-verify on another environment first",
            variable=self._preverify_enabled_var,
            command=self._on_preverify_toggle,
            font=FONTS["main"],
        ).pack(side="left", padx=10)

        self._preverify_frame = ctk.CTkFrame(main_frame)
        ctk.CTkLabel(self._preverify_frame, text="Pre-verify on:", font=FONTS["main_bold"]).pack(side="left", padx=10)
        self._preverify_env_var = tk.StringVar()
        self._preverify_env_combo = ctk.CTkComboBox(
            self._preverify_frame, variable=self._preverify_env_var,
            values=env_labels, width=260, font=FONTS["main"],
            command=self._on_preverify_env_selected,
        )
        self._preverify_env_combo.pack(side="left", padx=5)
        ctk.CTkLabel(self._preverify_frame, text="URL:", font=FONTS["main_bold"]).pack(side="left", padx=(12, 4))
        self._preverify_url_var = tk.StringVar()
        ctk.CTkEntry(
            self._preverify_frame, textvariable=self._preverify_url_var,
            width=420, placeholder_text="https://...", font=FONTS["main"],
        ).pack(side="left", fill="x", expand=True, padx=5)
        if self._url_options:
            self._preverify_env_combo.set(env_labels[0])
            self._preverify_url_var.set(self._url_options[0]["url"])
        # Pack then immediately hide — preserves pack order so show/hide works correctly
        self._preverify_frame.pack(fill="x", pady=(0, 8), after=self._preverify_toggle_frame)
        self._preverify_frame.pack_forget()

        # ── 3c. Execution config ──────────────────────────────────────────
        exec_config_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        exec_config_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(exec_config_frame, text="Pause between steps:", font=FONTS["main_bold"]).pack(side="left", padx=10)
        self._step_pause_var = tk.StringVar(value="0")
        ctk.CTkEntry(
            exec_config_frame, textvariable=self._step_pause_var,
            width=70, font=FONTS["main"],
        ).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(exec_config_frame, text="seconds", font=FONTS["main"]).pack(side="left")

        # ── 4. Column mapping (hidden until a sheet is loaded) ─────────
        self.mapping_outer = ctk.CTkFrame(main_frame)

        ctk.CTkLabel(
            self.mapping_outer, text="Column Mapping", font=FONTS["sub_header"]
        ).pack(anchor="w", padx=10, pady=(8, 4))

        mapping_inner = ctk.CTkFrame(self.mapping_outer, fg_color="transparent")
        mapping_inner.pack(fill="x", padx=10, pady=(0, 8))

        def _mapping_row(label, row, optional=False):
            display = f"{label}  (optional)" if optional else label
            ctk.CTkLabel(
                mapping_inner, text=display, font=FONTS["main_bold"], width=200, anchor="w"
            ).grid(row=row, column=0, padx=(0, 10), pady=4, sticky="w")
            var = tk.StringVar()
            combo = ctk.CTkComboBox(mapping_inner, variable=var, values=[], width=240, font=FONTS["main"])
            combo.grid(row=row, column=1, padx=(0, 20), pady=4, sticky="w")
            return var, combo

        self.main_xml_col_var,      self.main_xml_col_combo      = _mapping_row("Main XML Column:",         0)
        self.nested_xml_col_var,    self.nested_xml_col_combo    = _mapping_row("Nested XML Column:",       1, optional=True)
        self.extract_rules_col_var, self.extract_rules_col_combo = _mapping_row("Extraction Rules Column:", 2, optional=True)
        self.transaction_col_var,   self.transaction_col_combo   = _mapping_row("Transaction Name Column:", 3)
        self.assert_col_var,        self.assert_col_combo        = _mapping_row("Assertions Column:",       4, optional=True)
        self.tc_name_col_var,       self.tc_name_col_combo       = _mapping_row("Test Case Name Column:",   5, optional=True)
        self.skip_col_var,          self.skip_col_combo          = _mapping_row("Skip Step Column:",        6, optional=True)
        self.skip_preverify_col_var, self.skip_preverify_col_combo = _mapping_row("Skip Pre-verify Column:", 7, optional=True)

        notes_frame = ctk.CTkFrame(self.mapping_outer, fg_color="#141c2b", corner_radius=6)
        notes_frame.pack(fill="x", padx=10, pady=(0, 10))

        def _notes_section(title, syntax_lines, note=None, is_last=False):
            sec = ctk.CTkFrame(notes_frame, fg_color="transparent")
            sec.pack(fill="x", padx=12, pady=(8, 2 if not is_last else 10))
            ctk.CTkLabel(
                sec, text=title,
                font=("Roboto Medium", 13, "bold"), text_color="#82aaff", anchor="w",
            ).pack(anchor="w")
            for line in syntax_lines:
                ctk.CTkLabel(
                    sec, text=line,
                    font=("Courier New", 12), text_color="#9a9a9a", justify="left", anchor="w",
                ).pack(anchor="w", padx=(14, 0))
            if note:
                ctk.CTkLabel(
                    sec, text=note,
                    font=FONTS["small"], text_color="#606060", justify="left", anchor="w",
                ).pack(anchor="w", padx=(14, 0), pady=(3, 0))

        _notes_section(
            "Nested XML",
            ["Base64-encoded → substituted for  {{nested_xml}}  in the Main XML."],
        )
        _notes_section(
            "Extraction Rules  (semicolon-separated)",
            [
                "var=//xpath",
                "var=regex:pattern",
                "var=ElementName",
                "var=OuterElement>>Path.Element[attr=val].AttrName",
            ],
            note="Results are available as  {{EXTRACT.var}}  in all subsequent steps of the same test case.",
        )
        _notes_section(
            "Assertions  (semicolon-separated,  selector==expected)",
            [
                "//xpath==value",
                "regex:pattern==value",
                "EXTRACT.var==value",
                "ElementName==value",
                "OuterElement>>Path.Element[a=v1,b=v2]==found | not found | unique",
                "OuterElement>>Path.Element[attr=val].AttrName==expected_value",
            ],
            note="Expected values support {{...}} placeholders.  A failing assertion fails the step immediately.",
            is_last=True,
        )

        # ── 4. Test case tree ──────────────────────────────────────────
        ctk.CTkLabel(main_frame, text="Test Cases:", font=FONTS["sub_header"]).pack(
            anchor="w", padx=5, pady=(4, 2)
        )

        tree_frame = ctk.CTkFrame(main_frame)
        tree_frame.pack(fill="both", expand=True, pady=(0, 8))

        self.tree = ttk.Treeview(tree_frame, show="tree headings", height=18, selectmode="extended")
        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        self.tree.bind("<Double-1>", self._on_cell_double_click)

        self.tree.tag_configure("tc_header", background="#1f3a5f", foreground="white")
        self.tree.tag_configure("step_odd",  background="#1e1e1e")
        self.tree.tag_configure("step_even", background="#2a2a2a")

        # ── 5. Action buttons ──────────────────────────────────────────
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=6)

        self.run_btn = ctk.CTkButton(
            btn_frame, text="Run", command=self.start_run,
            fg_color="green", hover_color="#006400", width=120, font=FONTS["button"]
        )
        self.run_btn.pack(side="left", padx=(0, 10))

        self.cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancel Run", command=self.cancel_run,
            fg_color="red", hover_color="#8b0000", width=120, font=FONTS["button"],
            state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=(0, 10))

        self.open_report_btn = ctk.CTkButton(
            btn_frame, text="Open Last Report", command=self.open_last_report,
            fg_color="#1f538d", hover_color="#144070", font=FONTS["button"],
            state="normal"
        )
        self.open_report_btn.pack(side="left", padx=(0, 10))

        self.save_report_btn = ctk.CTkButton(
            btn_frame, text="Save Report", command=self.save_allure_report,
            fg_color="#1f538d", hover_color="#144070", font=FONTS["button"],
            state="normal"
        )
        self.save_report_btn.pack(side="left", padx=(0, 10))

        self.report_ado_btn = ctk.CTkButton(
            btn_frame, text="Report Failures to ADO", command=self._on_report_ado,
            fg_color="#5c2d91", hover_color="#3e1f63", font=FONTS["button"],
            state="disabled"
        )
        self.report_ado_btn.pack(side="left", padx=(0, 10))

        self.ado_update_bugs_btn = ctk.CTkButton(
            btn_frame, text="Update QA Bugs",
            command=self.show_update_bugs_dialog,
            fg_color="#1a6b4a", hover_color="#134d36", font=FONTS["button"]
        )
        self.ado_update_bugs_btn.pack(side="left")

        # ── 6. Status bar ──────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready — load an Excel file to begin.")
        ctk.CTkLabel(
            main_frame, textvariable=self.status_var,
            text_color="cyan", font=FONTS["main"]
        ).pack(anchor="w", pady=(0, 4))

    # ------------------------------------------------------------------
    # Environment / URL
    # ------------------------------------------------------------------

    def _on_env_selected(self, label: str):
        for option in self._url_options:
            if option["label"] == label:
                self.url_var.set(option["url"])
                break

    def _on_preverify_toggle(self):
        if self._preverify_enabled_var.get():
            self._preverify_frame.pack(fill="x", pady=(0, 8), after=self._preverify_toggle_frame)
        else:
            self._preverify_frame.pack_forget()

    def _on_preverify_env_selected(self, label: str):
        for option in self._url_options:
            if option["label"] == label:
                self._preverify_url_var.set(option["url"])
                break

    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------

    def browse_file(self):
        path = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls")],
        )
        if path:
            self.file_path_var.set(path)
            self.detect_sheets()

    def detect_sheets(self):
        path = self.file_path_var.get()
        if not path:
            return
        try:
            self.sheet_names = self.excel_handler.get_sheet_names(path)
            if len(self.sheet_names) > 1:
                self.sheet_combo.configure(values=self.sheet_names)
                self.sheet_combo.set(self.sheet_names[0])
                self.current_sheet = self.sheet_names[0]
                self.sheet_frame.pack(fill="x", pady=(0, 8), after=self.file_frame)
                self.status_var.set(f"{len(self.sheet_names)} sheets found — select one and click Load.")
            else:
                self.sheet_frame.pack_forget()
                self.current_sheet = self.sheet_names[0] if self.sheet_names else None
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read sheets: {e}")

    def load_file(self):
        path = self.file_path_var.get()
        if not path:
            messagebox.showwarning("Warning", "Please select a file first.")
            return
        if not self.sheet_names:
            self.detect_sheets()
        sheet = self.current_sheet or (self.sheet_names[0] if self.sheet_names else None)
        if not sheet:
            messagebox.showerror("Error", "No sheets found in the Excel file.")
            return
        self.load_sheet_data(sheet)

    def on_sheet_changed(self, value):
        self.current_sheet = value
        self.load_sheet_data(value)

    def load_sheet_data(self, sheet_name):
        path = self.file_path_var.get()
        try:
            self.status_var.set(f"Loading '{sheet_name}'…")
            self.frame.update()
            self.all_data = self.excel_handler.load_excel(path, sheet_name=sheet_name)
            self.columns = list(self.all_data[0].keys()) if self.all_data else []
            self.test_cases = self._group_by_tc(self.all_data)
            self._update_column_mapping()
            self.populate_table()
            self.status_var.set(
                f"Loaded {len(self.test_cases)} test case(s), "
                f"{len(self.all_data)} row(s) from '{sheet_name}'."
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load '{sheet_name}': {e}")

    # ------------------------------------------------------------------
    # Grouping
    # ------------------------------------------------------------------

    def _group_by_tc(self, rows):
        """
        Group flat rows into test cases.
        A new test case starts whenever TC_ID is non-empty.
        Returns a list of {"tc_id": str, "steps": [row_dict, ...]}.
        """
        groups = []
        current = None
        for row in rows:
            tc_id = str(row.get(TC_ID_COL, "") or "").strip()
            if tc_id:
                current = {"tc_id": tc_id, "steps": [row]}
                groups.append(current)
            elif current is not None:
                current["steps"].append(row)
        return groups

    # ------------------------------------------------------------------
    # Column mapping
    # ------------------------------------------------------------------

    def _update_column_mapping(self):
        optional_sentinel = ["(none)"]
        for combo, var, allow_none in [
            (self.main_xml_col_combo,      self.main_xml_col_var,      False),
            (self.nested_xml_col_combo,    self.nested_xml_col_var,    True),
            (self.extract_rules_col_combo, self.extract_rules_col_var, True),
            (self.transaction_col_combo,   self.transaction_col_var,   False),
            (self.assert_col_combo,        self.assert_col_var,        True),
            (self.tc_name_col_combo,       self.tc_name_col_var,       True),
            (self.skip_col_combo,           self.skip_col_var,           True),
            (self.skip_preverify_col_combo, self.skip_preverify_col_var, True),
        ]:
            values = (optional_sentinel + self.columns) if allow_none else self.columns
            combo.configure(values=values)
            if not var.get() or var.get() not in values:
                var.set(values[0])

        self.mapping_outer.pack(fill="x", pady=(0, 8))

    def make_processor(self) -> VariableProcessor:
        """Create a fresh VariableProcessor for a single test case execution."""
        return VariableProcessor()

    def get_effective_payload(self, row: dict, processor: VariableProcessor) -> str:
        """
        Build the final XML payload for a single step row using the shared processor.

        Processing order:
          1. Nested XML (if column configured and cell has value):
             - Run through processor so {{...}} placeholders are resolved.
             - Base64-encode the result.
             - Substitute {{nested_xml}} inside the main XML string.
          2. Main XML:
             - Run through processor (resolves built-in functions, custom functions,
               {{VAR.*}}, {{EXTRACT.*}} populated by earlier steps, etc.).

        The processor is shared across all steps of the same test case, so
        {{EXTRACT.*}} values from step N are available in step N+1.
        """
        main_col   = self.main_xml_col_var.get().strip()
        nested_col = self.nested_xml_col_var.get().strip()

        main_xml = str(row.get(main_col, "") or "").strip()

        if nested_col and nested_col != "(none)":
            nested_xml = str(row.get(nested_col, "") or "").strip()
            if nested_xml:
                processed_nested = processor.process_variables(nested_xml, excel_row_data=row)
                if NESTED_XML_ZIP_PLACEHOLDER in main_xml:
                    encoded = _b64_zip_encode(processed_nested)
                    main_xml = main_xml.replace(NESTED_XML_ZIP_PLACEHOLDER, encoded)
                else:
                    encoded = _b64_encode(processed_nested)
                    main_xml = main_xml.replace(NESTED_XML_PLACEHOLDER, encoded)

        return processor.process_variables(main_xml, excel_row_data=row)

    def extract_from_response(self, response_content: str, row: dict, processor: VariableProcessor) -> dict:
        """
        If the step row has extraction rules, parse the response and store the
        results in the processor so subsequent steps can use {{EXTRACT.var}}.
        Returns the dict of newly extracted variables (empty if none configured).
        """
        extract_col = self.extract_rules_col_var.get().strip()
        if not extract_col or extract_col == "(none)":
            return {}
        rules = str(row.get(extract_col, "") or "").strip()
        if not rules:
            return {}
        return processor.extract_values_from_response(response_content, rules)

    # ------------------------------------------------------------------
    # Run / Cancel / Report
    # ------------------------------------------------------------------

    def _validate_run_preconditions(self) -> bool:
        if not self.test_cases:
            messagebox.showwarning("Warning", "Please load a file first.")
            return False
        if not self.url_var.get().strip():
            messagebox.showwarning("Warning", "Please enter a URL.")
            return False
        if not self.main_xml_col_var.get():
            messagebox.showwarning("Warning", "Please select the Main XML column.")
            return False
        if not self.transaction_col_var.get():
            messagebox.showwarning("Warning", "Please select the Transaction Name column.")
            return False
        return True

    def _get_selected_tc_ids(self) -> list:
        """Return TC_IDs for all selected tree items (resolves steps up to their parent)."""
        tc_ids = []
        for item in self.tree.selection():
            if self.tree.parent(item) == "":
                # selected item is a TC header node
                tc_id = self.tree.item(item, "text").strip()
            else:
                # selected item is a step — use its parent's label
                tc_id = self.tree.item(self.tree.parent(item), "text").strip()
            if tc_id and tc_id not in tc_ids:
                tc_ids.append(tc_id)
        return tc_ids

    def start_run(self):
        if not self._validate_run_preconditions():
            return
        self._show_run_dialog()

    def _show_run_dialog(self):
        selected_ids = self._get_selected_tc_ids()

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Run E2E Tests")
        dialog.geometry("420x220")
        dialog.resizable(False, False)
        dialog.transient(self.frame)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="Choose which test cases to run:",
            font=FONTS["sub_header"]
        ).pack(pady=(20, 12))

        ctk.CTkButton(
            dialog,
            text=f"Run All  ({len(self.test_cases)} test case(s))",
            command=lambda: [dialog.destroy(), self._launch_run(None)],
            font=FONTS["button"], width=320, fg_color="green", hover_color="#006400"
        ).pack(pady=4)

        ctk.CTkButton(
            dialog,
            text=f"Run Selected  ({len(selected_ids)} selected)",
            command=lambda: [dialog.destroy(), self._launch_run(selected_ids)],
            font=FONTS["button"], width=320,
            fg_color="#1f7a1f" if selected_ids else "gray",
            hover_color="#145214" if selected_ids else "gray",
            state="normal" if selected_ids else "disabled"
        ).pack(pady=4)

        ctk.CTkButton(
            dialog, text="Cancel",
            command=dialog.destroy,
            fg_color="gray", hover_color="#404040", font=FONTS["button"], width=320
        ).pack(pady=4)

    def _build_env(self, specific_tc_ids: list | None, url: str | None = None, env_label: str = "") -> dict:
        env = os.environ.copy()
        env["E2E_EXCEL_FILE"]      = self.file_path_var.get()
        env["E2E_SHEET"]           = self.current_sheet or ""
        env["E2E_URL"]             = url if url is not None else self.url_var.get().strip()
        env["E2E_ENV_LABEL"]       = env_label
        env["E2E_MAIN_XML_COL"]    = self.main_xml_col_var.get()
        env["E2E_TRANSACTION_COL"] = self.transaction_col_var.get()
        nested     = self.nested_xml_col_var.get()
        extract    = self.extract_rules_col_var.get()
        assertions = self.assert_col_var.get()
        tc_name    = self.tc_name_col_var.get()
        skip       = self.skip_col_var.get()
        env["E2E_NESTED_XML_COL"]    = "" if nested     == "(none)" else nested
        env["E2E_EXTRACT_RULES_COL"] = "" if extract    == "(none)" else extract
        env["E2E_ASSERT_COL"]        = "" if assertions == "(none)" else assertions
        env["E2E_TC_NAME_COL"]       = "" if tc_name    == "(none)" else tc_name
        env["E2E_SKIP_COL"]          = "" if skip       == "(none)" else skip
        try:
            pause = max(0.0, float(self._step_pause_var.get() or "0"))
        except ValueError:
            pause = 0.0
        env["E2E_STEP_PAUSE"] = str(pause)
        if specific_tc_ids:
            env["E2E_SPECIFIC_CASES"] = ",".join(specific_tc_ids)
        else:
            env.pop("E2E_SPECIFIC_CASES", None)
        return env

    def _launch_run(self, specific_tc_ids: list | None):
        self.run_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.open_report_btn.configure(state="disabled")
        tc_label = "all" if not specific_tc_ids else f"{len(specific_tc_ids)} selected"
        self.status_var.set(f"Running {tc_label} test case(s)…")

        preverify_enabled = self._preverify_enabled_var.get()
        preverify_url     = self._preverify_url_var.get().strip() if preverify_enabled else ""
        preverify_label   = (self._preverify_env_var.get().strip() or "Pre-verification") if preverify_enabled else ""
        main_url          = self.url_var.get().strip()
        main_label        = self._env_var.get().strip() or "Main"

        self.allure_report_generated = False
        results_dir           = os.path.join(_PROJECT_ROOT, "allure-results")
        preverify_results_dir = os.path.join(_PROJECT_ROOT, "allure-results-preverify")

        try:
            if os.path.exists(results_dir):
                shutil.rmtree(results_dir)
            os.makedirs(results_dir, exist_ok=True)
        except Exception as e:
            print(f"WARNING: Could not clear allure-results: {e}")

        _python_exe = (
            str(pathlib.Path(sys.executable).parent / "python_runtime" / "python.exe")
            if getattr(sys, "frozen", False)
            else sys.executable
        )
        main_cmd = [
            _python_exe, "-m", "pytest",
            "utils/e2e_flows_allure_wrapper.py",
            "--alluredir=allure-results",
            "-v", "--tb=short",
        ]
        preverify_cmd = [
            _python_exe, "-m", "pytest",
            "utils/e2e_flows_allure_wrapper.py",
            "--alluredir=allure-results-preverify",
            "-v", "--tb=short",
        ]

        def _run():
            try:
                main_tc_ids = specific_tc_ids

                # ── Determine which TC_IDs bypass pre-verify ───────────
                skip_preverify_ids = set()
                if preverify_enabled:
                    skip_pv_col = self.skip_preverify_col_var.get().strip()
                    if skip_pv_col and skip_pv_col != "(none)":
                        all_req = (
                            list(specific_tc_ids)
                            if specific_tc_ids is not None
                            else [tc["tc_id"] for tc in self.test_cases]
                        )
                        for tc in self.test_cases:
                            if tc["tc_id"] not in all_req:
                                continue
                            first_row = tc["steps"][0] if tc["steps"] else {}
                            flag = str(first_row.get(skip_pv_col, "") or "").strip().lower()
                            if flag and flag not in ("no", "false", "0", "n"):
                                skip_preverify_ids.add(tc["tc_id"])

                # ── Pre-verification pass ──────────────────────────────
                if preverify_enabled and preverify_url:
                    all_requested = (
                        list(specific_tc_ids)
                        if specific_tc_ids is not None
                        else [tc["tc_id"] for tc in self.test_cases]
                    )
                    preverify_tc_ids = [tid for tid in all_requested if tid not in skip_preverify_ids]
                    bypass_ids       = [tid for tid in all_requested if tid in skip_preverify_ids]

                    passing_preverify_ids = list(preverify_tc_ids)

                    if preverify_tc_ids:
                        pv_label_count = f"{len(preverify_tc_ids)} case(s)"
                        self.frame.after(0, self.status_var.set,
                            f"Pre-verifying {pv_label_count} on {preverify_label}"
                            + (f" ({len(bypass_ids)} bypassing pre-verify)…" if bypass_ids else "…"))
                        try:
                            if os.path.exists(preverify_results_dir):
                                shutil.rmtree(preverify_results_dir)
                            os.makedirs(preverify_results_dir, exist_ok=True)
                        except Exception as e:
                            print(f"WARNING: Could not prepare preverify results dir: {e}")

                        env = self._build_env(preverify_tc_ids, url=preverify_url, env_label=preverify_label)
                        self._process = subprocess.Popen(
                            preverify_cmd, cwd=_PROJECT_ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                        )
                        for line in self._process.stdout:
                            stripped = line.rstrip()
                            if stripped:
                                self.frame.after(0, self.status_var.set, stripped[:150])
                        self._process.wait()

                        failed_ids = scan_e2e_failed_tc_ids(preverify_results_dir)
                        _copy_preverify_results(preverify_results_dir, results_dir)
                        try:
                            shutil.rmtree(preverify_results_dir)
                        except Exception:
                            pass

                        passing_preverify_ids = [tid for tid in preverify_tc_ids if tid not in failed_ids]

                    # Combine: cases that passed pre-verify + cases that bypassed it
                    all_main_ids = passing_preverify_ids + bypass_ids
                    if not all_main_ids:
                        self.frame.after(
                            0, self._on_run_done, 1, None,
                            f"All {len(preverify_tc_ids)} case(s) failed pre-verification on "
                            f"{preverify_label} — main run skipped.",
                        )
                        return

                    n_failed  = len(preverify_tc_ids) - len(passing_preverify_ids) if preverify_tc_ids else 0
                    n_passed  = len(passing_preverify_ids)
                    n_bypass  = len(bypass_ids)
                    parts = []
                    if n_failed:
                        parts.append(f"{n_failed} skipped (pre-verify failed)")
                    if n_passed:
                        parts.append(f"{n_passed} passed pre-verify")
                    if n_bypass:
                        parts.append(f"{n_bypass} bypassed pre-verify")
                    self.frame.after(0, self.status_var.set,
                        f"Pre-verification done: {', '.join(parts)} — running {len(all_main_ids)} on {main_label}…")
                    main_tc_ids = all_main_ids

                # ── Main run ───────────────────────────────────────────
                run_label = "all" if main_tc_ids is None else f"{len(main_tc_ids)}"
                self.frame.after(0, self.status_var.set,
                    f"Running {run_label} test case(s) on {main_label}…")
                env = self._build_env(main_tc_ids, url=main_url, env_label=main_label)
                self._process = subprocess.Popen(
                    main_cmd, cwd=_PROJECT_ROOT, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                )
                for line in self._process.stdout:
                    stripped = line.rstrip()
                    if stripped:
                        self.frame.after(0, self.status_var.set, stripped[:150])
                self._process.wait()
                self.frame.after(0, self._on_run_done, self._process.returncode, None, None)

            except Exception as exc:
                self.frame.after(0, self._on_run_done, -1, str(exc), None)

        threading.Thread(target=_run, daemon=True).start()

    def cancel_run(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
        self._process = None
        self.run_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.status_var.set("Run cancelled.")

    def _on_run_done(self, returncode: int, error: str | None, custom_msg: str | None = None):
        self._process = None
        self.run_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.open_report_btn.configure(state="normal")
        self.report_ado_btn.configure(state="normal")
        if error:
            self.status_var.set(f"Run failed to start: {error}")
        elif custom_msg:
            self.status_var.set(custom_msg)
        elif returncode == 0:
            self.status_var.set("All tests passed. Click 'Open Last Report' to view results.")
        else:
            self.status_var.set(
                f"Tests finished (exit code {returncode}). Click 'Open Last Report' to view results."
            )

    def _find_allure_executable(self):
        path = shutil.which("allure")
        if path:
            return path
        for name in ("allure.bat", "allure.cmd"):
            path = shutil.which(name)
            if path:
                return path
        return None

    def open_last_report(self):
        results_dir = os.path.join(_PROJECT_ROOT, "allure-results")
        if not os.path.exists(results_dir):
            messagebox.showwarning("Warning", "No test results found. Run tests first.")
            return
        allure_cmd = self._find_allure_executable()
        if allure_cmd:
            if self._allure_serve_process and self._allure_serve_process.poll() is None:
                self._allure_serve_process.terminate()
            self._allure_serve_process = subprocess.Popen(
                [allure_cmd, "serve", results_dir], shell=False, cwd=tempfile.gettempdir()
            )
        else:
            messagebox.showerror("Error", "Allure not found")

    def save_allure_report(self):
        results_dir = os.path.join(_PROJECT_ROOT, "allure-results")
        report_dir  = os.path.join(_PROJECT_ROOT, "allure-report")
        if not os.path.exists(results_dir):
            messagebox.showwarning("Warning", "No test results found. Run tests first.")
            return

        save_single = messagebox.askyesno(
            "Save Format",
            "Combine into a single HTML file?\n\nYes: Single .html (easier to share)\nNo: Full folder (standard Allure format)",
        )

        if save_single:
            # Allure natively supports single-file report generation
            # (allure generate --single-file), so no external dependency needed.
            allure_cmd = self._find_allure_executable()
            if not allure_cmd:
                messagebox.showerror("Error", "Allure not found.")
                return
            try:
                self.status_var.set("Generating single-file report…")
                self.frame.update()
                subprocess.run(
                    [allure_cmd, "generate", "--single-file", results_dir, "-o", report_dir, "--clean"],
                    capture_output=True, shell=False, check=True,
                )
                # report_dir now holds the single-file variant, not the regular
                # multi-file report, so it must be regenerated next time it's
                # needed as a folder.
                self.allure_report_generated = False

                source_file = os.path.join(report_dir, "index.html")
                if os.path.exists(source_file):
                    timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_path = filedialog.asksaveasfilename(
                        title="Save Single HTML Report",
                        defaultextension=".html",
                        initialfile=f"allure-report_{timestamp}.html",
                        filetypes=[("HTML files", "*.html")],
                    )
                    if file_path:
                        shutil.copy2(source_file, file_path)
                        messagebox.showinfo("Success", f"Report saved to:\n{file_path}")
                        self.status_var.set("Report saved.")
                    else:
                        self.status_var.set("Save cancelled.")
                else:
                    messagebox.showerror("Error", "index.html not found after generation.")
                    self.status_var.set("Generation failed.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate single-file report: {e}")
                self.status_var.set("Error generating report.")
        else:
            if not self.allure_report_generated:
                allure_cmd = self._find_allure_executable()
                if not allure_cmd:
                    messagebox.showerror("Error", "Allure not found.")
                    return
                self.status_var.set("Generating HTML report…")
                self.frame.update()
                subprocess.run(
                    [allure_cmd, "generate", results_dir, "-o", report_dir, "--clean"],
                    capture_output=True, shell=False,
                )
                self.allure_report_generated = True

            destination = filedialog.askdirectory(title="Select Destination Directory")
            if destination:
                try:
                    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
                    folder_name = simpledialog.askstring(
                        "Report Folder Name", "Enter folder name:",
                        initialvalue=f"allure-report_{timestamp}",
                    )
                    if folder_name:
                        dest_path = os.path.join(destination, folder_name)
                        shutil.copytree(report_dir, dest_path)
                        messagebox.showinfo("Success", f"Report saved to:\n{dest_path}")
                        self.status_var.set("Report saved.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save report: {e}")

    # ------------------------------------------------------------------
    # ADO failure reporting (post-run)
    # ------------------------------------------------------------------

    def _on_report_ado(self):
        results_dir = os.path.join(_PROJECT_ROOT, "allure-results")
        if not os.path.exists(results_dir):
            messagebox.showwarning("Warning", "No test results found. Run tests first.")
            return

        failures = scan_e2e_failures(results_dir)
        if not failures:
            messagebox.showinfo("ADO Reporting", "No failed E2E test cases found in the last run.")
            return

        selected = self._show_e2e_selection_dialog(failures)
        if selected is None:
            return

        creds = self._show_ado_credentials_dialog()
        if creds is None:
            return

        self._create_ado_bugs(creds, selected)

    def _show_e2e_selection_dialog(self, failures):
        """Show a filterable checklist of failed E2E tests. Returns selected failures or None."""
        result_ref = [None]
        cancelled  = [False]

        # Collect unique env labels from failures
        env_labels = []
        for f in failures:
            env_tag = next((t for t in f["all_tags"] if t.startswith("Env - ")), "")
            lbl = env_tag[len("Env - "):].strip() if env_tag else ""
            if lbl and lbl not in env_labels:
                env_labels.append(lbl)

        # Pre-select target env when pre-verify was used
        initial_filter = "All"
        if self._preverify_enabled_var.get():
            main_label = self._env_var.get().strip()
            if main_label in env_labels:
                initial_filter = main_label

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Select Failures to Report")
        dialog.geometry("680x520")
        dialog.resizable(True, True)
        dialog.transient(self.frame)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Failed E2E Test Cases", font=FONTS["sub_header"]).pack(pady=(15, 5))

        # ── Environment filter ─────────────────────────────────────────
        filter_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(filter_frame, text="Environment:", font=FONTS["main_bold"]).pack(side="left", padx=(0, 8))
        filter_var = tk.StringVar(value=initial_filter)
        ctk.CTkComboBox(
            filter_frame, variable=filter_var,
            values=["All"] + env_labels, width=280, font=FONTS["main"],
            command=lambda _: _rebuild_list(),
        ).pack(side="left")

        list_frame = ctk.CTkScrollableFrame(dialog)
        list_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # One BooleanVar per failure — persists across filter changes
        check_vars      = [tk.BooleanVar(value=True) for _ in failures]
        visible_indices = []

        def _rebuild_list():
            for w in list_frame.winfo_children():
                w.destroy()
            visible_indices.clear()
            selected_env = filter_var.get()
            for i, f in enumerate(failures):
                env_tag  = next((t for t in f["all_tags"] if t.startswith("Env - ")), "")
                env_lbl  = env_tag[len("Env - "):].strip() if env_tag else ""
                if selected_env != "All" and env_lbl != selected_env:
                    continue
                visible_indices.append(i)
                tc_id = f["rule_id"]
                name  = f["test_case_name"]
                label = f"[{tc_id}]  {name}"
                if env_tag:
                    label += f"  ({env_tag})"
                ctk.CTkCheckBox(
                    list_frame, text=label, variable=check_vars[i], font=FONTS["main"],
                ).pack(anchor="w", padx=10, pady=3)

        _rebuild_list()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(8, 15))

        def on_select_all():
            for i in visible_indices:
                check_vars[i].set(True)

        def on_deselect_all():
            for i in visible_indices:
                check_vars[i].set(False)

        def on_confirm():
            result_ref[0] = [f for f, v in zip(failures, check_vars) if v.get()]
            dialog.destroy()

        def on_cancel():
            cancelled[0] = True
            dialog.destroy()

        ctk.CTkButton(btn_frame, text="Select All",      command=on_select_all,   width=100, fg_color="gray",    font=FONTS["button"]).pack(side="left",  padx=4)
        ctk.CTkButton(btn_frame, text="Deselect All",    command=on_deselect_all, width=100, fg_color="gray",    font=FONTS["button"]).pack(side="left",  padx=4)
        ctk.CTkButton(btn_frame, text="Cancel",          command=on_cancel,       width=100, fg_color="gray",    hover_color="#404040", font=FONTS["button"]).pack(side="right", padx=4)
        ctk.CTkButton(btn_frame, text="Report Selected", command=on_confirm,      width=140, fg_color="#1f538d", font=FONTS["button"]).pack(side="right", padx=4)

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        self.frame.wait_window(dialog)

        if cancelled[0]:
            return None
        return result_ref[0]

    def _show_ado_credentials_dialog(self):
        """Modal wizard: ADO URL → PAT → project → PBI. Returns dict or None."""
        result    = {}
        cancelled = [False]

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Azure DevOps Connection")
        dialog.geometry("560x490")
        dialog.resizable(False, False)
        dialog.transient(self.frame)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Azure DevOps Wizard", font=FONTS["sub_header"]).pack(pady=(15, 5))

        url_var     = tk.StringVar(value="https://devops.malaffi.ae/ADHDS")
        pat_var     = tk.StringVar()
        project_var = tk.StringVar()
        pbi_id_var  = tk.StringVar()

        step1 = ctk.CTkFrame(dialog)
        step1.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(step1, text="1. Server Details", font=FONTS["main_bold"]).pack(anchor="w", padx=10, pady=(10, 5))

        row1 = ctk.CTkFrame(step1, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row1, text="ADO URL:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        ctk.CTkEntry(row1, textvariable=url_var, width=350, placeholder_text="e.g. http://server/tfs/DefaultCollection", font=FONTS["main"]).pack(side="left", padx=5)

        row3 = ctk.CTkFrame(step1, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row3, text="PAT:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        ctk.CTkEntry(row3, textvariable=pat_var, width=200, show="*", font=FONTS["main"]).pack(side="left", padx=5)

        status_label = ctk.CTkLabel(dialog, text="", text_color="cyan", font=FONTS["main"])
        status_label.pack(pady=5)

        step2 = ctk.CTkFrame(dialog)
        step2.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(step2, text="2. Project & PBI", font=FONTS["main_bold"]).pack(anchor="w", padx=10, pady=(10, 5))

        def on_project_selected(value):
            if value and value != "Select a project":
                pbi_entry.configure(state="normal")
                btn_verify.configure(state="normal")

        row4 = ctk.CTkFrame(step2, fg_color="transparent")
        row4.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row4, text="Project:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        proj_combo = ctk.CTkOptionMenu(row4, variable=project_var, values=["Select a project"], width=250, font=FONTS["main"], state="disabled", command=on_project_selected)
        proj_combo.pack(side="left", padx=5)

        row5 = ctk.CTkFrame(step2, fg_color="transparent")
        row5.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row5, text="PBI ID:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        pbi_entry = ctk.CTkEntry(row5, textvariable=pbi_id_var, width=120, font=FONTS["main"], state="disabled")
        pbi_entry.pack(side="left", padx=5)
        btn_verify = ctk.CTkButton(row5, text="Verify PBI", width=100, state="disabled")
        btn_verify.pack(side="left", padx=5)

        pbi_label = ctk.CTkLabel(step2, text="", text_color="lightgreen", font=FONTS["main"])
        pbi_label.pack(anchor="w", padx=120, pady=2)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(15, 10))
        btn_cancel  = ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray", hover_color="#404040", font=FONTS["button"])
        btn_cancel.pack(side="left", expand=True, padx=5)
        btn_connect = ctk.CTkButton(step1, text="Test Connection", width=120)
        btn_connect.pack(pady=10)
        btn_start = ctk.CTkButton(btn_frame, text="Start Reporting", fg_color="#1f538d", font=FONTS["button"], state="disabled")
        btn_start.pack(side="left", expand=True, padx=5)

        def on_test_connection():
            u, pat = url_var.get().strip(), pat_var.get().strip()
            if not u:
                status_label.configure(text="Please provide the ADO URL.", text_color="red")
                return
            status_label.configure(text="Testing connection...", text_color="cyan")
            dialog.update_idletasks()

            def do_test():
                ok, msg, projs = test_ado_connection(u, pat)
                def do_update():
                    if ok:
                        status_label.configure(text=msg, text_color="lightgreen")
                        if projs:
                            proj_combo.configure(values=projs, state="normal")
                            project_var.set(projs[0])
                            on_project_selected(projs[0])
                    else:
                        status_label.configure(text=msg, text_color="red")
                try: dialog.after(0, do_update)
                except: pass
            threading.Thread(target=do_test, daemon=True).start()

        def on_verify_pbi():
            u, pat = url_var.get().strip(), pat_var.get().strip()
            proj, pbi = project_var.get().strip(), pbi_id_var.get().strip()
            if not pbi:
                pbi_label.configure(text="Please enter a PBI ID.", text_color="red")
                return
            pbi_label.configure(text="Verifying PBI...", text_color="cyan")
            dialog.update_idletasks()

            def do_verify():
                ok, msg = get_pbi_details(u, proj, pbi, pat)
                def do_update():
                    if ok:
                        pbi_label.configure(text=msg, text_color="lightgreen")
                        btn_start.configure(state="normal")
                    else:
                        pbi_label.configure(text=msg, text_color="red")
                        btn_start.configure(state="disabled")
                try: dialog.after(0, do_update)
                except: pass
            threading.Thread(target=do_verify, daemon=True).start()

        def on_start():
            result["url"]     = url_var.get().strip()
            result["pat"]     = pat_var.get().strip()
            result["project"] = project_var.get().strip()
            result["pbi_id"]  = pbi_id_var.get().strip()
            dialog.destroy()

        def on_cancel():
            cancelled[0] = True
            dialog.destroy()

        btn_connect.configure(command=on_test_connection)
        btn_verify.configure(command=on_verify_pbi)
        btn_start.configure(command=on_start)
        btn_cancel.configure(command=on_cancel)
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        self.frame.wait_window(dialog)

        if cancelled[0] or not result:
            return None
        return result

    def _create_ado_bugs(self, creds, failures):
        """Create ADO bugs for every selected failure and show a progress dialog."""
        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Reporting Bugs to Azure DevOps")
        dialog.geometry("620x450")
        dialog.resizable(True, True)
        dialog.transient(self.frame)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Creating Bugs in Azure DevOps...", font=FONTS["sub_header"]).pack(pady=(15, 5))

        progress_var = tk.DoubleVar()
        progress_bar = ctk.CTkProgressBar(dialog, variable=progress_var)
        progress_bar.pack(fill="x", padx=20, pady=5)
        progress_bar.set(0)

        status_lbl = ctk.CTkLabel(dialog, text="Starting...", font=FONTS["main"], text_color="cyan")
        status_lbl.pack(pady=(0, 5))

        log_box = tk.Text(dialog, height=15, bg="#1e1e1e", fg="white", font=("Courier", 10), state="disabled", relief="flat")
        log_box.pack(fill="both", expand=True, padx=20, pady=5)
        log_box.tag_config("ok",    foreground="#4caf50")
        log_box.tag_config("error", foreground="#f44336")
        log_box.tag_config("info",  foreground="#82aaff")

        close_btn = ctk.CTkButton(dialog, text="Close", command=dialog.destroy, fg_color="gray", hover_color="#404040", font=FONTS["button"], state="disabled")
        close_btn.pack(pady=(5, 15))

        def log(text, tag="info"):
            def _do():
                log_box.configure(state="normal")
                log_box.insert(tk.END, text + "\n", tag)
                log_box.see(tk.END)
                log_box.configure(state="disabled")
            dialog.after(0, _do)

        def run_reporting():
            total   = len(failures)
            success = 0
            errors  = 0
            for i, failure in enumerate(failures):
                tc_name = failure["test_case_name"]
                dialog.after(0, lambda t=tc_name, j=i: status_lbl.configure(
                    text=f"Reporting {j+1}/{total}: {t[:60]}..."))
                log(f"[{i+1}/{total}] {tc_name}", "info")
                try:
                    ok, msg, _ = create_ado_bug(
                        url=creds["url"], project=creds["project"],
                        pat=creds["pat"], pbi_id=creds["pbi_id"],
                        failure=failure,
                    )
                    if ok:
                        success += 1
                        log(f"  \u2714 {msg}", "ok")
                    else:
                        errors += 1
                        log(f"  \u2718 {msg}", "error")
                except Exception as e:
                    errors += 1
                    log(f"  \u2718 Unexpected error: {e}", "error")
                dialog.after(0, lambda p=(i + 1) / total: progress_var.set(p))

            s, e = success, errors
            dialog.after(0, lambda: status_lbl.configure(text=f"Done \u2014 {s} created, {e} error(s)."))
            log(f"\n\u2550\u2550\u2550 Finished: {s} created, {e} errors. \u2550\u2550\u2550",
                "ok" if errors == 0 else "error")
            dialog.after(0, lambda: close_btn.configure(state="normal"))
            dialog.after(0, lambda: self.status_var.set(f"ADO Reporting complete: {s} created, {e} error(s)."))

        threading.Thread(target=run_reporting, daemon=True).start()

    # ------------------------------------------------------------------
    # Update QA Bugs
    # ------------------------------------------------------------------

    def show_update_bugs_dialog(self):
        """Entry point for the 'Update QA Bugs' flow: match config → credentials → run."""
        results_dir = os.path.join(_PROJECT_ROOT, "allure-results")
        if not os.path.exists(results_dir):
            messagebox.showerror("Error", "No test results found. Run tests first.")
            return

        test_cases = scan_all_e2e_results(results_dir)
        if not test_cases:
            messagebox.showinfo("No Results", "No E2E test case results found in allure-results.")
            return

        match_fields = self._show_bug_match_config_dialog()
        if match_fields is None:
            return

        creds = self._show_ado_connection_dialog()
        if creds is None:
            return

        self._run_update_bugs(creds, test_cases, match_fields)

    def _show_bug_match_config_dialog(self):
        """Show checkboxes for which fields to match bugs on. Returns a set of keys or None."""
        result_ref = [None]

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Bug Match Configuration")
        dialog.geometry("460x560")
        dialog.resizable(False, False)
        dialog.transient(self.frame)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Match bugs using:", font=FONTS["sub_header"]).pack(pady=(15, 5))
        ctk.CTkLabel(
            dialog,
            text="Select the fields to use when searching for a matching\n'Ready for QA' bug in ADO for each test case.",
            font=FONTS["main"],
            justify="center",
        ).pack(pady=(0, 10))

        fields = [
            ("transaction_type", "Transaction Type"),
            ("rule_id",          "Rule ID"),
            ("scenario_type",    "Scenario Type"),
            ("object",           "Object"),
            ("element",          "Element"),
            ("failure_tag",      "Failure Tag"),
            ("bug_title",        "Bug Title (test case name)"),
        ]

        vars_ = {}
        checks_frame = ctk.CTkFrame(dialog)
        checks_frame.pack(fill="x", padx=30, pady=5)

        for key, label in fields:
            var = tk.BooleanVar(value=(key == "bug_title"))
            vars_[key] = var
            ctk.CTkCheckBox(checks_frame, text=label, variable=var, font=FONTS["main"]).pack(anchor="w", pady=4)

        ctk.CTkLabel(dialog, text="Matching logic:", font=FONTS["main"], text_color="#aaaaaa").pack(pady=(10, 2))
        desc_label = ctk.CTkLabel(dialog, text="", font=FONTS["main"], wraplength=400, justify="left", text_color="#e0e0e0")
        desc_label.pack(padx=30, anchor="w")

        def build_description():
            selected = {k for k, v in vars_.items() if v.get()}
            if not selected:
                return "No fields selected — no bugs will match."
            criteria = []
            for key, _ in fields:
                if key not in selected:
                    continue
                if key == "transaction_type":
                    criteria.append("Transaction Type tag matches")
                elif key == "rule_id":
                    criteria.append("Rule ID tag matches")
                elif key == "scenario_type":
                    criteria.append("Scenario Type tag matches")
                elif key == "object":
                    criteria.append("Object tag matches")
                elif key == "element":
                    criteria.append("Element tag matches")
                elif key == "failure_tag":
                    criteria.append("Failure Tag matches (skipped for passed tests)")
                elif key == "bug_title":
                    criteria.append("bug title = test case name")
            if len(criteria) == 1:
                joined = criteria[0]
            elif len(criteria) == 2:
                joined = f"{criteria[0]} AND {criteria[1]}"
            else:
                joined = ", ".join(criteria[:-1]) + f", and {criteria[-1]}"
            return f"A bug matches when: {joined}."

        def update_description(*_):
            desc_label.configure(text=build_description())

        for var in vars_.values():
            var.trace_add("write", update_description)
        update_description()

        def on_confirm():
            selected = {k for k, v in vars_.items() if v.get()}
            if not selected:
                messagebox.showwarning("No Fields Selected", "Select at least one field to match on.", parent=dialog)
                return
            result_ref[0] = selected
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(10, 15))
        ctk.CTkButton(btn_frame, text="Continue", command=on_confirm, font=FONTS["button"]).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=on_cancel, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=10)

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        self.frame.wait_window(dialog)
        return result_ref[0]

    def _show_ado_connection_dialog(self):
        """ADO connection dialog (URL, PAT, project) without PBI — used for bug update flow."""
        result = {}
        cancelled = [False]

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Azure DevOps Connection")
        dialog.geometry("560x400")
        dialog.resizable(False, False)
        dialog.transient(self.frame)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Azure DevOps Connection", font=FONTS["sub_header"]).pack(pady=(15, 5))

        url_var     = tk.StringVar(value="https://devops.malaffi.ae/ADHDS")
        pat_var     = tk.StringVar()
        project_var = tk.StringVar()

        step1_frame = ctk.CTkFrame(dialog)
        step1_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(step1_frame, text="1. Server Details", font=FONTS["main_bold"]).pack(anchor="w", padx=10, pady=(10, 5))

        row1 = ctk.CTkFrame(step1_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row1, text="ADO URL:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        ctk.CTkEntry(row1, textvariable=url_var, width=350, placeholder_text="e.g. http://server/tfs/DefaultCollection", font=FONTS["main"]).pack(side="left", padx=5)

        row2 = ctk.CTkFrame(step1_frame, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row2, text="PAT:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        ctk.CTkEntry(row2, textvariable=pat_var, width=200, show="*", font=FONTS["main"]).pack(side="left", padx=5)

        btn_connect = ctk.CTkButton(step1_frame, text="Test Connection", width=120)
        btn_connect.pack(pady=10)

        status_label = ctk.CTkLabel(dialog, text="", text_color="cyan", font=FONTS["main"])
        status_label.pack(pady=5)

        step2_frame = ctk.CTkFrame(dialog)
        step2_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(step2_frame, text="2. Project", font=FONTS["main_bold"]).pack(anchor="w", padx=10, pady=(10, 5))

        row3 = ctk.CTkFrame(step2_frame, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=(5, 15))
        ctk.CTkLabel(row3, text="Project:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        proj_combo = ctk.CTkOptionMenu(row3, variable=project_var, values=["Select a project"], width=250, font=FONTS["main"], state="disabled")
        proj_combo.pack(side="left", padx=5)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(15, 10))
        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray", hover_color="#404040", font=FONTS["button"])
        btn_cancel.pack(side="left", expand=True, padx=5)
        btn_start = ctk.CTkButton(btn_frame, text="Continue", fg_color="#1f538d", font=FONTS["button"], state="disabled")
        btn_start.pack(side="left", expand=True, padx=5)

        def on_test_connection():
            u, pat = url_var.get().strip(), pat_var.get().strip()
            if not u:
                status_label.configure(text="Please provide the ADO URL.", text_color="red")
                return
            status_label.configure(text="Testing connection...", text_color="cyan")
            dialog.update_idletasks()

            def do_test():
                ok, msg, projs = test_ado_connection(u, pat)
                def do_update():
                    if ok:
                        status_label.configure(text=msg, text_color="lightgreen")
                        if projs:
                            proj_combo.configure(values=projs, state="normal")
                            project_var.set(projs[0])
                            btn_start.configure(state="normal")
                    else:
                        status_label.configure(text=msg, text_color="red")
                try: dialog.after(0, do_update)
                except: pass
            threading.Thread(target=do_test, daemon=True).start()

        def on_start():
            result["url"]     = url_var.get().strip()
            result["pat"]     = pat_var.get().strip()
            result["project"] = project_var.get().strip()
            dialog.destroy()

        def on_cancel_cmd():
            cancelled[0] = True
            dialog.destroy()

        btn_connect.configure(command=on_test_connection)
        btn_start.configure(command=on_start)
        btn_cancel.configure(command=on_cancel_cmd)
        dialog.protocol("WM_DELETE_WINDOW", on_cancel_cmd)
        self.frame.wait_window(dialog)

        if cancelled[0] or not result:
            return None
        return result

    def _run_update_bugs(self, creds, test_cases, match_fields=None):
        """For each E2E test case result, find its 'Ready for QA' bug and close or reopen it."""
        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Updating QA Bugs in Azure DevOps")
        dialog.geometry("650x480")
        dialog.resizable(True, True)
        dialog.transient(self.frame)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Updating 'Ready for QA' Bugs...", font=FONTS["sub_header"]).pack(pady=(15, 5))

        progress_var = tk.DoubleVar()
        progress_bar = ctk.CTkProgressBar(dialog, variable=progress_var)
        progress_bar.pack(fill="x", padx=20, pady=5)
        progress_bar.set(0)

        status_lbl = ctk.CTkLabel(dialog, text="Starting...", font=FONTS["main"], text_color="cyan")
        status_lbl.pack(pady=(0, 5))

        log_box = tk.Text(dialog, height=15, bg="#1e1e1e", fg="white", font=("Courier", 10), state="disabled", relief="flat")
        log_box.pack(fill="both", expand=True, padx=20, pady=5)
        log_box.tag_config("ok",      foreground="#4caf50")
        log_box.tag_config("error",   foreground="#f44336")
        log_box.tag_config("info",    foreground="#82aaff")
        log_box.tag_config("skipped", foreground="#aaaaaa")

        close_btn = ctk.CTkButton(dialog, text="Close", command=dialog.destroy, fg_color="gray", hover_color="#404040", font=FONTS["button"], state="disabled")
        close_btn.pack(pady=(5, 15))

        def log(text, tag="info"):
            log_box.configure(state="normal")
            log_box.insert(tk.END, text + "\n", tag)
            log_box.see(tk.END)
            log_box.configure(state="disabled")
            dialog.update_idletasks()

        def run():
            log("Fetching all 'Ready for QA' bugs from ADO...", "info")
            status_lbl.configure(text="Fetching 'Ready for QA' bugs from ADO...")
            dialog.update_idletasks()

            bugs, fetch_err = get_all_ready_for_qa_bugs(
                url=creds["url"], project=creds["project"], pat=creds["pat"]
            )

            if fetch_err:
                log(f"\u2718 Failed to fetch bugs: {fetch_err}", "error")
                close_btn.configure(state="normal")
                return

            if not bugs:
                log("No 'Ready for QA' bugs found in ADO.", "skipped")
                close_btn.configure(state="normal")
                return

            log(f"Found {len(bugs)} 'Ready for QA' bug(s). Matching against {len(test_cases)} executed test case(s)...", "info")

            total    = len(bugs)
            closed   = 0
            reopened = 0
            skipped  = 0
            errors   = 0

            for i, bug in enumerate(bugs):
                wi_id = bug["id"]
                title = bug["title"]
                status_lbl.configure(text=f"Processing {i+1}/{total}: Bug #{wi_id}...")
                log(f"[{i+1}/{total}] Bug #{wi_id}: {title[:60]}", "info")

                try:
                    tc = match_bug_to_test_case(bug, test_cases, match_fields)

                    if tc is None:
                        log("  \u23ed No matching executed test case found", "skipped")
                        skipped += 1
                        progress_var.set((i + 1) / total)
                        dialog.update_idletasks()
                        continue

                    tc_name   = tc["test_case_name"]
                    tc_status = tc["status"]
                    log(f"  Matched: {tc_name}  [{tc_status}]", "info")

                    new_state = "Ready for Release" if tc.get("qa_outcome") == "close" else "Reopened"
                    ok, msg = update_bug_for_qa_result(
                        url=creds["url"], project=creds["project"], pat=creds["pat"],
                        work_item_id=wi_id, test_case=tc, new_state=new_state,
                    )

                    if ok:
                        if new_state == "Ready for Release":
                            closed += 1
                        else:
                            reopened += 1
                        log(f"  \u2714 {msg}", "ok")
                    else:
                        errors += 1
                        log(f"  \u2718 {msg}", "error")

                except Exception as e:
                    errors += 1
                    log(f"  \u2718 Unexpected error: {e}", "error")

                progress_var.set((i + 1) / total)
                dialog.update_idletasks()

            summary = (
                f"Done \u2014 {closed} closed, {reopened} reopened, "
                f"{skipped} skipped (no match), {errors} error(s)."
            )
            status_lbl.configure(text=summary)
            log(f"\n\u2550\u2550\u2550 {summary} \u2550\u2550\u2550", "ok" if errors == 0 else "error")
            close_btn.configure(state="normal")
            self.status_var.set(f"QA bug update complete: {closed} closed, {reopened} reopened.")

        threading.Thread(target=run, daemon=True).start()
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        self.frame.wait_window(dialog)

    # ------------------------------------------------------------------
    # Table rendering
    # ------------------------------------------------------------------

    def populate_table(self):
        self.tree.delete(*self.tree.get_children())

        if not self.all_data or not self.columns:
            return

        step_cols = [c for c in self.columns if c != TC_ID_COL]
        self.tree["columns"] = step_cols
        self.tree.column("#0", width=220, minwidth=120, stretch=False)
        self.tree.heading("#0", text=TC_ID_COL)
        for col in step_cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150, minwidth=80)

        for tc in self.test_cases:
            parent = self.tree.insert(
                "", "end",
                text=tc["tc_id"],
                values=[""] * len(step_cols),
                open=False,
                tags=("tc_header",),
            )
            for step_idx, row in enumerate(tc["steps"]):
                tag = "step_odd" if step_idx % 2 == 0 else "step_even"
                self.tree.insert(
                    parent, "end",
                    text=f"  Step {step_idx + 1}",
                    values=[row.get(col, "") for col in step_cols],
                    tags=(tag,),
                )

    # ------------------------------------------------------------------
    # Cell viewer
    # ------------------------------------------------------------------

    def _on_cell_double_click(self, event):
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id:
            return

        step_cols = [c for c in self.columns if c != TC_ID_COL]

        if col_id == "#0":
            self._show_cell_dialog(TC_ID_COL, self.tree.item(row_id, "text"))
        else:
            col_index = int(col_id.replace("#", "")) - 1  # 0-based into step_cols
            if col_index < 0 or col_index >= len(step_cols):
                return
            col_name = step_cols[col_index]
            values = self.tree.item(row_id, "values")
            value = values[col_index] if col_index < len(values) else ""
            self._show_cell_dialog(col_name, value)

    def _show_cell_dialog(self, col_name, value):
        dialog = ctk.CTkToplevel(self.frame)
        dialog.title(col_name)
        dialog.geometry("800x500")
        dialog.transient(self.frame)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text=col_name, font=FONTS["sub_header"]).pack(anchor="w", padx=12, pady=(10, 4))

        text = ctk.CTkTextbox(dialog, font=FONTS["code"], wrap="none")
        text.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        text.insert("1.0", value)
        text.configure(state="disabled")

        ctk.CTkButton(
            dialog, text="Close", command=dialog.destroy,
            fg_color="gray", hover_color="#404040", font=FONTS["button"], width=100
        ).pack(pady=(0, 10))
