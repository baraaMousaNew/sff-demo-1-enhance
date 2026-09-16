"""
Manual Testing Tab - Single API request testing with variable processing
"""

import base64
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import pathlib
from utils.api_client import APIClient
from utils.xml_utils import format_xml
from utils.variable_processor import VariableProcessor
from utils.error_validator import ErrorValidator
from datetime import datetime
from .theme import FONTS

class ManualTab:
    def __init__(self, parent):
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.pack(fill="both", expand=True)
        self.api_client = APIClient()
        self.variable_processor = VariableProcessor()
        self.error_validator = ErrorValidator()
        self._search_matches = []
        self._search_index = -1
        self._loaded_files = {}  # {filename: {"content": str, "path": str}}
        self._loaded_inner_files = {}  # {filename: {"content": str, "path": str}}
        self._last_saved_response = None
        self.create_widgets()

    def create_widgets(self):
        """Create manual testing widgets"""
        _canvas = tk.Canvas(self.frame, highlightthickness=0)
        _scrollbar = tk.Scrollbar(self.frame, orient="vertical", command=_canvas.yview)
        _canvas.configure(yscrollcommand=_scrollbar.set)
        _scrollbar.pack(side="right", fill="y")
        _canvas.pack(side="left", fill="both", expand=True)

        main_frame = ctk.CTkFrame(_canvas, fg_color="transparent")
        _win = _canvas.create_window((0, 0), window=main_frame, anchor="nw")

        def _sync(_=None):
            _canvas.configure(scrollregion=_canvas.bbox("all"))
            _canvas.itemconfig(_win,
                width=_canvas.winfo_width(),
                height=max(_canvas.winfo_height(), main_frame.winfo_reqheight()))

        main_frame.bind("<Configure>", _sync)
        _canvas.bind("<Configure>", _sync)
        _canvas.bind_all("<MouseWheel>",
            lambda e: _canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Left side - Input
        left_frame = ctk.CTkFrame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        # Environment selector + URL input
        env_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        env_frame.pack(fill="x", padx=10, pady=(10, 0))

        ctk.CTkLabel(env_frame, text="Environment:", font=FONTS["main_bold"]).pack(side="left", padx=(0, 5))
        self._url_options = self._load_url_options()
        env_labels = [o["label"] for o in self._url_options]
        self._env_var = tk.StringVar()
        self._env_combo = ctk.CTkComboBox(
            env_frame, variable=self._env_var, values=env_labels,
            width=260, font=FONTS["main"], command=self._on_env_selected,
        )
        self._env_combo.pack(side="left")
        if env_labels:
            self._env_combo.set(env_labels[0])

        ctk.CTkLabel(left_frame, text="Endpoint URL:", anchor="w", font=FONTS["main_bold"]).pack(anchor="w", padx=10, pady=(8, 0))
        self.url_var = tk.StringVar()
        self.url_entry = ctk.CTkEntry(left_frame, textvariable=self.url_var, placeholder_text="http://...", font=FONTS["main"])
        self.url_entry.pack(fill="x", padx=10, pady=(5, 10))

        if self._url_options:
            self.url_var.set(self._url_options[0]["url"])

        # SOAP Version + Custom Headers
        headers_label_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        headers_label_row.pack(fill="x", padx=10)
        ctk.CTkLabel(headers_label_row, text="Custom Headers (one per line: Header: Value):", anchor="w", font=FONTS["main_bold"]).pack(side="left")
        self._soap_version_var = tk.StringVar(value="SOAP 1.1")
        soap_combo = ctk.CTkComboBox(
            headers_label_row, variable=self._soap_version_var,
            values=["SOAP 1.1", "SOAP 1.2"], width=110, font=FONTS["main"],
            command=self._on_soap_version_selected
        )
        soap_combo.pack(side="right")
        ctk.CTkLabel(headers_label_row, text="SOAP:", font=FONTS["main_bold"]).pack(side="right", padx=(10, 4))
        self.headers_text = ctk.CTkTextbox(left_frame, height=60)
        self.headers_text.pack(fill="x", padx=10, pady=(5, 10))
        self.headers_text.insert("1.0", "SOAPAction: \nContent-Type: text/xml; charset=utf-8")

        # Variable Definitions
        ctk.CTkLabel(left_frame, text="Variable Definitions (var_name={{FUNCTION()}};...):", anchor="w", font=FONTS["main_bold"]).pack(anchor="w", padx=10)
        self.variables_text = ctk.CTkTextbox(left_frame, height=50)
        self.variables_text.pack(fill="x", padx=10, pady=(5, 10))
        self.variables_text.insert("1.0", "txn_ref={{CUSTOM.generate_transaction_ref()}};batch_id={{RUN_ID()}}")

        # Inner XML Files — Base64-encoded and injected at {{nested_xml}}
        ctk.CTkLabel(left_frame, text="Inner XML Files (Base64-encoded as {{nested_xml}}):", anchor="w", font=FONTS["main_bold"]).pack(anchor="w", padx=10)

        inner_files_outer = ctk.CTkFrame(left_frame)
        inner_files_outer.pack(fill="x", padx=10, pady=(5, 0))

        inner_scrollbar = tk.Scrollbar(inner_files_outer)
        inner_scrollbar.pack(side="right", fill="y")

        self._inner_files_listbox = tk.Listbox(
            inner_files_outer, selectmode=tk.EXTENDED, height=4,
            yscrollcommand=inner_scrollbar.set,
            bg="#2b2b2b", fg="white", selectbackground="#1f538d",
            activestyle="none", font=("Consolas", 11),
            relief="flat", bd=0, highlightthickness=0
        )
        self._inner_files_listbox.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        inner_scrollbar.config(command=self._inner_files_listbox.yview)
        self._inner_files_listbox.bind("<<ListboxSelect>>", lambda e: self._update_inner_file_buttons())

        inner_file_btn_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        inner_file_btn_row.pack(fill="x", padx=10, pady=(4, 5))
        ctk.CTkButton(inner_file_btn_row, text="Load Inner XML File(s)", command=self.load_inner_xml_file, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=(0, 5))
        self._select_all_inner_btn = ctk.CTkButton(inner_file_btn_row, text="Select All", command=self.select_all_inner_files, fg_color="gray", hover_color="#404040", font=FONTS["button"], state="disabled")
        self._select_all_inner_btn.pack(side="left", padx=(0, 5))
        self._view_inner_xml_btn = ctk.CTkButton(inner_file_btn_row, text="View XML", command=self.view_loaded_inner_xml, fg_color="gray", hover_color="#404040", font=FONTS["button"], state="disabled")
        self._view_inner_xml_btn.pack(side="left", padx=(0, 5))
        self._remove_inner_btn = ctk.CTkButton(inner_file_btn_row, text="Remove", command=self.remove_selected_inner_files, fg_color="#8b0000", hover_color="#5c0000", font=FONTS["button"], state="disabled")
        self._remove_inner_btn.pack(side="left")

        ctk.CTkLabel(left_frame, text="Inner XML (used when no files selected):", anchor="w", font=FONTS["main_bold"]).pack(anchor="w", padx=10, pady=(5, 0))
        self.inner_xml_body = ctk.CTkTextbox(left_frame, height=120)
        self.inner_xml_body.pack(fill="x", padx=10, pady=(5, 10))

        # Loaded XML Files
        ctk.CTkLabel(left_frame, text="Loaded XML Files:", anchor="w", font=FONTS["main_bold"]).pack(anchor="w", padx=10)

        files_outer = ctk.CTkFrame(left_frame)
        files_outer.pack(fill="x", padx=10, pady=(5, 0))

        scrollbar = tk.Scrollbar(files_outer)
        scrollbar.pack(side="right", fill="y")

        self._files_listbox = tk.Listbox(
            files_outer, selectmode=tk.EXTENDED, height=5,
            yscrollcommand=scrollbar.set,
            bg="#2b2b2b", fg="white", selectbackground="#1f538d",
            activestyle="none", font=("Consolas", 11),
            relief="flat", bd=0, highlightthickness=0
        )
        self._files_listbox.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        scrollbar.config(command=self._files_listbox.yview)
        self._files_listbox.bind("<<ListboxSelect>>", lambda e: self._update_file_buttons())

        # File management buttons
        file_btn_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        file_btn_row.pack(fill="x", padx=10, pady=(4, 5))
        ctk.CTkButton(file_btn_row, text="Load XML File(s)", command=self.load_xml_file, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=(0, 5))
        self._select_all_btn = ctk.CTkButton(file_btn_row, text="Select All", command=self.select_all_files, fg_color="gray", hover_color="#404040", font=FONTS["button"], state="disabled")
        self._select_all_btn.pack(side="left", padx=(0, 5))
        self._view_xml_btn = ctk.CTkButton(file_btn_row, text="View XML", command=self.view_loaded_xml, fg_color="gray", hover_color="#404040", font=FONTS["button"], state="disabled")
        self._view_xml_btn.pack(side="left", padx=(0, 5))
        self._remove_btn = ctk.CTkButton(file_btn_row, text="Remove", command=self.remove_selected_files, fg_color="#8b0000", hover_color="#5c0000", font=FONTS["button"], state="disabled")
        self._remove_btn.pack(side="left")

        # XML Body (fallback when no files selected)
        ctk.CTkLabel(left_frame, text="XML Body (used when no files selected):", anchor="w", font=FONTS["main_bold"]).pack(anchor="w", padx=10, pady=(5, 0))
        self.xml_body = ctk.CTkTextbox(left_frame)
        self.xml_body.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        # Buttons — row 1: send actions
        btn_row1 = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_row1.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkButton(btn_row1, text="Send Request", command=self.send_request, fg_color="green", hover_color="#006400", font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_row1, text="Send Request and Save", command=self.send_request_and_save, fg_color="#1f538d", hover_color="#163d6b", font=FONTS["button"]).pack(side="left")

        # Buttons — row 2: utility
        btn_row2 = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_row2.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(btn_row2, text="Format XML", command=self.format_xml, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_row2, text="Clear", command=self.clear_all, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left")

        # Right side - Response
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self.status_var = tk.StringVar(value="Ready")
        ctk.CTkLabel(right_frame, textvariable=self.status_var, anchor="w", text_color="cyan", font=FONTS["main"]).pack(anchor="w", padx=10, pady=(10, 0))

        resp_label_row = ctk.CTkFrame(right_frame, fg_color="transparent")
        resp_label_row.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(resp_label_row, text="Response:", anchor="w", font=FONTS["main_bold"]).pack(side="left")

        # Search bar
        search_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=(4, 0))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.search_response())
        self.search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var,
                                         placeholder_text="Search response...", font=FONTS["main"])
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.search_entry.bind("<Return>", lambda e: self.find_next())
        self.search_entry.bind("<Shift-Return>", lambda e: self.find_prev())
        ctk.CTkButton(search_frame, text="▲", width=30, command=self.find_prev,
                      fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=(0, 2))
        ctk.CTkButton(search_frame, text="▼", width=30, command=self.find_next,
                      fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=(0, 6))
        self.search_count_var = tk.StringVar(value="")
        ctk.CTkLabel(search_frame, textvariable=self.search_count_var,
                     font=FONTS["main"], text_color="gray").pack(side="left")

        self.response_text = ctk.CTkTextbox(right_frame)
        self.response_text.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        resp_buttons = ctk.CTkFrame(right_frame, fg_color="transparent")
        resp_buttons.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkButton(resp_buttons, text="Decode Base64", command=self.decode_response, fg_color="#1f538d", font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(resp_buttons, text="Copy Response", command=self.copy_response, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=(0, 5))
        self._view_response_btn = ctk.CTkButton(resp_buttons, text="View Last Response", command=self.view_last_response, fg_color="#1f538d", hover_color="#163d6b", font=FONTS["button"], state="disabled")
        self._view_response_btn.pack(side="left")

        decode_check_row = ctk.CTkFrame(right_frame, fg_color="transparent")
        decode_check_row.pack(fill="x", padx=10, pady=(0, 10))
        self._auto_decode_error_report = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(decode_check_row, text="Auto-decode errorReport if found in response",
                        variable=self._auto_decode_error_report, font=FONTS["main"]).pack(side="left")

    # ── File list helpers ──────────────────────────────────────────────────────

    def _update_file_buttons(self):
        has_files = self._files_listbox.size() > 0
        has_selection = len(self._files_listbox.curselection()) > 0
        self._select_all_btn.configure(state="normal" if has_files else "disabled")
        self._remove_btn.configure(state="normal" if has_files else "disabled")
        self._view_xml_btn.configure(state="normal" if has_selection else "disabled")

    def _get_selected_filenames(self):
        return [self._files_listbox.get(i) for i in self._files_listbox.curselection()]

    def select_all_files(self):
        self._files_listbox.select_set(0, tk.END)
        self._update_file_buttons()

    def remove_selected_files(self):
        for i in reversed(self._files_listbox.curselection()):
            self._loaded_files.pop(self._files_listbox.get(i), None)
            self._files_listbox.delete(i)
        self._update_file_buttons()

    # ── Inner file list helpers ────────────────────────────────────────────────

    def _update_inner_file_buttons(self):
        has_files = self._inner_files_listbox.size() > 0
        has_selection = len(self._inner_files_listbox.curselection()) > 0
        self._select_all_inner_btn.configure(state="normal" if has_files else "disabled")
        self._remove_inner_btn.configure(state="normal" if has_files else "disabled")
        self._view_inner_xml_btn.configure(state="normal" if has_selection else "disabled")

    def _get_selected_inner_filenames(self):
        return [self._inner_files_listbox.get(i) for i in self._inner_files_listbox.curselection()]

    def select_all_inner_files(self):
        self._inner_files_listbox.select_set(0, tk.END)
        self._update_inner_file_buttons()

    def remove_selected_inner_files(self):
        for i in reversed(self._inner_files_listbox.curselection()):
            self._loaded_inner_files.pop(self._inner_files_listbox.get(i), None)
            self._inner_files_listbox.delete(i)
        self._update_inner_file_buttons()

    def load_inner_xml_file(self):
        file_paths = filedialog.askopenfilenames(
            title="Open Inner XML File(s)",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        for file_path in file_paths:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                name = pathlib.Path(file_path).name
                self._loaded_inner_files[name] = {"content": content, "path": file_path}
                if name not in self._inner_files_listbox.get(0, tk.END):
                    self._inner_files_listbox.insert(tk.END, name)
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to load {pathlib.Path(file_path).name}:\n{str(e)}")
        self._update_inner_file_buttons()

    def view_loaded_inner_xml(self):
        selected = self._get_selected_inner_filenames()
        if not selected:
            return
        name = selected[0]
        content = self._loaded_inner_files[name]["content"]
        window = ctk.CTkToplevel(self.frame)
        window.title(f"Inner XML Content — {name}")
        window.geometry("900x700")
        txt = ctk.CTkTextbox(window, font=FONTS["main"])
        txt.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        txt.insert("1.0", content)
        txt.configure(state="disabled")
        ctk.CTkButton(window, text="Close", command=window.destroy, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(pady=(0, 10))

    def load_xml_file(self):
        file_paths = filedialog.askopenfilenames(
            title="Open XML File(s)",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        for file_path in file_paths:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                name = pathlib.Path(file_path).name
                self._loaded_files[name] = {"content": content, "path": file_path}
                if name not in self._files_listbox.get(0, tk.END):
                    self._files_listbox.insert(tk.END, name)
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to load {pathlib.Path(file_path).name}:\n{str(e)}")
        self._update_file_buttons()

    def view_loaded_xml(self):
        selected = self._get_selected_filenames()
        if not selected:
            return
        name = selected[0]
        content = self._loaded_files[name]["content"]
        window = ctk.CTkToplevel(self.frame)
        window.title(f"XML Content — {name}")
        window.geometry("900x700")
        txt = ctk.CTkTextbox(window, font=FONTS["main"])
        txt.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        txt.insert("1.0", content)
        txt.configure(state="disabled")
        ctk.CTkButton(window, text="Close", command=window.destroy, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(pady=(0, 10))

    # ── Search ─────────────────────────────────────────────────────────────────

    def search_response(self):
        txt = self.response_text._textbox
        txt.tag_remove("search_highlight", "1.0", "end")
        txt.tag_remove("search_current", "1.0", "end")
        self._search_matches = []
        self._search_index = -1

        query = self.search_var.get()
        if not query:
            self.search_count_var.set("")
            return

        start = "1.0"
        while True:
            pos = txt.search(query, start, nocase=True, stopindex="end")
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            txt.tag_add("search_highlight", pos, end)
            self._search_matches.append(pos)
            start = end

        txt.tag_config("search_highlight", background="#b5890a", foreground="white")
        txt.tag_config("search_current", background="#e05c00", foreground="white")

        count = len(self._search_matches)
        if count:
            self._search_index = 0
            self._highlight_current()
        else:
            self.search_count_var.set("0 found")

    def _highlight_current(self):
        txt = self.response_text._textbox
        txt.tag_remove("search_current", "1.0", "end")
        if not self._search_matches:
            return
        pos = self._search_matches[self._search_index]
        end = f"{pos}+{len(self.search_var.get())}c"
        txt.tag_add("search_current", pos, end)
        txt.see(pos)
        self.search_count_var.set(f"{self._search_index + 1}/{len(self._search_matches)}")

    def find_next(self):
        if not self._search_matches:
            return
        self._search_index = (self._search_index + 1) % len(self._search_matches)
        self._highlight_current()

    def find_prev(self):
        if not self._search_matches:
            return
        self._search_index = (self._search_index - 1) % len(self._search_matches)
        self._highlight_current()

    # ── URL / env helpers ──────────────────────────────────────────────────────

    def _load_url_options(self) -> list:
        try:
            import json
            path = pathlib.Path(__file__).parent.parent / "resources" / "system_defaults.json"
            with open(path, "r") as f:
                data = json.load(f)
            options = []
            for system, envs in data.items():
                for env_name, url in envs.items():
                    options.append({"label": f"{system}  ›  {env_name}", "url": url})
            return options
        except Exception:
            return []

    def _on_env_selected(self, label: str):
        for option in self._url_options:
            if option["label"] == label:
                self.url_var.set(option["url"])
                break

    def _on_soap_version_selected(self, version: str):
        content_type = (
            "application/soap+xml; charset=utf-8" if version == "SOAP 1.2"
            else "text/xml; charset=utf-8"
        )
        lines = self.headers_text.get("1.0", "end").strip().split("\n")
        updated = []
        replaced = False
        for line in lines:
            if line.strip().lower().startswith("content-type:"):
                updated.append(f"Content-Type: {content_type}")
                replaced = True
            else:
                updated.append(line)
        if not replaced:
            updated.append(f"Content-Type: {content_type}")
        self.headers_text.delete("1.0", "end")
        self.headers_text.insert("1.0", "\n".join(updated))

    # ── Request execution ──────────────────────────────────────────────────────

    def _execute_request(self, xml_content=None, inner_xml_content=None):
        """Run the request and return (status_text, full_content). Raises on any error."""
        url = self.url_entry.get().strip()
        if xml_content is None:
            xml_content = self.xml_body.get("1.0", "end").strip()

        if not url or not xml_content:
            raise ValueError("Please fill URL and XML body (or load an XML file)")

        soap_action = None
        content_type = None
        for line in self.headers_text.get("1.0", "end").strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key_lower = key.strip().lower()
                if key_lower == 'soapaction':
                    soap_action = value.strip()
                elif key_lower == 'content-type':
                    content_type = value.strip()

        if inner_xml_content is None:
            inner_xml_content = self.inner_xml_body.get("1.0", "end").strip()
        if inner_xml_content:
            encoded_inner = base64.b64encode(inner_xml_content.encode("utf-8")).decode("utf-8")
            xml_content = xml_content.replace("{{nested_xml}}", encoded_inner)

        self.variable_processor.set_batch_context()
        self.variable_processor.set_test_context(1)
        variables_definition = self.variables_text.get("1.0", "end").strip()
        mock_excel_data = {}
        if variables_definition:
            mock_excel_data['Variable_Definitions'] = variables_definition

        processed_xml = self.variable_processor.process_variables(xml_content, mock_excel_data)
        response = self.api_client.send_request(url=url, xml_body=processed_xml, soap_action=soap_action, content_type=content_type, debug=True)

        status_text = f"Status: {response['status_code']} | Time: {response['response_time']:.2f}ms"

        debug_info = f"=== PROCESSED XML SENT ===\n{processed_xml}\n\n=== REQUEST HEADERS ===\n"
        for key, value in response.get('request_headers', {}).items():
            debug_info += f"{key}: {value}\n"
        debug_info += "\n=== RESPONSE HEADERS ===\n"
        for key, value in response.get('response_headers', {}).items():
            debug_info += f"{key}: {value}\n"
        debug_info += "\n=== RESPONSE BODY ===\n"

        return status_text, debug_info + response['content']

    def _build_error_report_section(self, content: str) -> str:
        """Return decoded errorReport as a formatted string, or empty string if not found/disabled."""
        if not self._auto_decode_error_report.get():
            return ""
        try:
            base64_report = self.error_validator.extract_error_report(content)
            if not base64_report:
                return ""
            rows = self.error_validator.decode_and_parse_error_report(base64_report)
            if not rows:
                return ""
            lines = ["\n\n=== DECODED ERROR REPORT ==="]
            for i, row in enumerate(rows, 1):
                lines.append(f"\n[{i}]")
                for col, val in row.items():
                    lines.append(f"  {col}: {val}")
            return "\n".join(lines)
        except Exception as e:
            return f"\n\n=== ERROR REPORT DECODE FAILED ===\n{str(e)}"

    def _maybe_append_error_report(self, content: str):
        section = self._build_error_report_section(content)
        if section:
            self.response_text.insert("end", section)

    def send_request(self):
        selected = self._get_selected_filenames()
        selected_inner = self._get_selected_inner_filenames()

        if len(selected) > 1 or len(selected_inner) > 1:
            messagebox.showwarning(
                "Multiple Files Selected",
                "Cannot execute multiple requests with 'Send Request'.\n\n"
                "Please use 'Send Request and Save' to execute multiple files."
            )
            return

        xml_content = self._loaded_files[selected[0]]["content"] if selected else None
        inner_xml_content = self._loaded_inner_files[selected_inner[0]]["content"] if selected_inner else None

        self.status_var.set("Processing variables and sending request...")
        self.frame.update()
        try:
            status_text, content = self._execute_request(xml_content, inner_xml_content)
            self.status_var.set(status_text)
            self.response_text.delete("1.0", "end")
            self._search_matches = []
            self._search_index = -1
            self.search_count_var.set("")
            self.response_text.insert("1.0", content)
            self._maybe_append_error_report(content)
        except ValueError as e:
            self.status_var.set("Ready")
            messagebox.showerror("Error", str(e))
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            messagebox.showerror("Request Error", str(e))

    def send_request_and_save(self):
        selected = self._get_selected_filenames()
        selected_inner = self._get_selected_inner_filenames()

        if selected_inner:
            self._send_inner_batch_and_save(selected_inner, selected)
        elif selected:
            self._send_body_batch_and_save(selected)
        else:
            self._send_single_and_save(None)

    def _send_inner_batch_and_save(self, selected_inner, selected_body):
        """Iterate over inner XML files, injecting each into the XML body template."""
        body_content = self._loaded_files[selected_body[0]]["content"] if selected_body else None

        output_folder = filedialog.askdirectory(title="Select Output Folder for Responses")
        if not output_folder:
            return
        output_folder = pathlib.Path(output_folder)

        errors = []
        for inner_name in selected_inner:
            inner_xml_content = self._loaded_inner_files[inner_name]["content"]
            out_path = output_folder / f"{pathlib.Path(inner_name).stem}_response.txt"

            self.status_var.set(f"Sending with inner XML: {inner_name}...")
            self.frame.update()

            try:
                status_text, content = self._execute_request(body_content, inner_xml_content)
                error_report_section = self._build_error_report_section(content)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(f"=== SAVED AT {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                    f.write(f"URL: {self.url_entry.get().strip()}\n")
                    f.write(f"Inner XML File: {inner_name}\n")
                    f.write(f"Status: {status_text}\n\n")
                    f.write(content)
                    f.write(error_report_section)
                self._last_saved_response = content + error_report_section
                self._view_response_btn.configure(state="normal")
            except Exception as e:
                errors.append(f"{inner_name}: {str(e)}")

        if errors:
            failed_log = output_folder / "failed_requests.txt"
            with open(failed_log, "w", encoding="utf-8") as f:
                f.write(f"=== FAILED REQUESTS — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
                for entry in errors:
                    f.write(f"{entry}\n")
            self.status_var.set(f"Completed with {len(errors)} error(s) — see failed_requests.txt")
            messagebox.showerror("Some Requests Failed", f"{len(errors)} request(s) failed.\nSee failed_requests.txt in the output folder.")
        else:
            self.status_var.set(f"Done — {len(selected_inner)} response(s) saved to {output_folder.name}")
            messagebox.showinfo("Done", f"{len(selected_inner)} response(s) saved to:\n{output_folder}")

    def _send_body_batch_and_save(self, selected):
        """Iterate over XML body files (original batch behaviour)."""
        output_folder = filedialog.askdirectory(title="Select Output Folder for Responses")
        if not output_folder:
            return
        output_folder = pathlib.Path(output_folder)

        errors = []
        for name in selected:
            xml_content = self._loaded_files[name]["content"]
            out_path = output_folder / f"{pathlib.Path(name).stem}_response.txt"

            self.status_var.set(f"Sending: {name}...")
            self.frame.update()

            try:
                status_text, content = self._execute_request(xml_content)
                error_report_section = self._build_error_report_section(content)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(f"=== SAVED AT {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                    f.write(f"URL: {self.url_entry.get().strip()}\n")
                    f.write(f"XML File: {name}\n")
                    f.write(f"Status: {status_text}\n\n")
                    f.write(content)
                    f.write(error_report_section)
                self._last_saved_response = content + error_report_section
                self._view_response_btn.configure(state="normal")
            except Exception as e:
                errors.append(f"{name}: {str(e)}")

        if errors:
            failed_log = output_folder / "failed_requests.txt"
            with open(failed_log, "w", encoding="utf-8") as f:
                f.write(f"=== FAILED REQUESTS — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
                for entry in errors:
                    f.write(f"{entry}\n")
            self.status_var.set(f"Completed with {len(errors)} error(s) — see failed_requests.txt")
            messagebox.showerror("Some Requests Failed", f"{len(errors)} request(s) failed.\nSee failed_requests.txt in the output folder.")
        else:
            self.status_var.set(f"Done — {len(selected)} response(s) saved to {output_folder.name}")
            messagebox.showinfo("Done", f"{len(selected)} response(s) saved to:\n{output_folder}")

    def _send_single_and_save(self, xml_content):
        """Original save behavior when no files are loaded/selected."""
        self.status_var.set("Processing variables and sending request...")
        self.frame.update()
        try:
            status_text, content = self._execute_request(xml_content)
        except ValueError as e:
            self.status_var.set("Ready")
            messagebox.showerror("Error", str(e))
            return
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            messagebox.showerror("Request Error", str(e))
            return

        self.status_var.set(status_text)

        file_path = filedialog.asksaveasfilename(
            title="Save Request and Response",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            error_report_section = self._build_error_report_section(content)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"=== SAVED AT {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                f.write(f"URL: {self.url_entry.get().strip()}\n")
                f.write(f"Status: {status_text}\n\n")
                f.write(content)
                f.write(error_report_section)
            self._last_saved_response = content + error_report_section
            self._view_response_btn.configure(state="normal")
            messagebox.showinfo("Saved", f"Request and response saved to:\n{file_path}\n\nClick 'View Last Response' to inspect it.")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def view_last_response(self):
        if not self._last_saved_response:
            return
        self.response_text.delete("1.0", "end")
        self._search_matches = []
        self._search_index = -1
        self.search_count_var.set("")
        self.response_text.insert("1.0", self._last_saved_response)

    # ── Utility ────────────────────────────────────────────────────────────────

    def clear_all(self):
        if self._url_options:
            self._env_combo.set(self._url_options[0]["label"])
            self.url_var.set(self._url_options[0]["url"])
        else:
            self.url_var.set("")
        self._loaded_inner_files.clear()
        self._inner_files_listbox.delete(0, tk.END)
        self._update_inner_file_buttons()
        self._loaded_files.clear()
        self._files_listbox.delete(0, tk.END)
        self._update_file_buttons()
        self._last_saved_response = None
        self._view_response_btn.configure(state="disabled")
        self.headers_text.delete("1.0", "end")
        self.headers_text.insert("1.0", "SOAPAction: \nContent-Type: text/xml; charset=utf-8")
        self.variables_text.delete("1.0", "end")
        self.variables_text.insert("1.0", "txn_ref={{CUSTOM.generate_transaction_ref()}};batch_id={{RUN_ID()}}")
        self.xml_body.delete("1.0", "end")
        self.inner_xml_body.delete("1.0", "end")
        self.response_text.delete("1.0", "end")
        self.status_var.set("Ready")

    def show_processed_xml_window(self, original_xml, processed_xml):
        window = ctk.CTkToplevel(self.frame)
        window.title("Variable Processing Results")
        window.geometry("1200x700")

        left_frame = ctk.CTkFrame(window)
        left_frame.pack(side="left", fill="both", expand=True, padx=(10, 5), pady=10)

        right_frame = ctk.CTkFrame(window)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 10), pady=10)

        ctk.CTkLabel(left_frame, text="Original XML (with variables):", anchor="w").pack(anchor="w", padx=10, pady=5)
        original_text = ctk.CTkTextbox(left_frame)
        original_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        original_text.insert("1.0", original_xml)
        original_text.configure(state='disabled')

        ctk.CTkLabel(right_frame, text="Processed XML (variables replaced):", anchor="w").pack(anchor="w", padx=10, pady=5)
        processed_text = ctk.CTkTextbox(right_frame)
        processed_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        processed_text.insert("1.0", processed_xml)
        processed_text.configure(state='disabled')

        button_frame = ctk.CTkFrame(window, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=(0, 10))

        def copy_processed():
            window.clipboard_clear()
            window.clipboard_append(processed_xml)
            messagebox.showinfo("Copied", "Processed XML copied to clipboard")

        def use_processed():
            self.xml_body.delete("1.0", "end")
            self.xml_body.insert("1.0", processed_xml)
            window.destroy()
            messagebox.showinfo("Updated", "XML body updated with processed version")

        def process_again():
            try:
                self.variable_processor.set_batch_context()
                self.variable_processor.set_test_context(1)
                new_processed = self.variable_processor.process_variables(original_xml)
                processed_text.configure(state='normal')
                processed_text.delete("1.0", "end")
                processed_text.insert("1.0", new_processed)
                processed_text.configure(state='disabled')
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reprocess: {str(e)}")

        ctk.CTkButton(button_frame, text="Copy Processed", command=copy_processed).pack(side="left", padx=(0, 5))
        ctk.CTkButton(button_frame, text="Use Processed", command=use_processed, fg_color="green", hover_color="#006400").pack(side="left", padx=(0, 5))
        ctk.CTkButton(button_frame, text="Process Again", command=process_again, fg_color="orange", hover_color="#b87400").pack(side="left", padx=(0, 5))
        ctk.CTkButton(button_frame, text="Close", command=window.destroy, fg_color="gray", hover_color="#404040").pack(side="right")

    def format_xml(self):
        xml_content = self.xml_body.get("1.0", "end").strip()
        if xml_content:
            formatted = format_xml(xml_content)
            if formatted:
                self.xml_body.delete("1.0", "end")
                self.xml_body.insert("1.0", formatted)

    def copy_response(self):
        content = self.response_text.get("1.0", "end").strip()
        self.frame.clipboard_clear()
        self.frame.clipboard_append(content)

    def decode_response(self):
        decode_window = ctk.CTkToplevel(self.frame)
        decode_window.title("Decode Base64 Content")
        decode_window.geometry("700x600")

        ctk.CTkLabel(decode_window, text="Paste the Base64 content you want to decode:", anchor="w").pack(anchor="w", padx=10, pady=(10, 5))

        input_frame = ctk.CTkFrame(decode_window)
        input_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        base64_input = ctk.CTkTextbox(input_frame, height=100)
        base64_input.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(decode_window, text="Decoded content will appear below:", anchor="w").pack(anchor="w", padx=10)

        decoded_output = ctk.CTkTextbox(decode_window)
        decoded_output.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        def perform_decode():
            base64_content = base64_input.get("1.0", "end").strip()
            if not base64_content:
                messagebox.showwarning("Warning", "Please paste Base64 content to decode")
                return
            try:
                from utils.xml_utils import decode_base64_content_manually
                decoded_result = decode_base64_content_manually(base64_content)
                decoded_output.delete("1.0", "end")
                decoded_output.insert("1.0", decoded_result)
            except Exception as e:
                messagebox.showerror("Decode Error", f"Failed to decode: {str(e)}")

        def save_decoded():
            content = decoded_output.get("1.0", "end").strip()
            if content:
                file_path = filedialog.asksaveasfilename(
                    title="Save Decoded Content",
                    defaultextension=".xlsx",
                    filetypes=[("Excel files", "*.xlsx"), ("Text files", "*.txt"), ("All files", "*.*")]
                )
                if file_path:
                    try:
                        if file_path.endswith('.xlsx'):
                            import pandas as pd
                            df = pd.DataFrame({
                                'Decoded_Content': [content],
                                'Timestamp': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                            })
                            df.to_excel(file_path, index=False)
                        else:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                        messagebox.showinfo("Success", f"Content saved to {file_path}")
                    except Exception as e:
                        messagebox.showerror("Save Error", str(e))

        button_frame = ctk.CTkFrame(decode_window, fg_color="transparent")
        button_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkButton(button_frame, text="Decode", command=perform_decode).pack(side="left", padx=(0, 5))
        ctk.CTkButton(button_frame, text="Save Decoded", command=save_decoded, fg_color="green", hover_color="#006400").pack(side="left", padx=(0, 5))
        ctk.CTkButton(button_frame, text="Close", command=decode_window.destroy, fg_color="gray", hover_color="#404040").pack(side="right")
