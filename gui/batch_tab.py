"""
Batch Testing Tab - Complete version with multi-sheet support, pagination, and execution dialog
"""
from utils.csv_custom_report import generate_custom_combined_report, get_available_rules_summary_columns
from utils.env_vars import EnvVar
from utils.execution_mode import ExecutionMode
from utils.azure_reporting import (
    create_ado_bug, scan_failures_by_tag,
    AVAILABLE_REPORT_TAGS, SYSTEM1_AVAILABLE_REPORT_TAGS,
    TARGET_TAGS, SYSTEM1_TARGET_TAGS,
    test_ado_connection, get_pbi_details, check_existing_bug,
    scan_all_results, scan_all_batch_results, update_bug_for_qa_result,
    get_all_ready_for_qa_bugs, get_all_closed_bugs, match_bug_to_test_case,
    add_failure_comment,
)
import json
import os
import re
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk
from pathlib import Path
from utils.excel_handler import ExcelHandler, validate_excel, create_excel_template
from utils.api_client import APIClient
from utils.variable_processor import VariableProcessor
import threading
from datetime import datetime
import shutil
from .theme import FONTS


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        
        frame = tk.Frame(self.tooltip_window, background="#ffffe0", relief="solid", borderwidth=1)
        frame.pack()
        
        label = tk.Label(frame, text=self.text, background="#ffffe0", foreground="black", justify="left", font=("Arial", 10))
        label.pack(padx=5, pady=2)
        
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class BatchTab:
    def __init__(self, parent):
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.pack(fill="both", expand=True)
        
        self.excel_handler = ExcelHandler()
        self.api_client = APIClient()
        self.variable_processor = VariableProcessor()
        self.testing_active = False
        self.sheet_names = []
        self.current_sheet = None
        self.current_process = None
        self.rules_summary_filename = "rules_summary.xlsx"
        self.legacy_summary_filename = "legacy_rules_summary.xlsx"
        self.custom_report_filename = "custom_report.xlsx"
        self.custom_report_sheets = [] # Stores selected sheets for custom report
        self.generate_custom_report = False
        self.full_report_comparison = None
        self.full_row_comparison = None
        self.last_custom_report_path = None  # Path of the last successfully saved custom report
        self.last_allure_dir = None           # Allure results dir used for the last report
        self.allure_report_generated = False


        # Pagination variables
        self.all_data = []  # Complete dataset
        self.current_page = 0
        self.rows_per_page = 100  # Default: 100 rows per page
        self.total_pages = 0

        # Sheet data cache for all sheets
        self.all_sheets_data = {}  # {sheet_name: data}

        self.use_specific_login = None
        self.provider_value = None
        self.payer_value = None
        self.tpa_value = None
        self.pharmacy_value = None
        self.use_custom_disposition_flag = None
        self.custom_disposition_flag_value = None

        self.create_widgets()

    def create_widgets(self):
        """Create batch testing widgets"""
        # Create scrollable container
        self.main_frame = ctk.CTkScrollableFrame(self.frame)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Description
        desc_text = "This tab is used for testing the upload transactions rules validation. An xml template is generated, request is sent, and assertion is made for the response against rules. Only 'Person Register, Prior Request, Prior Authorization, Claim Submission, Remittance Advice, Cost Submission' can be used here."
        ctk.CTkLabel(self.main_frame, text=desc_text, wraplength=800, justify="center", font=FONTS["main"]).pack(anchor="center", pady=(0, 15))

        # File selection
        file_frame = ctk.CTkFrame(self.main_frame)
        file_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(file_frame, text="Excel File:", anchor="w", font=FONTS["main_bold"]).pack(side="left", padx=10)
        self.file_path_var = tk.StringVar()
        ctk.CTkEntry(file_frame, textvariable=self.file_path_var, width=400, font=FONTS["main"]).pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(file_frame, text="Browse", command=self.browse_file, width=80, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(file_frame, text="Load", command=self.load_file, width=80, font=FONTS["button"]).pack(side="left", padx=5)

        # Sheet selection frame (initially hidden)
        self.sheet_frame = ctk.CTkFrame(self.main_frame)
        # Don't pack yet

        ctk.CTkLabel(self.sheet_frame, text="Select Sheet:", anchor="w", font=FONTS["main_bold"]).pack(side="left", padx=10)
        self.sheet_combo = ctk.CTkOptionMenu(self.sheet_frame, values=[], command=self.on_sheet_selected_optionmenu, width=200, font=FONTS["main"], dropdown_font=FONTS["main"])
        self.sheet_combo.pack(side="left", padx=5)
        
        ctk.CTkButton(self.sheet_frame, text="Refresh", command=self.refresh_sheet, width=80, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=5)

        # Pagination controls frame
        self.pagination_frame = ctk.CTkFrame(self.main_frame)
        # Will be shown when data is loaded

        # Left side - rows per page
        left_controls = ctk.CTkFrame(self.pagination_frame, fg_color="transparent")
        left_controls.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(left_controls, text="Rows per page:", anchor="w", font=FONTS["main"]).pack(side="left", padx=10)
        self.rows_per_page_var = tk.StringVar(value="100")
        rows_combo = ctk.CTkOptionMenu(left_controls, variable=self.rows_per_page_var,
                                  values=["50", "100", "200", "500", "1000", "All"],
                                  command=self.on_rows_per_page_changed_optionmenu,
                                  width=100, font=FONTS["main"], dropdown_font=FONTS["main"])
        rows_combo.pack(side="left", padx=5)

        # Right side - pagination controls
        right_controls = ctk.CTkFrame(self.pagination_frame, fg_color="transparent")
        right_controls.pack(side="right", padx=10)

        ctk.CTkButton(right_controls, text="|<<", command=self.go_to_first_page, width=40, height=24, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), font=FONTS["small"]).pack(side="left", padx=2)
        ctk.CTkButton(right_controls, text="<", command=self.go_to_prev_page, width=40, height=24, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), font=FONTS["small"]).pack(side="left", padx=2)

        self.page_label = ctk.CTkLabel(right_controls, text="Page 0 of 0", width=150, font=FONTS["main"])
        self.page_label.pack(side="left", padx=5)

        ctk.CTkButton(right_controls, text=">", command=self.go_to_next_page, width=40, height=24, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), font=FONTS["small"]).pack(side="left", padx=2)
        ctk.CTkButton(right_controls, text=">>|", command=self.go_to_last_page, width=40, height=24, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), font=FONTS["small"]).pack(side="left", padx=2)

        # Jump to page
        ctk.CTkLabel(right_controls, text="Go to:", font=FONTS["main"]).pack(side="left", padx=(10, 5))
        self.page_entry = ctk.CTkEntry(right_controls, width=50, font=FONTS["main"])
        self.page_entry.pack(side="left", padx=(0, 5))
        self.page_entry.bind('<Return>', self.go_to_page)
        ctk.CTkButton(right_controls, text="Go", command=self.go_to_page, width=40, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), font=FONTS["button"]).pack(side="left")

        # Configurations Group
        config_grid = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        config_grid.pack(fill="x", pady=(0, 10))

        # Config Column 1
        col1 = ctk.CTkFrame(config_grid)
        col1.pack(side="left", fill="both", expand=True, padx=(0, 5))
        ctk.CTkLabel(col1, text="Execution Sequence", font=FONTS["sub_header"]).pack(anchor="w", padx=10, pady=5)
        
        self.execution_sequence = tk.StringVar(value="full_scenario")
        ctk.CTkRadioButton(col1, text="Single API", variable=self.execution_sequence, value="single_api", font=FONTS["main"]).pack(anchor="w", padx=10, pady=2)
        ctk.CTkRadioButton(col1, text="Full Scenario", variable=self.execution_sequence, value="full_scenario", font=FONTS["main"]).pack(anchor="w", padx=10, pady=2)
        delay_row = ctk.CTkFrame(col1, fg_color="transparent")
        delay_row.pack(anchor="w", padx=10, pady=(4, 2))
        self.step_delay_label = ctk.CTkLabel(delay_row, text="Delay between steps:", font=FONTS["main"])
        self.step_delay_label.pack(side="left")
        self.step_delay_var = tk.StringVar(value="0")
        self.step_delay_entry = ctk.CTkEntry(delay_row, textvariable=self.step_delay_var, width=50, font=FONTS["main"])
        self.step_delay_entry.pack(side="left", padx=5)
        self.step_delay_unit_label = ctk.CTkLabel(delay_row, text="sec", font=FONTS["main"])
        self.step_delay_unit_label.pack(side="left")
        self.execution_sequence.trace_add("write", self.on_execution_sequence_change)
        self.on_execution_sequence_change()

        # Config Column 2
        col2 = ctk.CTkFrame(config_grid)
        col2.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(col2, text="Execution Mode", font=FONTS["sub_header"]).pack(anchor="w", padx=10, pady=5)

        self.execution_mode = tk.StringVar(value=ExecutionMode.SYSTEM1_ONLY)
        ctk.CTkRadioButton(col2, text="System legacy", variable=self.execution_mode, value=ExecutionMode.SYSTEM1_ONLY, command=self.on_mode_change, font=FONTS["main"]).pack(anchor="w", padx=10, pady=2)
        ctk.CTkRadioButton(col2, text="System 2.0", variable=self.execution_mode, value=ExecutionMode.SYSTEM2_ONLY, command=self.on_mode_change, font=FONTS["main"]).pack(anchor="w", padx=10, pady=2)
        ctk.CTkRadioButton(col2, text="Both Systems", variable=self.execution_mode, value=ExecutionMode.BOTH_SYSTEMS, command=self.on_mode_change, font=FONTS["main"]).pack(anchor="w", padx=10, pady=2)
        ctk.CTkRadioButton(col2, text="Both environments of legacy system", variable=self.execution_mode, value=ExecutionMode.SYSTEM1_BOTH_ENVS, command=self.on_mode_change, font=FONTS["main"]).pack(anchor="w", padx=10, pady=2)

        # Config Column 3
        col3 = ctk.CTkFrame(config_grid)
        col3.pack(side="left", fill="both", expand=True, padx=(5, 5))
        ctk.CTkLabel(col3, text="1.0 Target Environment", font=FONTS["sub_header"]).pack(anchor="w", padx=10, pady=5)
        
        self.target_env = tk.StringVar(value="pte")
        self.pte_radio = ctk.CTkRadioButton(col3, text="PTE", variable=self.target_env, value="pte", font=FONTS["main"])
        self.pte_radio.pack(anchor="w", padx=10, pady=2)
        self.prod_radio = ctk.CTkRadioButton(col3, text="Production", variable=self.target_env, value="production", text_color="red", font=FONTS["main"])
        self.prod_radio.pack(anchor="w", padx=10, pady=2)

        # Config Column 4
        col4 = ctk.CTkFrame(config_grid)
        col4.pack(side="left", fill="both", expand=True, padx=(0, 5))
        ctk.CTkLabel(col4, text="2.0 Target Environment", font=FONTS["sub_header"]).pack(anchor="w", padx=10, pady=5)
        
        self.new_target_env = tk.StringVar(value="test")
        self.new_target_test_radio = ctk.CTkRadioButton(col4, text="Test", variable=self.new_target_env, value="test", font=FONTS["main"])
        self.new_target_test_radio.pack(anchor="w", padx=10, pady=2)
        self.new_target_dev_radio = ctk.CTkRadioButton(col4, text="Dev", variable=self.new_target_env, value="dev", font=FONTS["main"])
        self.new_target_dev_radio.pack(anchor="w", padx=10, pady=2)
        self.new_target_uat_radio = ctk.CTkRadioButton(col4, text="UAT", variable=self.new_target_env, value="uat", font=FONTS["main"])
        self.new_target_uat_radio.pack(anchor="w", padx=10, pady=2)
        self.new_target_stage_radio = ctk.CTkRadioButton(col4, text="Stage", variable=self.new_target_env, value="stage", font=FONTS["main"])
        self.new_target_stage_radio.pack(anchor="w", padx=10, pady=2)

        # Parallel Execution
        parallel_frame = ctk.CTkFrame(self.main_frame)
        parallel_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(parallel_frame, text="Parallel Execution & Options", font=FONTS["sub_header"]).pack(anchor="w", padx=10, pady=5)
        
        p_inner = ctk.CTkFrame(parallel_frame, fg_color="transparent")
        p_inner.pack(fill="x", padx=10, pady=5)
        
        self.enable_parallel = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(p_inner, text="Enable Parallel Execution", variable=self.enable_parallel, font=FONTS["main"]).pack(side="left", padx=(0, 20))
        
        ctk.CTkLabel(p_inner, text="Workers:", font=FONTS["main"]).pack(side="left")
        self.worker_count = tk.StringVar(value="auto")
        ctk.CTkOptionMenu(p_inner, variable=self.worker_count, values=["auto", "2", "3", "4", "6", "8", "10", "12"], width=80, font=FONTS["main"], dropdown_font=FONTS["main"]).pack(side="left", padx=5)

        # Specific User Login
        login_frame = ctk.CTkFrame(self.main_frame)
        login_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(login_frame, text="Use specific user login", font=FONTS["sub_header"]).pack(anchor="w", padx=10, pady=5)
        
        l_inner = ctk.CTkFrame(login_frame, fg_color="transparent")
        l_inner.pack(fill="x", padx=10, pady=5)
        
        self.use_specific_login = tk.BooleanVar(value=False)
        self.provider_value = tk.StringVar(value="MalaffiProvidertestD")
        self.payer_value = tk.StringVar(value="MalaffiPayertestD")
        self.tpa_value = tk.StringVar(value="MalaffiPayer2testD")
        self.pharmacy_value = tk.StringVar(value="MalaffiProvider2testD")

        def toggle_login_entry():
            state = "normal" if self.use_specific_login.get() else "disabled"
            self.provider_entry.configure(state=state)
            self.payer_entry.configure(state=state)
            self.tpa_entry.configure(state=state)
            self.pharmacy_entry.configure(state=state)

        ctk.CTkCheckBox(l_inner, text="Enable", variable=self.use_specific_login, command=toggle_login_entry, font=FONTS["main"]).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(l_inner, text="Provider:", font=FONTS["main"]).pack(side="left", padx=(0, 5))
        self.provider_entry = ctk.CTkEntry(l_inner, textvariable=self.provider_value, width=150, font=FONTS["main"])
        self.provider_entry.pack(side="left", padx=5)

        ctk.CTkLabel(l_inner, text="Payer:", font=FONTS["main"]).pack(side="left", padx=(10, 5))
        self.payer_entry = ctk.CTkEntry(l_inner, textvariable=self.payer_value, width=150, font=FONTS["main"])
        self.payer_entry.pack(side="left", padx=5)

        ctk.CTkLabel(l_inner, text="TPA:", font=FONTS["main"]).pack(side="left", padx=(10, 5))
        self.tpa_entry = ctk.CTkEntry(l_inner, textvariable=self.tpa_value, width=150, font=FONTS["main"])
        self.tpa_entry.pack(side="left", padx=5)

        ctk.CTkLabel(l_inner, text="Pharmacy:", font=FONTS["main"]).pack(side="left", padx=(10, 5))
        self.pharmacy_entry = ctk.CTkEntry(l_inner, textvariable=self.pharmacy_value, width=150, font=FONTS["main"])
        self.pharmacy_entry.pack(side="left", padx=5)

        toggle_login_entry() # Initial state

        # Custom Disposition Flag
        disposition_frame = ctk.CTkFrame(self.main_frame)
        disposition_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(disposition_frame, text="Custom Disposition Flag", font=FONTS["sub_header"]).pack(anchor="w", padx=10, pady=5)

        df_inner = ctk.CTkFrame(disposition_frame, fg_color="transparent")
        df_inner.pack(fill="x", padx=10, pady=5)

        self.use_custom_disposition_flag = tk.BooleanVar(value=False)
        self.custom_disposition_flag_value = tk.StringVar(value="")

        def toggle_disposition_entry():
            state = "normal" if self.use_custom_disposition_flag.get() else "disabled"
            self.disposition_flag_entry.configure(state=state)

        ctk.CTkCheckBox(df_inner, text="Enable", variable=self.use_custom_disposition_flag, command=toggle_disposition_entry, font=FONTS["main"]).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(df_inner, text="Disposition Flag:", font=FONTS["main"]).pack(side="left", padx=(0, 5))
        self.disposition_flag_entry = ctk.CTkEntry(df_inner, textvariable=self.custom_disposition_flag_value, width=200, font=FONTS["main"])
        self.disposition_flag_entry.pack(side="left", padx=5)

        toggle_disposition_entry()  # Initial state

        # Assertions
        opts_frame = ctk.CTkFrame(self.main_frame)
        opts_frame.pack(fill="x", pady=(0, 10))

        self.assert_error_text = tk.BooleanVar(value=False)
        self.assert_error_text_cb = ctk.CTkCheckBox(opts_frame, text="Assert Error Text", variable=self.assert_error_text, command=self.on_mode_change, font=FONTS["main"])
        self.assert_error_text_cb.pack(side="left", padx=10, pady=10)

        self.assert_object_element = tk.BooleanVar(value=False)
        self.assert_object_element_cb = ctk.CTkCheckBox(opts_frame, text="Assert Object/Element", variable=self.assert_object_element, font=FONTS["main"])
        self.assert_object_element_cb.pack(side="left", padx=10, pady=10)

        self.assert_field_additional = tk.BooleanVar(value=False)
        self.assert_field_additional_cb = ctk.CTkCheckBox(opts_frame, text="Assert Field/Additional", variable=self.assert_field_additional, font=FONTS["main"])
        self.assert_field_additional_cb.pack(side="left", padx=10, pady=10)

        self.full_report_comparison = tk.BooleanVar(value=False)
        self.full_report_comparison_cb = ctk.CTkCheckBox(
            opts_frame,
            text="Enable full report comparison",
            variable=self.full_report_comparison,
            font=FONTS["main"],
            state="disabled",
            command=self._on_full_report_comparison_changed
        )
        self.full_report_comparison_cb.pack(side="left", padx=10, pady=10)

        self.full_row_comparison = tk.BooleanVar(value=False)
        self.full_row_comparison_cb = ctk.CTkCheckBox(
            opts_frame,
            text="Full Row Comparison",
            variable=self.full_row_comparison,
            font=FONTS["main"],
            state="disabled",
            command=self._on_full_row_comparison_changed
        )
        self.full_row_comparison_cb.pack(side="left", padx=10, pady=10)



        # Reporting options
        reporting_frame = ctk.CTkFrame(self.main_frame)
        reporting_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(reporting_frame, text="Allure HTML Reporting", font=FONTS["sub_header"]).pack(anchor="w", padx=10, pady=5)
        
        r_inner = ctk.CTkFrame(reporting_frame, fg_color="transparent")
        r_inner.pack(fill="x", padx=10, pady=5)
        
        if getattr(sys, 'frozen', False):
            _base = Path(sys.executable).parent
            self.allure_results_dir = tk.StringVar(value=str(_base / "allure-results"))
        else:
            self.allure_results_dir = tk.StringVar(value="allure-results")
        ctk.CTkButton(r_inner, text="Open Last Report", command=self.open_allure_report, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(r_inner, text="Generate HTML", command=self.generate_allure_html_report_manual, fg_color="#1f538d", font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(r_inner, text="Save Report", command=self.save_allure_report, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left")

        # Preview table
        ctk.CTkLabel(self.main_frame, text="File Preview:", font=FONTS["sub_header"]).pack(anchor="w", padx=5)

        tree_frame = ctk.CTkFrame(self.main_frame)
        tree_frame.pack(fill="both", expand=True, pady=(0, 10))

        # Use standard ttk Treeview but styled
        self.tree = ttk.Treeview(tree_frame, show='headings')
        
        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")

        # Progress and status
        progress_frame = ctk.CTkFrame(self.main_frame)
        progress_frame.pack(fill="x", pady=(0, 10))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ctk.CTkProgressBar(progress_frame, variable=self.progress_var)
        self.progress_bar.pack(fill="x", padx=10, pady=(10, 5))
        self.progress_bar.set(0)

        self.status_var = tk.StringVar(value="Ready")
        ctk.CTkLabel(progress_frame, textvariable=self.status_var, text_color="cyan", font=FONTS["main"]).pack(anchor="w", padx=10, pady=(0, 10))

        # Control buttons
        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=10)

        ctk.CTkButton(button_frame, text="Create Template", command=self.create_template, fg_color="#1f538d", font=FONTS["button"]).pack(side="left", padx=(0, 10))
        ctk.CTkButton(button_frame, text="Run Tests", command=self.show_execution_dialog, fg_color="green", hover_color="#006400", width=150, font=FONTS["button"]).pack(side="left", padx=(0, 10))
        ctk.CTkButton(button_frame, text="Stop", command=self.stop_tests, fg_color="red", hover_color="#8b0000", font=FONTS["button"]).pack(side="left", padx=(0, 10))
        self.regenerate_btn = ctk.CTkButton(
            button_frame,
            text="Generate Custom Report",
            command=self.regenerate_custom_report,
            fg_color="#6a0dad",
            hover_color="#4b0082",
            font=FONTS["button"]
        )
        self.regenerate_btn.pack(side="left")
        ToolTip(self.regenerate_btn, "Generate a custom report from the existing allure-results folder\n(no need to re-run tests)")

        self.ado_report_btn = ctk.CTkButton(
            button_frame,
            text="Report Failures ADO",
            command=self.show_ado_report_dialog,
            fg_color="#b85c00",
            hover_color="#7a3c00",
            font=FONTS["button"]
        )
        self.ado_report_btn.pack(side="left", padx=(10, 0))
        ToolTip(self.ado_report_btn, "Report failures as bugs in Azure DevOps")

        self.ado_update_bugs_btn = ctk.CTkButton(
            button_frame,
            text="Update QA Bugs",
            command=self.show_update_bugs_dialog,
            fg_color="#1a6b4a",
            hover_color="#134d36",
            font=FONTS["button"]
        )
        self.ado_update_bugs_btn.pack(side="left", padx=(10, 0))
        ToolTip(self.ado_update_bugs_btn, "For each executed test case, find its 'Ready for QA' bug in ADO\nand close it (pass) or reopen it (fail)")

        self.ado_was_ever_reported_btn = ctk.CTkButton(
            button_frame,
            text="Was Ever Reported",
            command=self.show_was_ever_reported_dialog,
            fg_color="#4a4a8a",
            hover_color="#33336b",
            font=FONTS["button"]
        )
        self.ado_was_ever_reported_btn.pack(side="left", padx=(10, 0))
        ToolTip(self.ado_was_ever_reported_btn, "Find test cases that have a Closed bug in ADO\nbut no 'Ready for QA' bug — i.e. were ever reported but not currently in QA")

        # Initial state update
        self.on_mode_change()


    # ──────────────────────────────────────────────────────────────────────────
    # Azure DevOps Reporting
    # ──────────────────────────────────────────────────────────────────────────

    def show_ado_report_dialog(self):
        """Main entry point: tag selection + preview → credentials → create bugs."""
        allure_dir = self.allure_results_dir.get() if hasattr(self, 'allure_results_dir') else "allure-results"
        if not Path(allure_dir).exists():
            messagebox.showerror("Error", f"Allure results directory not found:\n{allure_dir}")
            return

        mode = self.execution_mode.get()
        if mode == ExecutionMode.SYSTEM2_ONLY:
            report_tags  = SYSTEM1_AVAILABLE_REPORT_TAGS
            target_tags  = SYSTEM1_TARGET_TAGS
        else:
            report_tags  = AVAILABLE_REPORT_TAGS
            target_tags  = TARGET_TAGS

        # Step 1: tag selector + case list + preview
        selected = self._show_tag_selection_and_preview_dialog(allure_dir, report_tags, target_tags)
        if not selected:
            self.status_var.set("Ready")
            return

        # Step 2: credentials
        creds = self._show_ado_credentials_dialog()
        if creds is None:
            self.status_var.set("Ready")
            return

        # Step 3: create bugs
        self._create_ado_bugs(creds, selected, target_tags)


    def _show_ado_credentials_dialog(self):
        """
        Show a modal dialog asking for ADO credentials, tests connection, selects project, and validates PBI.
        Returns a dict with keys: url, username, password, project, pbi_id
        or None if the user cancelled.
        """
        result = {}
        cancelled = [False]

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Azure DevOps Connection")
        dialog.geometry("560x640")
        dialog.resizable(False, False)
        dialog.transient(self.frame)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Azure DevOps Wizard", font=FONTS["sub_header"]).pack(pady=(15, 5))

        url_var      = tk.StringVar(value="https://devops.malaffi.ae/ADHDS")
        pat_var      = tk.StringVar()
        project_var  = tk.StringVar()
        pbi_id_var   = tk.StringVar()
        priority_var = tk.StringVar(value="2")
        severity_var = tk.StringVar(value="3 - Medium")
        assignee_var = tk.StringVar()

        step1_frame = ctk.CTkFrame(dialog)
        step1_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(step1_frame, text="1. Server Details", font=FONTS["main_bold"]).pack(anchor="w", padx=10, pady=(10,5))
        
        row1 = ctk.CTkFrame(step1_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row1, text="ADO URL:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        ctk.CTkEntry(row1, textvariable=url_var, width=350, placeholder_text="e.g. http://server/tfs/DefaultCollection", font=FONTS["main"]).pack(side="left", padx=5)

        row3 = ctk.CTkFrame(step1_frame, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row3, text="PAT:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        ctk.CTkEntry(row3, textvariable=pat_var, width=200, show="*", font=FONTS["main"]).pack(side="left", padx=5)

        status_label = ctk.CTkLabel(dialog, text="", text_color="cyan", font=FONTS["main"])
        status_label.pack(pady=5)

        step2_frame = ctk.CTkFrame(dialog)
        step2_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(step2_frame, text="2. Project & PBI", font=FONTS["main_bold"]).pack(anchor="w", padx=10, pady=(10,5))
        
        def on_project_selected(value):
            if value and value != "Select a project":
                pbi_entry.configure(state="normal")
                btn_verify_pbi.configure(state="normal")

        row4 = ctk.CTkFrame(step2_frame, fg_color="transparent")
        row4.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row4, text="Project:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        proj_combo = ctk.CTkOptionMenu(row4, variable=project_var, values=["Select a project"], width=250, font=FONTS["main"], state="disabled", command=on_project_selected)
        proj_combo.pack(side="left", padx=5)

        row5 = ctk.CTkFrame(step2_frame, fg_color="transparent")
        row5.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row5, text="PBI ID:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        pbi_entry = ctk.CTkEntry(row5, textvariable=pbi_id_var, width=120, font=FONTS["main"], state="disabled")
        pbi_entry.pack(side="left", padx=5)
        
        btn_verify_pbi = ctk.CTkButton(row5, text="Verify PBI", width=100, state="disabled")
        btn_verify_pbi.pack(side="left", padx=5)

        pbi_name_label = ctk.CTkLabel(step2_frame, text="", text_color="lightgreen", font=FONTS["main"])
        pbi_name_label.pack(anchor="w", padx=120, pady=2)

        step3_frame = ctk.CTkFrame(dialog)
        step3_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(step3_frame, text="3. Bug Details", font=FONTS["main_bold"]).pack(anchor="w", padx=10, pady=(10, 5))

        row_pri = ctk.CTkFrame(step3_frame, fg_color="transparent")
        row_pri.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row_pri, text="Priority:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        ctk.CTkOptionMenu(row_pri, variable=priority_var, values=["1", "2", "3", "4"], width=80, font=FONTS["main"]).pack(side="left", padx=5)

        row_sev = ctk.CTkFrame(step3_frame, fg_color="transparent")
        row_sev.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row_sev, text="Severity:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        ctk.CTkOptionMenu(row_sev, variable=severity_var,
                          values=["1 - Critical", "2 - High", "3 - Medium", "4 - Low"],
                          width=200, font=FONTS["main"]).pack(side="left", padx=5)

        row_asn = ctk.CTkFrame(step3_frame, fg_color="transparent")
        row_asn.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row_asn, text="Assignee:", width=100, anchor="w", font=FONTS["main"]).pack(side="left")
        ctk.CTkEntry(row_asn, textvariable=assignee_var, width=300, font=FONTS["main"],
                     placeholder_text="Leave blank to auto-assign to yourself").pack(side="left", padx=5)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(15, 10))

        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray", hover_color="#404040", font=FONTS["button"])
        btn_cancel.pack(side="left", expand=True, padx=5)

        btn_connect = ctk.CTkButton(step1_frame, text="Test Connection", width=120)
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
                pbi_name_label.configure(text="Please enter a PBI ID.", text_color="red")
                return
            pbi_name_label.configure(text="Verifying PBI...", text_color="cyan")
            dialog.update_idletasks()
            
            def do_verify():
                ok, msg = get_pbi_details(u, proj, pbi, pat)
                def do_update():
                    if ok:
                        pbi_name_label.configure(text=msg, text_color="lightgreen")
                        btn_start.configure(state="normal")
                    else:
                        pbi_name_label.configure(text=msg, text_color="red")
                        btn_start.configure(state="disabled")
                try: dialog.after(0, do_update)
                except: pass
            threading.Thread(target=do_verify, daemon=True).start()

        def on_start():
            result["url"]      = url_var.get().strip()
            result["pat"]      = pat_var.get().strip()
            result["project"]  = project_var.get().strip()
            result["pbi_id"]   = pbi_id_var.get().strip()
            result["priority"] = priority_var.get().strip()
            result["severity"] = severity_var.get().strip()
            result["assignee"] = assignee_var.get().strip()
            dialog.destroy()

        def on_cancel_cmd():
            cancelled[0] = True
            dialog.destroy()

        btn_connect.configure(command=on_test_connection)
        btn_verify_pbi.configure(command=on_verify_pbi)
        btn_start.configure(command=on_start)
        btn_cancel.configure(command=on_cancel_cmd)
        
        dialog.protocol("WM_DELETE_WINDOW", on_cancel_cmd)
        self.frame.wait_window(dialog)

        if cancelled[0] or not result:
            return None
        return result


    def _show_tag_selection_and_preview_dialog(self, allure_dir, report_tags=None, target_tags=None):
        """
        Combined dialog: pick a tag → see filtered case list → click a case to preview
        the full bug (title + attachments) before reporting.
        Returns a list of selected failure dicts, or None if cancelled.
        """
        if report_tags is None:
            report_tags = AVAILABLE_REPORT_TAGS
        if target_tags is None:
            target_tags = TARGET_TAGS
        result_ref   = [None]
        cancelled    = [False]
        failures_ref     = []      # currently shown failures
        check_vars       = []      # BooleanVar per visible page row
        row_frames       = []      # CTkFrame per visible page row (for highlight)
        active_row       = [None]  # currently highlighted row frame
        fp_groups        = {}      # fingerprint → list of indices (shared between _on_done and unique-only button)
        selected_set     = set()   # global indices of selected failures
        current_page_ref = [0]     # current page (0-based)
        _bulk_updating   = [False] # suppresses per-checkbox _update_count during bulk ops
        _PAGE_SIZE       = 200     # failures shown per page

        # Uniqueness criteria BooleanVars (all enabled by default)
        fp_use_transaction_type = tk.BooleanVar(value=True)
        fp_use_rule_id          = tk.BooleanVar(value=True)
        fp_use_scenario_type    = tk.BooleanVar(value=True)
        fp_use_object           = tk.BooleanVar(value=True)
        fp_use_element          = tk.BooleanVar(value=True)
        fp_use_failure_reason   = tk.BooleanVar(value=True)
        fp_use_error_text       = tk.BooleanVar(value=False)
        fp_use_bug_title        = tk.BooleanVar(value=False)
        fp_use_sheet_name       = tk.BooleanVar(value=False)
        dup_comments_var        = tk.BooleanVar(value=False)
        dup_max_var             = tk.StringVar(value="3")
        dup_prefix_var          = tk.StringVar(value="")
        unique_only_active      = [False]

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Report Failures to Azure DevOps")
        dialog.geometry("1080x660")
        dialog.minsize(900, 520)
        dialog.resizable(True, True)
        dialog.transient(self.frame)
        dialog.grab_set()

        # ── Header
        hdr = ctk.CTkFrame(dialog, fg_color="transparent")
        hdr.pack(fill="x", padx=15, pady=(12, 0))
        ctk.CTkLabel(hdr, text="Select & Preview Failures for ADO Reporting",
                     font=FONTS["sub_header"]).pack(side="left")

        # ── Tag selector
        tag_frame = ctk.CTkFrame(dialog)
        tag_frame.pack(fill="x", padx=15, pady=(8, 6))
        ctk.CTkLabel(tag_frame, text="Filter by Tag:",
                     font=FONTS["main_bold"]).grid(row=0, column=0, padx=(10, 14), pady=(8, 2), sticky="w")

        selected_tag_var = tk.StringVar(value="")
        _COLS = 4
        for i, display_name in enumerate(report_tags):
            ctk.CTkRadioButton(
                tag_frame, text=display_name,
                variable=selected_tag_var, value=display_name,
                font=FONTS["main"]
            ).grid(row=1 + i // _COLS, column=i % _COLS, padx=10, pady=4, sticky="w")

        scan_status_var = tk.StringVar(value="← Select a tag to load failures")
        scan_lbl = ctk.CTkLabel(tag_frame, textvariable=scan_status_var,
                                font=FONTS["main"], text_color="gray")
        _last_row = 1 + (len(report_tags) - 1) // _COLS + 1
        scan_lbl.grid(row=_last_row, column=0, columnspan=_COLS, padx=10, pady=(2, 8), sticky="w")

        def _fingerprint(failure):
            tags = [t.lower() for t in failure.get("all_tags", [])]
            parts = []
            for prefix, var in (
                ("transaction type - ", fp_use_transaction_type),
                ("ruleid - ",           fp_use_rule_id),
                ("scenario type - ",    fp_use_scenario_type),
                ("object - ",           fp_use_object),
                ("element - ",          fp_use_element),
            ):
                if var.get():
                    val = next((t for t in tags if t.startswith(prefix)), "")
                    parts.append(val)
            if fp_use_failure_reason.get():
                reasons = tuple(sorted(t for t in tags if t in target_tags))
                parts.append(str(reasons))
            if fp_use_error_text.get():
                parts.append(failure.get("error_text", ""))
            if fp_use_bug_title.get():
                parts.append(failure.get("test_case_name", ""))
            if fp_use_sheet_name.get():
                val = next((t for t in tags if t.startswith("sheet - ")), "")
                parts.append(val)
            return tuple(parts)

        def _recompute_fingerprints(failures=None):
            from_checkbox = failures is None
            if failures is None:
                failures = list(failures_ref)
            if not failures:
                return
            fp_groups.clear()
            for i, f in enumerate(failures):
                fp = _fingerprint(f)
                fp_groups.setdefault(fp, []).append(i)
            distinct_bugs = len(fp_groups)
            scan_status_var.set(
                f"{len(failures)} failure(s) found  |  {distinct_bugs} distinct bug(s)  "
                f"— use \"Unique Only\" to auto-select one per bug"
            )
            scan_lbl.configure(text_color="lightgreen")
            if from_checkbox:
                _rebuild_list(failures)
                _select_unique_only()

        # ── Uniqueness criteria checkboxes
        fp_frame = ctk.CTkFrame(dialog)
        fp_frame.pack(fill="x", padx=15, pady=(0, 4))
        ctk.CTkLabel(fp_frame, text="Unique By:", font=FONTS["main_bold"]).pack(anchor="w", padx=(10, 8), pady=(6, 0))
        fp_row1 = ctk.CTkFrame(fp_frame, fg_color="transparent")
        fp_row1.pack(fill="x", padx=4, pady=(2, 0))
        for _fp_var, _fp_lbl in [
            (fp_use_transaction_type, "Transaction Type"),
            (fp_use_rule_id,          "Rule ID"),
            (fp_use_scenario_type,    "Scenario Type"),
            (fp_use_object,           "Object"),
            (fp_use_element,          "Element"),
        ]:
            ctk.CTkCheckBox(fp_row1, text=_fp_lbl, variable=_fp_var, font=FONTS["main"],
                            command=_recompute_fingerprints).pack(side="left", padx=8, pady=2)
        fp_row2 = ctk.CTkFrame(fp_frame, fg_color="transparent")
        fp_row2.pack(fill="x", padx=4, pady=(0, 4))
        for _fp_var, _fp_lbl in [
            (fp_use_failure_reason,   "Failure Reason"),
            (fp_use_error_text,       "Error Text"),
            (fp_use_bug_title,        "Bug Title"),
            (fp_use_sheet_name,       "Sheet Name"),
        ]:
            ctk.CTkCheckBox(fp_row2, text=_fp_lbl, variable=_fp_var, font=FONTS["main"],
                            command=_recompute_fingerprints).pack(side="left", padx=8, pady=2)

        # ── Content: left list | right preview
        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        # Left panel ────────────────────────────────────────────────────────────
        left = ctk.CTkFrame(content)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        ctrl_row = ctk.CTkFrame(left, fg_color="transparent")
        ctrl_row.pack(fill="x", padx=5, pady=(5, 2))
        count_lbl = ctk.CTkLabel(ctrl_row, text="No failures loaded",
                                 font=FONTS["main"], text_color="cyan")
        count_lbl.pack(side="left", padx=5)

        def _select_all():
            _bulk_updating[0] = True
            selected_set.update(range(len(failures_ref)))
            for v in check_vars:
                v.set(True)
            _bulk_updating[0] = False
            _update_count()
            unique_only_active[0] = False
            dup_options_frame.pack_forget()
            dup_comments_var.set(False)

        def _select_none():
            _bulk_updating[0] = True
            selected_set.clear()
            for v in check_vars:
                v.set(False)
            _bulk_updating[0] = False
            _update_count()
            unique_only_active[0] = False
            dup_options_frame.pack_forget()
            dup_comments_var.set(False)

        def _select_unique_only():
            """Select exactly one representative per fingerprint group, deselect the rest."""
            keep = set()
            for indices in fp_groups.values():
                keep.add(indices[0])
            _bulk_updating[0] = True
            selected_set.clear()
            selected_set.update(keep)
            page_start = current_page_ref[0] * _PAGE_SIZE
            for i_local, v in enumerate(check_vars):
                v.set((page_start + i_local) in selected_set)
            _bulk_updating[0] = False
            _update_count()
            unique_only_active[0] = True
            dup_options_frame.pack(fill="x", padx=5, pady=(0, 2))

        ctk.CTkButton(ctrl_row, text="None", width=55, fg_color="gray",
                      hover_color="#404040", font=FONTS["small"],
                      command=_select_none).pack(side="right", padx=2)
        ctk.CTkButton(ctrl_row, text="All", width=55, fg_color="gray",
                      hover_color="#404040", font=FONTS["small"],
                      command=_select_all).pack(side="right", padx=2)
        ctk.CTkButton(ctrl_row, text="Unique Only", width=90, fg_color="#1f538d",
                      hover_color="#153a6b", font=FONTS["small"],
                      command=_select_unique_only).pack(side="right", padx=2)

        # ── Duplicate-comments option (shown only when "Unique Only" is active)
        dup_options_frame = ctk.CTkFrame(left, fg_color="transparent")
        # not packed until _select_unique_only() is called
        dup_row1 = ctk.CTkFrame(dup_options_frame, fg_color="transparent")
        dup_row1.pack(fill="x")
        ctk.CTkCheckBox(
            dup_row1, text="Add duplicates in comments",
            variable=dup_comments_var, font=FONTS["small"],
        ).pack(side="left", padx=(5, 10))
        ctk.CTkLabel(dup_row1, text="Max:", font=FONTS["small"]).pack(side="left")
        tk.Spinbox(
            dup_row1, from_=1, to=10, textvariable=dup_max_var,
            width=3, justify="center",
            bg="#2b2b2b", fg="white", buttonbackground="#3a3a3a",
            relief="flat", highlightthickness=0,
        ).pack(side="left", padx=(2, 4))
        ctk.CTkLabel(
            dup_row1, text="comments per bug", font=FONTS["small"],
        ).pack(side="left")
        dup_row2 = ctk.CTkFrame(dup_options_frame, fg_color="transparent")
        dup_row2.pack(fill="x", pady=(3, 0))
        ctk.CTkLabel(dup_row2, text="Comment prefix text:", font=FONTS["small"]).pack(side="left", padx=(5, 4))
        ctk.CTkEntry(dup_row2, textvariable=dup_prefix_var, font=FONTS["small"], width=260).pack(side="left")

        # ── Pagination bar
        page_info_var = tk.StringVar(value="")
        page_bar = ctk.CTkFrame(left, fg_color="transparent")
        page_bar.pack(fill="x", padx=5, pady=(0, 2))
        prev_page_btn = ctk.CTkButton(
            page_bar, text="◀ Prev", width=70, fg_color="gray",
            hover_color="#404040", font=FONTS["small"],
            command=lambda: _render_page(current_page_ref[0] - 1),
            state="disabled")
        prev_page_btn.pack(side="left", padx=2)
        ctk.CTkLabel(page_bar, textvariable=page_info_var,
                     font=FONTS["small"], text_color="gray").pack(
            side="left", padx=8, expand=True)
        next_page_btn = ctk.CTkButton(
            page_bar, text="Next ▶", width=70, fg_color="gray",
            hover_color="#404040", font=FONTS["small"],
            command=lambda: _render_page(current_page_ref[0] + 1),
            state="disabled")
        next_page_btn.pack(side="right", padx=2)

        list_scroll = ctk.CTkScrollableFrame(left)
        list_scroll.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # Right panel (preview) ───────────────────────────────────────────
        right = ctk.CTkFrame(content, width=440)
        right.pack(side="right", fill="both")
        right.pack_propagate(False)

        ctk.CTkLabel(right, text="Bug Preview",
                     font=FONTS["main_bold"]).pack(anchor="w", padx=10, pady=(8, 2))
        preview_title_var = tk.StringVar(value="")
        ctk.CTkLabel(right, textvariable=preview_title_var, font=FONTS["main"],
                     wraplength=410, justify="left", anchor="w").pack(
            fill="x", padx=10, pady=(0, 4))
            
        att_sel_frame = ctk.CTkFrame(right, fg_color="transparent")
        att_sel_frame.pack(fill="x", padx=10, pady=(2, 2))
        row1 = ctk.CTkFrame(att_sel_frame, fg_color="transparent")
        row1.pack(fill="x", pady=1)
        

        ctk.CTkLabel(row1, text="Include:", font=FONTS["main_bold"]).pack(side="left", padx=(0, 5))
        
        def _on_att_check_changed():
            if active_row[0]:
                try:
                    local_idx = row_frames.index(active_row[0])
                    idx = current_page_ref[0] * _PAGE_SIZE + local_idx
                    failure = failures_ref[idx]
                    if "include_attachments" not in failure:
                        failure["include_attachments"] = {}
                    failure["include_attachments"]["request"]            = inc_req_var.get()
                    failure["include_attachments"]["include_assertions"] = inc_assertions_var.get()
                except ValueError:
                    pass

        def _apply_attachments_to_all():
            for f in failures_ref:
                if "include_attachments" not in f:
                    f["include_attachments"] = {}
                f["include_attachments"]["request"]            = inc_req_var.get()
                f["include_attachments"]["include_assertions"] = inc_assertions_var.get()

        inc_req_var        = tk.BooleanVar(value=True)
        inc_assertions_var = tk.BooleanVar(value=True)

        ctk.CTkCheckBox(row1, text="Req",        variable=inc_req_var,        font=FONTS["small"], width=10, command=_on_att_check_changed).pack(side="left", padx=5)
        ctk.CTkCheckBox(row1, text="Assertions", variable=inc_assertions_var, font=FONTS["small"], width=10, command=_on_att_check_changed).pack(side="left", padx=5)

        apply_all_btn = ctk.CTkButton(row1, text="Apply All", width=60, height=20, font=FONTS["small"], command=_apply_attachments_to_all)
        apply_all_btn.pack(side="right", padx=(5, 0))

        ctk.CTkFrame(right, height=1, fg_color="gray30").pack(fill="x", padx=8, pady=2)

        tab_view = ctk.CTkTabview(right)
        tab_view.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        for t in ["Request", "Assertions"]:
            tab_view.add(t)

        no_sel_lbl = ctk.CTkLabel(
            right, text="← Click a case\nto preview the bug",
            font=FONTS["main"], text_color="gray50", justify="center")
        no_sel_lbl.place(relx=0.5, rely=0.55, anchor="center")

        def _make_tab_txt(tab_name):
            frame = tab_view.tab(tab_name)
            txt = tk.Text(frame, bg="#1a1a2e", fg="#d4d4d4",
                          font=("Courier", 9), wrap="word",
                          relief="flat", state="disabled", borderwidth=0)
            sc = ttk.Scrollbar(frame, command=txt.yview)
            txt.configure(yscrollcommand=sc.set)
            sc.pack(side="right", fill="y")
            txt.pack(side="left", fill="both", expand=True)
            return txt

        txt_req        = _make_tab_txt("Request")
        txt_assertions = _make_tab_txt("Assertions")

        def _fill(widget, content):
            widget.configure(state="normal")
            widget.delete("1.0", tk.END)
            widget.insert("1.0", content if content else "(no content)")
            widget.configure(state="disabled")

        def _show_preview(failure):
            no_sel_lbl.place_forget()
            atts = failure["attachments"]
            preview_title_var.set(
                f"Title: {failure['test_case_name']}\nRule ID: {failure['rule_id']}")

            inc = failure.get("include_attachments", {
                "request": True, "include_assertions": True,
            })

            if atts.get("send"):
                _fill(txt_req, atts.get("send", ""))
            else:
                _fill(txt_req, atts.get("request", ""))

            # Combine all non-empty assertion blocks into one preview
            _ASSERT_LABELS = [
                ("assert_7efb21", "Assertion Details (A)"),
                ("assert_35b0bf", "Assertion Details (B)"),
                ("assert_392130", "Error Text Diff (C)"),
                ("assert_76b634", "Assertion Details (D)"),
                ("assert_bedd20", "Assertion Details (E)"),
                ("assert_bb87e7", "Assertion Details (F)"),
                ("assert_731468", "Assertion Details (G)"),
                ("assert_ad668e", "No Error Report (H)"),
                ("assert_979b2c", "Response Codes Diff (I)"),
                ("assert_d8b2e5", "Check Error Message"),
                ("assert_f3a1c9", "Check Error Code"),
                ("assert_a3f8b1", "Check Error Report"),
                ("assert_b5c3e7", "Response vs XML Template"),
                ("assert_c4e2f1", "Assert No Errors"),
                ("assert_c4f21a", "Compare Responses Error Fields"),
                ("assert_e8f3d2", "Row Comparison (Dual System)"),
                ("assert_b7f041", "Rule Presence Matches (Dual System)"),
                ("assert_3a8e6c", "Rule Presence Mismatch (Dual System)"),
                ("assert_5e2a1f", "Rule Not Found In System"),
                ("assert_9c4d83", "Rule Found/Not Found In System"),
                ("assert_6f2c9a", "Occurrence Count Mismatch"),
                ("assert_1d7e4b", "Occurrence Count Matches"),
                ("assert_b3d91c", "Object/Element Mismatch (Occurrences)"),
                ("assert_a1c7d4", "Object/Element Match (Occurrences)"),
                ("assert_c7e592", "Field/Additional Mismatch (Occurrences)"),
                ("assert_6a3fd8", "Field/Additional Match (Occurrences)"),
            ]
            parts = []
            for key, label in _ASSERT_LABELS:
                content = atts.get(key, "")
                if content:
                    parts.append(f"{'='*60}\n{label}\n{'='*60}\n{content}")
            _fill(txt_assertions, "\n\n".join(parts))

            inc_req_var.set(inc.get("request",            True))
            inc_assertions_var.set(inc.get("include_assertions", True))

        # ── Bottom buttons (declared early so rebuild_list can reference report_btn)
        bot = ctk.CTkFrame(dialog, fg_color="transparent")
        bot.pack(fill="x", padx=15, pady=(2, 12))

        def on_cancel():
            cancelled[0] = True
            dialog.destroy()

        # Place the tags variable before on_report so it can be accessed
        tags_var = tk.StringVar(value="")
        check_existing_var = tk.BooleanVar(value=True)

        def on_report():
            custom_tags = [t.strip() for t in tags_var.get().split(",") if t.strip()]
            check_existing = check_existing_var.get()
            sorted_indices = sorted(selected_set)
            selected = [failures_ref[i] for i in sorted_indices]
            fp_criteria = {
                "transaction_type": fp_use_transaction_type.get(),
                "rule_id":          fp_use_rule_id.get(),
                "scenario_type":    fp_use_scenario_type.get(),
                "object":           fp_use_object.get(),
                "element":          fp_use_element.get(),
                "failure_reason":   fp_use_failure_reason.get(),
                "error_text":       fp_use_error_text.get(),
                "bug_title":        fp_use_bug_title.get(),
                "sheet_name":       fp_use_sheet_name.get(),
            }
            if dup_comments_var.get():
                try:
                    max_dup = min(10, max(1, int(dup_max_var.get())))
                except ValueError:
                    max_dup = 3
                for orig_idx, f in zip(sorted_indices, selected):
                    fp = _fingerprint(f)
                    group = fp_groups.get(fp, [orig_idx])
                    f["duplicate_comments"] = [
                        failures_ref[j] for j in group if j != orig_idx
                    ][:max_dup]
                    f["duplicate_comment_prefix"] = dup_prefix_var.get().strip()
            for f in selected:
                f["custom_tags"] = custom_tags
                f["check_existing"] = check_existing
                f["fp_criteria"] = fp_criteria
            result_ref[0] = selected
            dialog.destroy()

        ctk.CTkButton(bot, text="Cancel", command=on_cancel,
                      fg_color="gray", hover_color="#404040",
                      font=FONTS["button"]).pack(side="left")

        ctk.CTkLabel(bot, text="Add Tags (comma separated):", font=FONTS["main_bold"]).pack(side="left", padx=(20, 5))
        ctk.CTkEntry(bot, textvariable=tags_var, font=FONTS["main"], width=250, placeholder_text="e.g. Sprint-1, Regression").pack(side="left", padx=5)

        ctk.CTkCheckBox(bot, text="Check Existing Bugs", variable=check_existing_var, font=FONTS["small"]).pack(side="left", padx=15)

        report_btn = ctk.CTkButton(
            bot, text="Report Selected (0)", command=on_report,
            fg_color="#b85c00", hover_color="#7a3c00",
            font=FONTS["button"], state="disabled")
        report_btn.pack(side="right")

        # ── Helpers that reference report_btn
        def _update_count(*_):
            n = len(selected_set)
            count_lbl.configure(text=f"{n} case(s) selected")
            report_btn.configure(
                text=f"Report Selected ({n})",
                state="normal" if n > 0 else "disabled")

        def _rebuild_list(failures):
            failures_ref.clear()
            failures_ref.extend(failures)
            _bulk_updating[0] = True
            selected_set.clear()
            selected_set.update(range(len(failures)))
            _bulk_updating[0] = False
            current_page_ref[0] = 0
            active_row[0] = None
            no_sel_lbl.place(relx=0.5, rely=0.55, anchor="center")
            preview_title_var.set("")
            for tw in (txt_req, txt_assertions):
                _fill(tw, "")
            _render_page(0)

        def _render_page(page):
            for w in list_scroll.winfo_children():
                w.destroy()
            check_vars.clear()
            row_frames.clear()
            active_row[0] = None

            total = len(failures_ref)
            if not total:
                ctk.CTkLabel(list_scroll,
                             text="No failures found for this tag.",
                             font=FONTS["main"], text_color="gray").pack(pady=20)
                page_info_var.set("")
                prev_page_btn.configure(state="disabled")
                next_page_btn.configure(state="disabled")
                count_lbl.configure(text="0 cases selected")
                report_btn.configure(text="Report Selected (0)", state="disabled")
                return

            total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
            page = max(0, min(page, total_pages - 1))
            current_page_ref[0] = page
            start = page * _PAGE_SIZE
            end = min(start + _PAGE_SIZE, total)

            for i_local, i_global in enumerate(range(start, end)):
                failure = failures_ref[i_global]
                var = tk.BooleanVar(value=(i_global in selected_set))

                def _on_check_changed(*_, ig=i_global, v=var):
                    if not _bulk_updating[0]:
                        if v.get():
                            selected_set.add(ig)
                        else:
                            selected_set.discard(ig)
                        _update_count()

                var.trace_add("write", _on_check_changed)
                check_vars.append(var)

                base_color = "#2a2a2a" if i_local % 2 == 0 else "#242424"
                row = ctk.CTkFrame(list_scroll, fg_color=base_color, corner_radius=4)
                row.pack(fill="x", pady=1, padx=2)
                row_frames.append(row)

                ctk.CTkCheckBox(row, text="", variable=var, width=24).pack(
                    side="left", padx=(6, 2), pady=4)

                text_frame = ctk.CTkFrame(row, fg_color="transparent")
                text_frame.pack(side="left", padx=(2, 8), pady=4, fill="x", expand=True)

                lbl = ctk.CTkLabel(
                    text_frame,
                    text=f"[{failure['rule_id']}]  {failure['test_case_name']}",
                    anchor="w", font=FONTS["main"], wraplength=270)
                lbl.pack(fill="x")

                if fp_use_error_text.get() and failure.get("error_text"):
                    err_lbl = ctk.CTkLabel(
                        text_frame,
                        text=failure["error_text"],
                        anchor="w", font=FONTS["small"], text_color="gray", wraplength=270)
                    err_lbl.pack(fill="x")

                def _on_click(ev=None, f=failure, r=row):
                    if active_row[0] and active_row[0] is not r:
                        prev = active_row[0]
                        try:
                            pi = row_frames.index(prev)
                            prev.configure(fg_color="#2a2a2a" if pi % 2 == 0 else "#242424")
                        except ValueError:
                            pass
                    active_row[0] = r
                    r.configure(fg_color="#1f538d")
                    _show_preview(f)

                row.bind("<Button-1>", _on_click)
                text_frame.bind("<Button-1>", _on_click)
                lbl.bind("<Button-1>", _on_click)

            page_info_var.set(
                f"Page {page + 1}/{total_pages}  ({start + 1}–{end} of {total})")
            prev_page_btn.configure(state="normal" if page > 0 else "disabled")
            next_page_btn.configure(
                state="normal" if page < total_pages - 1 else "disabled")
            _update_count()

        # ── Tag change → background scan
        def _on_tag_changed(*_):
            tag = selected_tag_var.get()
            if not tag:
                return
            scan_status_var.set("Scanning…")
            scan_lbl.configure(text_color="cyan")
            dialog.update_idletasks()

            def _do_scan():
                try:
                    found = scan_failures_by_tag(allure_dir, tag, report_tags)
                    try:
                        dialog.after(0, lambda: _on_done(found))
                    except tk.TclError:
                        pass
                except Exception as exc:
                    try:
                        dialog.after(0, lambda: _on_err(str(exc)))
                    except tk.TclError:
                        pass

            def _on_done(found):
                for f in found:
                    if "include_attachments" not in f:
                        f["include_attachments"] = {
                            "request": True, "include_assertions": True,
                        }
                n = len(found)

                _recompute_fingerprints(found)
                if not n:
                    scan_status_var.set("No failures found")
                    scan_lbl.configure(text_color="orange")
                _rebuild_list(found)

            def _on_err(err):
                scan_status_var.set(f"Error: {err}")
                scan_lbl.configure(text_color="red")

            threading.Thread(target=_do_scan, daemon=True).start()

        selected_tag_var.trace_add("write", _on_tag_changed)

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        self.frame.wait_window(dialog)

        if cancelled[0]:
            return None
        return result_ref[0]


    def _create_ado_bugs(self, creds, failures, target_tags=None):
        """Create ADO bugs for every selected failure and show a progress / results dialog."""

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
            total    = len(failures)
            success  = 0
            errors   = 0
            skipped  = 0

            for i, failure in enumerate(failures):
                failure["priority"] = creds.get("priority") or None
                failure["severity"] = creds.get("severity") or None
                failure["assignee"] = creds.get("assignee") or None
                tc_name = failure["test_case_name"]
                dialog.after(0, lambda t=tc_name, j=i: status_lbl.configure(
                    text=f"Reporting {j+1}/{total}: {t[:60]}..."))
                log(f"[{i+1}/{total}] Processing: {tc_name}", "info")

                try:
                    skip = False
                    if failure.get("check_existing"):
                        log(f"  Searching for existing bugs in ADO...", "info")
                        exists, skip_msg = check_existing_bug(
                            url         = creds["url"],
                            project     = creds["project"],
                            pat         = creds["pat"],
                            failure     = failure,
                            target_tags = target_tags,
                            fp_criteria = failure.get("fp_criteria"),
                        )
                        if exists:
                            log(f"  ⏭ {skip_msg}", "ok")
                            skipped += 1
                            skip = True

                    if not skip:
                        log(f"  Creating bug...", "info")
                        ok, msg, wi_id = create_ado_bug(
                            url        = creds["url"],
                            project    = creds["project"],
                            pat        = creds["pat"],
                            pbi_id     = creds["pbi_id"],
                            failure    = failure,
                        )

                        if ok:
                            success += 1
                            log(f"  ✔ {msg}", "ok")
                            dup_failures = failure.get("duplicate_comments", [])
                            dup_prefix = failure.get("duplicate_comment_prefix", "")
                            for k, dup in enumerate(dup_failures):
                                try:
                                    c_ok, c_msg = add_failure_comment(
                                        url=creds["url"],
                                        project=creds["project"],
                                        pat=creds["pat"],
                                        work_item_id=wi_id,
                                        failure=dup,
                                        prefix_text=dup_prefix,
                                    )
                                    if c_ok:
                                        log(f"    💬 Duplicate {k+1}/{len(dup_failures)}: comment added", "ok")
                                    else:
                                        log(f"    ⚠ Duplicate {k+1} comment failed: {c_msg}", "error")
                                except Exception as ce:
                                    log(f"    ⚠ Duplicate {k+1} comment error: {ce}", "error")
                        else:
                            errors += 1
                            log(f"  ✘ {msg}", "error")

                except Exception as e:
                    errors += 1
                    log(f"  ✘ Unexpected error: {e}", "error")

                dialog.after(0, lambda p=(i + 1) / total: progress_var.set(p))

            s, sk, e = success, skipped, errors
            dialog.after(0, lambda: status_lbl.configure(
                text=f"Done — {s} created, {sk} skipped, {e} error(s)."))
            log(f"\n═══ Finished: {s} created, {sk} skipped, {e} errors. ═══",
                "ok" if errors == 0 else "error")
            dialog.after(0, lambda: close_btn.configure(state="normal"))
            dialog.after(0, lambda: self.status_var.set(
                f"ADO Reporting complete: {s} created, {sk} skipped."))

        threading.Thread(target=run_reporting, daemon=True).start()

        dialog.protocol("WM_DELETE_WINDOW", lambda: None)  # prevent closing mid-run
        self.frame.wait_window(dialog)


    def show_update_bugs_dialog(self):
        """Entry point for the 'Update QA Bugs' flow: match config → credentials → run."""
        allure_dir = self.allure_results_dir.get() if hasattr(self, 'allure_results_dir') else "allure-results"
        if not Path(allure_dir).exists():
            messagebox.showerror("Error", f"Allure results directory not found:\n{allure_dir}")
            return

        test_cases = scan_all_batch_results(allure_dir)
        if not test_cases:
            messagebox.showinfo("No Results", "No test case results found in the allure-results directory.")
            return

        match_fields = self._show_bug_match_config_dialog()
        if match_fields is None:
            self.status_var.set("Ready")
            return

        failure_tag_scope = None
        if "failure_tag" in match_fields:
            failure_tag_scope = self._show_failure_tag_scope_dialog()
            if failure_tag_scope is None:
                self.status_var.set("Ready")
                return

        creds = self._show_ado_connection_dialog()
        if creds is None:
            self.status_var.set("Ready")
            return

        self._run_update_bugs(creds, test_cases, match_fields, failure_tag_scope)

    def _get_active_failure_tags(self):
        """Derive which failure tags were in scope based on current GUI checkbox state."""
        mode = self.execution_mode.get()
        dual = mode in (ExecutionMode.BOTH_SYSTEMS, ExecutionMode.SYSTEM1_BOTH_ENVS)

        tags = {"system 1 failure"}
        if dual:
            tags.add("system 2 failure")
        if self.assert_error_text.get():
            tags.add("system 1 error text failure")
            if dual:
                tags.add("system 2 error text failure")
        if self.assert_object_element.get():
            tags.add("system 1 object/element failure")
            if dual:
                tags.add("system 2 object/element failure")
        if self.assert_field_additional.get():
            tags.add("system 1 field/additional failure")
            if dual:
                tags.add("system 2 field/additional failure")
        if self.full_row_comparison.get():
            tags.add("dual system row failure")
        if self.full_report_comparison.get():
            tags.add("dual system failure")
            tags.add("dual system error text failure")
        return tags

    def _show_failure_tag_scope_dialog(self):
        """
        Show a dialog listing the failure tags relevant to the current execution
        mode, pre-checked based on the current GUI state. The user can override
        before confirming. Returns a set of lowercased tag strings, or None if
        cancelled.
        """
        pre_selected = self._get_active_failure_tags()
        mode = self.execution_mode.get()
        dual = mode in (ExecutionMode.BOTH_SYSTEMS, ExecutionMode.SYSTEM1_BOTH_ENVS)
        result_ref = [None]

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Failure Tag Scope")
        dialog.geometry("480x520")
        dialog.minsize(480, 400)
        dialog.resizable(True, True)
        dialog.transient(self.frame)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Failure tags tested in this run:", font=FONTS["sub_header"]).pack(pady=(15, 5))
        ctk.CTkLabel(
            dialog,
            text="Only bugs whose failure tag is checked below will be processed.\n"
                 "Bugs with an unchecked failure tag are skipped entirely.",
            font=FONTS["main"],
            justify="center",
        ).pack(pady=(0, 10))

        # System 1/2-only modes only ever emit "System 1 ..." tags (system_index
        # defaults to 1 for a lone system under test — see _execute_system2_only
        # in allure_wrapper.py). "System 2 ..." and "Dual System ..." tags only
        # occur in the true dual-comparison modes, so only offer them there.
        all_tags = [
            ("system 1 failure",                  "System 1 Failure"),
            ("system 1 error text failure",        "System 1 Error Text Failure"),
            ("system 1 object/element failure",    "System 1 Object/Element Failure"),
            ("system 1 field/additional failure",  "System 1 Field/Additional Failure"),
        ]
        if dual:
            all_tags += [
                ("system 2 failure",                   "System 2 Failure"),
                ("system 2 error text failure",        "System 2 Error Text Failure"),
                ("system 2 object/element failure",    "System 2 Object/Element Failure"),
                ("system 2 field/additional failure",  "System 2 Field/Additional Failure"),
                ("dual system failure",                "Dual System Failure"),
                ("dual system error text failure",     "Dual System Error Text Failure"),
                ("dual system row failure",            "Dual System Row Failure"),
            ]

        vars_ = {}
        checks_frame = ctk.CTkFrame(dialog)
        checks_frame.pack(fill="x", padx=30, pady=5)
        for tag_key, label in all_tags:
            var = tk.BooleanVar(value=(tag_key in pre_selected))
            vars_[tag_key] = var
            ctk.CTkCheckBox(checks_frame, text=label, variable=var, font=FONTS["main"]).pack(anchor="w", pady=4)

        def on_confirm():
            selected = {k for k, v in vars_.items() if v.get()}
            result_ref[0] = selected
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(15, 15))
        ctk.CTkButton(btn_frame, text="Confirm", command=on_confirm, font=FONTS["button"]).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=on_cancel, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=10)

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        self.frame.wait_window(dialog)
        return result_ref[0]

    def _show_bug_match_config_dialog(self):
        """
        Show a dialog with checkboxes for which fields to use when matching bugs.
        Returns a set of field keys, or None if cancelled.
        """
        result_ref = [None]

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Bug Match Configuration")
        dialog.geometry("460x600")
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
            ("bug_title",        "Bug Title"),
        ]
        tooltips = {
            "failure_tag": (
                "Matches the ADO bug by the failure type tag on the test case.\n"
                "e.g. \"System 2 Failure\", \"System 1 Failure\",\n"
                "     \"System 2 Error Text Failure\", \"Dual System Error\"\n\n"
                "Note: this condition is automatically skipped for passed test\n"
                "cases since they carry no failure tag."
            ),
            "bug_title": (
                "Matches the ADO bug title exactly against the test case name.\n"
                "Bug titles are stored in the format:\n"
                "  \"Test Case: {Transaction Type} - {Description}\"\n"
                "e.g. \"Test Case: Get New Transactions - Verify Person Register ACK appears\""
            ),
        }

        vars_ = {}
        checks_frame = ctk.CTkFrame(dialog)
        checks_frame.pack(fill="x", padx=30, pady=5)

        for key, label in fields:
            var = tk.BooleanVar(value=True)
            vars_[key] = var
            cb = ctk.CTkCheckBox(checks_frame, text=label, variable=var, font=FONTS["main"])
            cb.pack(anchor="w", pady=4)
            if key in tooltips:
                ToolTip(cb, tooltips[key])

        # Dynamic description label
        ctk.CTkLabel(dialog, text="Matching logic:", font=FONTS["main"], text_color="#aaaaaa").pack(pady=(10, 2))
        desc_label = ctk.CTkLabel(
            dialog,
            text="",
            font=FONTS["main"],
            wraplength=400,
            justify="left",
            text_color="#e0e0e0",
        )
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
                    criteria.append("bug title = test case name (case-insensitive)")
            if len(criteria) == 1:
                joined = criteria[0]
            elif len(criteria) == 2:
                joined = f"{criteria[0]} AND {criteria[1]}"
            else:
                joined = ", ".join(criteria[:-1]) + f", and {criteria[-1]}"
            return f"A bug matches a test case when: {joined}."

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

        self.frame.wait_window(dialog)
        return result_ref[0]

    def _show_ado_connection_dialog(self):
        """
        Lightweight ADO connection dialog: URL, PAT, project selection.
        No PBI — used for flows that only need to query/update existing bugs.
        Returns dict with keys: url, pat, project — or None if cancelled.
        """
        result = {}
        cancelled = [False]

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Azure DevOps Connection")
        dialog.geometry("560x420")
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

    def _run_update_bugs(self, creds, test_cases, match_fields=None, failure_tag_scope=None):
        """For each test case, find its 'Ready for QA' bug and close or reopen it."""

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
                log(f"✘ Failed to fetch bugs: {fetch_err}", "error")
                close_btn.configure(state="normal")
                return

            if not bugs:
                log("No 'Ready for QA' bugs found in ADO.", "skipped")
                close_btn.configure(state="normal")
                return

            log(f"Found {len(bugs)} 'Ready for QA' bug(s). Matching against {len(test_cases)} executed test cases...", "info")

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
                    if failure_tag_scope is not None:
                        all_known_failure_tags = {t for t in failure_tag_scope} | {
                            "system 1 failure", "system 1 error text failure", "system 1 object/element failure", "system 1 field/additional failure",
                            "system 2 failure", "system 2 error text failure", "system 2 object/element failure", "system 2 field/additional failure",
                            "dual system failure", "dual system error text failure",
                            "dual system row failure", "dual system mismatch failure",
                        }
                        bug_failure_tags = bug["tags"] & all_known_failure_tags
                        if bug_failure_tags and not (bug_failure_tags & failure_tag_scope):
                            log(f"  ⏭ Skipped — failure tag(s) {bug_failure_tags} not in scope", "skipped")
                            skipped += 1
                            progress_var.set((i + 1) / total)
                            dialog.update_idletasks()
                            continue

                    tc = match_bug_to_test_case(bug, test_cases, match_fields)

                    if tc is None:
                        log("  ⏭ No matching executed test case found", "skipped")
                        skipped += 1
                        progress_var.set((i + 1) / total)
                        dialog.update_idletasks()
                        continue

                    tc_name = tc["test_case_name"]
                    status  = tc["status"]
                    log(f"  Matched: {tc_name}  [{status}]", "info")

                    new_state = "Ready for Release" if tc.get("qa_outcome") == "close" else "Reopened"
                    ok, msg = update_bug_for_qa_result(
                        url          = creds["url"],
                        project      = creds["project"],
                        pat          = creds["pat"],
                        work_item_id = wi_id,
                        test_case    = tc,
                        new_state    = new_state,
                    )

                    if ok:
                        if new_state == "Ready for Release":
                            closed += 1
                        else:
                            reopened += 1
                        log(f"  ✔ {msg}", "ok")
                    else:
                        errors += 1
                        log(f"  ✘ {msg}", "error")

                except Exception as e:
                    errors += 1
                    log(f"  ✘ Unexpected error: {e}", "error")

                progress_var.set((i + 1) / total)
                dialog.update_idletasks()

            summary = f"Done — {closed} closed, {reopened} reopened, {skipped} skipped (no matching test case), {errors} error(s)."
            status_lbl.configure(text=summary)
            log(f"\n═══ {summary} ═══", "ok" if errors == 0 else "error")
            close_btn.configure(state="normal")
            self.status_var.set(f"QA bug update complete: {closed} closed, {reopened} reopened.")

        threading.Thread(target=run, daemon=True).start()

        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        self.frame.wait_window(dialog)

    def show_was_ever_reported_dialog(self):
        """Entry point for 'Was Ever Reported': match config → credentials → run."""
        allure_dir = self.allure_results_dir.get() if hasattr(self, 'allure_results_dir') else "allure-results"
        if not Path(allure_dir).exists():
            messagebox.showerror("Error", f"Allure results directory not found:\n{allure_dir}")
            return

        test_cases = scan_all_results(allure_dir)
        if not test_cases:
            messagebox.showinfo("No Results", "No test case results found in the allure-results directory.")
            return

        match_fields = self._show_bug_match_config_dialog()
        if match_fields is None:
            self.status_var.set("Ready")
            return

        creds = self._show_ado_connection_dialog()
        if creds is None:
            self.status_var.set("Ready")
            return

        self._run_was_ever_reported(creds, test_cases, match_fields)

    def _run_was_ever_reported(self, creds, test_cases, match_fields=None):
        """For each Closed bug that matches a test case in the current run and has no
        matching 'Ready for QA' bug, report it as 'was ever reported'."""

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Was Ever Reported — Azure DevOps")
        dialog.geometry("650x520")
        dialog.resizable(True, True)
        dialog.transient(self.frame)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Was Ever Reported", font=FONTS["sub_header"]).pack(pady=(15, 5))

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

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(5, 15))

        # matches keyed by test_case_name: {tc, bugs: []}
        matches_by_tc = {}

        def export_to_excel():
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            save_path = filedialog.asksaveasfilename(
                title="Save Was Ever Reported",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile="was_ever_reported.xlsx",
            )
            if not save_path:
                return
            try:
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Was Ever Reported"

                headers = ["Test Case Name", "All Tags", "Closed Bug IDs", "Closed Bug Titles"]
                header_fill = PatternFill("solid", fgColor="1F4E79")
                header_font = Font(bold=True, color="FFFFFF")
                for col, h in enumerate(headers, 1):
                    cell = ws.cell(row=1, column=col, value=h)
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(wrap_text=True, vertical="center")

                for row_idx, (tc_name, entry) in enumerate(matches_by_tc.items(), 2):
                    tc      = entry["tc"]
                    bugs    = entry["bugs"]
                    all_tags_str   = "; ".join(tc.get("all_tags", []))
                    bug_ids_str    = ", ".join(f"#{b['id']}" for b in bugs)
                    bug_titles_str = " | ".join(b["title"] for b in bugs)

                    ws.cell(row=row_idx, column=1, value=tc_name)
                    ws.cell(row=row_idx, column=2, value=all_tags_str)
                    ws.cell(row=row_idx, column=3, value=bug_ids_str)
                    ws.cell(row=row_idx, column=4, value=bug_titles_str)
                    for col in range(1, 5):
                        ws.cell(row=row_idx, column=col).alignment = Alignment(wrap_text=True, vertical="top")

                ws.column_dimensions["A"].width = 55
                ws.column_dimensions["B"].width = 60
                ws.column_dimensions["C"].width = 20
                ws.column_dimensions["D"].width = 60

                wb.save(save_path)
                messagebox.showinfo("Exported", f"Report saved to:\n{save_path}", parent=dialog)
            except Exception as e:
                messagebox.showerror("Export Failed", str(e), parent=dialog)

        export_btn = ctk.CTkButton(btn_frame, text="Export to Excel", command=export_to_excel,
                                   fg_color="#1a6b4a", hover_color="#134d36",
                                   font=FONTS["button"], state="disabled")
        export_btn.pack(side="left", padx=10)

        close_btn = ctk.CTkButton(btn_frame, text="Close", command=dialog.destroy,
                                  fg_color="gray", hover_color="#404040",
                                  font=FONTS["button"], state="disabled")
        close_btn.pack(side="left", padx=10)

        def log(text, tag="info"):
            log_box.configure(state="normal")
            log_box.insert(tk.END, text + "\n", tag)
            log_box.see(tk.END)
            log_box.configure(state="disabled")
            dialog.update_idletasks()

        def run():
            log("Fetching all Closed bugs from ADO...", "info")
            status_lbl.configure(text="Fetching Closed bugs from ADO...")
            dialog.update_idletasks()

            closed_bugs, err1 = get_all_closed_bugs(
                url=creds["url"], project=creds["project"], pat=creds["pat"]
            )
            if err1:
                log(f"✘ Failed to fetch Closed bugs: {err1}", "error")
                close_btn.configure(state="normal")
                return

            if not closed_bugs:
                log("No Closed bugs found in ADO.", "skipped")
                close_btn.configure(state="normal")
                return

            log(f"Found {len(closed_bugs)} Closed bug(s). Fetching 'Ready for QA' bugs...", "info")
            status_lbl.configure(text="Fetching 'Ready for QA' bugs from ADO...")
            dialog.update_idletasks()

            rfqa_bugs, err2 = get_all_ready_for_qa_bugs(
                url=creds["url"], project=creds["project"], pat=creds["pat"]
            )
            if err2:
                log(f"✘ Failed to fetch 'Ready for QA' bugs: {err2}", "error")
                close_btn.configure(state="normal")
                return

            log(f"Found {len(rfqa_bugs)} 'Ready for QA' bug(s). Matching against {len(test_cases)} executed test cases...", "info")

            total    = len(closed_bugs)
            reported = 0
            skipped  = 0
            errors   = 0

            for i, bug in enumerate(closed_bugs):
                wi_id = bug["id"]
                title = bug["title"]
                status_lbl.configure(text=f"Processing {i+1}/{total}: Bug #{wi_id}...")

                try:
                    tc = match_bug_to_test_case(bug, test_cases, match_fields)

                    if tc is None:
                        skipped += 1
                        progress_var.set((i + 1) / total)
                        dialog.update_idletasks()
                        continue

                    has_rfqa = any(
                        match_bug_to_test_case(rfqa_bug, [tc], match_fields) is not None
                        for rfqa_bug in rfqa_bugs
                    )

                    if has_rfqa:
                        skipped += 1
                        progress_var.set((i + 1) / total)
                        dialog.update_idletasks()
                        continue

                    reported += 1
                    tc_name = tc["test_case_name"]
                    status  = tc["status"]
                    log(f"[{reported}] Bug #{wi_id}: {title[:60]}", "ok")
                    log(f"     Matched: {tc_name}  [{status}]", "info")

                    if tc_name not in matches_by_tc:
                        matches_by_tc[tc_name] = {"tc": tc, "bugs": []}
                    matches_by_tc[tc_name]["bugs"].append(bug)

                except Exception as e:
                    errors += 1
                    log(f"  ✘ Unexpected error on Bug #{wi_id}: {e}", "error")

                progress_var.set((i + 1) / total)
                dialog.update_idletasks()

            summary = (
                f"Done — {reported} was-ever-reported, "
                f"{skipped} skipped (no test case match or has RFQA bug), "
                f"{errors} error(s)."
            )
            status_lbl.configure(text=summary)
            log(f"\n═══ {summary} ═══", "ok" if errors == 0 else "error")
            if matches_by_tc:
                export_btn.configure(state="normal")
            close_btn.configure(state="normal")
            self.status_var.set(f"Was Ever Reported complete: {reported} found.")

        threading.Thread(target=run, daemon=True).start()

        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        self.frame.wait_window(dialog)

    def on_sheet_selected_optionmenu(self, selected):
        """Handle sheet selection from option menu"""
        if selected:
            self.current_sheet = selected
            self.status_var.set(f"Sheet '{selected}' selected. Click Load to preview.")

    def on_rows_per_page_changed_optionmenu(self, choice):
        """Handle rows per page change"""
        self.rows_per_page_var.set(choice)
        self.on_rows_per_page_changed()

    def show_custom_report_dialog(self):
        """Show advanced dialog to configure sheets and columns for custom report"""
        
        # Initialize internal config state for the duration of the dialog
        # Structure: [{'name': 'Sheet Name', 'columns': ['Col1', 'Col2']}]
        
        available_columns = get_available_rules_summary_columns(self.execution_mode.get(), self.assert_error_text.get(), self.assert_field_additional.get())
        
        editing_config = []
        # Default configuration
        s1_name = "System 1"
        s2_name = "System 2"
        
        mode = self.execution_mode.get()
        if mode == ExecutionMode.BOTH_SYSTEMS:
            s1_name = "Legacy System"
            s2_name = "System 2.0"
        elif mode == ExecutionMode.SYSTEM1_BOTH_ENVS:
            s1_name = "Legacy System (Prod)"
            s2_name = "Legacy System (PTE)"
        elif mode == ExecutionMode.SYSTEM1_ONLY:
            s1_name = "Legacy System"
        elif mode == ExecutionMode.SYSTEM2_ONLY:
            s1_name = "System 2.0"

        # Default configuration
        default_criteria = [
            f'{s1_name} Failure',
            f'{s2_name} Failure',
            f'{s1_name} Error Text Failure',
            f'{s2_name} Error Text Failure',
            f'{s1_name} Object/Element Failure',
            f'{s2_name} Object/Element Failure',
            f'{s1_name} Field/Additional Failure',
            f'{s2_name} Field/Additional Failure',
            'System Comparison Failure',
            'System Comparison Error Text Failure',
            'System Row Comparison Failure',
        ]
        
        # Check if we are in a single-system mode (System 1 only or System 2 only)
        # in which case the *other* system's criteria and Dual System comparisons are not relevant.
        # Note: in SYSTEM2_ONLY mode, s1_name holds the tested system's display name ("System 2.0")
        # while s2_name stays at its default ("System 2") and is unused — so it must be filtered too.
        # Use exact-name matching (not substring) here: s2_name ("System 2") is a literal prefix of
        # s1_name ("System 2.0"), so a naive `s2_name in c` check would also match/filter the
        # legitimate "System 2.0 ..." criteria.
        current_mode = self.execution_mode.get()
        # User requested that 'system1_both_envs' SHOULD enable System 2 / Dual System checkboxes (likely for comparison)
        is_system1_mode = current_mode in (ExecutionMode.SYSTEM1_ONLY, ExecutionMode.SYSTEM2_ONLY)
        print(f"DEBUG: Opening Custom Report. Mode={current_mode}, SingleSystemMode={is_system1_mode}")

        other_system_criteria = {
            f'{s2_name} Failure',
            f'{s2_name} Error Text Failure',
            f'{s2_name} Object/Element Failure',
            f'{s2_name} Field/Additional Failure',
        }

        if is_system1_mode:
            filtered_criteria = []
            for c in default_criteria:
                if c not in other_system_criteria and "System Comparison" not in c:
                    filtered_criteria.append(c)
            default_criteria = filtered_criteria

        if not self.assert_object_element.get():
            default_criteria = [c for c in default_criteria if c not in (f'{s1_name} Object/Element Failure', f'{s2_name} Object/Element Failure')]
        if not self.assert_field_additional.get():
            default_criteria = [c for c in default_criteria if c not in (f'{s1_name} Field/Additional Failure', f'{s2_name} Field/Additional Failure')]
        if not self.full_report_comparison.get() or self.full_row_comparison.get():
            default_criteria = [c for c in default_criteria if c not in ('System Comparison Failure', 'System Comparison Error Text Failure')]
        if not self.full_row_comparison.get():
            default_criteria = [c for c in default_criteria if c != 'System Row Comparison Failure']

        editing_config.append({'name': 'Rules Summary', 'columns': list(available_columns), 'criteria': default_criteria})

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Custom Report Configuration")
        dialog.geometry("800x700")
        dialog.minsize(700, 600)  # Set minimum size
        dialog.transient(self.frame)
        dialog.grab_set()
        dialog.resizable(True, True)  # Make dialog resizable

        # Button frame at bottom (pack first to reserve space)
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom", padx=10, pady=10)

        # Create main scrollable container for all content
        main_scroll_container = ctk.CTkScrollableFrame(dialog)
        main_scroll_container.pack(fill="both", expand=True, padx=5, pady=(5, 0))

        # === Top Frame: Sheet Management ===
        top_frame = ctk.CTkFrame(main_scroll_container)
        top_frame.pack(fill="x", padx=5, pady=(5, 5))

        ctk.CTkLabel(top_frame, text="Report Sheets", font=FONTS["sub_header"]).pack(anchor="w", padx=10, pady=5)

        sheet_list_frame = ctk.CTkFrame(top_frame)
        sheet_list_frame.pack(fill="x", padx=10, pady=5)

        # Listbox for sheets
        sheet_listbox = tk.Listbox(sheet_list_frame, height=5, bg="#333333", fg="white", selectbackground="#1f538d", highlightthickness=0, bd=0, font=("Arial", 11), exportselection=False)
        sheet_listbox.pack(side="left", fill="both", expand=True)

        sheet_controls = ctk.CTkFrame(sheet_list_frame, fg_color="transparent")
        sheet_controls.pack(side="right", fill="y", padx=5)

        # === Bottom Frame: Columns & Criteria Management ===
        bottom_frame = ctk.CTkFrame(main_scroll_container)
        bottom_frame.pack(fill="both", expand=True, padx=5, pady=(5, 5))

        # --- Criteria Section ---
        criteria_frame = ctk.CTkFrame(bottom_frame)
        criteria_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(criteria_frame, text="Monitoring Criteria (Relationship: OR)", font=FONTS["main_bold"]).pack(anchor="w", padx=5, pady=(5, 0))

        # helper: determine whether a criterion is irrelevant given the current execution mode /
        # comparison settings. These are fixed for the lifetime of this dialog (mode and comparison
        # toggles come from the outer GUI and cannot change while this dialog is open), so criteria
        # that fail this check are excluded entirely below rather than shown disabled.
        is_full_report_comparison = self.full_report_comparison.get()
        is_full_row_comparison = self.full_row_comparison.get()

        def is_mode_disabled(name):
            if is_system1_mode and (name in other_system_criteria or "System Comparison" in name):
                return True
            if name in ('System Comparison Failure', 'System Comparison Error Text Failure'):
                if not is_full_report_comparison or is_full_row_comparison:
                    return True
            if name == 'System Row Comparison Failure':
                if not is_full_row_comparison:
                    return True
            return False

        # Criteria Variables (irrelevant-for-this-mode/settings criteria are excluded entirely)
        _all_criteria_names = [
             f'{s1_name} Failure',
             f'{s2_name} Failure',
             f'{s1_name} Error Text Failure',
             f'{s2_name} Error Text Failure',
             f'{s1_name} Object/Element Failure',
             f'{s2_name} Object/Element Failure',
             f'{s1_name} Field/Additional Failure',
             f'{s2_name} Field/Additional Failure',
             'System Comparison Failure',
             'System Comparison Error Text Failure',
             'System Row Comparison Failure',
             'Failed - No Failure Tag',
             'No Failure',
             'Broken',
             'Default Statistics',
             'Transactions Default Statistics',
        ]
        self.criteria_vars = {
            name: tk.BooleanVar() for name in _all_criteria_names if not is_mode_disabled(name)
        }
        _EXCLUSIVE_STATS = {'Default Statistics', 'Transactions Default Statistics'}
        _EXCLUSIVE_FILTERS = {'Broken'}
        # Registry of checkbox widgets so we can enable/disable them later
        self._criteria_checkboxes = {}

        # Create scrollable frame for criteria checkboxes
        criteria_scroll_frame = ctk.CTkScrollableFrame(criteria_frame, height=120, fg_color="transparent")
        criteria_scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

        def get_current_sheet_idx_ref():
            # Helper to get index within sub-functions
            sel = sheet_listbox.curselection()
            if sel: return sel[0]
            return None

        def set_columns_locked(locked):
            """Grey-out / restore the column add/remove controls."""
            state = "disabled" if locked else "normal"
            listbox_avail.configure(state=state)
            listbox_sel.configure(state=state)
            for btn in col_buttons:
                btn.configure(state=state)

        def on_criteria_change(name):
             idx = get_current_sheet_idx_ref()
             if idx is None: return
             sheet_conf = editing_config[idx]
             current = sheet_conf.get('criteria', [])

             if name in _EXCLUSIVE_STATS:
                 if self.criteria_vars[name].get():
                     # Uncheck & remove every other criterion
                     for other, var in self.criteria_vars.items():
                         if other != name:
                             var.set(False)
                             if other in current:
                                 current.remove(other)
                         cb = self._criteria_checkboxes.get(other)
                         if cb:
                             cb.configure(state="disabled")
                     if name not in current:
                         current.append(name)
                     # Lock columns section
                     set_columns_locked(True)
                 else:
                     # Re-enable all other checkboxes (respecting mode rules)
                     for other, var in self.criteria_vars.items():
                         if other == name: continue
                         cb = self._criteria_checkboxes.get(other)
                         if cb:
                             cb.configure(state="disabled" if is_mode_disabled(other) else "normal")
                     if name in current:
                         current.remove(name)
                     set_columns_locked(False)
             elif name in _EXCLUSIVE_FILTERS:
                 if self.criteria_vars[name].get():
                     # Uncheck & remove every other criterion; columns remain unlocked
                     for other, var in self.criteria_vars.items():
                         if other != name:
                             var.set(False)
                             if other in current:
                                 current.remove(other)
                             cb = self._criteria_checkboxes.get(other)
                             if cb:
                                 cb.configure(state="disabled")
                     if name not in current:
                         current.append(name)
                 else:
                     # Re-enable all other checkboxes (respecting mode rules)
                     for other, var in self.criteria_vars.items():
                         if other == name: continue
                         cb = self._criteria_checkboxes.get(other)
                         if cb:
                             cb.configure(state="disabled" if is_mode_disabled(other) else "normal")
                     if name in current:
                         current.remove(name)
             else:
                 # Any other criterion: uncheck any active exclusive stats or filters
                 for excl_name in list(_EXCLUSIVE_STATS) + list(_EXCLUSIVE_FILTERS):
                     if self.criteria_vars[excl_name].get():
                         self.criteria_vars[excl_name].set(False)
                         if excl_name in current:
                             current.remove(excl_name)
                 # Re-enable all non-exclusive checkboxes
                 for other, var in self.criteria_vars.items():
                     if other in _EXCLUSIVE_STATS: continue
                     cb = self._criteria_checkboxes.get(other)
                     if cb:
                         cb.configure(state="disabled" if is_mode_disabled(other) else "normal")
                 set_columns_locked(False)

                 if self.criteria_vars[name].get():
                     if name not in current:
                         current.append(name)
                 else:
                     if name in current:
                         current.remove(name)

             sheet_conf['criteria'] = current

        # Create checkboxes in scrollable frame
        for name, var in self.criteria_vars.items():
            cb = ctk.CTkCheckBox(criteria_scroll_frame, text=name, variable=var, command=lambda n=name: on_criteria_change(n), font=FONTS["main"])
            self._criteria_checkboxes[name] = cb

            # Visual separators before grouped sections
            if name in ('Failed - No Failure Tag', 'Default Statistics'):
                sep = ctk.CTkLabel(criteria_scroll_frame, text="─" * 30, text_color="gray", font=("Arial", 9))
                sep.pack(anchor="w", padx=10)

            cb.pack(anchor="w", padx=10, pady=5)
            
        # --- Columns Section ---
        current_sheet_label = ctk.CTkLabel(bottom_frame, text="Columns Configuration", font=FONTS["sub_header"])
        current_sheet_label.pack(anchor="w", padx=10, pady=5)

        cols_container = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        cols_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Left: Available
        left_frame = ctk.CTkFrame(cols_container)
        left_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        ctk.CTkLabel(left_frame, text="Available Columns", font=FONTS["main_bold"]).pack()
        listbox_avail = tk.Listbox(left_frame, selectmode=tk.MULTIPLE, bg="#333333", fg="white", highlightthickness=0, bd=0, font=("Arial", 10), exportselection=False)
        listbox_avail.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Middle: Buttons
        mid_frame = ctk.CTkFrame(cols_container, fg_color="transparent")
        mid_frame.pack(side="left", fill="y", padx=5)

        # Right: Selected
        right_frame = ctk.CTkFrame(cols_container)
        right_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        ctk.CTkLabel(right_frame, text="Selected Columns", font=FONTS["main_bold"]).pack()
        listbox_sel = tk.Listbox(right_frame, selectmode=tk.MULTIPLE, bg="#333333", fg="white", highlightthickness=0, bd=0, font=("Arial", 10), exportselection=False)
        listbox_sel.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        # Functions
        def get_current_sheet_idx():
            sel = sheet_listbox.curselection()
            if sel: return sel[0]
            return None

        def refresh_criteria_view():
            idx = get_current_sheet_idx()
            if idx is None:
                for var in self.criteria_vars.values(): var.set(False)
                return

            sheet_conf = editing_config[idx]
            current = sheet_conf.get('criteria', [])

            for name, var in self.criteria_vars.items():
                var.set(name in current)

            # Apply exclusive stats lock state
            is_exclusive_stats = any(s in current for s in _EXCLUSIVE_STATS)
            for name, cb in self._criteria_checkboxes.items():
                if name in _EXCLUSIVE_STATS and name in current:
                    continue  # keep the active exclusive stat's checkbox enabled so user can uncheck it
                if is_exclusive_stats:
                    cb.configure(state="disabled")
                else:
                    cb.configure(state="disabled" if is_mode_disabled(name) else "normal")
            set_columns_locked(is_exclusive_stats)

        def refresh_columns_view():
            idx = get_current_sheet_idx()
            if idx is None:
                current_sheet_label.configure(text="No sheet selected")
                listbox_avail.delete(0, tk.END)
                listbox_sel.delete(0, tk.END)
                return

            sheet_conf = editing_config[idx]
            current_sheet_label.configure(text=f"Columns for '{sheet_conf['name']}'")

            selected_cols = sheet_conf['columns']
            available_cols = [c for c in available_columns if c not in selected_cols]

            listbox_avail.delete(0, tk.END)
            for col in available_cols:
                listbox_avail.insert(tk.END, col)

            listbox_sel.delete(0, tk.END)
            for col in selected_cols:
                listbox_sel.insert(tk.END, col)

            refresh_criteria_view()

        def on_sheet_select(event):
            refresh_columns_view()

        sheet_listbox.bind('<<ListboxSelect>>', on_sheet_select)

        def refresh_sheet_list():
            sheet_listbox.delete(0, tk.END)
            for sheet in editing_config:
                sheet_listbox.insert(tk.END, sheet['name'])
            if editing_config:
                sheet_listbox.select_set(0)
                refresh_columns_view()

        def add_sheet():
            new_name = simpledialog.askstring("New Sheet", "Enter sheet name:", parent=dialog)
            if new_name:
                count = 1
                base_name = new_name
                existing_names = [s['name'] for s in editing_config]
                while new_name in existing_names:
                    new_name = f"{base_name}_{count}"
                    count += 1
                editing_config.append({'name': new_name, 'columns': list(available_columns), 'criteria': []})
                refresh_sheet_list()
                sheet_listbox.select_clear(0, tk.END)
                sheet_listbox.select_set(len(editing_config)-1)
                refresh_columns_view()

        def remove_sheet():
            sel = sheet_listbox.curselection()
            if not sel: return
            idx = sel[0]
            if len(editing_config) <= 1:
                messagebox.showwarning("Warning", "Report must have at least one sheet.", parent=dialog)
                return
            del editing_config[idx]
            refresh_sheet_list()

        def rename_sheet():
            sel = sheet_listbox.curselection()
            if not sel: return
            idx = sel[0]
            current_name = editing_config[idx]['name']
            new_name = simpledialog.askstring("Rename Sheet", "Enter new sheet name:", initialvalue=current_name, parent=dialog)
            if new_name and new_name != current_name:
                existing_names = [s['name'] for i, s in enumerate(editing_config) if i != idx]
                if new_name in existing_names:
                    messagebox.showerror("Error", "Sheet name already exists.", parent=dialog)
                    return
                editing_config[idx]['name'] = new_name
                refresh_sheet_list()
                sheet_listbox.select_set(idx)

        ctk.CTkButton(sheet_controls, text="Add Sheet", command=add_sheet, width=80, font=FONTS["button"]).pack(pady=2)
        ctk.CTkButton(sheet_controls, text="Rename", command=rename_sheet, width=80, font=FONTS["button"]).pack(pady=2)
        ctk.CTkButton(sheet_controls, text="Remove", command=remove_sheet, width=80, fg_color="red", hover_color="#8b0000", font=FONTS["button"]).pack(pady=2)

        def add_col():
            idx = get_current_sheet_idx()
            if idx is None: return
            indices = listbox_avail.curselection()
            if not indices: return
            sheet_conf = editing_config[idx]
            to_add = [listbox_avail.get(i) for i in indices]
            sheet_conf['columns'].extend(to_add)
            refresh_columns_view()

        def remove_col():
            idx = get_current_sheet_idx()
            if idx is None: return
            indices = listbox_sel.curselection()
            if not indices: return
            sheet_conf = editing_config[idx]
            to_remove = [listbox_sel.get(i) for i in indices]
            sheet_conf['columns'] = [c for c in sheet_conf['columns'] if c not in to_remove]
            refresh_columns_view()
            
        def add_all():
            idx = get_current_sheet_idx()
            if idx is None: return
            editing_config[idx]['columns'] = list(available_columns)
            refresh_columns_view()

        def remove_all():
            idx = get_current_sheet_idx()
            if idx is None: return
            editing_config[idx]['columns'] = []
            refresh_columns_view()

        # Keep references to column buttons so we can lock them
        col_buttons = []
        col_buttons.append(ctk.CTkButton(mid_frame, text="Add >", command=add_col, width=80, font=FONTS["button"]))
        col_buttons[-1].pack(pady=2)
        col_buttons.append(ctk.CTkButton(mid_frame, text="< Remove", command=remove_col, width=80, font=FONTS["button"]))
        col_buttons[-1].pack(pady=2)
        col_buttons.append(ctk.CTkButton(mid_frame, text="Add All >>", command=add_all, width=80, font=FONTS["button"]))
        col_buttons[-1].pack(pady=10)
        col_buttons.append(ctk.CTkButton(mid_frame, text="<< Clear", command=remove_all, width=80, font=FONTS["button"]))
        col_buttons[-1].pack(pady=2)

        def save():
            for sheet in editing_config:
                # Exclusive stats sheets have fixed columns — skip the column check
                if any(s in sheet.get('criteria', []) for s in ('Default Statistics', 'Transactions Default Statistics')):
                    continue
                if not sheet['columns']:
                    messagebox.showwarning("Warning", f"Sheet '{sheet['name']}' has no columns selected.", parent=dialog)
                    return
                if not sheet.get('criteria') or all(c == 'Group By Criteria' for c in sheet.get('criteria', [])):
                    if not messagebox.askyesno("Warning", f"Sheet '{sheet['name']}' has no failure monitoring criteria selected.\nAll test cases will be shown (no failure filtering).\n\nContinue?", parent=dialog):
                        return
            self.custom_report_sheets = editing_config
            self.generate_custom_report = True
            dialog.destroy()
            
        def cancel():
            # If user cancels, we might just unset the flag or allow them to continue without custom report
            # But usually cancel just closes dialog.
            # self.generate_custom_report = False -> Logic in caller might define this.
            # But caller sets generate_custom_report=True only if save called.
            self.generate_custom_report = False
            dialog.destroy()

        # Populate button frame (already created and packed at top of function)
        
        ctk.CTkButton(btn_frame, text="Cancel", command=cancel, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=10, expand=True)
        ctk.CTkButton(btn_frame, text="Save & Run", command=save, fg_color="green", hover_color="#006400", font=FONTS["button"]).pack(side="left", padx=10, expand=True)

        refresh_sheet_list()
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.frame.wait_window(dialog)


    # Reuse the original methods but adapted slightly
    
    def browse_file(self):
        """Browse for Excel file"""
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if file_path:
            self.file_path_var.set(file_path)
            self.all_sheets_data = {}
            self.detect_sheets()

    def detect_sheets(self):
        """Detect and populate sheet names from the selected file"""
        file_path = self.file_path_var.get()
        if not file_path:
            return

        try:
            self.sheet_names = self.excel_handler.get_sheet_names(file_path)

            if len(self.sheet_names) > 1:
                # Multiple sheets - show sheet selector
                self.sheet_combo.configure(values=self.sheet_names)
                self.sheet_combo.set(self.sheet_names[0])
                self.current_sheet = self.sheet_names[0]
                self.sheet_frame.pack(fill="x", pady=(0, 10), after=self.main_frame.winfo_children()[1]) # Pack after file frame
                self.status_var.set(f"File has {len(self.sheet_names)} sheets. Select a sheet and click Load.")
            else:
                # Single sheet - hide selector
                self.sheet_frame.pack_forget()
                self.sheet_combo.configure(values=[])
                self.current_sheet = self.sheet_names[0] if self.sheet_names else None

        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file sheets: {str(e)}")

    def refresh_sheet(self):
        if self.current_sheet:
            self.load_sheet_data(self.current_sheet)

    def load_file(self):
        file_path = self.file_path_var.get()
        if not file_path:
            messagebox.showwarning("Warning", "Please select a file first")
            return

        if not self.sheet_names:
            self.detect_sheets()

        sheet_to_load = self.current_sheet if self.current_sheet else (self.sheet_names[0] if self.sheet_names else None)

        if sheet_to_load:
            self.load_sheet_data(sheet_to_load)
        else:
            messagebox.showerror("Error", "No sheets found in the Excel file")

    def show_execution_dialog(self):
        file_path = self.file_path_var.get()
        if not file_path or not self.sheet_names:
            messagebox.showwarning("Warning", "Please load a file first")
            return

        dialog = ctk.CTkToplevel(self.frame)
        dialog.title("Test Execution Options")
        dialog.geometry("650x800")
        dialog.transient(self.frame)
        dialog.grab_set()

        # Create scrollable main container
        main_scroll = ctk.CTkScrollableFrame(dialog)
        main_scroll.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_scroll, text="Select Test Scope", font=FONTS["title"]).pack(pady=(0, 10))
        ctk.CTkLabel(main_scroll, text=f"File: {os.path.basename(file_path)}", text_color="gray").pack(pady=(0, 5))
        ctk.CTkLabel(main_scroll, text=f"Total sheets: {len(self.sheet_names)}", text_color="gray").pack(pady=(0, 20))

        scope_var = tk.StringVar(value="current")

        # Placeholder for widgets that will be referenced in on_scope_change
        case_listbox = None
        load_cases_btn = None
        rule_id_entry = None
        rule_id_preview_btn = None
        rule_id_sheet_combo = None

        def on_scope_change():
            """Enable/disable case listbox / rule_id entry based on scope selection"""
            scope = scope_var.get()
            if case_listbox and load_cases_btn:
                if scope == "specific":
                    case_listbox.configure(state="normal")
                    load_cases_btn.configure(state="normal")
                else:
                    case_listbox.configure(state="disabled")
                    load_cases_btn.configure(state="disabled")
            if rule_id_entry and rule_id_preview_btn and rule_id_sheet_combo:
                if scope == "rule_id":
                    rule_id_entry.configure(state="normal")
                    rule_id_preview_btn.configure(state="normal")
                    rule_id_sheet_combo.configure(state="normal")
                else:
                    rule_id_entry.configure(state="disabled")
                    rule_id_preview_btn.configure(state="disabled")
                    rule_id_sheet_combo.configure(state="disabled")

        # Current Sheet Option
        current_frame = ctk.CTkFrame(main_scroll, border_width=1)
        current_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkRadioButton(current_frame, text="Current Sheet Only", variable=scope_var, value="current", font=FONTS["main_bold"], command=on_scope_change).pack(anchor="w", padx=10, pady=5)
        ctk.CTkLabel(current_frame, text=f"   → Test only: {self.current_sheet}", text_color="#1f538d", font=FONTS["main"]).pack(anchor="w", padx=20, pady=(0, 5))

        # All Sheets Option
        all_frame = ctk.CTkFrame(main_scroll, border_width=1)
        all_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkRadioButton(all_frame, text="All Sheets in File", variable=scope_var, value="all", font=FONTS["main_bold"], command=on_scope_change).pack(anchor="w", padx=10, pady=5)
        ctk.CTkLabel(all_frame, text=f"   → Test all {len(self.sheet_names)} sheets", text_color="#1f538d", font=FONTS["main"]).pack(anchor="w", padx=20, pady=(0, 5))

        # Selected Sheets Option
        selected_frame = ctk.CTkFrame(main_scroll, border_width=1)
        selected_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkRadioButton(selected_frame, text="Selected Sheets", variable=scope_var, value="selected", font=FONTS["main_bold"], command=on_scope_change).pack(anchor="w", padx=10, pady=5)
        ctk.CTkLabel(selected_frame, text="   → Choose specific sheets below:", text_color="#1f538d", font=FONTS["main"]).pack(anchor="w", padx=20, pady=(0, 5))

        listbox_frame = ctk.CTkFrame(selected_frame, height=120)
        listbox_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side="right", fill="y")
        sheet_listbox = tk.Listbox(listbox_frame, selectmode=tk.MULTIPLE, yscrollcommand=scrollbar.set, height=6, bg="#333333", fg="white", selectbackground="#1f538d", font=("Arial", 11))
        sheet_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=sheet_listbox.yview)

        for sheet in self.sheet_names:
            sheet_listbox.insert(tk.END, f"{sheet}")

        quick_btn_frame = ctk.CTkFrame(selected_frame, fg_color="transparent")
        quick_btn_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkButton(quick_btn_frame, text="Select All", command=lambda: sheet_listbox.selection_set(0, tk.END), width=80, fg_color="transparent", border_width=1, font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(quick_btn_frame, text="Clear All", command=lambda: sheet_listbox.selection_clear(0, tk.END), width=80, fg_color="transparent", border_width=1, font=FONTS["button"]).pack(side="left")

        # Specific Cases Option
        specific_frame = ctk.CTkFrame(main_scroll, border_width=1)
        specific_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkRadioButton(specific_frame, text="Specific Cases", variable=scope_var, value="specific", font=FONTS["main_bold"], command=on_scope_change).pack(anchor="w", padx=10, pady=5)
        ctk.CTkLabel(specific_frame, text="   → Choose specific test cases below:", text_color="#1f538d", font=FONTS["main"]).pack(anchor="w", padx=20, pady=(0, 5))
        
        # Frame for sheet selection for cases
        case_sheet_frame = ctk.CTkFrame(specific_frame, fg_color="transparent")
        case_sheet_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(case_sheet_frame, text="Load cases from:", font=FONTS["main"]).pack(side="left", padx=(0, 5))
        case_sheet_var = tk.StringVar(value=self.current_sheet if self.current_sheet else self.sheet_names[0])
        case_sheet_combo = ctk.CTkComboBox(case_sheet_frame, values=self.sheet_names, variable=case_sheet_var, width=150, font=FONTS["main"])
        case_sheet_combo.pack(side="left", padx=(0, 5))
        
        # Store test cases data
        test_cases_data = {}
        
        def load_test_cases():
            """Load test cases from selected sheet"""
            selected_sheet = case_sheet_var.get()
            if not selected_sheet:
                return
            
            try:
                # Load sheet data if not already loaded
                if selected_sheet not in self.all_sheets_data:
                    data = self.excel_handler.load_excel(file_path, sheet_name=selected_sheet)
                    self.all_sheets_data[selected_sheet] = data
                else:
                    data = self.all_sheets_data[selected_sheet]
                
                # Enable listbox to allow modifications
                case_listbox.configure(state="normal")
                
                # Clear current listbox
                case_listbox.delete(0, tk.END)
                test_cases_data.clear()
                
                # Populate with TC IDs
                for row in data:
                    tc_id = row.get('TC ID', '')
                    if tc_id:
                        case_listbox.insert(tk.END, str(tc_id))
                        test_cases_data[str(tc_id)] = row
                
                case_count_label.configure(text=f"   {len(test_cases_data)} cases loaded from '{selected_sheet}'")
                
                # Keep listbox enabled after loading
                # (it will be disabled by on_scope_change if user switches to another option)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load test cases: {str(e)}", parent=dialog)
        
        load_cases_btn = ctk.CTkButton(case_sheet_frame, text="Load Cases", command=load_test_cases, width=100, font=FONTS["button"])
        load_cases_btn.pack(side="left")
        
        case_count_label = ctk.CTkLabel(specific_frame, text="   Click 'Load Cases' to see available test cases", text_color="gray", font=FONTS["main"])
        case_count_label.pack(anchor="w", padx=20, pady=(0, 5))
        
        case_listbox_frame = ctk.CTkFrame(specific_frame, height=150)
        case_listbox_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        case_scrollbar = ttk.Scrollbar(case_listbox_frame)
        case_scrollbar.pack(side="right", fill="y")
        case_listbox = tk.Listbox(case_listbox_frame, selectmode=tk.EXTENDED, yscrollcommand=case_scrollbar.set, height=8, bg="#333333", fg="white", selectbackground="#1f538d", font=("Arial", 11), state="disabled")
        case_listbox.pack(side="left", fill="both", expand=True)
        case_scrollbar.config(command=case_listbox.yview)
        
        case_quick_btn_frame = ctk.CTkFrame(specific_frame, fg_color="transparent")
        case_quick_btn_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkButton(case_quick_btn_frame, text="Select All", command=lambda: case_listbox.selection_set(0, tk.END), width=80, fg_color="transparent", border_width=1, font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(case_quick_btn_frame, text="Clear All", command=lambda: case_listbox.selection_clear(0, tk.END), width=80, fg_color="transparent", border_width=1, font=FONTS["button"]).pack(side="left")

        # ── By Rule ID Option ──────────────────────────────────────────────────
        rule_id_outer_frame = ctk.CTkFrame(main_scroll, border_width=1)
        rule_id_outer_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkRadioButton(rule_id_outer_frame, text="By Rule ID", variable=scope_var, value="rule_id", font=FONTS["main_bold"], command=on_scope_change).pack(anchor="w", padx=10, pady=5)
        ctk.CTkLabel(rule_id_outer_frame, text="   → Run cases from a selected sheet that match the given Rule ID(s)", text_color="#1f538d", font=FONTS["main"]).pack(anchor="w", padx=20, pady=(0, 5))

        # Sheet selector row (same pattern as Specific Cases)
        rule_id_sheet_frame = ctk.CTkFrame(rule_id_outer_frame, fg_color="transparent")
        rule_id_sheet_frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(rule_id_sheet_frame, text="Load from:", font=FONTS["main"]).pack(side="left", padx=(0, 5))
        rule_id_sheet_var = tk.StringVar(value=self.current_sheet if self.current_sheet else self.sheet_names[0])
        rule_id_sheet_combo = ctk.CTkComboBox(rule_id_sheet_frame, values=self.sheet_names, variable=rule_id_sheet_var, width=150, font=FONTS["main"], state="disabled")
        rule_id_sheet_combo.pack(side="left", padx=(0, 10))

        # Rule ID entry row
        rule_id_input_frame = ctk.CTkFrame(rule_id_outer_frame, fg_color="transparent")
        rule_id_input_frame.pack(fill="x", padx=20, pady=(0, 5))

        ctk.CTkLabel(rule_id_input_frame, text="Rule ID(s):", font=FONTS["main"]).pack(side="left", padx=(0, 5))
        rule_id_var = tk.StringVar()
        rule_id_entry = ctk.CTkEntry(rule_id_input_frame, textvariable=rule_id_var, width=200, placeholder_text="e.g. 92  or  82, 92", font=FONTS["main"], state="disabled")
        rule_id_entry.pack(side="left", padx=(0, 5))

        rule_id_count_label = ctk.CTkLabel(rule_id_outer_frame, text="", text_color="gray", font=FONTS["main"])
        rule_id_count_label.pack(anchor="w", padx=20, pady=(0, 3))

        # Read-only listbox to show matched cases
        rule_id_listbox_frame = ctk.CTkFrame(rule_id_outer_frame, height=130)
        rule_id_listbox_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        rule_id_listbox_frame.pack_propagate(False)

        rule_id_scrollbar = ttk.Scrollbar(rule_id_listbox_frame)
        rule_id_scrollbar.pack(side="right", fill="y")
        rule_id_listbox = tk.Listbox(
            rule_id_listbox_frame,
            yscrollcommand=rule_id_scrollbar.set,
            height=6,
            bg="#2b2b2b",
            fg="#cccccc",
            selectbackground="#2b2b2b",
            selectforeground="#cccccc",
            font=("Courier", 10),
            state="disabled",
        )
        rule_id_listbox.pack(side="left", fill="both", expand=True)
        rule_id_scrollbar.config(command=rule_id_listbox.yview)

        def preview_rule_id_cases():
            """Load selected sheet, populate the listbox with matching cases."""
            raw = rule_id_var.get().strip()
            if not raw:
                messagebox.showwarning("No Rule ID", "Please enter at least one Rule ID.", parent=dialog)
                return
            selected_sheet = rule_id_sheet_var.get()
            rule_ids = [r.strip() for r in raw.split(',') if r.strip()]
            try:
                if selected_sheet not in self.all_sheets_data:
                    data = self.excel_handler.load_excel(file_path, sheet_name=selected_sheet)
                    self.all_sheets_data[selected_sheet] = data
                matched = [
                    row for row in self.all_sheets_data[selected_sheet]
                    if str(row.get('Rule ID', '')).strip() in rule_ids
                ]
                # Populate listbox
                rule_id_listbox.configure(state="normal")
                rule_id_listbox.delete(0, tk.END)
                for row in matched:
                    tc_id_val = str(row.get('TC ID', '')).strip()
                    tc_name_val = str(row.get('Name', row.get('TC Name', row.get('Test Name', '')))).strip()
                    label = f"{tc_id_val}"  + (f"  |  {tc_name_val}" if tc_name_val else "")
                    rule_id_listbox.insert(tk.END, label)
                rule_id_listbox.configure(state="disabled")
                rule_id_count_label.configure(
                    text=f"   {len(matched)} matching case(s) in '{selected_sheet}' for Rule ID(s): {', '.join(rule_ids)}",
                    text_color="#4CAF50" if matched else "#FF5252"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to preview: {str(e)}", parent=dialog)

        rule_id_preview_btn = ctk.CTkButton(rule_id_input_frame, text="Preview", command=preview_rule_id_cases, width=80, font=FONTS["button"], state="disabled")
        rule_id_preview_btn.pack(side="left")

        # Button frame at bottom
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=(0, 20))

        def run():
            scope = scope_var.get()
            specific_cases = None
            specific_rule_ids = None

            if scope == "current":
                sheets_to_test = [self.current_sheet]
            elif scope == "all":
                sheets_to_test = self.sheet_names
            elif scope == "selected":
                selected_indices = sheet_listbox.curselection()
                if not selected_indices:
                    messagebox.showwarning("No Selection", "Please select at least one sheet", parent=dialog)
                    return
                sheets_to_test = [self.sheet_names[i] for i in selected_indices]
            elif scope == "specific":
                selected_indices = case_listbox.curselection()
                if not selected_indices:
                    messagebox.showwarning("No Selection", "Please select at least one test case", parent=dialog)
                    return
                specific_cases = [case_listbox.get(i) for i in selected_indices]
                sheets_to_test = [case_sheet_var.get()]
            elif scope == "rule_id":
                raw = rule_id_var.get().strip()
                if not raw:
                    messagebox.showwarning("No Rule ID", "Please enter at least one Rule ID.", parent=dialog)
                    return
                specific_rule_ids = [r.strip() for r in raw.split(',') if r.strip()]
                sheets_to_test = [rule_id_sheet_var.get()]  # only the selected sheet
            else:
                sheets_to_test = [self.current_sheet]

            dialog.destroy()
            self.execute_tests(sheets_to_test, specific_cases=specific_cases, specific_rule_ids=specific_rule_ids)

        ctk.CTkButton(button_frame, text="Cancel", command=dialog.destroy, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="right", padx=(5, 0))
        ctk.CTkButton(button_frame, text="Run Tests", command=run, fg_color="green", hover_color="#006400", font=FONTS["button"]).pack(side="right")


    def execute_tests(self, sheets_to_test, specific_cases=None, specific_rule_ids=None):
        file_path = self.file_path_var.get()
        
        # Load any sheets that aren't cached
        for sheet in sheets_to_test:
            if sheet not in self.all_sheets_data:
                try:
                    data = self.excel_handler.load_excel(file_path, sheet_name=sheet)
                    self.all_sheets_data[sheet] = data
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load sheet '{sheet}': {str(e)}")
                    return

        # Filter test cases based on selection mode
        if specific_cases:
            filtered_data = {}
            for sheet in sheets_to_test:
                data = self.all_sheets_data[sheet]
                filtered_rows = [row for row in data if str(row.get('TC ID', '')) in specific_cases]
                filtered_data[sheet] = filtered_rows
            test_data_to_use = filtered_data
        elif specific_rule_ids:
            filtered_data = {}
            for sheet in sheets_to_test:
                data = self.all_sheets_data[sheet]
                filtered_rows = [row for row in data if str(row.get('Rule ID', '')).strip() in specific_rule_ids]
                filtered_data[sheet] = filtered_rows
            test_data_to_use = filtered_data
        else:
            test_data_to_use = {sheet: self.all_sheets_data[sheet] for sheet in sheets_to_test}

        total_tests = 0
        for sheet in sheets_to_test:
            data = test_data_to_use[sheet]
            executable = len([row for row in data])
            total_tests += executable

        if total_tests == 0:
            messagebox.showwarning("Warning", "No test cases found matching the selection")
            return

        # Update confirmation message based on selection mode
        if specific_cases:
            confirm_msg = f"Ready to execute {total_tests} specific test case(s)?"
        elif specific_rule_ids:
            confirm_msg = f"Ready to execute {total_tests} test case(s) matching Rule ID(s): {', '.join(specific_rule_ids)}?"
        else:
            confirm_msg = f"Ready to execute {total_tests} tests across {len(sheets_to_test)} sheets?"
        
        if not messagebox.askyesno("Confirm Execution", confirm_msg):
            return

        if not self.assert_error_text.get():
            if not messagebox.askyesno("Confirm Assertion", "Assert Error Text is unchecked.\n\nAre you sure you want to proceed without textual assertions?", icon='warning'):
                return

        if self.target_env.get() == "production":
            if not messagebox.askyesno("Confirm Production", "WARNING: TESTING ON PRODUCTION! Proceed?", icon='warning'):
                return

        if messagebox.askyesno("Custom Report", "Do you want to generate a custom report?"):
            self.show_custom_report_dialog()
            if not self.generate_custom_report:
                 # User cancelled the dialog, abort execution
                 return
        else:
            self.generate_custom_report = False
            self.custom_report_sheets = []



        self.status_var.set(f"Executing {total_tests} tests...")
        
        result, message = validate_excel(test_data_to_use)
        if result:
            if not message:
                self.run_allure_tests_only(file_path, ", ".join(sheets_to_test), specific_cases, specific_rule_ids)
            else:
                messagebox.showwarning("Warning", f"Extra columns: {message}")
                self.run_allure_tests_only(file_path, ", ".join(sheets_to_test), specific_cases, specific_rule_ids)
        else:
            messagebox.showerror("Error", f"Missing columns: {message}")

    def run_allure_tests_only(self, file_path, sheets_to_test, specific_cases=None, specific_rule_ids=None):
        try:
            os.environ[EnvVar.SOAP_EXCEL_FILE] = file_path
            os.environ[EnvVar.EXCEL_FILE_TEST_SHEETS] = sheets_to_test
            os.environ[EnvVar.SOAP_EXECUTION_MODE] = self.execution_mode.get()
            os.environ[EnvVar.SOAP_EXECUTION_SEQUENCE] = self.execution_sequence.get()
            step_delay = 0.0
            if self.execution_sequence.get() == "full_scenario":
                try:
                    step_delay = max(0.0, float(self.step_delay_var.get() or "0"))
                except ValueError:
                    step_delay = 0.0
            os.environ[EnvVar.SOAP_STEP_DELAY] = str(step_delay)
            os.environ[EnvVar.SOAP_GENERATE_RULES_SUMMARY] = "false"
            os.environ[EnvVar.SOAP_GENERATE_LEGACY_RULES_SUMMARY] = "false"
            os.environ[EnvVar.SOAP_GENERATE_SYSTEM_RULES_SUMMARY] = "false"
            os.environ[EnvVar.ASSERT_ERROR_TEXT] = "true" if self.assert_error_text.get() else "false"
            os.environ[EnvVar.ASSERT_OBJECT_ELEMENT] = "true" if self.assert_object_element.get() else "false"
            os.environ[EnvVar.ASSERT_FIELD_ADDITIONAL] = "true" if self.assert_field_additional.get() else "false"
            os.environ[EnvVar.FULL_REPORT_COMPARISON] = "true" if self.full_report_comparison.get() else "false"
            os.environ[EnvVar.FULL_ROW_COMPARISON] = "true" if self.full_row_comparison.get() else "false"
            os.environ[EnvVar.TARGET_ENVIRONMENT] = self.target_env.get()
            os.environ[EnvVar.NEW_TARGET_ENVIRONMENT] = self.new_target_env.get()

            # Set specific cases filter if provided
            if specific_cases:
                os.environ[EnvVar.SPECIFIC_TEST_CASES] = ",".join(specific_cases)
            else:
                if EnvVar.SPECIFIC_TEST_CASES in os.environ:
                    del os.environ[EnvVar.SPECIFIC_TEST_CASES]

            # Set Rule ID filter if provided
            if specific_rule_ids:
                os.environ[EnvVar.SPECIFIC_RULE_IDS] = ",".join(specific_rule_ids)
            else:
                if EnvVar.SPECIFIC_RULE_IDS in os.environ:
                    del os.environ[EnvVar.SPECIFIC_RULE_IDS]

            if self.use_specific_login.get():
                os.environ[EnvVar.USE_SPECIFIC_LOGIN] = "true"
                os.environ[EnvVar.PROVIDER_VALUE] = self.provider_value.get()
                os.environ[EnvVar.PAYER_VALUE] = self.payer_value.get()
                os.environ[EnvVar.TPA_VALUE] = self.tpa_value.get()
                os.environ[EnvVar.PHARMACY_VALUE] = self.pharmacy_value.get()
            else:
                if EnvVar.USE_SPECIFIC_LOGIN in os.environ:
                    del os.environ[EnvVar.USE_SPECIFIC_LOGIN]
                if EnvVar.PROVIDER_VALUE in os.environ:
                    del os.environ[EnvVar.PROVIDER_VALUE]
                if EnvVar.PAYER_VALUE in os.environ:
                    del os.environ[EnvVar.PAYER_VALUE]
                if EnvVar.TPA_VALUE in os.environ:
                    del os.environ[EnvVar.TPA_VALUE]
                if EnvVar.PHARMACY_VALUE in os.environ:
                    del os.environ[EnvVar.PHARMACY_VALUE]

            if self.use_custom_disposition_flag.get():
                os.environ[EnvVar.CUSTOM_DISPOSITION_FLAG] = self.custom_disposition_flag_value.get()
            else:
                if EnvVar.CUSTOM_DISPOSITION_FLAG in os.environ:
                    del os.environ[EnvVar.CUSTOM_DISPOSITION_FLAG]

            allure_dir = self.allure_results_dir.get()
            self._clear_allure_results(allure_dir)

            if getattr(sys, 'frozen', False):
                project_root = Path(sys.executable).parent
                python_exe = project_root / "python_runtime" / "python.exe"
            else:
                current_file = Path(__file__).resolve()
                project_root = current_file.parent.parent
                python_exe = sys.executable

            wrapper_path = project_root / "utils" / "allure_wrapper.py"

            cmd = [str(python_exe), "-m", "pytest", str(wrapper_path), "--alluredir", allure_dir, "--tb=short", "-v"]

            if self.enable_parallel.get():
                worker_count = self.worker_count.get()
                if worker_count == "auto":
                    cmd.extend(["-n", "auto"])
                else:
                    cmd.extend(["-n", worker_count])

            def run_pytest():
                try:
                    self.current_process = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                        text=True, cwd=str(project_root), creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    stdout, stderr = self.current_process.communicate()
                    result_code = self.current_process.returncode

                    if result_code == 0 or result_code == 1:
                        self.status_var.set("Allure tests completed successfully")
                        if self.generate_custom_report and self.custom_report_sheets:

                            # We need a path to save the report. Using self.file_path_var's directory or asking?
                            # Using the same directory as source excel or specific "reports" dir?
                            # The old code relied on self.rules_summary_path which was likely set by user or default.
                            # I will ask the user for save location or use a default.
                            # Just using default logic: report in 'reports' folder or alongside
                            
                            try:
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                default_name = f"custom_report_{timestamp}.xlsx"
                                
                                report_path = filedialog.asksaveasfilename(
                                    title="Save Custom Report",
                                    defaultextension=".xlsx",
                                    initialfile=default_name,
                                    filetypes=[("Excel files", "*.xlsx")]
                                )
                                
                                if report_path:
                                    generate_custom_combined_report(
                                        allure_dir,
                                        report_path,
                                        self.custom_report_sheets,
                                        assert_error_text_enabled=self.assert_error_text.get(),
                                        assert_field_additional_enabled=self.assert_field_additional.get()
                                    )
                                    # Remember for quick regeneration
                                    self.last_custom_report_path = report_path
                                    self.last_allure_dir = allure_dir
                                    messagebox.showinfo("Excel Generated", f"Custom report generated at:\n{report_path}")
                                else:
                                    self.status_var.set("Custom report generation cancelled")
                            except Exception as e:
                                messagebox.showerror("Excel Error", f"Failed to generate Custom Report: {e}")
                    else:
                        self.status_var.set(f"Tests completed with issues (exit code: {result_code})")

                    self._show_run_summary_dialog(allure_dir)
                    self.show_pytest_output(stdout, stderr)

                except Exception as e:
                    self.status_var.set(f"Failed to run Allure tests: {str(e)}")
                    messagebox.showerror("Execution Error", str(e))
                finally:
                    self.current_process = None
                    self.testing_active = False

            thread = threading.Thread(target=run_pytest)
            thread.daemon = True
            thread.start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start Allure tests: {str(e)}")

    def show_pytest_output(self, stdout, stderr):
        output_window = ctk.CTkToplevel(self.frame)
        output_window.title("Pytest Execution Output")
        output_window.geometry("800x600")

        tabview = ctk.CTkTabview(output_window)
        tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        tabview.add("Standard Output")
        tabview.add("Error Output")

        stdout_text = ctk.CTkTextbox(tabview.tab("Standard Output"))
        stdout_text.pack(fill="both", expand=True)
        stdout_text.insert("1.0", stdout)
        stdout_text.configure(state='disabled')

        stderr_text = ctk.CTkTextbox(tabview.tab("Error Output"))
        stderr_text.pack(fill="both", expand=True)
        stderr_text.insert("1.0", stderr)
        stderr_text.configure(state='disabled')

        ctk.CTkButton(output_window, text="Close", command=output_window.destroy).pack(pady=5)

    def _show_run_summary_dialog(self, allure_dir):
        counts = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0}
        for file in Path(allure_dir).glob("*-result.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                status = data.get("status", "")
                if status in counts:
                    counts[status] += 1
            except (json.JSONDecodeError, OSError):
                continue

        total = sum(counts.values())
        if total == 0:
            return

        broken = counts["failed"] + counts["broken"]
        lines = [
            f"Broken / Failed:  {broken} out of {total} total\n",
            f"  Passed:   {counts['passed']}",
            f"  Failed:   {counts['failed']}",
            f"  Broken:   {counts['broken']}",
        ]
        if counts["skipped"]:
            lines.append(f"  Skipped:  {counts['skipped']}")

        messagebox.showinfo("Run Complete", "\n".join(lines))

    def _clear_allure_results(self, allure_dir):
        self.allure_report_generated = False
        try:
            if os.path.exists(allure_dir):
                shutil.rmtree(allure_dir)
            os.makedirs(allure_dir, exist_ok=True)
        except Exception as e:
            print(f"WARNING: Could not clear allure results: {e}")

    def load_sheet_data(self, sheet_name):
        file_path = self.file_path_var.get()
        try:
            self.status_var.set(f"Loading sheet '{sheet_name}'...")
            self.frame.update()

            if sheet_name in self.all_sheets_data:
                self.all_data = self.all_sheets_data[sheet_name]
            else:
                self.all_data = self.excel_handler.load_excel(file_path, sheet_name=sheet_name)
                self.all_sheets_data[sheet_name] = self.all_data

            if self.all_data:
                total_rows = len(self.all_data)
                rows_per_page_str = self.rows_per_page_var.get()

                if rows_per_page_str == "All":
                    self.rows_per_page = total_rows
                else:
                    self.rows_per_page = int(rows_per_page_str)

                self.total_pages = (total_rows + self.rows_per_page - 1) // self.rows_per_page
                self.current_page = 0

                if total_rows > 100:
                    self.pagination_frame.pack(fill="x", pady=(0, 10), before=self.tree.master)
                else:
                    self.pagination_frame.pack_forget()

                self.display_current_page()
                
                status_msg = f"Loaded {total_rows} rows"
                self.status_var.set(status_msg)
            else:
                self.status_var.set("Loaded 0 rows")
                self.pagination_frame.pack_forget()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sheet '{sheet_name}': {str(e)}")

    def display_current_page(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not self.all_data:
            return

        start_idx = self.current_page * self.rows_per_page
        end_idx = min(start_idx + self.rows_per_page, len(self.all_data))
        page_data = self.all_data[start_idx:end_idx]

        if not self.tree['columns']:
            columns = list(self.all_data[0].keys())
            self.tree['columns'] = columns
            for col in columns:
                self.tree.heading(col, text=col)
                self.tree.column(col, width=150)

        for row in page_data:
            columns = self.tree['columns']
            values = [row.get(col, '') for col in columns]
            self.tree.insert('', 'end', values=values)

        self.page_label.configure(text=f"Page {self.current_page + 1} of {self.total_pages} (Rows {start_idx + 1}-{end_idx} of {len(self.all_data)})")

    def on_rows_per_page_changed(self, event=None):
        rows_per_page_str = self.rows_per_page_var.get()
        if rows_per_page_str == "All":
            self.rows_per_page = len(self.all_data)
            self.pagination_frame.pack_forget()
        else:
            self.rows_per_page = int(rows_per_page_str)
            if len(self.all_data) > 100:
                self.pagination_frame.pack(fill="x", pady=(0, 10), before=self.tree.master)

        self.total_pages = max(1, (len(self.all_data) + self.rows_per_page - 1) // self.rows_per_page)
        self.current_page = 0
        self.display_current_page()

    def go_to_first_page(self):
        if self.current_page != 0:
            self.current_page = 0
            self.display_current_page()

    def go_to_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_current_page()

    def go_to_next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_current_page()

    def go_to_last_page(self):
        if self.current_page != self.total_pages - 1:
            self.current_page = self.total_pages - 1
            self.display_current_page()

    def go_to_page(self, event=None):
        try:
            page_num = int(self.page_entry.get())
            if 1 <= page_num <= self.total_pages:
                self.current_page = page_num - 1
                self.display_current_page()
                self.page_entry.delete(0, tk.END)
            else:
                messagebox.showwarning("Invalid Page", f"Please enter a page between 1 and {self.total_pages}")
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid page number")

    def create_template(self):
        file_path = filedialog.asksaveasfilename(title="Save Template", defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            try:
                create_excel_template(file_path)
                messagebox.showinfo("Success", f"Template created at {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create template: {str(e)}")

    def save_allure_report(self):
        if getattr(sys, 'frozen', False):
            report_dir = str(Path(sys.executable).parent / "allure-report")
        else:
            report_dir = "allure-report"
        results_dir = self.allure_results_dir.get()
        if not os.path.exists(results_dir):
            messagebox.showwarning("Error", "No test results found. Please run tests first.")
            return

        # Ask user for format preference
        save_single = messagebox.askyesno("Save Format", "Do you want to combine the report into a single HTML file?\n\nYes: Single .html file (easier to share)\nNo: Full folder (standard Allure format)")

        if save_single:
            # Allure natively supports single-file report generation
            # (allure generate --single-file), so no external dependency needed.
            allure_cmd = self._find_allure_executable()
            if not allure_cmd:
                messagebox.showerror("Error", "Allure not found.")
                return
            try:
                self.status_var.set("Generating single-file report...")
                self.frame.update()
                subprocess.run(
                    [allure_cmd, "generate", "--single-file", results_dir, "-o", report_dir, "--clean"],
                    capture_output=True, shell=False, check=True, cwd=tempfile.gettempdir(),
                )
                # report_dir now holds the single-file variant, not the regular
                # multi-file report, so it must be regenerated next time it's
                # needed as a folder.
                self.allure_report_generated = False

                source_file = os.path.join(report_dir, "index.html")
                if os.path.exists(source_file):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    default_name = f"allure-report_{timestamp}.html"

                    file_path = filedialog.asksaveasfilename(
                        title="Save Single HTML Report",
                        defaultextension=".html",
                        initialfile=default_name,
                        filetypes=[("HTML files", "*.html")]
                    )

                    if file_path:
                        shutil.copy2(source_file, file_path)
                        messagebox.showinfo("Success", f"Report saved to:\n{file_path}")
                        self.status_var.set("Report saved")
                    else:
                        self.status_var.set("Save cancelled")
                else:
                    messagebox.showerror("Error", "Failed to generate single file (index.html NOT found).")
                    self.status_var.set("Generation failed")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate single-file report: {e}")
                self.status_var.set("Error generating report")

        else:
            # Regenerate HTML only if tests were run since the last generation
            if not self.allure_report_generated:
                allure_cmd = self._find_allure_executable()
                if not allure_cmd:
                    messagebox.showerror("Error", "Allure not found.")
                    return
                self.status_var.set("Generating HTML report from latest results...")
                self.frame.update()
                subprocess.run([allure_cmd, "generate", results_dir, "-o", report_dir, "--clean"], capture_output=True, shell=False, cwd=tempfile.gettempdir())
                self.allure_report_generated = True

            # Standard Folder Copy
            destination = filedialog.askdirectory(title="Select Directory")
            if destination:
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    default_name = f"allure-report_{timestamp}"
                    folder_name = simpledialog.askstring("Report Folder Name", "Enter folder name:", initialvalue=default_name)

                    if folder_name:
                        dest_path = os.path.join(destination, folder_name)
                        shutil.copytree(report_dir, dest_path)
                        if messagebox.askyesno("Zip Report", "Do you want to zip the report folder?"):
                            self.status_var.set("Zipping report...")
                            self.frame.update()
                            zip_path = shutil.make_archive(dest_path, 'zip', destination, folder_name)
                            shutil.rmtree(dest_path)
                            messagebox.showinfo("Success", f"Report saved and zipped to:\n{zip_path}")
                            self.status_var.set("Report saved and zipped")
                        else:
                            messagebox.showinfo("Success", f"Report saved to:\n{dest_path}")
                            self.status_var.set("Report saved")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save: {e}")

    def open_allure_report(self):
        results_dir = os.path.abspath(self.allure_results_dir.get())
        if not os.path.exists(results_dir):
            messagebox.showwarning("Error", "No test results found.")
            return

        allure_cmd = self._find_allure_executable()
        if allure_cmd:
            # Use 'serve' to generate report from results on the fly,
            # avoiding issues if the allure-report folder was modified/combined
            subprocess.Popen([allure_cmd, "serve", results_dir], shell=False, cwd=tempfile.gettempdir())
        else:
            messagebox.showerror("Error", "Allure not found")

    def generate_allure_html_report_manual(self):
        self.generate_allure_html_report(self.allure_results_dir.get())

    def generate_allure_html_report(self, results_dir):
        allure_cmd = self._find_allure_executable()
        if not allure_cmd:
             messagebox.showerror("Error", "Allure not found")
             return
        
        if getattr(sys, 'frozen', False):
            report_dir = str(Path(sys.executable).parent / "allure-report")
        else:
            report_dir = "allure-report"
        subprocess.run([allure_cmd, "generate", results_dir, "-o", report_dir, "--clean"], capture_output=True, shell=False, cwd=tempfile.gettempdir())
        self.status_var.set(f"HTML report generated in {report_dir}")
        messagebox.showinfo("Success", "HTML generated")

    def _find_allure_executable(self):
        import shutil
        if getattr(sys, 'frozen', False):
            base = Path(sys.executable).parent
            bundled = base / "allure" / "bin" / "allure.bat"
            if bundled.exists():
                jre = base / "jre"
                if jre.exists():
                    os.environ["JAVA_HOME"] = str(jre)
                return str(bundled)
        path = shutil.which("allure")
        if path: return path
        for name in ("allure.bat", "allure.cmd"):
            path = shutil.which(name)
            if path: return path
        return None

    def regenerate_custom_report(self):
        """Generate a custom report from the existing allure-results folder (no re-run needed)."""
        # Fall back to the default allure-results dir on disk if no in-session run happened yet
        allure_dir = self.last_allure_dir or self.allure_results_dir.get()

        if not os.path.isdir(allure_dir):
            messagebox.showwarning(
                "No Allure Results",
                f"Allure results folder not found:\n{allure_dir}\n\nPlease run tests first."
            )
            return

        # Sync env vars from current GUI state so generate_rules_summary uses the right mode
        os.environ[EnvVar.SOAP_EXECUTION_MODE]    = self.execution_mode.get()
        os.environ[EnvVar.ASSERT_ERROR_TEXT]        = "true" if self.assert_error_text.get() else "false"
        os.environ[EnvVar.ASSERT_OBJECT_ELEMENT]    = "true" if self.assert_object_element.get() else "false"
        os.environ[EnvVar.ASSERT_FIELD_ADDITIONAL]  = "true" if self.assert_field_additional.get() else "false"
        os.environ[EnvVar.FULL_REPORT_COMPARISON]   = "true" if self.full_report_comparison.get() else "false"
        os.environ[EnvVar.FULL_ROW_COMPARISON]      = "true" if self.full_row_comparison.get() else "false"

        self.show_custom_report_dialog()
        if not self.generate_custom_report:
            return  # User cancelled

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"custom_report_{timestamp}.xlsx"

            report_path = filedialog.asksaveasfilename(
                title="Save Custom Report",
                defaultextension=".xlsx",
                initialfile=default_name,
                initialdir=os.path.dirname(self.last_custom_report_path) if self.last_custom_report_path else None,
                filetypes=[("Excel files", "*.xlsx")]
            )

            if not report_path:
                self.status_var.set("Report generation cancelled")
                return

            self.status_var.set("Generating custom report...")
            generate_custom_combined_report(
                allure_dir,
                report_path,
                self.custom_report_sheets,
                assert_error_text_enabled=self.assert_error_text.get(),
                assert_field_additional_enabled=self.assert_field_additional.get()
            )
            self.last_custom_report_path = report_path
            self.last_allure_dir = allure_dir
            self.status_var.set(f"Custom report generated: {os.path.basename(report_path)}")
            messagebox.showinfo("Excel Generated", f"Custom report generated at:\n{report_path}")

        except Exception as e:
            messagebox.showerror("Excel Error", f"Failed to generate Custom Report: {e}")
            self.status_var.set("Report generation failed")

    def stop_tests(self):
        self.testing_active = False
        self.status_var.set("Stopping...")
        if self.current_process:
            self.current_process.terminate()





    def on_execution_sequence_change(self, *args):
        # Step delay only applies between transactions of a Full Scenario chain
        enabled = self.execution_sequence.get() == "full_scenario"
        self.step_delay_entry.configure(state="normal" if enabled else "disabled")
        text_color = ("gray10", "gray90") if enabled else ("gray60", "gray45")
        self.step_delay_label.configure(text_color=text_color)
        self.step_delay_unit_label.configure(text_color=text_color)

    def on_mode_change(self, *args):
        mode = self.execution_mode.get()
        # assert_text = self.assert_error_text.get()
        
        if mode == ExecutionMode.SYSTEM1_BOTH_ENVS:
            self.execution_sequence.set("single_api")

        # Removed legacy checkboxes logic

        if mode in [ExecutionMode.SYSTEM1_ONLY, ExecutionMode.BOTH_SYSTEMS]:
            self.pte_radio.configure(state='normal')
            self.prod_radio.configure(state='normal')
        else:
            self.pte_radio.configure(state='disabled')
            self.prod_radio.configure(state='disabled')
            if mode == ExecutionMode.SYSTEM2_ONLY:
                self.target_env.set("pte")

        if mode in [ExecutionMode.SYSTEM2_ONLY, ExecutionMode.BOTH_SYSTEMS]:
            self.new_target_test_radio.configure(state='normal')
            self.new_target_dev_radio.configure(state='normal')
            self.new_target_uat_radio.configure(state='normal')
            self.new_target_stage_radio.configure(state='normal')
        else:
            self.new_target_test_radio.configure(state='disabled')
            self.new_target_dev_radio.configure(state='disabled')
            self.new_target_uat_radio.configure(state='disabled')
            self.new_target_stage_radio.configure(state='disabled')

        if self.full_report_comparison is not None:
            if mode in [ExecutionMode.BOTH_SYSTEMS, ExecutionMode.SYSTEM1_BOTH_ENVS]:
                self.full_report_comparison_cb.configure(state='normal')
            else:
                self.full_report_comparison_cb.configure(state='disabled')
                self.full_report_comparison.set(False)

        if self.full_row_comparison is not None:
            if mode in [ExecutionMode.BOTH_SYSTEMS, ExecutionMode.SYSTEM1_BOTH_ENVS]:
                self.full_row_comparison_cb.configure(state='normal')
            else:
                self.full_row_comparison_cb.configure(state='disabled')
                self.full_row_comparison.set(False)

        # ADO Report button: relevant when both systems are compared or system2_only
        if hasattr(self, 'ado_report_btn'):
            if mode in (ExecutionMode.BOTH_SYSTEMS, ExecutionMode.SYSTEM2_ONLY):
                self.ado_report_btn.configure(state='normal')
            else:
                self.ado_report_btn.configure(state='disabled')

        if hasattr(self, 'ado_update_bugs_btn'):
            if mode in (ExecutionMode.BOTH_SYSTEMS, ExecutionMode.SYSTEM2_ONLY):
                self.ado_update_bugs_btn.configure(state='normal')
            else:
                self.ado_update_bugs_btn.configure(state='disabled')

        if hasattr(self, 'ado_was_ever_reported_btn'):
            if mode in (ExecutionMode.BOTH_SYSTEMS, ExecutionMode.SYSTEM2_ONLY):
                self.ado_was_ever_reported_btn.configure(state='normal')
            else:
                self.ado_was_ever_reported_btn.configure(state='disabled')

    def _on_full_report_comparison_changed(self):
        if self.full_report_comparison.get():
            self.full_row_comparison.set(False)
            self.full_row_comparison_cb.configure(state='disabled')
        else:
            mode = self.execution_mode.get()
            if mode in (ExecutionMode.BOTH_SYSTEMS, ExecutionMode.SYSTEM1_BOTH_ENVS):
                self.full_row_comparison_cb.configure(state='normal')

    def _on_full_row_comparison_changed(self):
        if self.full_row_comparison.get():
            self.full_report_comparison.set(False)
            self.full_report_comparison_cb.configure(state='disabled')
        else:
            mode = self.execution_mode.get()
            if mode in (ExecutionMode.BOTH_SYSTEMS, ExecutionMode.SYSTEM1_BOTH_ENVS):
                self.full_report_comparison_cb.configure(state='normal')