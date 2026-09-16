"""
Help & Documentation Tab
"""

import tkinter as tk
import customtkinter as ctk
from .theme import FONTS


class HelpTab:
    def __init__(self, parent):
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.pack(fill="both", expand=True)
        self.create_widgets()

    def create_widgets(self):
        main_frame = ctk.CTkFrame(self.frame)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self._create_search_bar(main_frame)

        self.tabview = ctk.CTkTabview(main_frame)
        self.tabview.pack(fill="both", expand=True)

        self.tab_names = [
            "Test Data Rules", "Custom Functions", "Dependency", "Dependency Variables",
            "Request Flows", "Batch vs Assertion", "Assertion Engine", "Failure Reasons",
            "Custom Report", "Update QA Bugs", "CI/CD Integration",
        ]
        for name in self.tab_names:
            self.tabview.add(name)

        self.create_test_data_tab(self.tabview.tab("Test Data Rules"))
        self.create_custom_functions_tab(self.tabview.tab("Custom Functions"))
        self.create_dependency_tab(self.tabview.tab("Dependency"))
        self.create_dependency_variables_tab(self.tabview.tab("Dependency Variables"))
        self.create_request_flows_tab(self.tabview.tab("Request Flows"))
        self.create_batch_vs_assertion_tab(self.tabview.tab("Batch vs Assertion"))
        self.create_assertion_engine_tab(self.tabview.tab("Assertion Engine"))
        self.create_failure_reasons_tab(self.tabview.tab("Failure Reasons"))
        self.create_custom_report_tab(self.tabview.tab("Custom Report"))
        self.create_update_qa_bugs_tab(self.tabview.tab("Update QA Bugs"))
        self.create_cicd_tab(self.tabview.tab("CI/CD Integration"))

        # Each tab holds exactly one CTkTextbox, added by create_text_area.
        self.text_areas = {name: self.tabview.tab(name).winfo_children()[0] for name in self.tab_names}

    def _create_search_bar(self, parent):
        search_frame = ctk.CTkFrame(parent, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(search_frame, text="Search docs:").pack(side="left", padx=(4, 6))

        self.search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(
            search_frame, textvariable=self.search_var, width=280,
            placeholder_text="e.g. generate, validate_strategy, {{EXTRACT..."
        )
        search_entry.pack(side="left", padx=(0, 6))
        search_entry.bind("<Return>", lambda e: self._search_next())
        search_entry.bind("<Shift-Return>", lambda e: self._search_prev())
        search_entry.bind("<KeyRelease>", lambda e: self._on_search_text_changed())

        ctk.CTkButton(search_frame, text="◀ Prev", width=70, command=self._search_prev).pack(side="left", padx=(0, 4))
        ctk.CTkButton(search_frame, text="Next ▶", width=70, command=self._search_next).pack(side="left", padx=(0, 4))
        ctk.CTkButton(search_frame, text="Clear", width=60, command=self._search_clear).pack(side="left", padx=(0, 4))

        self.search_status_label = ctk.CTkLabel(search_frame, text="", text_color="gray")
        self.search_status_label.pack(side="left", padx=(10, 0))

        self.text_areas = {}
        self.search_matches = []
        self.search_current_index = -1
        self._last_searched_query = None

    def _run_search(self, query):
        for textbox in self.text_areas.values():
            textbox.tag_remove("search_match", "1.0", "end")
            textbox.tag_remove("search_current", "1.0", "end")

        self.search_matches = []
        self.search_current_index = -1
        self._last_searched_query = query

        if not query:
            self.search_status_label.configure(text="")
            return

        for name in self.tab_names:
            textbox = self.text_areas[name]
            start = "1.0"
            while True:
                pos = textbox.search(query, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos}+{len(query)}c"
                textbox.tag_add("search_match", pos, end)
                self.search_matches.append((name, pos, end))
                start = end
            textbox.tag_config("search_match", background="#f5d90a", foreground="black")

        if self.search_matches:
            self.search_current_index = self._closest_match_index_to_current_tab()
            self._show_current_match()
        else:
            self.search_status_label.configure(text="No matches")

    def _closest_match_index_to_current_tab(self):
        """Prefer a match on the tab the user is currently viewing; otherwise the
        nearest tab after it in tab order (wrapping), instead of always jumping
        back to whichever tab happens to be first in self.tab_names."""
        current_tab = self.tabview.get()
        try:
            current_pos = self.tab_names.index(current_tab)
        except ValueError:
            return 0
        for offset in range(len(self.tab_names)):
            candidate_tab = self.tab_names[(current_pos + offset) % len(self.tab_names)]
            for i, (name, _, _) in enumerate(self.search_matches):
                if name == candidate_tab:
                    return i
        return 0

    def _show_current_match(self):
        for textbox in self.text_areas.values():
            textbox.tag_remove("search_current", "1.0", "end")

        name, pos, end = self.search_matches[self.search_current_index]
        textbox = self.text_areas[name]
        textbox.tag_add("search_current", pos, end)
        textbox.tag_config("search_current", background="#ff8c00", foreground="black")
        self.tabview.set(name)
        textbox.see(pos)
        self.search_status_label.configure(
            text=f"{self.search_current_index + 1} of {len(self.search_matches)} in \"{name}\""
        )

    def _on_search_text_changed(self):
        query = self.search_var.get().strip()
        if query != self._last_searched_query:
            self._run_search(query)

    def _search_next(self):
        query = self.search_var.get().strip()
        if query != self._last_searched_query:
            self._run_search(query)
            return
        if not self.search_matches:
            return
        self.search_current_index = (self.search_current_index + 1) % len(self.search_matches)
        self._show_current_match()

    def _search_prev(self):
        query = self.search_var.get().strip()
        if query != self._last_searched_query:
            self._run_search(query)
            return
        if not self.search_matches:
            return
        self.search_current_index = (self.search_current_index - 1) % len(self.search_matches)
        self._show_current_match()

    def _search_clear(self):
        self.search_var.set("")
        self._run_search("")

    def create_text_area(self, parent, content):
        text = ctk.CTkTextbox(parent, font=FONTS["code"], wrap="word")
        text.pack(fill="both", expand=True, padx=5, pady=5)
        text.insert("1.0", content)
        text.configure(state='disabled')
        return text

    def create_test_data_tab(self, parent):
        content = """
═══════════════════════════════════════════════════════════════════════════════
                              TEST DATA RULES
═══════════════════════════════════════════════════════════════════════════════

The "Test Data" column lets you override specific values in the XML request
template before it is sent. Each entry is a key=value assignment. Multiple
assignments are separated by semicolons (;).

───────────────────────────────────────────────────────────────────────────────
RULE 1 — SIMPLE ELEMENT REPLACEMENT
───────────────────────────────────────────────────────────────────────────────

  Format:   elementName=value
  Example:  firstName=John; lastName=Doe; age=45

  Finds the element by tag name in the XML template and replaces its text.
  For nested elements use a dot-separated path:

  Example:  Body.Request.PersonInfo.firstName=John

  Special keywords (case-insensitive, with any bracket style):
    {empty}   or  <empty>   →  Sets element text to an empty string
    {valid}   or  <valid>   →  Sets element to a predefined valid value
    {invalid} or  <invalid> →  Sets element to a predefined invalid value

───────────────────────────────────────────────────────────────────────────────
RULE 2 — PARENT ELEMENT REPETITION (count control)
───────────────────────────────────────────────────────────────────────────────

  Format:   <elementName>=N   (angle brackets, curly braces, parens, or square
            {elementName}=N    brackets all work)
  Example:  <claim>=3         →  Duplicate the <claim> element 3 times
  Example:  <diagnosis>=0     →  Remove the <diagnosis> element entirely
  Example:  {item}=1          →  Keep exactly one <item> element

  Rules:
    • N = 0  → element is removed from the template
    • N = 1  → element kept as-is (single occurrence)
    • N > 1  → element is duplicated N times

  After setting a count you can target individual copies by index:
    claim[1].diagnosisCode=A00   →  Sets diagnosisCode in the 1st claim
    claim[2].diagnosisCode=B01   →  Sets diagnosisCode in the 2nd claim

───────────────────────────────────────────────────────────────────────────────
RULE 3 — DYNAMIC VALUES WITH {{...}} FUNCTIONS
───────────────────────────────────────────────────────────────────────────────

  Format:   elementName={{FUNCTION(params)}}
  Example:  serviceDate={{DATE(YYYY-MM-DD)}}

  ┌─────────────────────────────────────────────────────────────────────────┐
  │ BUILT-IN FUNCTIONS                                                      │
  ├─────────────────────────┬───────────────────────────────────────────────┤
  │ {{DATE(format)}}        │ Current date, e.g. {{DATE(YYYY-MM-DD)}}       │
  │ {{DATETIME(format)}}    │ Current date+time                             │
  │ {{DATE_ADD(days,fmt)}}  │ Future date, e.g. {{DATE_ADD(5,YYYY-MM-DD)}}  │
  │ {{DATE_SUB(days,fmt)}}  │ Past date                                     │
  │ {{RANDOM(min,max)}}     │ Random integer between min and max            │
  │ {{RANDOM_DECIMAL(       │ Random decimal, e.g.                          │
  │     min,max,decimals)}} │   {{RANDOM_DECIMAL(1.0,9.9,2)}}               │
  │ {{RANDOM_STRING(        │ Random string — types: ALPHANUMERIC, LETTERS, │
  │     length,type)}}      │   UPPERCASE, LOWERCASE, DIGITS                │
  │ {{UUID()}}              │ Full UUID v4                                  │
  │ {{UUID(short)}}         │ Shortened UUID                                │
  │ {{SEQUENCE(key,         │ Auto-incrementing counter per key             │
  │     start,prefix,fmt)}} │                                               │
  │ {{RUN_ID}}              │ Current batch run identifier                  │
  │ {{TEST_INDEX}}          │ Current test index within the run             │
  │ {{TIMESTAMP}}           │ Unix timestamp (seconds)                      │
  │ {{NOW(format)}}         │ Alias for DATETIME                            │
  └─────────────────────────┴───────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────┐
  │ VARIABLE REFERENCES                                                     │
  ├─────────────────────────┬───────────────────────────────────────────────┤
  │ {{VAR.name}}            │ Value of a declared variable (from            │
  │                         │   Variable_Definitions column)                │
  │ {{EXTRACT.name}}        │ Value extracted from a dependency's response  │
  │                         │   (dormant — see Dependency Variables tab,    │
  │                         │   this project's sheets don't use it)         │
  │ {{CUSTOM.func(args)}}   │ Call a function from custom_functions.py      │
  │ {{ENCODED_XML_Suffix}}  │ Base64-encoded content of Raw_XML_Suffix col  │
  └─────────────────────────┴───────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────────────────────
PROCESSING ORDER & IMPORTANT RULES
───────────────────────────────────────────────────────────────────────────────

  1. The Test Data string is split on semicolons (;) into individual rules.
  2. Rules are sorted longest-key-first so nested paths are processed safely.
  3. Enclosed parent-count rules (<element>=N) are applied first.
  4. Leaf element replacements are applied next.
  5. {{...}} expressions inside values are evaluated by the variable engine.

  • The column is optional — leave it empty to send the template unchanged.
  • Commas and newlines inside values are NOT separators; only ; separates rules.
  • Each rule must contain exactly one = (value may contain = signs).
  • If an element path is not found in the template it is silently skipped.
  • If a {{...}} variable cannot be resolved, {{ERROR: name}} is written in its place.

───────────────────────────────────────────────────────────────────────────────
FULL EXAMPLE
───────────────────────────────────────────────────────────────────────────────

  <claim>=2; claim[1].diagnosisCode=A00.0; claim[2].diagnosisCode=B01;
  serviceDate={{DATE(YYYY-MM-DD)}}; memberId={{EXTRACT.memberId}};
  requestId={{UUID()}}; notes={empty}

  What happens:
    1. The <claim> element is duplicated twice.
    2. Each copy gets its own diagnosisCode.
    3. serviceDate is set to today's date.
    4. memberId is filled from the dependency's extracted response value
       (EXTRACT.* is dormant in this project — see "Dependency Variables"
       tab — so in practice this would resolve to {{ERROR: memberId}}).
    5. requestId gets a fresh UUID.
    6. notes is cleared to an empty string.

═══════════════════════════════════════════════════════════════════════════════
"""
        self.create_text_area(parent, content)

    def create_dependency_tab(self, parent):
        content = """
═══════════════════════════════════════════════════════════════════════════════
                    DEPENDENCY LOGIC — NOT USED IN THIS PROJECT
═══════════════════════════════════════════════════════════════════════════════

  This is dormant/dead code. No test sheet in this project uses it, and it
  is not part of any workflow you should follow. Nothing below is a
  recommendation — it is a reference for what the unused code does, kept
  in case someone stumbles on it and wonders why it exists.

  Confirmed facts:
    • No sheet in this project has a column titled "Dependency".
    • It is NOT added by "Create Template" (utils/excel_handler.py:
      create_excel_template), NOT in the shipped example sheet
      (docs/example_test_cases_sheet.xlsx), and NOT required by
      validate_excel / validate_assertion_excel.
    • Batch Testing (utils/allure_wrapper.py) never reads it — the code
      only exists in utils/assertion_allure_wrapper.py +
      utils/dependency_tracker.py (Assertion Testing only).
    • Since the column never appears on any real sheet, this code path
      never actually executes — every row reads an empty string and the
      dependency check is a permanent no-op in practice.

───────────────────────────────────────────────────────────────────────────────
WHAT THE DORMANT CODE WOULD DO, IF SOMEONE ADDED THIS COLUMN
───────────────────────────────────────────────────────────────────────────────

  (utils/dependency_tracker.py + utils/assertion_allure_wrapper.py)

  • A "Dependency" cell would hold the TC ID of a prerequisite test.
  • Tests would be topologically sorted so a dependency runs before its
    dependents.
  • Before a dependent test runs, it would poll a shared state file for the
    dependency's recorded result (passed / failed / skipped), up to 300s,
    then proceed or skip accordingly (skips cascade down the chain).
  • A cycle (A → B → A) would print a console warning and fall back to
    original sheet order rather than dropping tests.
  • None of this is reachable today because the triggering column does not
    exist on any sheet in use.

═══════════════════════════════════════════════════════════════════════════════
"""
        self.create_text_area(parent, content)

    def create_dependency_variables_tab(self, parent):
        content = """
═══════════════════════════════════════════════════════════════════════════════
              DEPENDENCY VARIABLES LOGIC — NOT USED IN THIS PROJECT
═══════════════════════════════════════════════════════════════════════════════

  Same status as the "Dependency" tab: this is dormant/dead code. No test
  sheet in this project has a "Dependency Variables" column, so this logic
  never actually runs. Nothing below is a recommendation to use it — it is
  a reference for what the unused code would do.

  Confirmed facts:
    • Not added by "Create Template", not in the shipped example sheet, not
      required by validate_excel / validate_assertion_excel.
    • Only reachable from ASSERTION TESTING
      (utils/assertion_allure_wrapper.py); Batch Testing never reads it.
    • It only means anything paired with the "Dependency" column (also
      unused) on the dependent row — since neither exists on any real
      sheet, extraction and injection never fire.

───────────────────────────────────────────────────────────────────────────────
WHAT THE DORMANT CODE WOULD DO, IF SOMEONE ADDED THESE COLUMNS
───────────────────────────────────────────────────────────────────────────────

  • Each line/semicolon entry would be a rule: variableName = <spec>.
  • Simple element:      varName = ElementTag
    → first matching tag's text anywhere in the XML response.
  • Filtered parent:     varName = ParentTag[child=val].extractChild
    → picks the repeated ParentTag instance whose child(ren) match, then
      reads extractChild. Supports {{TEMPLATE.path}} inside the filter value.
  • Request template:    varName = TEMPLATE.dot.separated.path
    → reads from the outgoing request XML instead of the response.
  • Once stored, a dependent test could reference {{EXTRACT.varName}} in its
    Test Data (plain substitution) or Objective (full expression evaluation,
    including inside CUSTOM.* calls).
  • Missing elements/filters just print a WARNING and skip storing — never
    a hard failure.

  Since the triggering columns don't exist on any sheet in use, none of this
  is reachable today.

═══════════════════════════════════════════════════════════════════════════════
"""
        self.create_text_area(parent, content)

    def create_custom_functions_tab(self, parent):
        content = """
═══════════════════════════════════════════════════════════════════════════════
                     CUSTOM FUNCTIONS & TEMPLATE VARIABLES
═══════════════════════════════════════════════════════════════════════════════

There are TWO separate {{...}} processing engines in this tool. Knowing which
engine reads a given column tells you which functions/variables actually work
there. Using a function in the wrong column silently fails or is never
evaluated.

───────────────────────────────────────────────────────────────────────────────
THE TWO ENGINES
───────────────────────────────────────────────────────────────────────────────

  VariableProcessor
    Columns:   Test Data, Variable_Definitions
    Supports:  {{CUSTOM.func()}}, {{VAR.name}}, {{EXTRACT.name}},
               {{DATE(...)}}, {{UUID()}}, {{RANDOM(...)}}, {{SEQUENCE(...)}},
               {{RUN_ID}}, {{TEST_INDEX}}, {{TIMESTAMP}}, etc.
    Errors:    a bad variable/function leaves an inline {ERROR: expr} marker
               and KEEPS PROCESSING the rest of the string.

  ErrorTextProcessor
    Columns:   Error Text, Field Value, Additional Reference,
               Objective (Expected Result)
    Supports:  {{CUSTOM.func()}}, {{TEMPLATE.path}}, {{PRE_TEMPLATE.step.path}}
               ONLY.
    Does NOT support {{DATE(...)}}, {{RANDOM(...)}}, {{UUID()}}, {{VAR.name}}
    — none of the built-in/VAR functions have a branch here.
    Errors:    a bad variable/function RAISES immediately, aborting that
               assertion entirely.

  {{EXTRACT.name}} is a special case tied to the Dependency/Dependency
  Variables mechanism, which is dormant in this project (see the
  "Dependency Variables" tab — no sheet in use has those columns, so
  {{EXTRACT.*}} never actually resolves today).

───────────────────────────────────────────────────────────────────────────────
{{CUSTOM.function_name(args)}} — HOW IT'S CALLED
───────────────────────────────────────────────────────────────────────────────

  Every function below lives in functions/custom_functions.py and is invoked
  as {{CUSTOM.function_name(arg1,arg2)}}. All arguments arrive as raw strings
  (quotes stripped); functions that need numbers cast internally.

  • Unknown function name               → {ERROR: Custom function 'X' not found}
  • custom_functions.py fails to import → every CUSTOM.* call returns
                                            {ERROR: No custom functions loaded}
  • Some functions retry internally (up to 10x) to avoid generating a value
    that collides with one already used in this run; after 10 failures they
    raise an Exception.

───────────────────────────────────────────────────────────────────────────────
ID / STRING GENERATION
───────────────────────────────────────────────────────────────────────────────

  generate_numbers_id(preceding='', length='10')
      Random N-digit numeric string; "PRECEDING-NNNNN" if preceding given.
  generate_numbers_id_hash(preceding='', length='10')
      Same as above, joined with '#' instead of '-'.
  generate_random_number(n='5')
      Random N-digit integer.
  generate_random_digit_string(length='10')
      Random alphanumeric (mixed case) string.
  generate_random_digit_string_with_whitespaces(length='10', whitespaces='3',
                                                 start_end_whitespaces='0')
      Alphanumeric string of the given total length with N interior random
      spaces and N boundary-anchored spaces (half start/half end, extra to
      start) — useful for testing whitespace-trimming bugs.
  generate_claim_id(prefix='MF3505')
      "PREFIX-######-XXXXXX-D" combining numeric + alphanumeric + digit parts.
  remove_last_chars_from_string(value, characters_remove)
      Drops the last N characters off value.
  remove_chars(value, n='0')
      N>0 strips the first N chars; N<0 strips the last |N| chars.
  convert_to_uppercase(value)
      str(value).upper()
  add_to_number(value, amount) / sub_from_number(value, amount)
      Integer add/subtract, returned as a string —
      e.g. {{CUSTOM.add_to_number(EXTRACT.downloadCount,1)}}

───────────────────────────────────────────────────────────────────────────────
PERSON / IDENTITY DATA
───────────────────────────────────────────────────────────────────────────────

  generate_person_data(data_type)
      Dispatch by type string: phone, passport, email,
      emirates_id (valid Luhn check digit), emirates_unified_number,
      member_id, nationality / location / emirate (random from resource
      Excel), first_name, last_name. Unknown type →
      "<Error with data type: X>".
  generate_dob(min_age='18')
      Random DOB making the person older than min_age (up to 100).
  get_dob_for_age(age)
      DOB for someone turning exactly `age` today.
  get_random_provider_login / get_random_payer_id / get_random_provider_id /
  get_random_payer_login
      Random pick from small hardcoded test-account lists. No params.
  get_login_from_id(key)
      Looks up a login from the hardcoded `users` dict by key
      (e.g. T001_Malaffi). If USE_SPECIFIC_LOGIN=true, overrides with the
      matching PAYER_VALUE / TPA_VALUE / PROVIDER_VALUE / PHARMACY_VALUE
      env var.
  get_password_from_id(key)
      Password for the same hardcoded `users` dict.

───────────────────────────────────────────────────────────────────────────────
DATE / TIME
───────────────────────────────────────────────────────────────────────────────

  get_current_date_time / get_current_date / get_current_date_iso /
  get_current_year
      Now, formatted DD/MM/YYYY HH:MM, DD/MM/YYYY, YYYY-MM-DD, and year
      respectively.
  add_minutes_to_current_date_time / sub_minutes_to_current_date_time
  (minutes='5')
      +/- minutes from now, DD/MM/YYYY HH:MM.
  add_hours_to_current_date_time / sub_hours_to_current_date_time (hours='1')
      +/- hours from now.
  add_days_to_current_date_time / sub_days_to_current_date_time (days='5')
      +/- days from now, with time.
  add_days_to_current_date / sub_days_to_current_date (days='5')
      +/- days, date only.
  get_date_offset(days='5')
      Negative subtracts, positive adds (single signed-offset helper).
  add_months_to_current_date / subtract_months_from_current_date
  (months, days=0, date_format='%d/%m/%Y')
      +/- calendar months (+days), custom strftime output.
  format_date_to_iso / format_datetime_to_iso (date_text)
      Reformats a DD/MM/YYYY[ HH:MM] string to ISO; on parse failure logs and
      returns the original text unchanged (does not raise).
  append_time_to_date(date_str, time_str='00:00')
      Appends a time to a date string, auto-detecting format among
      %Y-%m-%d, %d/%m/%Y, %m/%d/%Y, %d-%m-%Y; raises ValueError if
      unrecognized.

───────────────────────────────────────────────────────────────────────────────
REFERENCE-DATA LOOKUPS
───────────────────────────────────────────────────────────────────────────────

  All read cached Excel/CSV files under resources/ (thread-safe caching). On
  a missing file/column they return an error/info string — they never raise.

    get_random_facility_license
    get_random_facility_license_number_by_status(status='Active')
    get_random_encounter_type              get_random_diagnosis_type
    get_random_icd_code(is_expired='false')
    get_icd_code_effective_date(code)      get_icd_code_expiry_date(code)
    get_random_code_type                   get_random_cpt_code
    get_random_hcpcs_code                  get_random_service_code
    get_random_uscls_code                  get_random_drg_code
    get_random_observation_type            get_random_loinc
    get_random_dha_license                 get_random_moh_license
    get_random_haad_license                get_random_tooth_numbering
    get_random_insurer                     get_random_broker_or_tpa(classification)
    get_random_denial_code(status)
    get_random_icd9_diagnosis_code         get_random_icd10_diagnosis_code
    get_random_consultation_tariff_code

  Two advanced clinician lookups support a leading "! " to NEGATE a filter:

    get_clinician_license_starting_with(major, profession, category)
      Each param is a case-insensitive "starts with" filter. "! pharma"
      excludes that prefix. Only ACTIVE licenses count (per
      Clinician Licensing History.xlsx).

    get_clinician_license_containing(major, profession, category)
      Same idea, but "contains (not at position 0)" instead of "starts with".

───────────────────────────────────────────────────────────────────────────────
BINARY / ENCODING / MISC
───────────────────────────────────────────────────────────────────────────────

  get_image_as_base64(image_name)
      Base64-encodes a file under resources/.
  zip_xml_templates_as_base64(template1, template2=None)
      Zips one or two files from xml_templates/, returns base64 of the zip.
  generate_filename(extension='xml', include_timestamp=True)
      Random test filename.
  clear_excel_cache / get_cache_info
      Cache maintenance/debug helpers.

  zip_file / zip_files are internal helpers (take xml.etree.Element objects,
  not strings) — not meant to be called directly from an excel cell.

───────────────────────────────────────────────────────────────────────────────
{{TEMPLATE.path}} AND {{PRE_TEMPLATE.step.path}} — PATH SYNTAX
───────────────────────────────────────────────────────────────────────────────

  Dot-separated tag names walk down the XML tree from the root:

    {{TEMPLATE.Body.Request.PersonInfo.firstName}}

  Add [N] (1-based) to any segment to pick the Nth occurrence of a repeated
  tag (counted only among siblings sharing that tag):

    {{TEMPLATE.Body.Claims[2].claimID}}      → claimID inside the 2nd <Claims>

  TEMPLATE.path    → resolves against the CURRENT request's template XML.
  PRE_TEMPLATE.stepName.path
                   → resolves against an EARLIER step's template in a
                     multi-step flow. The first path segment is the step
                     label (e.g. PersonRegister, PriorRequest — see the
                     "Request Flows" tab for what steps exist per flow).

  Examples:
    {{PRE_TEMPLATE.PersonRegister.MemberID}}
    {{PRE_TEMPLATE.PriorAuthorization.Activity[1].PriorAuthorizationID}}

  Errors:
    • Path segment not found     → "Cannot find the element in the template
                                     using variable path: X"
    • Step name not found        → exception listing the available step
                                     labels for that flow
    • No template_flow supplied  → exception (PRE_TEMPLATE used somewhere
                                     with no multi-step flow context)
  Any of the above, inside Error Text / Field Value / Additional Reference /
  Objective, ABORTS that assertion (ErrorTextProcessor raises immediately —
  see the engine comparison above).

───────────────────────────────────────────────────────────────────────────────
WHICH COLUMNS SUPPORT WHAT
───────────────────────────────────────────────────────────────────────────────

  ┌───────────────────────┬────────┬──────────┬──────────────┬──────┬─────────┬─────────┐
  │ Column                 │ CUSTOM │ TEMPLATE │ PRE_TEMPLATE │ VAR  │ EXTRACT │ DATE/etc│
  ├───────────────────────┼────────┼──────────┼──────────────┼──────┼─────────┼─────────┤
  │ Test Data              │  yes   │   no     │     no       │ yes  │   yes   │   yes   │
  │ Variable_Definitions   │  yes   │   no     │     no       │ n/a  │   yes   │   yes   │
  │ Error Text             │  yes   │   yes    │     yes      │ no   │   no*   │   no    │
  │ Field Value            │  yes   │   yes    │     yes      │ no   │   no*   │   no    │
  │ Additional Reference   │  yes   │   yes    │     yes      │ no   │   no*   │   no    │
  │ Objective              │  yes   │   yes    │     yes      │ no   │  yes**  │   no    │
  └───────────────────────┴────────┴──────────┴──────────────┴──────┴─────────┴─────────┘

  *  Not a native ErrorTextProcessor feature — unconfirmed for these columns.
  ** In principle works in Objective via dependency-variable injection
     (EXTRACT substituted before ErrorTextProcessor sees the column), but
     that mechanism is dormant in this project — see "Dependency Variables"
     tab. In practice {{EXTRACT.*}} never resolves today.

  Built-in functions (DATE, DATETIME, DATE_ADD, DATE_SUB, RANDOM,
  RANDOM_DECIMAL, RANDOM_STRING, UUID, SEQUENCE, RUN_ID, TEST_INDEX,
  TIMESTAMP, NOW) are documented in full on the "Test Data Rules" tab.

═══════════════════════════════════════════════════════════════════════════════
"""
        self.create_text_area(parent, content)

    def create_request_flows_tab(self, parent):
        content = """
═══════════════════════════════════════════════════════════════════════════════
                       REQUEST FLOWS (TRANSACTION CHAINS)
═══════════════════════════════════════════════════════════════════════════════

Every transaction type in the Excel sheet (one sheet = one transaction type,
e.g. "ClaimSubmission", "PriorAuthorization") maps to a request-mapper class
in utils/request_mapper/. Each class implements do_request(system, live_data)
and knows its own prerequisite chain — the sequence of upstream requests that
must be built and sent before the "request under test" itself.

Full technical detail lives in docs/request_mapper_transaction_flows.md — this
tab summarizes the parts a test writer actually needs.

───────────────────────────────────────────────────────────────────────────────
SINGLE API vs FULL SCENARIO
───────────────────────────────────────────────────────────────────────────────

  Controlled by the Execution Sequence setting (SOAP_EXECUTION_SEQUENCE):

  Full Scenario
    Builds and sends EVERY prerequisite step in the chain (e.g. Person
    Register → Prior Request → Prior Authorization) before sending the
    request under test. If the same object already built these templates in
    a previous call, it re-sends the cached templates instead of rebuilding
    them.

  Single API (isolated)
    Skips every prerequisite step. Sends only a self-contained "_isolated"
    template for the request under test, which already embeds the data it
    needs.

  A few transactions do NOT support Single API at all and raise "Please use
  full scenario for this transaction type" if you try: PersonCorrected
  ClaimChecker, SecondRemittanceAdviceAfterTKBK. Two more (SecondRemittance
  Advice, ThirdRemittanceAdvice) always rebuild the full chain unconditionally
  regardless of the setting.

───────────────────────────────────────────────────────────────────────────────
PRECONDITION → PER-STEP LIVE DATA (ClaimChecker family only)
───────────────────────────────────────────────────────────────────────────────

  The Precondition column normally targets the request under test. For the
  ClaimChecker family of transactions, it can ALSO target an individual
  prerequisite step using a prefix:

    PersonRegister.firstName=John; PriorRequest.serviceDate={{DATE(...)}}

  Recognised prefixes: PersonRegister, PriorRequest, PriorAuthorization,
  ClaimSubmission, RemittanceAdvice. For a repeated step (e.g. the 2nd Person
  Register in PersonCorrectedClaimChecker), suffix the index:
  PersonRegister[2].path=value. A bare PersonRegister[1].path=value is
  accepted as an alias for PersonRegister.path=value.

  If a Precondition entry's prefix doesn't match ANY step in that specific
  flow (e.g. a RemittanceAdvice. entry inside ClaimCheckerNoRemittance, which
  has no remittance step), the flow raises "Unconsumed precondition entries
  (no matching step in this flow)" rather than silently ignoring it.

  Flows outside the ClaimChecker family don't use this mechanism — their
  prerequisite steps always send with no live data of their own.

───────────────────────────────────────────────────────────────────────────────
SYSTEMS
───────────────────────────────────────────────────────────────────────────────

  OLD_SYSTEM (1)        Legacy (1.0) system
  NEW_SYSTEM (2)        New (2.0) system
  DUAL_SYSTEMS (3)      Both systems, results compared
  DUAL_OLD_SYSTEM (4)   Legacy system, both PTE and Production environments

───────────────────────────────────────────────────────────────────────────────
ASSERTION-TAB-ONLY TRANSACTIONS
───────────────────────────────────────────────────────────────────────────────

  These 7 transactions don't build a claims chain at all — instead they
  optionally resolve a single prerequisite transaction (from the Precondition
  column) and pull fields out of ITS response/template. Batch Testing
  explicitly REJECTS all of them; they only ever run under the Assertion tab
  (see the "Batch vs Assertion" tab):

    Search Transactions              Get New Prior Authorization Transactions
    Get New Transactions             Download Transaction
    Set Transaction Downloaded       Claim Count Reconciliation
    Get Person Insurance History

───────────────────────────────────────────────────────────────────────────────
CHAIN SUMMARY (prerequisite steps → request under test)
───────────────────────────────────────────────────────────────────────────────

  PersonRegister                    — (none) → Person Register
  PersonRegisterResubmission        Person Register → Person Register Resubmission
  PersonRegisterTPA                 — (none) → Person Register TPA
  PriorRequest                      Person Register → Prior Request
  PriorRequestToTPA                 Person Register (TPA) → Prior Request to TPA
  PriorRequestMultipleXmls          Person Register, Prior Request → (multi XML send)
  PriorRequestGreaterThan6MB        Person Register, Prior Request, Prior Authorization
                                       → Prior Request Resubmission (>6MB)
  PriorRequestResubmission          Person Register, Prior Request, Prior Authorization
                                       → Prior Request Resubmission
  PriorRequestZipped                Person Register, Prior Request → (zipped send)
  PriorAuthorizationPrescription/   Person Register, Prior Request (variant)
    Cancellation/Extension/           → Prior Authorization (matching variant)
    Eligibility/Large
  PriorAuthorization                Person Register, Prior Request → Prior Authorization
  PriorAuthorizationTPA             Person Register TPA, Prior Request to TPA
                                       → Prior Authorization TPA
  ClaimSubmission                   Person Register, Prior Request → Claim Submission
  ClaimChecker *                    Person Register, Prior Request, Prior Authorization
                                       → Claim Checker
  PersonCorrectedClaimChecker *     Person Register, Person Register Resubmission
                                       (2nd/correction), Prior Request, Prior Authorization
                                       → Claim Checker  (full-scenario only)
  ClaimCheckerNoPriorAuthorization* Person Register, Prior Request
                                       → Claim Checker (no prior auth)
  ClaimCheckerResubmission *        Person Register, Prior Request, Claim Submission,
                                       Remittance Advice → Claim Checker Resubmission
  ClaimCheckerNoRemittance *        Person Register, Prior Request, Claim Submission
                                       → Claim Checker (no remittance)
  ClaimCheckerConsultationNo        Person Register, Prior Request Consultation,
    Remittance *                      Claim Submission → Claim Checker (no remittance)
  ClaimCheckerSelfPay *             Person Register (self pay) → Claim Checker (self pay)
  ClaimCheckerMultipleClaimsZipped* Person Register, Prior Request, Prior Authorization
                                       → Claim Checker (multi claims, zipped)
  ClaimSubmissionMultipleActivities Person Register, Prior Request (multi activity)
                                       → Claim Submission (multi activity)
  ClaimSubmissionSelfPay            Person Register (self pay) → Claim Submission (self pay)
  PreconditionClaimSubmission       Person Register, Prior Request
                                       → Claim Submission (live_data = precondition text)
  SecondClaimNoRemittance           Person Register, Prior Request, Claim Submission
                                       → Claim Resubmission (no remittance)
  ClaimSubmissionToTPA              Person Register (TPA), Prior Request to TPA
                                       → Claim Submission to TPA
  ClaimSubmissionMultipleClaims     Person Register, Prior Request, Prior Authorization
                                       → Claim Submission (multi claims)
  ClaimSubmissionMultipleClaims     Person Register, Prior Request, Prior Authorization
    Zipped                            → Claim Submission (multi claims, zipped)
  ClaimResubmissionToTakeBack       Person Register, Prior Request, Claim Submission,
                                       Remittance Advice (takeback)
                                       → Claim Resubmission (correction)
  ClaimResubmission                 Person Register, Prior Request, Claim Submission,
                                       Remittance Advice → Claim Resubmission
  ClaimResubmissionConsultation     Person Register, Prior Request (consultation),
                                       Claim Submission, Remittance Advice
                                       → Claim Resubmission
  ClaimResubmissionConsultationNo   Person Register, Prior Request (consultation),
    Remittance                        Claim Submission → Claim Resubmission (no remittance)
  ClaimSecondResubmission           Person Register, Prior Request, Claim Submission,
                                       Claim Resubmission (1st)
                                       → Claim Submission (2nd resubmission)
  RemittanceAdvice                  Person Register, Prior Request, Claim Submission
                                       → Remittance Advice
  RemittanceAdviceMultipleActivities Person Register, Prior Request (multi activity),
                                       Claim Submission (multi activity)
                                       → Remittance Advice (multi activity)
  RemittanceAdviceTPA               Person Register (TPA), Prior Request to TPA,
                                       Claim Submission to TPA → Remittance Advice TPA
  CostSubmission                    Person Register, Prior Request, Claim Submission
                                       → Cost Submission
  CostSubmissionMultipleClaims      Person Register, Prior Request,
                                       Claim Submission (multi claims)
                                       → Cost Submission (multi claims)
  CostSubmissionZipped              Person Register, Prior Request, Claim Submission
                                       → Cost Submission (zipped)
  CostResubmission                  Person Register, Prior Request, Claim Submission,
                                       Cost Submission → Cost Resubmission
  RemittanceAdviceMultipleClaims    Person Register, Prior Request,
                                       Claim Submission (multi claims)
                                       → Remittance Advice (multi claims)
  SecondRemittanceAdvice            Person Register, Prior Request, Claim Submission,
                                       Remittance Advice (tkbk), Claim Resubmission
                                       (correction) → Second Remittance Advice
                                       (full-scenario only)
  ThirdRemittanceAdvice             ...as above, plus 2nd tkbk + 2nd correction
                                       → Third/Second Remittance Advice
                                       (full-scenario only)
  SecondRemittanceAdviceAfterTKBK   Person Register, Prior Request, Claim Submission,
                                       Remittance Advice (tkbk) → Second Remittance Advice
                                       (full-scenario only; no single-request mode)
  RemittanceAdviceHAADClaim         Person Register, Prior Request,
                                       Claim Submission (HAAD) → Remittance Advice
  PayForQuality                     — (none) → Pay For Quality (always sent directly)

  * = uses per-step live data extraction via Precondition prefixes (see above)

  Non-chained / Assertion-only (see box above): SearchTransactions,
  GetNewPriorAuthorizationTransactions, GetNewTransactions, DownloadTransaction,
  SetTransactionDownloaded, Reconciliation, GetPersonInsuranceHistory.

═══════════════════════════════════════════════════════════════════════════════
"""
        self.create_text_area(parent, content)

    def create_batch_vs_assertion_tab(self, parent):
        content = """
═══════════════════════════════════════════════════════════════════════════════
             BATCH TESTING vs ASSERTION TESTING — WHAT FALLS WHERE
═══════════════════════════════════════════════════════════════════════════════

The Batch and Assertion tabs run on two entirely separate pytest wrappers with
different assertion engines. This tab explains the technical distinction —
for UI click-through steps see docs/batch-and-assertion-tabs-guide.md.

───────────────────────────────────────────────────────────────────────────────
THE CORE DIFFERENCE
───────────────────────────────────────────────────────────────────────────────

  BATCH TESTING answers:
    "Did the transaction's ERROR/WARNING REPORT contain the expected row —
     matching on Rule ID, Object, Element, Error Text, Field Value,
     Additional Reference, and Occurrence count?"

  ASSERTION TESTING answers:
    "Is this SEARCH/RETRIEVAL-style transaction's actual response content
     correct — was it found, downloaded, does an element equal X, etc.?"

───────────────────────────────────────────────────────────────────────────────
SIDE BY SIDE
───────────────────────────────────────────────────────────────────────────────

  Dispatcher
    Batch:      XMLAsserterContext → XMLSingleAsserter (utils/asserter/asserter.py)
    Assertion:  CustomAsserterContext.get_request_strategy().determine(...)
                (utils/asserter/custom_requests_asserter.py)

  Eligible transaction types
    Batch:      Any transaction produced by the request mapper.
    Assertion:  ONLY Search Transactions, Get New Prior Authorization
                Transactions, Get New Transactions, Download Transaction,
                Set Transaction Downloaded, Claim Count Reconciliation, Get
                Person Insurance History. Anything else raises "doesn't
                qualify for assertion run".

  Objective column
    Batch:      First word decides the call: pass*/fail*/warning*/
                notification* → dedicated assert_*; anything else →
                custom_assert mini-language (see "Assertion Engine" tab).
    Assertion:  A multi-line SCRIPT — each line is its own statement (found /
                not found / retrieved downloaded / report generated /
                errorcode / element / file found, etc. — see "Assertion
                Engine" tab).

  System comparison
    Batch:      Full dual-system support — System1-only, System2-only, both
                (row-by-row report diff), System1-both-envs. Presence
                Comparison Mode available.
    Assertion:  Single-system only — System1-baseline or System2-regression.
                No dual-system diff exists.

  Dependency chains
    Batch:      Not present in this wrapper.
    Assertion:  Code exists (topological sort, skip-on-failure cascade,
                {{EXTRACT.var}} injection) but is DORMANT — no sheet in
                this project has "Dependency"/"Dependency Variables"
                columns, so it never actually runs. See "Dependency" /
                "Dependency Variables" tabs.

  Uses SchemaRulesValidator / error-report XML
    Batch:      Yes — every rule-report assertion goes through it.
    Assertion:  No — never touches the error-report XML at all; only
                inspects the raw response body XML.

  In short: use BATCH for validating rule/error/warning reporting on any
  transaction; use ASSERTION for validating search/retrieval/download
  behaviour on the 7 transactions listed above, and for chained,
  dependency-driven scenarios.

═══════════════════════════════════════════════════════════════════════════════
"""
        self.create_text_area(parent, content)

    def create_assertion_engine_tab(self, parent):
        content = """
═══════════════════════════════════════════════════════════════════════════════
                              ASSERTION ENGINE
═══════════════════════════════════════════════════════════════════════════════

How each assertion statement is evaluated, and how the 4 "Rule ID" matching
strategies inside SchemaRulesValidator work.

───────────────────────────────────────────────────────────────────────────────
BATCH TESTING — ASSERTION STATEMENTS (utils/asserter/asserter.py)
───────────────────────────────────────────────────────────────────────────────

  assert_no_warnings_or_errors
    Response code must equal "success" ('0'). Nothing else is checked.

  assert_no_errors
    Response code must be "success" or "warning_only". If an error report
    exists, no row may have Type == 'ERROR'.

  assert_error_exists     [Objective starts with fail/warning/notification]
    Full pipeline, in order:
      1. Response code must be in the allowed set for this assertion type.
      2. The error/warning report must not be empty.
      3. SchemaRulesValidator.validate_strategy finds the matching row(s)
         (see the 4 strategies below).
      4. The rule must actually be found (else fail).
      5. Occurrence count must match the Occurrences column, if given.
      6. Object/Element match — only if Assert Object/Element is enabled.
      7. Field Value/Additional Reference match — only if Assert Field/
         Additional is enabled.
      8. Error Text match — only if Assert Error Text is enabled.
    Driven by: Rule ID, Object, Element, Error Text, Field Value, Additional
    Reference, Occurrences columns.

  assert_error_doesnt_exist     [Objective starts with "pass"]
    Response code must be success/warning/failed_with_errors. If a report
    exists, SchemaRulesValidator must NOT find the given Rule ID at all.

  custom_assert     [Objective is anything else]
    Parses the Objective column as a line-based mini-language:
      ErrorCode - {code}                      → response result code == code
      ErrorReport - Col1=Val1;Col2=Val2       → some report row matches all
                                                  given column=value pairs
      Response matches xml template - file.xml→ raw response XML == that
                                                  file under xml_templates/
      No Errors                               → same as assert_no_errors
      Error - {message}                       → response errorMessage ==
                                                  message (processed via
                                                  ErrorTextProcessor)
      (anything else)                         → immediate failure

  Dual-system only — report/row diffing:
    XMLDualAsserter.assert_responses_errors       [Full Report Comparison]
      Compares response codes, error counts, and every row's Type/RuleID/
      Transaction/Object Name/HAAD Field/Field Value/Additional Reference/
      Error Text between System 1 and System 2.
    XMLDualSingleRowAsserter.assert_responses_errors [Full Row Comparison]
      Compares every column of the single matched row between systems.

───────────────────────────────────────────────────────────────────────────────
ASSERTION TESTING — OBJECTIVE STATEMENT SCRIPT (utils/asserter/custom_requests_asserter.py)
───────────────────────────────────────────────────────────────────────────────

  Only usable against the 7 transactions listed on the "Request Flows" tab.
  Objective is a multi-line script — each line is evaluated as one of:

    Found / Retrieved / Transaction Found      → prerequisite transaction ID
      (+ variants)                                appears in the returned
                                                   list; its FileName/
                                                   SenderID/ReceiverID/
                                                   RecordCount/
                                                   TransactionDate/
                                                   TransactionTimestamp/
                                                   IsDownloaded ('False')
                                                   must all match
    New Transaction Found (+ variants)         → same, scoped to
                                                   new_transaction_found
    New Prior Auth Found (+ variants)          → same, scoped to
                                                   prior_auth_found
    Retrieved Downloaded / Found Downloaded    → same field checks, but
                                                   IsDownloaded == 'True'
    Not Found (+ variants)                      → transaction ID must NOT
                                                   appear in the file list
    Report Generated / Report is Generated      → Reconciliation result ==
                                                   '0', errorMessage ==
                                                   'Operation is successful',
                                                   upload/download counts
                                                   exist and are numeric
    ErrorCode - {code}                          → {Request}Result == code
    Error - {message}  (or <none>)               → errorMessage == message
                                                   (or must be absent)
    Downloaded / Request is Downloaded          → decoded file element ==
                                                   the request template XML
    Set Downloaded / Request is Set Downloaded  → SetTransactionDownloaded
                                                   Result == '0', no
                                                   errorMessage
    Element - tag = value                       → extracted XML value ==
      (supports ParentTag[key=val].childTag=value) expected
    File Found - key1=val1;key2=val2            → at least one <File> in
                                                   PersonInsuranceDetails
                                                   matches all filters
    File Not Found - key1=val1;key2=val2        → no <File> matches all
                                                   filters
    (anything else)                             → immediate failure

───────────────────────────────────────────────────────────────────────────────
THE 4 validate_strategy BRANCHES (SchemaRulesValidator)
───────────────────────────────────────────────────────────────────────────────

  Dispatch key = the Rule ID cell (case-insensitive, trimmed):

  1. "schema validation"
     Looks for an ERROR row where Object Name == Transaction ==
     "Schema Validation" and HAAD Field == ''. If another row has an empty
     RuleID with a DIFFERENT Object Name, fails immediately (that row is a
     conflicting generic error, not this schema error).
     Use for: XSD/structural failures, not a specific business rule.

  2. "common types"
     Finds the first ERROR row with an empty RuleID. If that row's Object
     Name is "Schema Validation", fails immediately (it's actually a schema
     error). Otherwise it's accepted.
     Use for: generic/shared validation errors with no specific Rule ID
     (e.g. a shared lookup-code error).

  3. "routine reporting"
     Only matches rows with RuleID == '82', AND only those whose Error Text
     is >= 99.8% similar (whitespace-stripped) to the expected/processed
     text. The highest-similarity qualifying row becomes the match. Requires
     Error Text assertion to be enabled — raises otherwise.
     Use for: informational messages that vary slightly run-to-run (e.g. an
     embedded timestamp) but should still count as the same occurrence.

  4. Any other Rule ID (the normal case — e.g. "1001")
     Collects every row whose Type is ERROR/WARNING/NOTIFICATION (as
     applicable) and whose RuleID matches exactly.
       • If none of Error Text / Field Value / Additional Reference were
         requested → the FIRST matching row is "best" (Rule ID alone
         disambiguates).
       • Otherwise → "best" is the row with the highest COMBINED similarity
         score — the sum of text-similarity across whichever of the three
         criteria were actually requested (each is only added to the score
         if its corresponding Assert flag is on).
       • Occurrence count = every row that EXACTLY equals "best" on
         whichever of those same criteria were requested (exact string
         equality, not similarity — a separate grouping step from picking
         "best").

     Example: Rule ID "1001" appears on 3 rows with slightly different Error
     Text. With Assert Error Text on, the row closest to the expected text
     becomes "best"; only rows sharing that EXACT Error Text count toward
     Occurrences. With Assert Field/Additional also on, both criteria's
     similarity scores are summed to pick "best", and a row must match BOTH
     exactly to count as an occurrence.

  Note: similarity picks the best/representative row; the FINAL pass/fail
  check afterward is always exact-string comparison against every row that's
  supposed to count as an occurrence (assert_text / assert_object_element /
  assert_field_additional). A row can win "best" by similarity and still
  fail the final assertion if it isn't a perfect match.

───────────────────────────────────────────────────────────────────────────────
ERROR TEXT / FIELD VALUE / ADDITIONAL REFERENCE — SOURCING & PROCESSING
───────────────────────────────────────────────────────────────────────────────

  Excel columns: "Error Text", "Field Value", "Additional Reference".

  1. Error Text is read from the test case and is ALWAYS run through
     ErrorTextProcessor (resolving {{CUSTOM...}}/{{TEMPLATE...}}/
     {{PRE_TEMPLATE...}}) regardless of whether Assert Error Text is on —
     but it's only PASSED to SchemaRulesValidator (and thus only affects
     matching/asserting) when Assert Error Text is enabled.

  2. Field Value and Additional Reference are read as optional (default
     empty string) and are ONLY processed through ErrorTextProcessor, and
     only passed to SchemaRulesValidator, when Assert Field/Additional is
     enabled — mirroring Error Text's gating exactly.

  3. Passing None (flag off) for any of the three means that criterion:
       • contributes nothing to the combined-similarity "best" selection
       • is skipped entirely in the exact-match occurrence grouping

  4. After SchemaRulesValidator returns matched_rows, three independent
     final checks run — each still gated by its own flag:
       _assert_error_text_matches        (Assert Error Text)
       _assert_object_element_matches    (Assert Object/Element)
       _assert_field_additional_matches  (Assert Field/Additional)
     These are plain EXACT string comparisons against every row that counts
     as an occurrence — separate from, and stricter than, the similarity
     scoring used to pick "best" earlier.

═══════════════════════════════════════════════════════════════════════════════
"""
        self.create_text_area(parent, content)

    def create_failure_reasons_tab(self, parent):
        content = """
═══════════════════════════════════════════════════════════════════════════════
                              FAILURE REASONS
═══════════════════════════════════════════════════════════════════════════════

Every assertion failure is recorded two ways: a human-readable Allure TAG
(shown in the report UI, used for ADO bug matching — see the "Update QA Bugs"
tab) and a machine-readable "failure_reason" LABEL. Both are set together by
fail_with_tag(tag, reason, message) before pytest.fail() is called.

───────────────────────────────────────────────────────────────────────────────
BATCH TESTING FAILURE TAGS
───────────────────────────────────────────────────────────────────────────────

  System {N} Failure                  (failure_reason: system_{N}_issue)
    The catch-all "something about this system's response is wrong" tag:
    response code not allowed; report empty when a rule was expected; rule
    ID not found; occurrence count mismatch; any generic custom_assert /
    assert_no_errors / error-code / error-message / error-report / xml-
    template failure.

  System {N} Object/Element Failure   (system_{N}_object_element_issue)
    Object Name or HAAD Field mismatch on at least one occurrence. Only
    checked when Assert Object/Element is enabled.

  System {N} Field/Additional Failure (system_{N}_field_additional_issue)
    Field Value or Additional Reference mismatch on at least one occurrence.
    Only checked when Assert Field/Additional is enabled.

  System {N} Error Text Failure       (system_{N}_error_text_issue)
    Actual Error Text differs from expected on at least one occurrence.
    Only checked when Assert Error Text is enabled.

  Dual System Failure                 (dual_system_failure)
    Response codes differ between systems, OR error/field values differ
    (non-text) between matched rows, OR a row exists in one system's report
    but not the other, OR error counts differ between the two reports.

  Dual System Error Text Failure      (dual_system_error_text_failure)
    A row matches across both systems on Type/RuleID/Transaction/Object
    Name/HAAD Field/Field Value/Additional Reference, but the Error Text
    itself differs.

  Dual System Row Failure             (dual_system_row_failure)
    Full Row Comparison mode: any column of the single matched row differs
    between System 1 and System 2.

  Note: assert_no_errors / assert_no_warnings_or_errors currently have their
  tag/label lines commented out in the code — these two specific checks
  pytest.fail() with NO tag at all, unlike every other Batch assertion. They
  will not appear correctly tagged in Allure or match ADO bugs by tag.

───────────────────────────────────────────────────────────────────────────────
ASSERTION TESTING FAILURE TAG
───────────────────────────────────────────────────────────────────────────────

  System 1 Failure                    (system_1_issue)
    Every failure in the search/retrieval statement language (found/not
    found/element/downloaded/set downloaded/report generated/file found/
    file not found/error code/error) tags "System 1 Failure" — this module
    has no per-system tag parameterization, regardless of which system
    actually ran.

───────────────────────────────────────────────────────────────────────────────
WHY THIS MATTERS
───────────────────────────────────────────────────────────────────────────────

  • The Custom Report's failure criteria (see "Custom Report" tab) filter on
    exactly these tags.
  • "Report Failures ADO" groups/fingerprints bugs using these tags.
  • "Update QA Bugs" matches ADO bugs by "Failure Tag" using these same
    strings (see that tab for the special passed-vs-failed handling).

═══════════════════════════════════════════════════════════════════════════════
"""
        self.create_text_area(parent, content)

    def create_update_qa_bugs_tab(self, parent):
        content = """
═══════════════════════════════════════════════════════════════════════════════
                           UPDATE QA BUGS
═══════════════════════════════════════════════════════════════════════════════

"Update QA Bugs" scans the executed test results and matches them against
"Ready for QA" bugs in Azure DevOps. For each matched bug it automatically
updates the bug state and posts a comment with the test result details.

Available via the "Update QA Bugs" button in the Batch Testing, Assertion
Testing, and E2E Flows tabs.

───────────────────────────────────────────────────────────────────────────────
HOW IT WORKS — STEP BY STEP
───────────────────────────────────────────────────────────────────────────────

  1. FIELD SELECTION
     A configuration dialog opens asking which fields to use when matching
     bugs. Only bugs that satisfy ALL selected fields are considered a match.

  2. CREDENTIALS
     You are prompted for your Azure DevOps URL, project name, and PAT.

  3. MATCHING
     For each "Ready for QA" bug in ADO, the tool searches the executed test
     results for a test case that matches on all selected fields.

  4. STATE UPDATE
     ┌───────────────────────────────────┬───────────────────────────────────┐
     │ Matched test case                 │ New bug state                     │
     ├───────────────────────────────────┼───────────────────────────────────┤
     │ passed                            │ Ready for Release                 │
     │ failed, reproduces the bug's      │ Reopened                          │
     │   own failure tag                 │                                   │
     │ failed, with a different failure  │ Ready for Release — only if it's  │
     │   tag that PROVES the bug's own   │ provable the bug's own tracked    │
     │   tracked check passed this run   │ check actually ran and passed     │
     │   (see FAILURE TAG section below) │                                   │
     └───────────────────────────────────┴───────────────────────────────────┘

     A failed test case whose failure tag differs from the bug's but can't be
     proven safe (e.g. the check the bug tracks never got a chance to run) is
     neither reopened nor closed — it's skipped, same as "no failure tag".

  5. COMMENT
     A comment is added to the bug with the test result details.

───────────────────────────────────────────────────────────────────────────────
MATCH FIELDS
───────────────────────────────────────────────────────────────────────────────

  You can match bugs against test cases using any combination of these fields:

  ┌─────────────────┬──────────────────────────────────────────────────────────┐
  │ Field           │ How it matches                                           │
  ├─────────────────┼──────────────────────────────────────────────────────────┤
  │ Transaction     │ The test case's "Transaction Type - X" tag must appear   │
  │ Type            │ in the bug's ADO tags.                                   │
  ├─────────────────┼──────────────────────────────────────────────────────────┤
  │ Rule ID         │ The test case's "RuleId - X" tag must appear in the      │
  │                 │ bug's ADO tags.                                          │
  ├─────────────────┼──────────────────────────────────────────────────────────┤
  │ Scenario Type   │ The test case's "Scenario Type - X" tag must appear in   │
  │                 │ the bug's ADO tags.                                      │
  ├─────────────────┼──────────────────────────────────────────────────────────┤
  │ Object          │ The test case's "Object - X" tag must appear in the      │
  │                 │ bug's ADO tags.                                          │
  ├─────────────────┼──────────────────────────────────────────────────────────┤
  │ Element         │ The test case's "Element - X" tag must appear in the     │
  │                 │ bug's ADO tags.                                          │
  ├─────────────────┼──────────────────────────────────────────────────────────┤
  │ Failure Tag     │ See the dedicated section below — this field has special │
  │                 │ behaviour depending on the test case status.             │
  ├─────────────────┼──────────────────────────────────────────────────────────┤
  │ Bug Title       │ The bug's ADO title must exactly match the test case     │
  │                 │ name (case-insensitive).                                 │
  │                 │ Expected title format:                                   │
  │                 │   "Test Case: {Transaction Type} - {Description}"        │
  └─────────────────┴──────────────────────────────────────────────────────────┘

  IMPORTANT — missing tag behaviour:
    For all tag-based fields (Transaction Type, Rule ID, Scenario Type,
    Object, Element): if the field is selected but the test case has no tag
    for it, the test case is REJECTED and does not match the bug.
    The field is only skipped when it is NOT selected.

───────────────────────────────────────────────────────────────────────────────
FAILURE TAG — SPECIAL BEHAVIOUR
───────────────────────────────────────────────────────────────────────────────

  The Failure Tag field behaves differently from other tag fields because
  passed test cases never carry a failure tag by definition, and a failed
  test case's failure tag doesn't have to match the bug's exactly — it can
  also PROVE the bug's own tracked check passed this run.

  +---------------------------------------+------------------------------------------+
  | Test case                             | Failure Tag check                        |
  +---------------------------------------+------------------------------------------+
  | Passed -- no failure tag              | Check is skipped entirely. The test case |
  |                                        | can still match the bug on other fields. |
  | Failed -- no failure tag              | Skipped -- no comparison possible.       |
  | Failed -- same failure tag as the bug | Reopened. The bug's own issue is still   |
  |                                        | reproducing.                             |
  | Failed -- a DIFFERENT failure tag     | Depends on whether the differing tag     |
  |   than the bug's                      | proves the bug's check ran and passed.   |
  |                                        | See "Different tag" below.               |
  +---------------------------------------+------------------------------------------+

  DIFFERENT TAG -- is it safe to close?
  --------------------------------------
  Some checks only run after an earlier one passes (e.g. the object/element
  check never runs if the response-code check already failed). So a
  test case failing with tag B instead of the bug's tag A only proves A is
  fixed if reaching B's check required A's check to have already passed.
  Otherwise there's no evidence either way, and the bug is left untouched
  (skipped) rather than risk closing an unverified issue.

  System 1 / System 2:
    "System N Failure" (hard) short-circuits before the 3 soft checks
    (Error Text / Object-Element / Field-Additional) ever run.
      - Bug = "System N Failure", TC fails with a soft tag   -> Closed
        (reaching a soft check proves the hard check passed)
      - Bug = a soft tag, TC fails with "System N Failure"   -> Skipped
        (the soft check never ran -- nothing is proven)
      - Bug = a soft tag, TC fails with a DIFFERENT soft tag -> Closed
        (all enabled soft checks run together regardless of one another,
         so the bug's specific soft tag not appearing means it passed)

  Dual System:
    Ordered chain: Dual System Failure -> Dual System Error Text Failure ->
    Dual System Row Failure. Each stage only runs if every earlier stage
    passed, so a differing tag closes the bug only if it's LATER in this
    chain than every one of the bug's own tags -- otherwise it's skipped.

    Dual System Mismatch Failure comes from a separate assertion mode
    (presence comparison) with no proven relationship to the chain above,
    so any mismatch across that boundary is always skipped.

  Example failure tags: "System 2 Failure", "System 1 Failure",
                        "System 2 Error Text Failure", "Dual System Failure"

───────────────────────────────────────────────────────────────────────────────
MULTIPLE MATCHES — PRIORITY RULE
───────────────────────────────────────────────────────────────────────────────

  If more than one test case matches the same bug, a Reopen outcome takes
  priority over a Close outcome.

    → The bug is only closed (Ready for Release) when NO matching test case
      says Reopen.
    → If even one matching test case reproduces the bug's own failure tag,
      the bug is reopened — regardless of other matches that would otherwise
      close it.

  This prevents a bug from being incorrectly closed when the failure is still
  reproducible in another test case.

───────────────────────────────────────────────────────────────────────────────
EXAMPLE SCENARIOS
───────────────────────────────────────────────────────────────────────────────

  Bug in ADO — tags: Object - Payment, Element - Name, System 2 Failure
  Match fields selected: Object, Element, Failure Tag

  +------+--------------+---------------+--------+----------------------------+
  | TC   | Object       | Element       | Status | Outcome                    |
  +------+--------------+---------------+--------+----------------------------+
  | TC-1 | Payment (ok) | Name (ok)     | Failed | Skipped -- no failure      |
  |      |              |               |        |   tag on a failed case     |
  | TC-2 | Payment (ok) | Different (x) | Failed | Skipped -- element tag     |
  |      |              |               |        |   does not match           |
  | TC-3 | Payment (ok) | Name (ok)     | Failed | Reopened -- same failure   |
  |      |              |               |        |   tag as the bug           |
  | TC-4 | Payment (ok) | Name (ok)     | Failed | Closed -- different, but   |
  |      |              |               |        |   provably later, tag      |
  | TC-5 | Payment (ok) | Name (ok)     | Passed | Closed -- failure tag      |
  |      |              |               |        |   check skipped for passed |
  +------+--------------+---------------+--------+----------------------------+

  TC-3 has "System 2 Failure" (same as the bug) — the bug is still
  reproducible, so it's reopened even though TC-4 and TC-5 would each
  close it on their own (see MULTIPLE MATCHES — PRIORITY RULE above).

  TC-4 has "System 2 Object/Element Failure" instead — reaching that soft
  check proves the bug's hard "System 2 Failure" check already passed, so
  on its own it would close the bug.

  If only TC-4 and TC-5 matched (no TC-3), the bug would be set to
  Ready for Release.

═══════════════════════════════════════════════════════════════════════════════
"""
        self.create_text_area(parent, content)

    def create_cicd_tab(self, parent):
        content = """
═══════════════════════════════════════════════════════════════════════════════
                          CI/CD INTEGRATION
═══════════════════════════════════════════════════════════════════════════════

The tool supports fully headless execution — no GUI required. The GUI already
works by setting environment variables and calling:

    python -m pytest utils/allure_wrapper.py --alluredir allure-results

The run_tests.py script in the project root does exactly the same thing from
the command line, making it suitable for any CI/CD pipeline.

───────────────────────────────────────────────────────────────────────────────
QUICK START
───────────────────────────────────────────────────────────────────────────────

  # Install CI dependencies (no GUI packages)
  pip install -r requirements-ci.txt

  # Run tests
  python run_tests.py --excel path/to/tests.xlsx --sheets "Sheet1"

───────────────────────────────────────────────────────────────────────────────
run_tests.py — ALL OPTIONS
───────────────────────────────────────────────────────────────────────────────

  REQUIRED
    --excel      PATH     Path to the Excel test file
    --sheets     TEXT     Comma-separated sheet names  e.g. "Sheet1, Sheet2"

  EXECUTION CONFIG
    --mode       MODE     system1_only | system2_only | both_systems |
                          system1_both_envs       (default: system2_only)
    --sequence   SEQ      single_api | full_scenario  (default: full_scenario)
    --env        ENV      pte | production             (default: pte)
    --new-env    ENV      test | dev | uat | stage      (default: test)

  ASSERTIONS
    --assert-error-text       Enable error text assertion (flag)
    --assert-object-element   Enable object/element assertion (flag)

  FILTERS
    --tc-ids    "TC001,TC002"   Run only these specific TC IDs
    --rule-ids  "R001,R002"    Run only test cases with these Rule IDs

  PARALLELISM
    --parallel              Enable parallel execution via pytest-xdist
    --workers  auto|N       Number of workers  (default: auto)

  REPORTING
    --allure-dir   DIR    Where to write Allure JSON results
                          (default: allure-results)
    --generate-report     Also generate the HTML report after the run
                          (requires the allure CLI to be installed)
    --report-dir   DIR    Output directory for the HTML report
                          (default: allure-report)

───────────────────────────────────────────────────────────────────────────────
EXAMPLES
───────────────────────────────────────────────────────────────────────────────

  Basic run, System 2.0, test environment:
    python run_tests.py \\
      --excel tests/rules.xlsx \\
      --sheets "Sheet1" \\
      --mode system2_only --new-env test --assert-error-text

  Multiple sheets in parallel:
    python run_tests.py \\
      --excel tests/rules.xlsx \\
      --sheets "Sheet1, Sheet2, Sheet3" \\
      --parallel --workers 4

  Filter to specific Rule IDs:
    python run_tests.py \\
      --excel tests/rules.xlsx \\
      --sheets "Sheet1" \\
      --rule-ids "R001,R002,R005"

  Run and generate HTML report:
    python run_tests.py \\
      --excel tests/rules.xlsx \\
      --sheets "Sheet1" \\
      --generate-report --report-dir allure-report

───────────────────────────────────────────────────────────────────────────────
ENVIRONMENT VARIABLES
───────────────────────────────────────────────────────────────────────────────

  run_tests.py translates its arguments into the same environment variables
  the GUI uses. You can also set them directly when calling pytest manually:

  ┌─────────────────────────────┬─────────────────────────────────────────────┐
  │ Environment variable        │ Set by argument                             │
  ├─────────────────────────────┼─────────────────────────────────────────────┤
  │ SOAP_EXCEL_FILE             │ --excel                                     │
  │ EXCEL_FILE_TEST_SHEETS      │ --sheets                                    │
  │ SOAP_EXECUTION_MODE         │ --mode                                      │
  │ SOAP_EXECUTION_SEQUENCE     │ --sequence                                  │
  │ TARGET_ENVIRONMENT          │ --env                                       │
  │ NEW_TARGET_ENVIRONMENT      │ --new-env                                   │
  │ ASSERT_ERROR_TEXT           │ --assert-error-text                         │
  │ ASSERT_OBJECT_ELEMENT       │ --assert-object-element                     │
  │ SPECIFIC_TEST_CASES         │ --tc-ids                                    │
  │ SPECIFIC_RULE_IDS           │ --rule-ids                                  │
  └─────────────────────────────┴─────────────────────────────────────────────┘

  Store sensitive values (endpoint URLs, passwords) as secrets in your CI
  platform. Never commit credentials to the repository.

───────────────────────────────────────────────────────────────────────────────
GENERATING THE HTML REPORT
───────────────────────────────────────────────────────────────────────────────

  Allure results (JSON files in allure-results/) are produced automatically
  by pytest. Converting them to a browsable HTML report requires the separate
  Allure CLI tool:

    npm       →  npm install -g allure-commandline
    Homebrew  →  brew install allure
    Scoop     →  scoop install allure

  Once installed:
    allure generate allure-results -o allure-report --clean
    # Open allure-report/index.html in a browser

  Or pass --generate-report to run_tests.py and it will do this for you.

  In CI pipelines, always run the report generation in a separate step so
  the report is produced even when tests fail.

───────────────────────────────────────────────────────────────────────────────
CI PIPELINE FILES
───────────────────────────────────────────────────────────────────────────────

  Two ready-to-use pipeline configs are included in the repository root:

    .github/workflows/soap-tests.yml   →  GitHub Actions
    azure-pipelines.yml                →  Azure Pipelines (ADO)

  Both pipelines:
    • Install requirements-ci.txt (no GUI packages)
    • Run run_tests.py with configurable parameters
    • Upload allure-results/ as an artifact even when tests fail
    • Generate and upload the HTML report

  SECRETS TO CONFIGURE IN YOUR CI PLATFORM

    SOAP_ENDPOINT_URL      Endpoint URL for the legacy (1.0) system
    SOAP_ENDPOINT_URL_NEW  Endpoint URL for the new (2.0) system
    TEST_EXCEL_FILE        Path to the Excel test file  (variable, not secret)
    TEST_SHEETS            Default sheet names           (variable, not secret)

  GitHub Actions:
    Settings → Secrets and variables → Actions

  Azure Pipelines:
    Pipelines → Library → Variable Groups → soap-test-secrets

───────────────────────────────────────────────────────────────────────────────
EXIT CODES
───────────────────────────────────────────────────────────────────────────────

  run_tests.py exits with pytest's standard codes, which CI platforms read:

    0  →  All tests passed
    1  →  One or more tests failed  (pipeline step marked as failed)
    2  →  Test run was interrupted
    4  →  pytest usage error
    5  →  No tests were collected

═══════════════════════════════════════════════════════════════════════════════
"""
        self.create_text_area(parent, content)

    def create_custom_report_tab(self, parent):
        content = """
═══════════════════════════════════════════════════════════════════════════════
                            CUSTOM REPORT
═══════════════════════════════════════════════════════════════════════════════

The Custom Report is an Excel file generated from the Allure results after a
test run. It lets you slice, filter, and aggregate test outcomes in ways the
standard Allure HTML report does not offer — one configurable sheet per
analysis need, saved as a single .xlsx file.

Available in both Batch Testing and Assertion Testing tabs via the purple
"Generate Custom Report" button.

───────────────────────────────────────────────────────────────────────────────
HOW TO GENERATE
───────────────────────────────────────────────────────────────────────────────

  TWO WAYS to create the report:

  1. DURING A TEST RUN
     After confirming execution, a prompt asks "Do you want to generate a
     custom report?". If you say Yes, the configuration dialog opens before
     the tests start. After the run completes the save dialog appears
     automatically.

  2. FROM THE BUTTON (no re-run needed)
     Click "Generate Custom Report" at any time. If allure-results already
     exists on disk the report is generated immediately from the existing
     data — no need to re-run tests. Useful for changing the view after the
     fact or trying different configurations.

───────────────────────────────────────────────────────────────────────────────
CONFIGURATION DIALOG
───────────────────────────────────────────────────────────────────────────────

  The dialog has three sections:

  ┌─ REPORT SHEETS ──────────────────────────────────────────────────────────┐
  │ Each sheet in the output Excel is configured independently.              │
  │ • Add Sheet   — create a new sheet with a custom name                   │
  │ • Rename      — rename the selected sheet                               │
  │ • Remove      — delete a sheet (at least one must remain)               │
  │ The sheet selected in the list drives the Criteria and Columns sections. │
  └──────────────────────────────────────────────────────────────────────────┘

  ┌─ MONITORING CRITERIA ────────────────────────────────────────────────────┐
  │ Criteria determine which test cases appear on the sheet (OR logic).      │
  │ A test case is included if it matches ANY selected criterion.            │
  │                                                                          │
  │ Criteria options vary by tab:                                            │
  │                                                                          │
  │ BATCH TESTING                          ASSERTION TESTING                 │
  │ ─────────────────────────────          ────────────────────────────────  │
  │ Legacy System Failure                  Legacy System Failure             │
  │ System 2.0 Failure                     Group By Criteria                 │
  │ System 2.0 Error Text Failure          Default Statistics      ─────┐   │
  │ Legacy System Error Text Failure       Transactions Default Stats ──┘   │
  │ System Comparison Failure                                                │
  │ System Comparison Error Text Failure   Note: Assertion testing always   │
  │ Group By Criteria                      tags failures as "Legacy System   │
  │ Default Statistics          ─────┐     Failure" only — there is no       │
  │ Transactions Default Statistics ─┘     system comparison in this tab.   │
  │                                                                          │
  │ EXCLUSIVE CRITERIA (marked with ─┐ above):                              │
  │   "Default Statistics" and "Transactions Default Statistics" are         │
  │   mutually exclusive with all other criteria. Selecting one locks out    │
  │   all others and also locks the Columns section (fixed output columns).  │
  │                                                                          │
  │ SPECIAL CRITERION — "Group By Criteria":                                 │
  │   When enabled, instead of showing one row per test case the sheet       │
  │   groups all matching rows by the selected columns and adds a Count      │
  │   column. Useful for counting failures by Rule ID, sheet name, etc.      │
  │                                                                          │
  │ NO CRITERIA SELECTED:                                                    │
  │   The sheet shows ALL test cases regardless of pass/fail status.         │
  │   A warning is shown before saving to confirm this is intentional.       │
  └──────────────────────────────────────────────────────────────────────────┘

  ┌─ COLUMNS CONFIGURATION ──────────────────────────────────────────────────┐
  │ Choose which columns appear in the sheet.                                │
  │ • Available Columns — all columns you can add                           │
  │ • Selected Columns  — columns that will appear in the output            │
  │ Buttons: Add >, < Remove, Add All >>, << Clear                          │
  │                                                                          │
  │ The column list is locked (greyed out) when an exclusive statistics      │
  │ criterion is selected — those sheets have fixed predefined columns.      │
  └──────────────────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────────────────────
AVAILABLE CRITERIA — WHAT EACH ONE DOES
───────────────────────────────────────────────────────────────────────────────

  Legacy System Failure
    Includes tests that failed due to a System 1 (legacy) issue.
    The asserter tags the test "System 1 Failure" on any assertion failure.

  System 2.0 Failure  [Batch only]
    Includes tests tagged "System 2 Failure".

  Error Text Failure variants  [Batch only]
    Same as above but for tests that failed on error text comparison.
    Only populated when "Assert Error Text" is enabled in Batch Testing.

  System Comparison Failure  [Batch only]
    Includes tests where both systems were compared and a discrepancy was
    found (tagged "Dual System Failure").

  Default Statistics
    Aggregates all test cases by Rule ID. Output columns are fixed:
      Rule ID | Total Cases | Pass Cases | Fail Cases on Old System |
      Fail Cases on New System | Completion %
    One row per Rule ID. Covers all test cases regardless of pass/fail.

  Transactions Default Statistics
    Same aggregation but grouped by Transaction Type (= sheet name).
    Output columns:
      Transaction Type | Total Cases | Pass Cases | Fail Cases on Old System |
      Fail Cases on New System | Completion %
    One row per sheet. Requires tests to have been run across multiple sheets.

  Group By Criteria
    Groups and counts the filtered rows by the columns you selected.
    Output: Count | Col1 | Col2 | ...
    Example: select "Rule ID" to count failures per rule.
    Example: select "Rule ID" + "Test Case Status" to break down by status.

───────────────────────────────────────────────────────────────────────────────
AVAILABLE COLUMNS
───────────────────────────────────────────────────────────────────────────────

  ┌─────────────────────────────┬────────────────────────────────────────────┐
  │ Column                      │ What it contains                           │
  ├─────────────────────────────┼────────────────────────────────────────────┤
  │ Rule ID                     │ Rule ID tag from the test case             │
  │ Test Case Name              │ Full name/ID of the test case              │
  │ Test Case Status            │ passed / failed / skipped / broken         │
  │ Request Content             │ The XML request that was sent              │
  │ Response Content            │ The XML response received (single-system)  │
  │ Response Content Legacy     │ System 1 response  [dual mode, batch only] │
  │ Response Content System 2.0 │ System 2 response  [dual mode, batch only] │
  │ Error Text Difference       │ Error text diff (batch, assert-text only)  │
  └─────────────────────────────┴────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────────────────────
DIFFERENCES: BATCH TESTING vs ASSERTION TESTING
───────────────────────────────────────────────────────────────────────────────

  ┌──────────────────────────┬──────────────────────┬────────────────────────┐
  │ Feature                  │ Batch Testing        │ Assertion Testing      │
  ├──────────────────────────┼──────────────────────┼────────────────────────┤
  │ Failure criteria options │ All 6 criteria       │ Legacy System Failure  │
  │                          │ (per execution mode) │ only                   │
  │ Error Text columns       │ Yes (when enabled)   │ Never                  │
  │ System 2 / Comparison    │ Yes (in dual modes)  │ Never                  │
  │ Transaction Type source  │ Sheet name (auto)    │ Sheet name (auto)      │
  │ Report mode used         │ Actual run mode      │ Always system1_only    │
  └──────────────────────────┴──────────────────────┴────────────────────────┘

───────────────────────────────────────────────────────────────────────────────
MULTIPLE SHEETS IN ONE REPORT — EXAMPLE
───────────────────────────────────────────────────────────────────────────────

  Sheet 1 — "All Failures"
    Criteria: Legacy System Failure
    Columns:  Rule ID, Test Case Name, Test Case Status, Response Content
    → One row per failed test case

  Sheet 2 — "Stats by Rule"
    Criteria: Default Statistics
    → Fixed columns, one row per Rule ID with pass/fail counts

  Sheet 3 — "Stats by Transaction"
    Criteria: Transactions Default Statistics
    → Fixed columns, one row per sheet/transaction type

  Sheet 4 — "Failure Count by Rule"
    Criteria: Legacy System Failure + Group By Criteria
    Columns:  Rule ID
    → Output: Count | Rule ID  (number of failures per rule)

  All sheets are written into a single .xlsx file in one generation.

───────────────────────────────────────────────────────────────────────────────
REGENERATING WITHOUT RE-RUNNING TESTS
───────────────────────────────────────────────────────────────────────────────

  The "Generate Custom Report" button works independently of the test runner.
  As long as the allure-results folder exists on disk you can change the sheet
  configuration, add or remove columns, switch criteria, and save to a new file
  — all without re-running a single test.

  The button uses the allure-results directory from the last run in the current
  session, or falls back to the default "allure-results" folder if no run has
  happened yet in this session.

═══════════════════════════════════════════════════════════════════════════════
"""
        self.create_text_area(parent, content)
