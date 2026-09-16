"""
Validator Tab — SFF XML Validation GUI.

Layout:
  Top : DB connection panel (required before validation)
  Left: XML input panel (paste or upload)
  Right: Results panel (treeview + summary)
"""

import threading
import tkinter as tk
from tkinter import filedialog, ttk
import customtkinter as ctk
from xml.etree import ElementTree as ET

from gui.theme import FONTS, COLORS
from utils.iris_db import IrisDBClient, IRIS_JDBC_JAR_PATH
from utils.validator.xml_parser import XMLParser
from utils.validator.rules_validator import RulesValidator
from utils.validator.resource_provider import ResourceProvider


_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class ValidatorTab:

    def __init__(self, parent):
        self._parent = parent
        self._db: IrisDBClient | None = None
        self._resources: ResourceProvider | None = None
        self._spinner_idx = 0
        self._spinner_job = None

        self._all_results: list = []
        self._build_ui(parent)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self, parent):
        parent.configure(fg_color=COLORS["bg_main"])

        # Connection card (top)
        conn_card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=12)
        conn_card.pack(fill="x", padx=16, pady=(12, 6))
        self._build_connection_panel(conn_card)

        # Content area (bottom: XML left, results right)
        content = ctk.CTkFrame(parent, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        content.grid_columnconfigure(0, weight=2)
        content.grid_columnconfigure(1, weight=3)
        content.grid_rowconfigure(0, weight=1)

        xml_card = ctk.CTkFrame(content, fg_color=COLORS["bg_card"], corner_radius=12)
        xml_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._build_xml_panel(xml_card)

        results_card = ctk.CTkFrame(content, fg_color=COLORS["bg_card"], corner_radius=12)
        results_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._build_results_panel(results_card)

    # ── Connection panel ──────────────────────────────────────────────────────

    def _build_connection_panel(self, card):
        card.grid_columnconfigure(tuple(range(6)), weight=1)

        ctk.CTkLabel(card, text="DB Connection", font=FONTS["sub_header"],
                     text_color=COLORS["text"]).grid(
            row=0, column=0, columnspan=6, sticky="w", padx=14, pady=(10, 4))

        fields = [
            ("Host",      "afthibdsvr001.internal.npsff.ae", "host"),
            ("Port",      "1972",                             "port"),
            ("Namespace", "HIBDB",                            "namespace"),
            ("Username",  "superuser",                         "username"),
            ("Password",  "T3V9XKoie#4",                      "password"),
        ]
        self._conn_entries: dict[str, ctk.CTkEntry] = {}
        for col, (label, placeholder, key) in enumerate(fields):
            ctk.CTkLabel(card, text=label, font=FONTS["small"],
                         text_color=COLORS["text_sub"]).grid(
                row=1, column=col, padx=(14, 2), sticky="w")
            entry = ctk.CTkEntry(card, font=FONTS["main"], width=140,
                                 placeholder_text=placeholder,
                                 show="*" if key == "password" else "")
            entry.grid(row=2, column=col, padx=(14, 2), pady=(0, 10), sticky="ew")
            if placeholder:
                entry.insert(0, placeholder)
            self._conn_entries[key] = entry

        # Connect button + status in the last column
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.grid(row=1, column=5, rowspan=3, padx=14, pady=(0, 10), sticky="e")

        self._connect_btn = ctk.CTkButton(
            btn_frame, text="Connect", font=FONTS["button"],
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            width=110, command=self._on_connect)
        self._connect_btn.pack(pady=(4, 4))

        self._conn_status = ctk.CTkLabel(
            btn_frame, text="● Disconnected", font=FONTS["small"],
            text_color=COLORS["danger"])
        self._conn_status.pack()

        # JDBC JAR path row
        ctk.CTkLabel(card, text="JDBC JAR Path", font=FONTS["small"],
                     text_color=COLORS["text_sub"]).grid(
            row=3, column=0, padx=(14, 2), sticky="w", pady=(0, 10))
        self._jar_var = ctk.StringVar(value=IRIS_JDBC_JAR_PATH)
        ctk.CTkEntry(card, textvariable=self._jar_var, font=FONTS["main"]).grid(
            row=3, column=1, columnspan=3, padx=(2, 6), pady=(0, 10), sticky="ew")
        ctk.CTkButton(
            card, text="Browse…", width=90,
            command=self._browse_jar,
            font=FONTS["button"],
            fg_color="gray40", hover_color="gray30",
        ).grid(row=3, column=4, padx=(0, 2), pady=(0, 10), sticky="w")

    def _browse_jar(self):
        path = filedialog.askopenfilename(
            title="Select InterSystems JDBC JAR",
            filetypes=[("JAR files", "*.jar"), ("All files", "*.*")],
        )
        if path:
            self._jar_var.set(path)

    # ── XML input panel ───────────────────────────────────────────────────────

    def _build_xml_panel(self, card):
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)

        header_row = ctk.CTkFrame(card, fg_color="transparent")
        header_row.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        ctk.CTkLabel(header_row, text="XML Input", font=FONTS["sub_header"],
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(header_row, text="Upload File", font=FONTS["small"],
                      width=100, fg_color=COLORS["primary"],
                      hover_color=COLORS["primary_hover"],
                      command=self._upload_file).pack(side="right", padx=(4, 0))
        ctk.CTkButton(header_row, text="Clear", font=FONTS["small"],
                      width=70, fg_color="#555555", hover_color="#444444",
                      command=self._clear_xml).pack(side="right")

        self._xml_box = ctk.CTkTextbox(
            card, font=FONTS["code"], fg_color="#1e1e1e",
            text_color=COLORS["text"], wrap="none", corner_radius=8)
        self._xml_box.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 8))

        self._validate_btn = ctk.CTkButton(
            card, text="Validate XML", font=FONTS["button"], height=40,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            command=self._on_validate)
        self._validate_btn.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))

    # ── Results panel ─────────────────────────────────────────────────────────

    def _build_results_panel(self, card):
        card.grid_rowconfigure(2, weight=1)  # tree row expands
        card.grid_columnconfigure(0, weight=1)

        # Header row
        header_row = ctk.CTkFrame(card, fg_color="transparent")
        header_row.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        ctk.CTkLabel(header_row, text="Results", font=FONTS["sub_header"],
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(header_row, text="Clear Results", font=FONTS["small"],
                      width=110, fg_color="#555555", hover_color="#444444",
                      command=self._clear_results).pack(side="right")

        # Filter row
        filter_row = ctk.CTkFrame(card, fg_color="transparent")
        filter_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 4))
        ctk.CTkLabel(filter_row, text="Show:", font=FONTS["small"],
                     text_color=COLORS["text_sub"]).pack(side="left", padx=(0, 6))
        self._filter_var = ctk.StringVar(value="All")
        ctk.CTkSegmentedButton(
            filter_row, values=["All", "Active", "Inactive"],
            variable=self._filter_var,
            font=FONTS["small"],
            command=lambda _: self._apply_filter(),
        ).pack(side="left")

        # Tree frame
        tree_frame = ctk.CTkFrame(card, fg_color="transparent")
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 4))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        columns = ("rule_id", "status", "type", "message")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings",
                                   selectmode="browse")
        self._tree.heading("#0",      text="",        anchor="w")
        self._tree.heading("rule_id", text="Rule ID", anchor="center")
        self._tree.heading("status",  text="Status",  anchor="center")
        self._tree.heading("type",    text="Type",    anchor="center")
        self._tree.heading("message", text="Message", anchor="w")
        self._tree.column("#0",      width=30,  minwidth=30, stretch=False)
        self._tree.column("rule_id", width=70,  stretch=False, anchor="center")
        self._tree.column("status",  width=80,  stretch=False, anchor="center")
        self._tree.column("type",    width=80,  stretch=False, anchor="center")
        self._tree.column("message", width=500, stretch=True,  anchor="w")
        self._tree.tag_configure("ERROR",            foreground=COLORS["danger"])
        self._tree.tag_configure("WARNING",          foreground=COLORS["warning"])
        self._tree.tag_configure("PASS",             foreground=COLORS["success"])
        self._tree.tag_configure("INACTIVE_ERROR",   foreground="#888888")
        self._tree.tag_configure("INACTIVE_WARNING", foreground="#888888")
        self._tree.tag_configure("trace_step",       foreground="#606060")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal",  command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._summary_label = ctk.CTkLabel(
            card, text="", font=FONTS["small"], text_color=COLORS["text_sub"])
        self._summary_label.grid(row=3, column=0, sticky="w", padx=14, pady=(4, 10))

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_connect(self):
        self._connect_btn.configure(state="disabled")
        self._conn_status.configure(text="● Connecting…", text_color=COLORS["warning"])
        threading.Thread(target=self._connect_worker, daemon=True).start()

    def _connect_worker(self):
        try:
            if self._db and self._db.is_connected():
                self._db.disconnect()
            self._resources = None

            host = self._conn_entries["host"].get().strip()
            port = int(self._conn_entries["port"].get().strip() or "1972")
            ns = self._conn_entries["namespace"].get().strip()
            user = self._conn_entries["username"].get().strip()
            pwd = self._conn_entries["password"].get()

            db = IrisDBClient(host=host, port=port, namespace=ns,
                              username=user, password=pwd,
                              jar_path=self._jar_var.get().strip() or None)
            db.connect()
            self._db = db
            self._resources = ResourceProvider(db)
            self._parent.after(0, self._on_connected)
        except Exception as exc:
            self._parent.after(0, lambda: self._on_connect_failed(str(exc)))

    def _on_connected(self):
        host = self._conn_entries["host"].get().strip()
        self._conn_status.configure(
            text=f"● Connected to {host}", text_color=COLORS["success"])
        self._connect_btn.configure(state="normal", text="Reconnect")

    def _on_connect_failed(self, msg):
        self._conn_status.configure(
            text=f"● {msg[:60]}", text_color=COLORS["danger"])
        self._connect_btn.configure(state="normal", text="Connect")

    def _upload_file(self):
        path = filedialog.askopenfilename(
            title="Select XML file",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self._xml_box.delete("1.0", "end")
            self._xml_box.insert("1.0", content)
        except Exception as exc:
            self._set_summary(f"Could not read file: {exc}", COLORS["danger"])

    def _clear_xml(self):
        self._xml_box.delete("1.0", "end")

    def _clear_results(self):
        self._all_results = []
        for row in self._tree.get_children():
            self._tree.delete(row)
        self._summary_label.configure(text="")

    def _on_validate(self):
        if not self._db or not self._db.is_connected():
            self._set_summary("Connect to the database first.", COLORS["danger"])
            return

        xml_text = self._xml_box.get("1.0", "end").strip()
        if not xml_text:
            self._set_summary("Paste or upload an XML file first.", COLORS["danger"])
            return

        self._clear_results()
        self._validate_btn.configure(state="disabled")
        self._resources.clear()
        self._start_spinner()
        threading.Thread(
            target=self._validate_worker,
            args=(xml_text,),
            daemon=True,
        ).start()

    def _validate_worker(self, xml_text: str):
        try:
            model = XMLParser().parse(xml_text)
            results = RulesValidator().validate(model, self._resources)
            self._parent.after(0, lambda: self._on_validate_done(results))
        except ET.ParseError as exc:
            self._parent.after(0, lambda: self._on_parse_error(f"Malformed XML: {exc}"))
        except ValueError as exc:
            self._parent.after(0, lambda: self._on_parse_error(f"Schema/CommonTypes error: {exc}"))
        except Exception as exc:
            self._parent.after(0, lambda: self._on_parse_error(f"Unexpected error: {exc}"))

    def _on_validate_done(self, results):
        self._stop_spinner()
        self._validate_btn.configure(state="normal")
        self._all_results = results

        if not results:
            self._tree.insert("", "end", values=("—", "—", "PASS", "No issues found"),
                              tags=("PASS",))
            self._set_summary("Validation passed with 0 errors and 0 warnings.",
                              COLORS["success"])
            return

        self._apply_filter()

        active_errors   = sum(1 for r in results if r.type == "ERROR"   and r.is_active)
        active_warnings = sum(1 for r in results if r.type == "WARNING" and r.is_active)
        inactive_count  = sum(1 for r in results if not r.is_active)

        color = COLORS["danger"] if active_errors else COLORS["warning"] if active_warnings else COLORS["text_sub"]
        parts = [f"{active_errors} error(s)", f"{active_warnings} warning(s)"]
        if inactive_count:
            parts.append(f"{inactive_count} inactive")
        self._set_summary("  ·  ".join(parts), color)

    def _on_parse_error(self, msg: str):
        self._stop_spinner()
        self._validate_btn.configure(state="normal")
        self._tree.insert("", "end", values=("—", "—", "ERROR", msg), tags=("ERROR",))
        self._set_summary("Validation aborted — see error above.", COLORS["danger"])

    def _apply_filter(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        mode = self._filter_var.get()  # "All" | "Active" | "Inactive"
        for r in self._all_results:
            if mode == "Active"   and not r.is_active:
                continue
            if mode == "Inactive" and r.is_active:
                continue
            status = "active" if r.is_active else "inactive"
            tag    = r.type if r.is_active else f"INACTIVE_{r.type}"
            iid = self._tree.insert("", "end",
                                    values=(r.rule_id, status, r.type, r.message),
                                    tags=(tag,), open=False)
            for step in r.trace:
                self._tree.insert(iid, "end",
                                  values=("", "", "", step),
                                  tags=("trace_step",))


    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_summary(self, text: str, color: str):
        self._summary_label.configure(text=text, text_color=color)

    def _start_spinner(self):
        self._spinner_idx = 0
        self._animate_spinner()

    def _animate_spinner(self):
        frame = _SPINNER_FRAMES[self._spinner_idx % len(_SPINNER_FRAMES)]
        self._validate_btn.configure(text=f"{frame}  Validating…")
        self._spinner_idx += 1
        self._spinner_job = self._parent.after(80, self._animate_spinner)

    def _stop_spinner(self):
        if self._spinner_job:
            self._parent.after_cancel(self._spinner_job)
            self._spinner_job = None
        self._validate_btn.configure(text="Validate XML")
