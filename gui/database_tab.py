"""
Database Tab - Connect to InterSystems IRIS and execute SQL queries.
Uses IrisDBClient (utils/iris_db.py) via JDBC / jaydebeapi.
"""

import threading
import csv
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk

from utils.iris_db import IrisDBClient, IRIS_JDBC_JAR_PATH
from .theme import FONTS, COLORS

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
_STATUS_DISCONNECTED = "● Disconnected"
_STATUS_CONNECTING   = "◌ Connecting…"
_STATUS_CONNECTED    = "● Connected"
_STATUS_ERROR        = "● Error"

_COLOR_DISCONNECTED = "#aaaaaa"
_COLOR_CONNECTING   = "#ffc107"
_COLOR_CONNECTED    = "#2cc985"
_COLOR_ERROR        = "#ff4d4d"


class DatabaseTab:
    """
    Database tab that provides a full-featured IRIS DB query interface:
      - Connection settings panel  (host, port, namespace, user, password, JAR)
      - Connect / Disconnect buttons with live status pill
      - SQL editor  (multi-line)
      - Execute Query (SELECT) and Execute Statement (INSERT/UPDATE/DELETE)
      - Results grid (ttk.Treeview) with row count
      - Export results to CSV
    """

    # Spinner frames — braille rolling dots give a smooth feel
    _SPINNER_FRAMES = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]

    def __init__(self, parent):
        self.client: IrisDBClient | None = None
        self._lock = threading.Lock()
        self._schema_data: dict = {}

        # Spinner state
        self._spinner_job = None
        self._spinner_idx = 0
        self._spinner_label = ""

        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.pack(fill="both", expand=True)

        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # UI Construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Assemble the full tab layout."""
        # ── Top row: connection card + status ────────────────────────────────
        self._build_connection_panel()

        # ── Content area: schema browser (left) + editor/results (right) ─────
        content_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True)

        self._build_schema_browser(content_frame)

        right = ctk.CTkFrame(content_frame, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        self._build_query_panel(right)
        self._build_results_panel(right)

    # --- Schema browser panel ------------------------------------------------

    def _build_schema_browser(self, parent):
        browser_card = ctk.CTkFrame(parent, corner_radius=12, width=230)
        browser_card.pack(side="left", fill="y", padx=(12, 0), pady=6)
        browser_card.pack_propagate(False)

        # Header row
        hdr = ctk.CTkFrame(browser_card, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=(10, 4))

        ctk.CTkLabel(
            hdr, text="🗂  Schema Browser",
            font=FONTS["sub_header"], anchor="w",
        ).pack(side="left")

        self.refresh_schema_btn = ctk.CTkButton(
            hdr, text="⟳", width=34,
            command=self._refresh_schema_browser,
            font=FONTS["button"],
            fg_color="gray40", hover_color="gray30",
            state="disabled",
        )
        self.refresh_schema_btn.pack(side="right")

        # Filter box
        self.schema_filter_var = ctk.StringVar()
        self.schema_filter_var.trace_add("write", lambda *_: self._apply_schema_filter())
        ctk.CTkEntry(
            browser_card,
            textvariable=self.schema_filter_var,
            placeholder_text="Filter schemas / tables…",
            font=FONTS["small"],
            height=28,
        ).pack(fill="x", padx=10, pady=(0, 6))

        # Treeview
        tree_frame = ctk.CTkFrame(browser_card, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        v_scroll.pack(side="right", fill="y")

        self.schema_tree = ttk.Treeview(
            tree_frame,
            yscrollcommand=v_scroll.set,
            selectmode="browse",
            show="tree",
        )
        self.schema_tree.pack(fill="both", expand=True)
        v_scroll.config(command=self.schema_tree.yview)

        self.schema_tree.bind("<Double-1>", self._on_table_double_click)

    def _refresh_schema_browser(self):
        """Load schemas and tables from the DB in a background thread."""
        with self._lock:
            if not self.client or not self.client.is_connected():
                return
        self.refresh_schema_btn.configure(state="disabled")
        threading.Thread(target=self._do_refresh_schema_browser, daemon=True).start()

    def _do_refresh_schema_browser(self):
        try:
            with self._lock:
                client = self.client
            data = client.get_schemas_and_tables()
            self.frame.after(0, lambda: self._populate_schema_browser(data))
        except Exception as exc:
            self.frame.after(0, lambda: self._show_message(
                f"Schema browser error: {exc}", color=COLORS["danger"]
            ))
        finally:
            self.frame.after(0, lambda: self.refresh_schema_btn.configure(state="normal"))

    def _populate_schema_browser(self, data: dict):
        """Store fresh schema data and render with the current filter applied."""
        self._schema_data = data
        self._apply_schema_filter()

    def _apply_schema_filter(self):
        """Re-render the schema tree filtered by the current search text."""
        query = self.schema_filter_var.get().strip().lower()
        for item in self.schema_tree.get_children():
            self.schema_tree.delete(item)
        for schema in sorted(self._schema_data.keys()):
            tables = self._schema_data[schema]
            if query:
                matching_tables = [t for t in tables if query in t.lower() or query in schema.lower()]
                if not matching_tables:
                    continue
                schema_matches = query in schema.lower()
                display_tables = tables if schema_matches else matching_tables
            else:
                display_tables = tables
            schema_node = self.schema_tree.insert(
                "", "end", text=f"📁 {schema}", open=bool(query)
            )
            for table in display_tables:
                self.schema_tree.insert(
                    schema_node, "end",
                    text=f"  {table}",
                    values=(f"{schema}.{table}",),
                )

    def _on_table_double_click(self, event):
        """Insert the selected table's full name (Schema.Table) at the SQL editor cursor."""
        item = self.schema_tree.focus()
        if not item:
            return
        values = self.schema_tree.item(item, "values")
        if not values:
            return  # clicked a schema node, not a table
        table_ref = values[0]
        self.sql_editor.insert(tk.INSERT, table_ref)
        self.sql_editor.focus_set()

    # --- Connection panel ----------------------------------------------------

    def _build_connection_panel(self):
        conn_card = ctk.CTkFrame(self.frame, corner_radius=12)
        conn_card.pack(fill="x", padx=12, pady=(12, 6))

        # Title row
        title_row = ctk.CTkFrame(conn_card, fg_color="transparent")
        title_row.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            title_row,
            text="🔌  IRIS Database Connection",
            font=FONTS["sub_header"],
            anchor="w",
        ).pack(side="left")

        # Status pill
        self.status_label = ctk.CTkLabel(
            title_row,
            text=_STATUS_DISCONNECTED,
            font=FONTS["small"],
            text_color=_COLOR_DISCONNECTED,
            anchor="e",
        )
        self.status_label.pack(side="right")

        # Fields grid  (two rows of three fields each)
        fields_frame = ctk.CTkFrame(conn_card, fg_color="transparent")
        fields_frame.pack(fill="x", padx=12, pady=(0, 4))

        def labeled_entry(parent, label, default="", show="", width=200):
            col = ctk.CTkFrame(parent, fg_color="transparent")
            col.pack(side="left", padx=(0, 10))
            ctk.CTkLabel(col, text=label, font=FONTS["small"], anchor="w").pack(anchor="w")
            var = ctk.StringVar(value=default)
            entry = ctk.CTkEntry(col, textvariable=var, width=width, show=show, font=FONTS["main"])
            entry.pack()
            return var

        # Row 1 – server coords
        row1 = ctk.CTkFrame(fields_frame, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 6))

        self.host_var      = labeled_entry(row1, "Host",      "afthibdsvr001.internal.npsff.ae", width=260)
        self.port_var      = labeled_entry(row1, "Port",      "1972",     width=80)
        self.namespace_var = labeled_entry(row1, "Namespace", "HIBDB",    width=120)
        self.user_var      = labeled_entry(row1, "Username",  "testteamadhds", width=160)
        self.pass_var      = labeled_entry(row1, "Password",  "Testteamadhds123$", show="●", width=160)

        # Row 2 – JAR path + buttons
        row2 = ctk.CTkFrame(fields_frame, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(row2, text="JDBC JAR Path", font=FONTS["small"], anchor="w").pack(side="left")
        self.jar_var = ctk.StringVar(value=IRIS_JDBC_JAR_PATH)
        jar_entry = ctk.CTkEntry(row2, textvariable=self.jar_var, width=420, font=FONTS["main"])
        jar_entry.pack(side="left", padx=(6, 6))

        ctk.CTkButton(
            row2, text="Browse…", width=90,
            command=self._browse_jar,
            font=FONTS["button"],
            fg_color="gray40", hover_color="gray30",
        ).pack(side="left", padx=(0, 16))

        # Connect / Disconnect
        self.connect_btn = ctk.CTkButton(
            row2, text="Connect", width=110,
            command=self._connect,
            font=FONTS["button"],
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
        )
        self.connect_btn.pack(side="left", padx=(0, 6))

        self.disconnect_btn = ctk.CTkButton(
            row2, text="Disconnect", width=110,
            command=self._disconnect,
            font=FONTS["button"],
            fg_color="#7b2020", hover_color="#5a1818",
            state="disabled",
        )
        self.disconnect_btn.pack(side="left")

    # --- SQL editor panel ----------------------------------------------------

    def _build_query_panel(self, parent):
        query_card = ctk.CTkFrame(parent, corner_radius=12)
        query_card.pack(fill="both", expand=False, padx=12, pady=6)

        # Header row
        hdr = ctk.CTkFrame(query_card, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(hdr, text="🗄️  SQL Editor", font=FONTS["sub_header"], anchor="w").pack(side="left")

        # Action buttons (right-aligned)
        btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_frame.pack(side="right")

        self.exec_query_btn = ctk.CTkButton(
            btn_frame, text="▶  Execute Query", width=150,
            command=self._execute_query,
            font=FONTS["button"],
            fg_color=COLORS["success"], hover_color="#1a8f5a",
        )
        self.exec_query_btn.pack(side="left", padx=(0, 6))

        self.exec_stmt_btn = ctk.CTkButton(
            btn_frame, text="⚡  Execute Statement", width=170,
            command=self._execute_statement,
            font=FONTS["button"],
            fg_color="#b05e00", hover_color="#7d4300",
        )
        self.exec_stmt_btn.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_frame, text="Clear", width=80,
            command=self._clear_editor,
            font=FONTS["button"],
            fg_color="gray40", hover_color="gray30",
        ).pack(side="left")

        # SQL text box
        self.sql_editor = ctk.CTkTextbox(
            query_card,
            height=130,
            font=FONTS["code"],
        )
        self.sql_editor.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.sql_editor.insert("1.0", "SELECT TOP 10 * FROM ")

    # --- Results panel -------------------------------------------------------

    def _build_results_panel(self, parent):
        result_card = ctk.CTkFrame(parent, corner_radius=12)
        result_card.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        # Header row
        hdr = ctk.CTkFrame(result_card, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(hdr, text="📋  Query Results", font=FONTS["sub_header"], anchor="w").pack(side="left")

        self.row_count_label = ctk.CTkLabel(
            hdr, text="", font=FONTS["small"], text_color=COLORS["text_sub"], anchor="e"
        )
        self.row_count_label.pack(side="left", padx=12)

        ctk.CTkButton(
            hdr, text="⬇  Export CSV", width=130,
            command=self._export_csv,
            font=FONTS["button"],
            fg_color="gray40", hover_color="gray30",
        ).pack(side="right")

        # Treeview inside a scrollable container
        tree_frame = ctk.CTkFrame(result_card, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # horizontal + vertical scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal")
        v_scroll.pack(side="right",  fill="y")
        h_scroll.pack(side="bottom", fill="x")

        self.results_tree = ttk.Treeview(
            tree_frame,
            yscrollcommand=v_scroll.set,
            xscrollcommand=h_scroll.set,
            selectmode="browse",
            style="Treeview",
        )
        self.results_tree.pack(fill="both", expand=True)

        v_scroll.config(command=self.results_tree.yview)
        h_scroll.config(command=self.results_tree.xview)

        # Status / message bar at the very bottom
        self.message_var = ctk.StringVar(value="")
        self.message_bar = ctk.CTkLabel(
            result_card,
            textvariable=self.message_var,
            font=FONTS["small"],
            text_color=COLORS["text_sub"],
            anchor="w",
        )
        self.message_bar.pack(fill="x", padx=12, pady=(0, 6))

    # ─────────────────────────────────────────────────────────────────────────
    # Connection logic
    # ─────────────────────────────────────────────────────────────────────────

    def _browse_jar(self):
        path = filedialog.askopenfilename(
            title="Select InterSystems JDBC JAR",
            filetypes=[("JAR files", "*.jar"), ("All files", "*.*")],
        )
        if path:
            self.jar_var.set(path)

    def _connect(self):
        """Kick off a background thread to open the DB connection."""
        self._set_status(_STATUS_CONNECTING, _COLOR_CONNECTING)
        self.connect_btn.configure(state="disabled")
        threading.Thread(target=self._do_connect, daemon=True).start()

    def _do_connect(self):
        try:
            client = IrisDBClient(
                host=self.host_var.get().strip(),
                port=self.port_var.get().strip(),
                namespace=self.namespace_var.get().strip(),
                username=self.user_var.get().strip(),
                password=self.pass_var.get(),
                jar_path=self.jar_var.get().strip() or None,
            )
            client.connect()
            with self._lock:
                self.client = client
            self.frame.after(0, self._on_connected)
        except Exception as exc:
            err = str(exc)
            self.frame.after(0, lambda: self._on_connect_error(err))

    def _on_connected(self):
        self._set_status(_STATUS_CONNECTED, _COLOR_CONNECTED)
        self.connect_btn.configure(state="disabled")
        self.disconnect_btn.configure(state="normal")
        self.refresh_schema_btn.configure(state="normal")
        self._show_message("Connected successfully.", color=COLORS["success"])
        self._refresh_schema_browser()

    def _on_connect_error(self, msg):
        self._set_status(_STATUS_ERROR, _COLOR_ERROR)
        self.connect_btn.configure(state="normal")
        self._show_message(f"Connection failed: {msg}", color=COLORS["danger"])
        messagebox.showerror("Connection Error", msg)

    def _disconnect(self):
        with self._lock:
            if self.client:
                try:
                    self.client.disconnect()
                except Exception:
                    pass
                self.client = None
        self._set_status(_STATUS_DISCONNECTED, _COLOR_DISCONNECTED)
        self.connect_btn.configure(state="normal")
        self.disconnect_btn.configure(state="disabled")
        self.refresh_schema_btn.configure(state="disabled")
        self._schema_data = {}
        self.schema_filter_var.set("")
        for item in self.schema_tree.get_children():
            self.schema_tree.delete(item)
        self._show_message("Disconnected.")

    # ─────────────────────────────────────────────────────────────────────────
    # Query execution
    # ─────────────────────────────────────────────────────────────────────────

    def _get_sql(self) -> str:
        return self.sql_editor.get("1.0", "end").strip()

    def _execute_query(self):
        """Run a SELECT query and populate the results grid."""
        sql = self._get_sql()
        if not sql:
            messagebox.showwarning("Empty Query", "Please enter a SQL query.")
            return
        with self._lock:
            if not self.client or not self.client.is_connected():
                messagebox.showwarning("Not Connected", "Please connect to the database first.")
                return
        self._start_spinner("Fetching results")
        threading.Thread(target=self._do_execute_query, args=(sql,), daemon=True).start()

    def _do_execute_query(self, sql: str):
        try:
            with self._lock:
                client = self.client
            print(f"[DatabaseTab] Running query: {sql[:120]}")
            rows = client.execute_query(sql)
            print(f"[DatabaseTab] Query returned {len(rows)} row(s).")
            self.frame.after(0, lambda: self._stop_spinner())
            self.frame.after(0, lambda: self._populate_results(rows))
        except Exception as exc:
            print(f"[DatabaseTab] Query error: {exc}")
            err = str(exc)
            self.frame.after(0, lambda: self._stop_spinner())
            self.frame.after(0, lambda: self._on_query_error(err))

    def _execute_statement(self):
        """Run an INSERT / UPDATE / DELETE statement."""
        sql = self._get_sql()
        if not sql:
            messagebox.showwarning("Empty Statement", "Please enter a SQL statement.")
            return
        with self._lock:
            if not self.client or not self.client.is_connected():
                messagebox.showwarning("Not Connected", "Please connect to the database first.")
                return
        self._start_spinner("Executing statement")
        threading.Thread(target=self._do_execute_statement, args=(sql,), daemon=True).start()

    def _do_execute_statement(self, sql: str):
        try:
            with self._lock:
                client = self.client
            affected = client.execute_non_query(sql)
            self.frame.after(0, lambda: self._stop_spinner())
            self.frame.after(
                0,
                lambda: self._show_message(
                    f"Statement executed successfully. Rows affected: {affected}",
                    color=COLORS["success"],
                ),
            )
            # Clear any stale results
            self.frame.after(0, lambda: self._clear_results())
        except Exception as exc:
            err = str(exc)
            self.frame.after(0, lambda: self._stop_spinner())
            self.frame.after(0, lambda: self._on_query_error(err))

    def _on_query_error(self, msg: str):
        self._stop_spinner()   # safety — in case stop wasn't called before this
        self._show_message(f"Error: {msg}", color=COLORS["danger"])
        messagebox.showerror("Query Error", msg)

    # ─────────────────────────────────────────────────────────────────────────
    # Results grid helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _populate_results(self, rows: list):
        """Fill the Treeview with query results."""
        try:
            self._clear_results()

            if not rows:
                self.row_count_label.configure(text="0 rows")
                self._show_message("Query returned no rows.", color=COLORS["text_sub"])
                return

            columns = list(rows[0].keys())
            self.results_tree.configure(columns=columns, show="headings")

            # Sample only the first 200 rows for auto-width (avoids UI freeze on large result sets)
            sample = rows[:200]
            for col in columns:
                self.results_tree.heading(col, text=col)
                # Auto-width: cap at 300 px, min 80 px
                max_len = max(
                    len(col),
                    max((len(str(r.get(col))) if r.get(col) is not None else len("NULL") for r in sample), default=0),
                )
                width = min(max(max_len * 9, 80), 300)
                self.results_tree.column(col, width=width, minwidth=60, stretch=False)

            for row in rows:
                values = [str(row.get(c)) if row.get(c) is not None else "NULL" for c in columns]
                self.results_tree.insert("", "end", values=values)

            count = len(rows)
            self.row_count_label.configure(text=f"{count} row{'s' if count != 1 else ''}")
            self._show_message(f"Query completed — {count} row(s) returned.", color=COLORS["success"])

            # Keep a cached copy for CSV export
            self._last_columns = columns
            self._last_rows    = rows

        except Exception as exc:
            print(f"[DatabaseTab] Error populating results: {exc}")
            self._show_message(f"Display error: {exc}", color=COLORS["danger"])
            messagebox.showerror("Display Error", str(exc))

    def _clear_results(self):
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.results_tree.configure(columns=[], show="headings")
        self.row_count_label.configure(text="")
        self._last_columns = []
        self._last_rows    = []

    # ─────────────────────────────────────────────────────────────────────────
    # CSV export
    # ─────────────────────────────────────────────────────────────────────────

    def _export_csv(self):
        if not getattr(self, "_last_rows", None):
            messagebox.showwarning("No Data", "There are no results to export.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Results As CSV",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self._last_columns)
                writer.writeheader()
                writer.writerows(self._last_rows)
            self._show_message(f"Exported {len(self._last_rows)} row(s) to {os.path.basename(path)}.", color=COLORS["success"])
            messagebox.showinfo("Export Successful", f"Results saved to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc))

    # ─────────────────────────────────────────────────────────────────────────
    # Misc helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _clear_editor(self):
        self.sql_editor.delete("1.0", "end")

    def _set_status(self, text: str, color: str):
        self.status_label.configure(text=text, text_color=color)

    def _show_message(self, text: str, color: str = "#aaaaaa"):
        self.message_var.set(text)
        self.message_bar.configure(text_color=color)

    # ─────────────────────────────────────────────────────────────────────────
    # Spinner animation
    # ─────────────────────────────────────────────────────────────────────────

    def _start_spinner(self, label: str = "Working"):
        """Begin the spinner animation and lock the execute buttons."""
        self._spinner_label = label
        self._spinner_idx   = 0
        self.exec_query_btn.configure(state="disabled")
        self.exec_stmt_btn.configure(state="disabled")
        self._tick_spinner()

    def _tick_spinner(self):
        """Advance one spinner frame and schedule the next tick."""
        frame = self._SPINNER_FRAMES[self._spinner_idx % len(self._SPINNER_FRAMES)]
        self._spinner_idx += 1
        self._show_message(f"{frame}  {self._spinner_label}…", color=COLORS["warning"])
        # Schedule next tick (80 ms gives ~12 fps — smooth without hammering the event loop)
        self._spinner_job = self.frame.after(80, self._tick_spinner)

    def _stop_spinner(self):
        """Cancel the spinner and re-enable the execute buttons."""
        if self._spinner_job is not None:
            self.frame.after_cancel(self._spinner_job)
            self._spinner_job = None
        self.exec_query_btn.configure(state="normal")
        self.exec_stmt_btn.configure(state="normal")
