"""
Batch Testing Tab - Complete version with multi-sheet support, pagination, and execution dialog
"""
import json
import os
import re
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
from utils.excel_handler import ExcelHandler, validate_excel, create_excel_template
from utils.api_client import APIClient
from utils.variable_processor import VariableProcessor
import threading


class BatchTab:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.excel_handler = ExcelHandler()
        self.api_client = APIClient()
        self.variable_processor = VariableProcessor()
        self.testing_active = False
        self.sheet_names = []
        self.current_sheet = None
        self.current_process = None

        # Pagination variables
        self.all_data = []  # Complete dataset
        self.current_page = 0
        self.rows_per_page = 100  # Default: 100 rows per page
        self.total_pages = 0

        # Sheet data cache for all sheets
        self.all_sheets_data = {}  # {sheet_name: data}

        self.create_widgets()

    def create_widgets(self):
        """Create batch testing widgets"""
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # File selection
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(file_frame, text="Excel File:").pack(side=tk.LEFT)
        self.file_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_path_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True,
                                                                              padx=(5, 5))
        ttk.Button(file_frame, text="Browse", command=self.browse_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_frame, text="Load", command=self.load_file).pack(side=tk.LEFT)

        # Sheet selection frame (initially hidden)
        self.sheet_frame = ttk.LabelFrame(main_frame, text="Sheet Selection", padding=10)
        # Don't pack it yet - will be shown when file is loaded

        ttk.Label(self.sheet_frame, text="Select Sheet:").pack(side=tk.LEFT, padx=(0, 5))
        self.sheet_combo = ttk.Combobox(self.sheet_frame, state='readonly', width=30)
        self.sheet_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.sheet_combo.bind('<<ComboboxSelected>>', self.on_sheet_selected)

        ttk.Button(self.sheet_frame, text="Refresh", command=self.refresh_sheet).pack(side=tk.LEFT)

        # Pagination controls frame
        self.pagination_frame = ttk.LabelFrame(main_frame, text="Data Navigation", padding=10)
        # Will be shown when data is loaded

        # Left side - rows per page
        left_controls = ttk.Frame(self.pagination_frame)
        left_controls.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(left_controls, text="Rows per page:").pack(side=tk.LEFT, padx=(0, 5))
        self.rows_per_page_var = tk.StringVar(value="100")
        rows_combo = ttk.Combobox(left_controls, textvariable=self.rows_per_page_var,
                                  values=["50", "100", "200", "500", "1000", "All"],
                                  width=10, state='readonly')
        rows_combo.pack(side=tk.LEFT, padx=(0, 10))
        rows_combo.bind('<<ComboboxSelected>>', self.on_rows_per_page_changed)

        # Right side - pagination controls
        right_controls = ttk.Frame(self.pagination_frame)
        right_controls.pack(side=tk.RIGHT)

        ttk.Button(right_controls, text="⏮ First", command=self.go_to_first_page, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(right_controls, text="◀ Prev", command=self.go_to_prev_page, width=8).pack(side=tk.LEFT, padx=2)

        self.page_label = ttk.Label(right_controls, text="Page 0 of 0", width=15)
        self.page_label.pack(side=tk.LEFT, padx=10)

        ttk.Button(right_controls, text="Next ▶", command=self.go_to_next_page, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(right_controls, text="Last ⏭", command=self.go_to_last_page, width=8).pack(side=tk.LEFT, padx=2)

        # Jump to page
        ttk.Label(right_controls, text="Go to:").pack(side=tk.LEFT, padx=(10, 5))
        self.page_entry = ttk.Entry(right_controls, width=6)
        self.page_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.page_entry.bind('<Return>', self.go_to_page)
        ttk.Button(right_controls, text="Go", command=self.go_to_page, width=5).pack(side=tk.LEFT)

        # Execution mode selection
        mode_frame = ttk.LabelFrame(main_frame, text="Execution Mode", padding=10)
        mode_frame.pack(fill=tk.X, pady=(0, 10))

        self.execution_mode = tk.StringVar(value="system1_only")

        # Parallel execution options
        parallel_frame = ttk.LabelFrame(main_frame, text="Parallel Execution", padding=10)
        parallel_frame.pack(fill=tk.X, pady=(0, 10))

        self.enable_parallel = tk.BooleanVar(value=False)
        ttk.Checkbutton(parallel_frame, text="Enable Parallel Execution",
                        variable=self.enable_parallel).pack(anchor=tk.W)

        workers_frame = ttk.Frame(parallel_frame)
        workers_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(workers_frame, text="Number of Workers:").pack(side=tk.LEFT)
        self.worker_count = tk.StringVar(value="auto")
        worker_combo = ttk.Combobox(workers_frame, textvariable=self.worker_count,
                                    values=["auto", "2", "3", "4", "6", "8", "10", "12"],
                                    width=10, state='readonly')
        worker_combo.pack(side=tk.LEFT, padx=(5, 0))

        ttk.Radiobutton(mode_frame, text="System 1 Only (Collect Expected Errors)",
                        variable=self.execution_mode, value="system1_only").pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Both Systems (Regression Testing)",
                        variable=self.execution_mode, value="both_systems").pack(anchor=tk.W)

        # Reporting options
        reporting_frame = ttk.LabelFrame(main_frame, text="Reporting Options", padding=10)
        reporting_frame.pack(fill=tk.X, pady=(0, 10))

        self.reporting_mode = tk.StringVar(value="allure_only")

        ttk.Label(reporting_frame, text="Allure HTML Report (Rich visual reporting)",
                 font=('', 9, 'normal')).pack(anchor=tk.W)

        # Allure-specific options
        allure_options_frame = ttk.Frame(reporting_frame)
        allure_options_frame.pack(fill=tk.X, pady=(5, 0))

        self.allure_results_dir = tk.StringVar(value="allure-results")

        ttk.Button(allure_options_frame, text="Open Last Report", command=self.open_allure_report).pack(side=tk.LEFT,
                                                                                                        padx=(0, 5))
        ttk.Button(allure_options_frame, text="Generate HTML", command=self.generate_allure_html_report_manual).pack(
            side=tk.LEFT, padx=(0, 5))
        ttk.Button(allure_options_frame, text="Save Report", command=self.save_allure_report).pack(side=tk.LEFT)

        # Preview table
        ttk.Label(main_frame, text="File Preview:").pack(anchor=tk.W)

        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        tree_frame.configure(height=200)  # Fixed height prevents expansion
        tree_frame.pack_propagate(False)  # Don't let children control size

        self.tree = ttk.Treeview(tree_frame, show='headings')

        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Progress and status
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var)
        self.progress_bar.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.status_var).pack(anchor=tk.W, pady=(5, 0))

        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Create Template", command=self.create_template).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Run Tests", command=self.show_execution_dialog).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Stop", command=self.stop_tests).pack(side=tk.LEFT)

    def browse_file(self):
        """Browse for Excel file"""
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if file_path:
            self.file_path_var.set(file_path)
            # Clear cached data
            self.all_sheets_data = {}
            # Auto-detect sheets when file is selected
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
                self.sheet_combo['values'] = self.sheet_names
                self.sheet_combo.current(0)
                self.current_sheet = self.sheet_names[0]
                self.sheet_frame.pack(fill=tk.X, pady=(0, 10), after=self.sheet_frame.master.winfo_children()[0])
                self.status_var.set(f"File has {len(self.sheet_names)} sheets. Select a sheet and click Load.")
            else:
                # Single sheet - hide selector
                self.sheet_frame.pack_forget()
                self.current_sheet = self.sheet_names[0] if self.sheet_names else None

        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file sheets: {str(e)}")

    def on_sheet_selected(self, event=None):
        """Handle sheet selection change"""
        selected = self.sheet_combo.get()
        if selected:
            self.current_sheet = selected
            self.status_var.set(f"Sheet '{selected}' selected. Click Load to preview.")

    def refresh_sheet(self):
        """Reload the currently selected sheet"""
        if self.current_sheet:
            self.load_sheet_data(self.current_sheet)

    def load_file(self):
        """Load and preview Excel file"""
        file_path = self.file_path_var.get()
        if not file_path:
            messagebox.showwarning("Warning", "Please select a file first")
            return

        # Detect sheets if not already done
        if not self.sheet_names:
            self.detect_sheets()

        # Load the selected sheet (or first sheet if only one)
        sheet_to_load = self.current_sheet if self.current_sheet else (self.sheet_names[0] if self.sheet_names else None)

        if sheet_to_load:
            self.load_sheet_data(sheet_to_load)
        else:
            messagebox.showerror("Error", "No sheets found in the Excel file")

    def show_execution_dialog(self):
        """Show dialog to choose execution scope before running tests"""
        file_path = self.file_path_var.get()
        if not file_path or not self.sheet_names:
            messagebox.showwarning("Warning", "Please load a file first")
            return

        # Single sheet file - go directly to execution
        if len(self.sheet_names) == 1:
            self.execute_tests([self.sheet_names[0]])
            return

        # Multiple sheets - show selection dialog
        dialog = tk.Toplevel(self.frame)
        dialog.title("Test Execution Options")
        dialog.geometry("550x650")
        dialog.transient(self.frame)
        dialog.grab_set()

        # Main container
        main_container = ttk.Frame(dialog, padding=20)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_container,
                 text="Select Sheets to Test",
                 font=('', 12, 'bold')).pack(pady=(0, 10))

        ttk.Label(main_container,
                 text=f"File: {os.path.basename(file_path)}",
                 foreground="gray").pack(pady=(0, 5))

        ttk.Label(main_container,
                 text=f"Total sheets: {len(self.sheet_names)}",
                 foreground="gray").pack(pady=(0, 20))

        # Execution scope selection
        scope_var = tk.StringVar(value="current")

        # Option 1: Current Sheet Only
        current_frame = ttk.Frame(main_container, relief=tk.RIDGE, padding=10)
        current_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Radiobutton(current_frame,
                       text="Current Sheet Only",
                       variable=scope_var,
                       value="current").pack(anchor=tk.W)

        current_label = ttk.Label(current_frame,
                                 text=f"   → Test only: {self.current_sheet}",
                                 foreground="blue")
        current_label.pack(anchor=tk.W, padx=(20, 0))

        # Option 2: All Sheets
        all_frame = ttk.Frame(main_container, relief=tk.RIDGE, padding=10)
        all_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Radiobutton(all_frame,
                       text="All Sheets in File",
                       variable=scope_var,
                       value="all").pack(anchor=tk.W)

        all_label = ttk.Label(all_frame,
                             text=f"   → Test all {len(self.sheet_names)} sheets",
                             foreground="blue")
        all_label.pack(anchor=tk.W, padx=(20, 0))

        # Option 3: Selected Sheets
        selected_frame = ttk.Frame(main_container, relief=tk.RIDGE, padding=10)
        selected_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Radiobutton(selected_frame,
                       text="Selected Sheets",
                       variable=scope_var,
                       value="selected").pack(anchor=tk.W)

        ttk.Label(selected_frame,
                 text="   → Choose specific sheets below:",
                 foreground="blue").pack(anchor=tk.W, padx=(20, 0))

        # Sheet selection listbox
        listbox_frame = ttk.Frame(selected_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=(20, 0), pady=(10, 0))

        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        sheet_listbox = tk.Listbox(listbox_frame,
                                   selectmode=tk.MULTIPLE,
                                   yscrollcommand=scrollbar.set,
                                   height=8)
        sheet_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=sheet_listbox.yview)

        # Add all sheets with test counts
        for sheet in self.sheet_names:
            if sheet in self.all_sheets_data:
                data = self.all_sheets_data[sheet]
            else:
                try:
                    data = self.excel_handler.load_excel(file_path, sheet_name=sheet)
                    self.all_sheets_data[sheet] = data
                except:
                    data = []
            sheet_listbox.insert(tk.END, f"{sheet}")

        # Quick selection buttons
        quick_btn_frame = ttk.Frame(selected_frame)
        quick_btn_frame.pack(fill=tk.X, padx=(20, 0), pady=(5, 0))

        def select_all():
            sheet_listbox.selection_set(0, tk.END)

        def clear_all():
            sheet_listbox.selection_clear(0, tk.END)

        ttk.Button(quick_btn_frame, text="Select All", command=select_all, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(quick_btn_frame, text="Clear All", command=clear_all, width=12).pack(side=tk.LEFT)

        # Separator
        ttk.Separator(main_container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20)

        # Action buttons
        button_frame = ttk.Frame(main_container)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        def cancel():
            dialog.destroy()

        def run():
            scope = scope_var.get()

            if scope == "current":
                sheets_to_test = [self.current_sheet]
            elif scope == "all":
                sheets_to_test = self.sheet_names
            elif scope == "selected":
                selected_indices = sheet_listbox.curselection()
                if not selected_indices:
                    messagebox.showwarning("No Selection",
                                         "Please select at least one sheet",
                                         parent=dialog)
                    return
                sheets_to_test = [self.sheet_names[i] for i in selected_indices]
            else:
                sheets_to_test = [self.current_sheet]

            dialog.destroy()
            self.execute_tests(sheets_to_test)

        ttk.Button(button_frame, text="Cancel", command=cancel, width=15).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Run Tests", command=run, width=15).pack(side=tk.RIGHT)

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

    def execute_tests(self, sheets_to_test):
        """Execute tests on selected sheets"""
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

        # Calculate total tests
        total_tests = 0
        for sheet in sheets_to_test:
            data = self.all_sheets_data[sheet]
            executable = len([row for row in data])
            total_tests += executable

        # Confirmation
        sheet_list = ", ".join(sheets_to_test[:3])
        if len(sheets_to_test) > 3:
            sheet_list += f" (+{len(sheets_to_test) - 3} more)"

        confirm_msg = (
            f"Ready to execute tests:\n\n"
            f"Sheets: {sheet_list}\n"
            f"Total sheets: {len(sheets_to_test)}\n"
            f"Total executable tests: {total_tests}\n\n"
            f"Proceed?"
        )

        if not messagebox.askyesno("Confirm Execution", confirm_msg):
            return

        # Start execution
        self.status_var.set(f"Executing {total_tests} tests across {len(sheets_to_test)} sheet(s)...")

        # Placeholder for actual test execution
        messagebox.showinfo("Test Execution",
                          f"Test execution would start here.\n\n"
                          f"Sheets: {len(sheets_to_test)}\n"
                          f"Tests: {total_tests}\n\n")

        result, message = validate_excel(self.all_sheets_data)
        if result:
            if not message:
                self.run_allure_tests_only(file_path, ", ".join(sheets_to_test))
            else:
                messagebox.showwarning("Warning - Sheet Format", f"Extra columns: {message}")
                self.run_allure_tests_only(file_path, ", ".join(sheets_to_test))
        else:
            messagebox.showerror("Error - Sheet Format", f"Missing columns: {message}")

    def run_allure_tests_only(self, file_path, sheets_to_test):
        """Pure Allure test execution via pytest"""
        try:
            # Set environment variables
            os.environ['SOAP_EXCEL_FILE'] = file_path
            os.environ['EXCEL_FILE_TEST_SHEETS'] = sheets_to_test
            os.environ['SOAP_EXECUTION_MODE'] = self.execution_mode.get()

            allure_dir = self.allure_results_dir.get()

            # Clear previous results
            self._clear_allure_results(allure_dir)

            # Find wrapper path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
            wrapper_path = project_root / "utils" / "allure_wrapper.py"

            if not wrapper_path.exists():
                messagebox.showerror("File Not Found", f"Allure wrapper not found at:\n{wrapper_path}")
                return

            cmd = [
                "python", "-m", "pytest",
                str(wrapper_path),
                "--alluredir", allure_dir,
                "--tb=short",
                "-v"
            ]

            # Add parallel execution if enabled
            if self.enable_parallel.get():
                worker_count = self.worker_count.get()
                if worker_count == "auto":
                    cmd.extend(["-n", "auto"])
                else:
                    cmd.extend(["-n", worker_count])

                # Use selected distribution strategy
                # cmd.extend(["--dist", self.dist_strategy.get()])

            def run_pytest():
                try:
                    self.current_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=str(project_root)
                    )
                    # Wait for process to complete and capture output
                    stdout, stderr = self.current_process.communicate()
                    result_code = self.current_process.returncode

                    if result_code == 0 or result_code == 1:
                        self.status_var.set("Allure tests completed successfully")
                        self.generate_allure_html_report(allure_dir)
                    else:
                        self.status_var.set(f"Tests completed with issues (exit code: {result_code})")

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
        """Show pytest execution output in a dialog"""
        output_window = tk.Toplevel(self.frame)
        output_window.title("Pytest Execution Output")
        output_window.geometry("800x600")

        notebook = ttk.Notebook(output_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Stdout tab
        stdout_frame = ttk.Frame(notebook)
        notebook.add(stdout_frame, text="Standard Output")
        stdout_text = scrolledtext.ScrolledText(stdout_frame)
        stdout_text.pack(fill=tk.BOTH, expand=True)
        stdout_text.insert("1.0", stdout)
        stdout_text.configure(state='disabled')

        # Stderr tab
        stderr_frame = ttk.Frame(notebook)
        notebook.add(stderr_frame, text="Error Output")
        stderr_text = scrolledtext.ScrolledText(stderr_frame)
        stderr_text.pack(fill=tk.BOTH, expand=True)
        stderr_text.insert("1.0", stderr)
        stderr_text.configure(state='disabled')

        ttk.Button(output_window, text="Close", command=output_window.destroy).pack(pady=5)

    def _clear_allure_results(self, allure_dir):
        """Clear previous Allure results before new run"""
        try:
            if os.path.exists(allure_dir):
                import shutil
                shutil.rmtree(allure_dir)
                print(f"DEBUG: Cleared previous results from {allure_dir}")
            os.makedirs(allure_dir, exist_ok=True)
        except Exception as e:
            print(f"WARNING: Could not clear allure results: {e}")

    def load_sheet_data(self, sheet_name):
        """Load data from a specific sheet with pagination support"""
        file_path = self.file_path_var.get()

        try:
            self.status_var.set(f"Loading sheet '{sheet_name}'...")
            self.frame.update()

            # Load data (use cache if available)
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
                    self.pagination_frame.pack(fill=tk.X, pady=(0, 10), before=self.tree.master)
                else:
                    self.pagination_frame.pack_forget()

                self.display_current_page()

                sheet_info = f"Sheet: '{sheet_name}'" if len(self.sheet_names) > 1 else ""
                status_msg = f"Loaded {total_rows} rows"
                if sheet_info:
                    status_msg = f"{sheet_info} | {status_msg}"

                if total_rows > self.rows_per_page:
                    status_msg += f" | Showing {self.rows_per_page} per page"

                executable = len([row for row in self.all_data
                                if str(row.get('Execute', '')).upper() in ['TRUE', '1.0']])
                status_msg += f" | {executable} executable tests"

                self.status_var.set(status_msg)
            else:
                self.status_var.set("Loaded 0 rows")
                self.pagination_frame.pack_forget()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sheet '{sheet_name}': {str(e)}")
            self.pagination_frame.pack_forget()

    def display_current_page(self):
        """Display the current page of data"""
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
                max_width = max(len(str(col)),
                               max((len(str(row.get(col, ''))) for row in self.all_data[:min(100, len(self.all_data))]), default=0))
                self.tree.column(col, width=min(max_width * 8, 300))

        for row in page_data:
            columns = self.tree['columns']
            values = [row.get(col, '') for col in columns]
            self.tree.insert('', 'end', values=values)

        self.page_label.config(text=f"Page {self.current_page + 1} of {self.total_pages} (Rows {start_idx + 1}-{end_idx} of {len(self.all_data)})")

    def on_rows_per_page_changed(self, event=None):
        """Handle rows per page selection change"""
        rows_per_page_str = self.rows_per_page_var.get()

        if rows_per_page_str == "All":
            self.rows_per_page = len(self.all_data)
            self.pagination_frame.pack_forget()
        else:
            self.rows_per_page = int(rows_per_page_str)
            if len(self.all_data) > 100:
                self.pagination_frame.pack(fill=tk.X, pady=(0, 10), before=self.tree.master)

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
                messagebox.showwarning("Invalid Page",
                                      f"Please enter a page number between 1 and {self.total_pages}")
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid page number")

    def create_template(self):
        """Create template Excel file"""
        file_path = filedialog.asksaveasfilename(
            title="Save Template",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )

        if file_path:
            try:
                create_excel_template(file_path)
                messagebox.showinfo("Success", f"Template created at {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create template: {str(e)}")

    def save_allure_report(self):
        """Save the Allure HTML report to a user-selected directory"""
        report_dir = "allure-report"

        # Check if report exists
        if not os.path.exists(report_dir):
            messagebox.showwarning("No Report Found",
                                 f"No Allure report found at {report_dir}.\nGenerate the HTML report first.")
            return

        # Check if index.html exists
        index_file = os.path.join(report_dir, "index.html")
        if not os.path.exists(index_file):
            messagebox.showwarning("Incomplete Report",
                                 f"Report directory exists but index.html not found.\nGenerate the HTML report first.")
            return

        # Ask user for destination directory
        destination = filedialog.askdirectory(
            title="Select Directory to Save Allure Report"
        )

        if not destination:
            return  # User cancelled

        try:
            import shutil
            from datetime import datetime

            # Create a timestamped folder name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_folder_name = f"allure-report_{timestamp}"
            destination_path = os.path.join(destination, report_folder_name)

            # Copy the entire report directory
            shutil.copytree(report_dir, destination_path)

            # Show success message
            messagebox.showinfo("Report Saved Successfully",
                               f"Allure report saved to:\n{destination_path}")

        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save report:\n{str(e)}")

    def open_allure_report(self):
        """Open Allure HTML report in browser"""
        report_dir = "allure-report"
        try:
            report_dir = "allure-report"
            allure_cmd = self._find_allure_executable()
            if not allure_cmd:
                messagebox.showerror("Allure Not Found", "Allure command line tool not found.")
                return
            cmd = f'"{allure_cmd}" open "{report_dir}"'
            subprocess.Popen(cmd, shell=True)
        except Exception as e:
            messagebox.showerror("Report Error", f"Error opening report: {str(e)}")

    def generate_allure_html_report_manual(self):
        """Manual trigger for HTML report generation"""
        allure_dir = self.allure_results_dir.get()
        if not os.path.exists(allure_dir):
            messagebox.showwarning("No Results",
                                   f"No Allure results found in {allure_dir}.\nRun tests with Allure reporting first.")
            return
        self.generate_allure_html_report(allure_dir)

    def generate_allure_html_report(self, allure_results_dir):
        """Generate Allure HTML report from results"""
        try:
            report_dir = "allure-report"
            allure_cmd = self._find_allure_executable()
            if not allure_cmd:
                messagebox.showerror("Allure Not Found", "Allure command line tool not found.")
                return

            cmd = f'"{allure_cmd}" generate "{allure_results_dir}" -o "{report_dir}" --clean'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

            if result.returncode == 0:
                self.status_var.set(f"Allure HTML report generated in {report_dir}")
                messagebox.showinfo("Report Generated", "Allure HTML report generated successfully!")
            else:
                messagebox.showerror("Report Generation Failed",
                                     f"Failed to generate HTML report.\n\n{result.stderr or result.stdout}")

        except Exception as e:
            messagebox.showerror("Report Error", f"Error generating report: {str(e)}")

    def _find_allure_executable(self):
        """Find Allure executable"""
        import shutil
        for cmd in ["allure", "allure.bat", "allure.cmd"]:
            if shutil.which(cmd):
                return cmd
        return None

    def stop_tests(self):
        """Stop running tests"""
        self.testing_active = False
        self.status_var.set("Stopping tests...")
        # Also terminate the subprocess if it's running
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
                self.status_var.set("Tests stopped by user")
            except:
                pass