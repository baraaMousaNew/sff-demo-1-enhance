# AI Test Case Generation Guide

This document is meant to be handed to an AI model (as context/system prompt) so it can author new
test cases for this framework. A test case is one row in an Excel sheet; the framework (`pytest` +
`utils/allure_wrapper.py` / `utils/assertion_allure_wrapper.py`) turns each row into a parameterized
test that builds a SOAP XML request, sends it, and asserts on the response. No code needs to be
written to add a test case — only a correctly-formed Excel row.

There are two independent test styles, each with its own Excel schema and runner module:

| Style | Runner module | Purpose |
|---|---|---|
| **Batch** | `utils/allure_wrapper.py` | Post a transaction, assert error-report content (pass/fail/warning/notification, rule IDs). |
| **Assertion** | `utils/assertion_allure_wrapper.py` | Post a transaction, then assert search/retrieval/custom behavior (search transactions, download, reconciliation, etc.), with optional cross-row dependencies. |

Both are driven by the same underlying request-building engine (`utils/request_mapper`,
`utils/template_generator`). Everything below applies to the "Batch" style unless marked
**[Assertion only]**.

---

## 1. How a row becomes a test

1. `run_tests.py` sets environment variables and invokes `pytest utils/allure_wrapper.py` (or
   `assertion_allure_wrapper.py` for assertion runs).
2. `pytest_generate_tests` loads the Excel file/sheet(s) via pandas, turns each row into a dict
   (`NaN` → `''`), and parametrizes one pytest test per row, using the `TC ID` column as the test ID.
3. For each row: `do_requests(test_case['Transaction Type'], test_case['Precondition'])` builds a
   `RequestMapper` subclass instance for that transaction type (see §4), then
   `.do_request(system=..., live_data=test_case['Test Data'])` builds every prerequisite XML request
   in the chain, sends them, builds the final "request under test" (with `Test Data` applied), sends
   it, and returns `(response, template, template_flow)`.
4. The row's `Objective (Expected Result)` column decides which assertion path runs (see §6).

A generated test case therefore needs, at minimum: a valid `Transaction Type` (§4), well-formed
`Test Data` (§5) that will actually trigger the rule/scenario under test, and an `Objective` that
tells the framework what to check for.

---

## 2. Excel schema

### Required columns (Batch — `utils/common_variables.py`)

| Column | Meaning |
|---|---|
| `TC ID` | Unique test case ID, used as the pytest test ID. Convention seen in practice: `TC_<ShortTxnCode>_<RuleNum>_<Seq>`, e.g. `TC_CSub_82_001` (Claim Submission, rule 82, case 1). |
| `Transaction Type` | One of the values in §4 (case-insensitive string, e.g. `Claim Submission`, `Prior Authorization`, `Claim Checker`). |
| `Rule ID` | The business rule identifier the row exercises. Matched against the error-report `RuleID` field on assert. Also filterable via `--rule-ids` / `Rule ID` scope. |
| `Precondition` | Optional. Injects live data into a *prerequisite* step of the transaction chain, or (for search-style transactions) names which prerequisite transaction to run first. See §5.2. Leave blank for a plain chain with no per-step overrides. |
| `Object` | Expected `Object Name` value in the error-report row for this rule (used when `--assert-object-element` is on). |
| `Element` | Expected `HAAD Field` value in the error-report row (used when `--assert-object-element` is on). |
| `Title ` (note trailing space in the template) / `Name` | Human-readable case title/name. `Name` is what shows as the Allure test description. |
| `Description` | Free text describing the case. |
| `Test Data` | The live data applied to the request-under-test XML. See §5.1. This is the main field that defines *what's actually different* about this test case. |
| `Actual Result` | Free text / left blank; filled in manually or by tooling, not consumed by the assertion engine. |
| `Objective (Expected Result)` | Drives which assertion runs. See §6. |
| `Priority` | Free text (e.g. `High`/`Medium`/`Low`). Not consumed by assertion logic; informational only. |
| `Scenario Type` / `ScenarioType` | Conventionally `Positive` or `Negative`. Shown as an Allure tag; not itself asserted. |
| `Error Text` | Expected error/warning/notification text for the rule. Supports `{{TEMPLATE.path}}` / `{{PRE_TEMPLATE.Step.path}}` substitution — see §7. Only checked when `--assert-error-text` is on. |
| `Notes` | Free text, informational. |

### Additional optional columns

| Column | Meaning |
|---|---|
| `Occurrences` | Expected number of times the rule occurs in the error report. If set, the framework does a strict count check and validates **every** matched occurrence's Object/Element/Error Text (not just the first). Leave blank to skip count checking. |
| `Field Value` | Expected `Field Value` cell in the error-report row (checked only when `--assert-field-additional`, i.e. `ASSERT_FIELD_ADDITIONAL=true`). |
| `Additional Reference` | Expected `Additional Reference` cell in the error-report row (same flag as above). |
| `Skip Env 1` | Any non-empty value other than `false`/`no`/`0`/`nan` skips System 1 (legacy) execution in dual/both-envs modes — the test runs against System 2 (or the second env) only. |
| `Raw_XML_<Suffix>` | Raw XML content that gets variable-processed then Base64-encoded and substituted into the main template wherever `{{ENCODED_XML_<Suffix>}}` appears. Used for transactions that embed a whole encoded XML document as a field value. |
| `Variable_Definitions` | Semicolon-separated `name={{FUNCTION()}}` or `name=literal` pairs, declared once and then referenced later in the same row (or a Raw_XML_ column) as `{{VAR.name}}`. |
| `Dependency` / `Dependency Variables` | **[Assertion only]** — see §9. |
| `_sheet_name` | Auto-added by the loader (the sheet the row came from); not something you author. |

### Column presence check

`excel_handler.validate_excel()` requires exactly: `TC ID, Description, Test Data, Rule ID, Name,
Transaction Type, Precondition, Objective (Expected Result), Scenario Type, Error Text` to be
present as headers (values may be blank). The Assertion-tab variant (`validate_assertion_excel`)
drops the `Error Text` requirement. Extra columns beyond these are fine and ignored by validation.

---

## 3. Execution model (how a case gets run, not authored — for context)

- `--mode`: `system1_only` / `system2_only` / `both_systems` (default) / `system1_both_envs` — which
  system(s) the request is sent to. This does not change what you write in the row.
- `--sequence`: `full_scenario` (builds the whole prerequisite chain, real IDs flow between steps) vs
  `single_api` (sends only a self-contained "isolated" template for the transaction under test —
  faster, but only usable when an `_isolated` variant of that transaction exists, see §4).
- `--assert-error-text`, `--assert-object-element` — toggle whether `Error Text` / `Object`+`Element`
  are actually compared, on top of the mandatory Rule ID presence/absence check.

---

## 4. Transaction Type values and their prerequisite chains

`Transaction Type` must match (case-insensitively) one of the values of `RequestsName` in
`utils/template_generator/requests_name_enums.py`. Full authoritative list is in that enum; the most
commonly used ones, and what prerequisite chain each implies, are documented case-by-case in
**`docs/request_mapper_transaction_flows.md`** — read that file for the exact chain (e.g. `claim
checker` implies Person Register → Prior Request → Prior Authorization → Claim Checker) before
writing `Test Data`/`Precondition` for a given transaction, since the chain determines which
`RequestPrefix` values are valid in `Precondition` (§5.2) and which fields even exist to target in
`Test Data`.

Key naming conventions in the enum:
- A transaction name with `_isolated` (e.g. `claim checker isolated`) is the self-contained template
  used only in `single_api` sequence mode — do not put this in `Transaction Type` directly; the
  isolated variant is selected automatically by `--sequence single_api` for transactions that have
  one. Put the plain name (e.g. `claim checker`) in `Transaction Type` regardless of sequence mode.
- Families: `person register*`, `prior request*`, `prior authorization*`, `claim submission*`,
  `claim checker*`, `claim resubmission*`, `remittance advice*`, `cost submission*`,
  `cost resubmission*`, plus non-chained "API-style" transactions (`search transactions`,
  `get new transactions`, `download transaction file`, `set transaction downloaded`,
  `get claim count reconciliation`, `get person insurance history`, `pay for quality`).

---

## 5. Data syntax

### 5.1 `Test Data` (a.k.a. `live_data`) — sets fields on the request-under-test

Format: semicolon-separated `path=value` pairs, applied to the **final** XML template (the request
under test, not the prerequisites — for those, use `Precondition`, §5.2).

```
Claim.Activity.Type=9;Claim.Activity.Code=C1786;Claim.Activity.Net=0
```

**Path syntax**
- Dot-separated element names walking down the XML tree from the root, matching element **local
  names** (namespace-agnostic): `Claim.Activity.Observation.Code`.
- `Element[N]` targets the Nth occurrence of a repeated element at that level, e.g.
  `Claim.Activity[2].ID=...` sets the ID of the 2nd `Activity`.
- Enclosing the whole path in `<...>` (also accepted: `{...}`, `(...)`, `[...]`) switches from
  "set a leaf's text" to "control how many times a repeated element/element group occurs":
  - `<Claim.Activity.Observation>=0` — **delete** that element (occurrence count 0). Used to
    simulate the element being entirely absent, e.g. "No Observation Present".
  - `<Claim.Activity.Diagnosis>=3` — ensure that element occurs 3 times (clones it from a freshly
    generated instance of the same transaction template as needed).
  - `<Claim.Activity.Diagnosis>=1` — asserts the element exists (no-op multiplier).

**Leaf value syntax** (right-hand side of a plain `path=value` pair):
- A literal string/number — used verbatim as the element's text.
- `<empty>` (or `{empty}`/`(empty)`/`[empty]`) — sets the element's text to an explicit empty
  string. Distinct from deleting the element entirely.
- `{{FUNCTION(args)}}` or `{{VAR.name}}` etc. — evaluated through the variable processor, see §5.3.
  Can be embedded inside a larger literal, e.g. `MF3505-{{CUSTOM.generate_numbers_id()}}`.
- Inside a `{{...}}` function call whose args reference the field's own *current* value, the bare
  word `value` is substituted with the current text before evaluation.

**Occurrences of `<Path>=0` vs plain deletion**: use this to test "rule fires when element X is
missing" scenarios — much more common than trying to author a raw XML with the element physically
absent.

### 5.2 `Precondition` — per-step live data for prerequisite steps in the chain

Only meaningful for transactions whose chain has multiple steps and whose `RequestMapper` subclass
supports per-step live data (the "Yes" column in `docs/request_mapper_transaction_flows.md`'s
summary table — the whole `ClaimChecker` family, notably). Format: semicolon-delimited entries,
each `StepPrefix.path=value` (same path/value syntax as §5.1, applied to that *prerequisite* step's
template instead of the final one):

```
PersonRegister.PersonalDetails.FirstName=Ali;PriorRequest.Activity.Net=100
```

- `StepPrefix` is one of the `RequestPrefix` enum values: `PersonRegister`, `PriorRequest`,
  `PriorAuthorization`, `ClaimSubmission`, `RemittanceAdvice`, plus family-specific ones
  (`ClaimChecker`, `ClaimCheckerNoRemittance`, `ClaimCheckerSelfPay`, `RemittanceAdviceTkbk`,
  `CostSubmission`, `PayForQuality`).
- For a step that occurs twice in the same chain (e.g. `PersonCorrectedClaimChecker`'s 2nd
  registration), disambiguate with a `[2]` suffix: `PersonRegister[2].path=value`. A bare
  (unsuffixed) prefix is an alias for `[1]` (the first occurrence).
- Any entry whose prefix doesn't match a step that actually exists in this transaction's chain
  raises an error at request-build time ("Unconsumed precondition entries") — only target steps
  that are actually present per `request_mapper_transaction_flows.md`.
- For the non-chained "API-style" transactions (`search transactions`, `get new transactions`,
  `download transaction file`, etc.), `Precondition` has a *different* meaning: it's a
  newline-delimited list where the **last** line names a prerequisite transaction to run and pull
  identifiers from (e.g. `TransactionID`, `SenderID`) — everything above the last line becomes
  *that* prerequisite transaction's own `Precondition`. Leave `Test Data` on these rows for
  overriding the search/download request itself, not the prerequisite.

### 5.3 Variable functions (usable in `Test Data`, `Precondition`, `Raw_XML_*`, `Variable_Definitions`)

All are `{{...}}`-wrapped. Multiple can appear in one value; evaluated left to right.

**Built-in** (`utils/variable_processor.py::evaluate_builtin_function`):

| Function | Notes |
|---|---|
| `DATE(fmt)` | Current date. `fmt` uses `YYYY`/`MM`/`DD`/`HH`/`mm`/`ss` tokens (default `YYYY-MM-DD`). |
| `DATETIME(fmt)` | Same, default `YYYY-MM-DD HH:mm:ss`. |
| `DATE_ADD(days, fmt)` / `DATE_SUB(days, fmt)` | Date offset from now. |
| `RANDOM(min, max)` | Random int. |
| `RANDOM_DECIMAL(min, max, decimals)` | Random float. |
| `RANDOM_STRING(length, type)` | `type` ∈ `ALPHANUMERIC`/`LETTERS`/`UPPERCASE`/`LOWERCASE`/`DIGITS`. |
| `UUID(style)` | `style='short'` → first UUID segment only. |
| `SEQUENCE(key, start, prefix, fmt)` | Auto-incrementing counter per `key`, scoped to the batch run. |
| `RUN_ID()` | The batch's run ID. |
| `TIMESTAMP()` / `NOW(fmt)` | Current epoch / formatted now. |

**Custom** (`functions/custom_functions.py` — loaded once per worker process; add new ones there if
a generator you need doesn't exist yet). Highlights relevant to authoring healthcare test data:
`generate_numbers_id(prefix, length)`, `generate_claim_id(prefix)`, `generate_person_data(type)`
(type ∈ `phone`/`passport`/`email`/`emirates_id`/`emirates_unified_number`/`member_id`/
`nationality`/`location`/`emirate`/`first_name`/`last_name`), `generate_dob(min_age)` /
`get_dob_for_age(age)`, `get_random_icd_code(is_expired)` / `get_random_icd9_diagnosis_code()` /
`get_random_icd10_diagnosis_code()`, `get_random_cpt_code()` / `get_random_hcpcs_code()` /
`get_random_service_code()` / `get_random_uscls_code()` / `get_random_drg_code()` /
`get_random_loinc()` / `get_random_tooth_numbering()`, `get_random_dha_license()` /
`get_random_moh_license()` / `get_random_haad_license()` / `get_random_ne_facility_license()` /
`get_random_facility_license()` / `get_random_facility_license_number_by_status(status)`,
`get_random_clinician_license()` / `get_clinician_license_starting_with(major, profession,
category)` / `get_clinician_license_containing(...)`, `get_random_denial_code(status)`,
`get_random_encounter_type()`, `get_random_diagnosis_type()`, `get_random_code_type()`,
`get_random_observation_type()`, `add_months_to_current_date(months, days, fmt)` /
`subtract_months_from_current_date(...)`, `get_image_as_base64(image_name)`,
`zip_xml_templates_as_base64(template1, template2)`, `add_to_number(value, amount)` /
`sub_from_number(...)`, `convert_to_uppercase(value)`, `remove_chars(value, n)`. Most of these read
from lookup files under `resources/` (ICD/CPT/HCPCS/DRG/LOINC code lists, license lists, etc.) — use
them instead of hardcoding a plausible-looking code, since hardcoded values may not exist/be active
in the target environment and the rule may depend on that.

**Prefixed forms**:
- `{{VAR.name}}` — read a previously-declared variable (see `Variable_Definitions` column, or a
  `VAR(name).` assignment elsewhere in the same row).
- `{{VAR(name).CUSTOM.func(...)}}` / `{{VAR(name).builtin_func(...)}}` — evaluate and **also**
  store the result under `name` for later `{{VAR.name}}` references later in the same row.
- `{{CUSTOM.func(args)}}` — call a function from `functions/custom_functions.py` directly.
- `{{EXTRACT.name}}` — a value previously extracted from a response (§9, Assertion-tab
  dependency chains only).

---

## 6. `Objective (Expected Result)` — what gets asserted (Batch)

The first word (case-insensitive) selects the assertion path:

| Starts with | Behavior |
|---|---|
| `Pass` | `assert_error_doesnt_exist` — the rule (`Rule ID`) must **not** appear in the response's error report. |
| `Fail` | `assert_error_exists(..., expected_type=ERROR)` — the rule must appear as an **ERROR** row. |
| `Warning` | Same, but `expected_type=WARNING`. |
| `Notification` | Same, but `expected_type=NOTIFICATION` (also tolerates a success response code, since notifications don't flip the overall status). |
| *(anything else)* | Falls through to `custom_assert` — a free-form, line-based mini-DSL (see below). Each non-empty line of `Objective` is evaluated independently; unrecognized lines fail the test. |

`custom_assert` line formats (each is one line inside the `Objective` cell):
- `ErrorCode - <code>` — response's overall error code must equal `<code>`.
- `ErrorReport - Col1=Val1;Col2=Val2` — at least one row in the decoded error report must match all
  given column/value pairs.
- `Response matches xml template - <filename.xml>` — the raw response XML must equal (structurally,
  via `ET.tostring`) the named file under `xml_templates/`.
- `No errors` — response error report must contain no `ERROR`-typed rows.
- `Error - <message>` — the response's `errorMessage` element must equal `<message>` (supports
  `{{TEMPLATE.path}}` substitution from the request template).

When using `Pass`/`Fail`/`Warning`/`Notification`, always also fill in `Rule ID` (required to look
up the row) and — when the relevant CLI flags are enabled — `Error Text`, `Object`, `Element`.

### 6.1 `Objective` for Assertion-tab rows

For `Transaction Type` in the "search/API-style" family (`search transactions`,
`get new prior authorization transactions`, `get new transactions`, `download transaction file`,
`set transaction downloaded`, `get claim count reconciliation`, `get person insurance history`), the
Assertion runner (`utils/assertion_allure_wrapper.py` → `CustomAsserterContext`) recognizes a
different line-based vocabulary instead:
- `Retrieved` / `Found` / `Transaction Found` (and close variants) — assert the prerequisite
  transaction is present in the search/list response, with FileName/SenderID/ReceiverID/
  RecordCount/TransactionDate/Timestamp all matching and `IsDownloaded=False`.
- `Retrieved Downloaded` / `Found Downloaded` — same, but asserts `IsDownloaded=True` and every
  field must match exactly (strict variant).
- `New Transaction Retrieved` / `New Transaction Found` — same shape but for `get new transactions`.
- `New Prior Auth Retrieved` / `New Prior Auth Found` — same shape but for
  `get new prior authorization transactions`.
- `Not Found` / `Not Retrieved` — asserts the prerequisite transaction's ID does **not** appear.
- `Downloaded` — asserts the downloaded file content (base64, decoded) equals the built template.
- `Set Downloaded` — asserts `SetTransactionDownloadedResult` code is `0` with empty error message.
- `Report Generated` — for reconciliation: asserts result code `0`, message `Operation is
  successful`, and that `uploadCount`/`downloadCount` are present and numeric.
- `Element - <tag> = <expected>` — generic single-element equality check against the response;
  `<tag>` also supports `ParentTag[filterChild=filterValue].childTag` filtered lookup.
- `File Found - key1=val1;key2=val2` / `File Not Found - ...` — for
  `get person insurance history`: asserts a `File` entry in `PersonInsuranceDetails` matching (or
  not matching) the given attribute filters exists. Supports `{{TEMPLATE.path}}` in the filter
  values.
- `ErrorCode - <code>` / `Error - <message>` — same idea as the Batch DSL, adapted per-transaction
  (looks up `<TransactionTypeTitleCase>Result` / `errorMessage`).

Any `Transaction Type` **not** in that search/API family falls back to `DefaultTransactionsStrategy`,
which raises for every one of these lines — i.e. plain chained transactions (Person Register, Claim
Submission, etc.) are not valid `Transaction Type` values for Assertion-tab rows.

---

## 7. `Error Text` (and error-message assertions generally) — dynamic value substitution

`Error Text` (and any `Error - ...` / `ErrorReport - ...` custom-assert line, and `File Found -
...` filters) is run through `ErrorTextProcessor`, which resolves:
- `{{TEMPLATE.dot.path}}` — pulls the *actual* value that ended up in the request-under-test XML at
  that path (namespace-agnostic dot path, same as `Test Data` paths, supports `Element[N]`
  ordering) — use this instead of hardcoding a value that's generated dynamically (e.g. a
  `{{CUSTOM...}}`-generated code), so the expected text always matches what was actually sent.
- `{{PRE_TEMPLATE.StepName.dot.path}}` — same, but reaches into a **prerequisite** step's template
  by its flow label (only available when `template_flow` is populated, i.e. full-scenario mode with
  a chain that records step labels).
- `{{CUSTOM.func(...)}}` / any builtin function — evaluated the same as in `Test Data`, with
  `TEMPLATE.`/`PRE_TEMPLATE.` references inside the function's arguments also resolved first.

Example (real, from `docs/example_test_cases_sheet.xlsx`):
```
Activity requires observation data to be presented: IR-DRG Code {{TEMPLATE.Claim.Activity.Code}} must have observation with File code 'Invoice' with proper value and value type.
```

---

## 8. `Scenario Type`, `Priority`, `Rule ID`, `Occurrences` — informational vs. enforced

- `Rule ID` is enforced — it's the key looked up in the decoded error report.
- `Occurrences`, `Object`, `Element`, `Error Text`, `Field Value`, `Additional Reference` are only
  enforced when the corresponding CLI flag/env var is on (`--assert-object-element`,
  `--assert-error-text`, `--assert-field-additional` / `ASSERT_FIELD_ADDITIONAL`), **except**
  `Occurrences`, which is enforced whenever non-blank regardless of flags.
- `Scenario Type` (`Positive`/`Negative`) and `Priority` are Allure tags/metadata only — free text,
  not validated against a fixed list, but keep them consistent for reporting/filtering purposes.

---

## 9. `Dependency` / `Dependency Variables` — chaining Assertion-tab rows

Assertion-tab rows can depend on another row's outcome and reuse values it produced:

- `Dependency` = the `TC ID` of a prerequisite row. If that row is part of the same run and did not
  pass, this row is skipped (not failed). Rows are topologically sorted so dependencies run first.
- `Dependency Variables` on the **prerequisite** row (not the dependent one) declares what to
  extract from its response/template once it passes, one rule per line or `;`-separated:
  - `varName = ElementTag` — first matching element's text from the response.
  - `varName = ParentElement[filterChild=filterValue].extractChild` (supports multiple
    comma-separated filters) — filtered search over repeated elements in the response.
  - `varName = TEMPLATE.dot.path` or `varName = {{TEMPLATE.dot.path}}` — pulled from the request
    template instead of the response.
- The dependent row then references these via `{{EXTRACT.varName}}` inside its own `Test Data` or
  `Objective` (including nested inside function calls, e.g.
  `{{CUSTOM.add_to_number(EXTRACT.download_count, 1)}}`).

---

## 10. Practical checklist for generating a new row

1. Confirm the `Transaction Type` value exists in `RequestsName` (§4) and read its chain in
   `docs/request_mapper_transaction_flows.md`.
2. Decide `Objective`: is this a Pass/Fail/Warning/Notification rule check, or a custom-assert line?
   Fill `Rule ID` accordingly (blank only for pure custom-assert rows that don't reference a rule).
3. Write `Test Data` to actually trigger (or avoid triggering) the condition: pick the exact field
   path(s) per §5.1, use `<Path>=0` to simulate a missing element, use `{{CUSTOM...}}`/other
   functions from real reference data (§5.3) rather than made-up codes/IDs.
4. If the rule targets a prerequisite step's data rather than the final request, use `Precondition`
   with the right `RequestPrefix` (§5.2) — check first that the chain actually has that step.
5. Fill `Object`/`Element`/`Error Text`/`Occurrences`/`Field Value`/`Additional Reference` to match
   what the real system is expected to report for that rule (use `{{TEMPLATE.path}}` for any value
   that was itself dynamically generated in step 3, so the expectation self-updates).
6. Give it a unique, descriptive `TC ID` and a `Name` that documents the scenario (existing sheets
   use `TransactionType | Rule-<id> | <short scenario name>`).
7. Mimic an existing row for the same rule/transaction where possible —
   `docs/example_test_cases_sheet.xlsx` (sheet `Routine-Reporting`) has real examples end to end.

---

## 11. Appendix: XML template field reference

This section documents the actual field shapes under `xml_templates/*.xml` so `Test Data` /
`Precondition` paths can be written without opening each file. **The root element tag itself is
never part of the path** — a path always starts from the root's immediate children (e.g. for
`claim_submission_template.xml`, whose root is `<Claim.Submission>`, a path starts with `Header.` or
`Claim.`, never `Claim.Submission.Header.`).

### 11.1 Domain-style templates (chained transactions: Person Register, Prior Request, Prior
Authorization, Claim Submission/Checker/Resubmission, Remittance Advice, Cost Submission/
Resubmission, Pay for Quality)

Every one of these starts with the same `Header` block:

```
Header.SenderID
Header.ReceiverID
Header.TransactionDate      (default: {{DATE(DD/MM/YYYY)}} HH:mm)
Header.RecordCount
Header.DispositionFlag      (default: PRODUCTION)
```

Root element and main body structure per family (`element*` = repeatable — target a later
occurrence with `Element[2]`, `Element[3]`, ...; nested blocks shown indented):

| Transaction family | Root tag | Body path | Fields (repeatable marked `*`) |
|---|---|---|---|
| Person Register | `Person.Register` | `Person.*` | `UnifiedNumber, FirstName, FirstNameEn, MiddleNameEn, LastNameEn, FirstNameAr, MiddleNameAr, LastNameAr, ContactNumber, BirthDate, Gender, Nationality, NationalityCode, City, CityCode, CountryOfResidence, EmirateOfResidence, PassportNumber, EmiratesIDNumber, SponsorNumber, SponsorNameEn, SponsorNameAr, SpecialNationality, Privileges, COCReferenceNumber, BirthCertificateNumber`, then `Member.ID, Member.Relation, Member.RelationTo, Member.RelationToEmiratesIDNumber, Member.RelationToUnifiedNumber`, then `Member.Contract.PayerID, .TPAID, .PackageName, .StartDate, .RenewalDate, .ExpiryDate, .GrossPremium, .PolicyHolder, .CompanyID, .CollectedPremium, .VAT, .VATPercent, .Status` |
| Prior Request | `Prior.Request` | `Authorization.*` | `Type, ID, MemberID, PayerID, EmiratesIDNumber, DateOrdered`, then `Encounter.FacilityID, .Type, .Start, .End`, then `Diagnosis*.Type, Diagnosis*.Code, Diagnosis*.DxInfo.Type, Diagnosis*.DxInfo.Code`, then `Activity*.ID, .Start, .Type, .Code, .Quantity, .Net, .OrderingClinician, .Clinician`, then `Activity*.Observation*.Type, .Code, .Value, .ValueType` |
| Prior Authorization | `Prior.Authorization` | `Authorization.*` | `Result, ID, IDPayer, DenialCode, Start, End, Limit, Comments`, then `Activity*.ID, .Type, .Code, .Quantity, .Net, .List, .PatientShare, .PaymentAmount, .DenialCode`, then `Activity*.Observation*.Type, .Code, .Value, .ValueType` |
| Claim Submission / Claim Checker / Claim Resubmission (and their `*_multiple*` / `*_no_remittance` / `*_selfpay` / `_to_tpa` / `_HAAD` variants) | `Claim.Submission` | `Claim*.*` (repeatable `Claim` for the `multiple` variants) | `ID, IDPayer, MemberID, PayerID, ProviderID, EmiratesIDNumber, Gross, PatientShare, Net, VAT`, then `Encounter.FacilityID, .Type, .PatientID, .EligibilityIDPayer, .Start, .End, .StartType, .EndType, .TransferSource, .TransferDestination`, then `Diagnosis*.Type, Diagnosis*.Code, Diagnosis*.DxInfo.Type, Diagnosis*.DxInfo.Code`, then `Activity*.ID, .Start, .Type, .Code, .Quantity, .Net, .OrderingClinician, .Clinician, .PriorAuthorizationID, .VAT, .VATPercent, .DateOrdered`, then `Activity*.Observation*.Type, .Code, .Value, .ValueType`, then `Contract.PackageName` |
| Remittance Advice (and `*_tkbk` / `_multiple*` / `_tpa` / `_HAAD_claim` variants) | `Remittance.Advice` | `Claim*.*` | `ID, IDPayer, ProviderID, DenialCode, PaymentReference, DateSettlement`, then `Encounter.FacilityID`, then `Activity*.ID, .Start, .Type, .Code, .Quantity, .Net, .List, .OrderingClinician, .Clinician, .PriorAuthorizationID, .Gross, .PatientShare, .PaymentAmount, .DenialCode` |
| Cost Submission / Cost Resubmission (and `_multiple*` variants) | `Cost.Submission` | `Claim.*` | `ID, ProviderID`, then `Encounter.FacilityID, .ID, .PatientID, .Type, .Start, .End, .StartType, .Specialty, .SubSpecialty, .DRGCode, .EndType`, then `Encounter.Diagnosis.Type, .Code`, then `Encounter.Procedure.Type, .Code, .Duration`, then `Encounter.EDTriageLevel, .OPAttendanceType, .TheatreAttendanceFlag, .CriticalCareTime, .VentilationTime`, then `Encounter.CostBucketDirect.<Allied\|Anaesthesia\|ED\|ICU\|Imaging\|Laboratory\|Physician\|OP\|OR\|Other\|Pharmacy\|Prosthesis\|Supplies\|SPS\|Ward>` (and the same list again under `Encounter.CostBucketOverheads.*`), then `Encounter.CostTypeDetails.<SWNurs\|SWDoc\|SWAllied\|SWNonClin\|Laboratory\|Imaging\|Pharmacy\|Prostheses\|MS\|Hotel\|GS\|Depreciation\|OHF\|OHC\|NABMs>` |

Notes:
- `_isolated` template variants (used automatically under `--sequence single_api`) expose the exact
  same field paths — they're just self-contained (hardcoded/`{{CUSTOM...}}`-generated values instead
  of `{{VAR.xxx}}` references into earlier steps), so `Test Data` written for full-scenario mode
  works unchanged against the isolated variant.
- `*_multiple*` variants (`claim_submission_multiple_template.xml`,
  `claim_submission_multiple_activities_template.xml`, `cost_submission_multiple_template.xml`,
  `remittance_advice_multiple_template.xml`, etc.) simply repeat the `Claim` or `Activity` block
  several times — use `Claim[2].ID=...` / `Activity[3].Code=...` etc. to target a specific one.
- A field left as an empty element in the template (e.g. `<IDPayer></IDPayer>`,
  `<TransferSource></TransferSource>`) is a normal leaf — set it with a plain `path=value` like any
  other field, or `<empty>` to keep it explicitly blank.
- Cross-step linkage: a value generated in an earlier chain step via
  `{{VAR(name).CUSTOM.func()}}` (e.g. `facility_id`, `member_id`, `emirates_id`, `activity_id`,
  `activity_code`, `clinician_license`, `observation_code`, `claim_id`, `id_payer` /
  `remittance_id_payer`, `prior_request_id`) is simply referenced later as `{{VAR.name}}` in a
  downstream step's template. If you need to change one of these system-wide (e.g. force a specific
  `activity_code` across Prior Request → Prior Authorization → Claim Submission), set it via
  `Precondition` on the **step that first generates it** (§5.2), not via `Test Data` on the final
  step alone — otherwise only the final step's own copy changes and earlier steps still send the
  auto-generated value.

### 11.2 SOAP-envelope-style templates (non-chained "API-style" transactions, and any
`*_upload_transaction*` template)

`search_transactions_template.xml`, `get_new_transactions_template.xml`,
`get_new_prior_authorization_transactions.xml`, `download_transaction_file_template.xml`,
`set_transaction_downloaded_template.xml`, `reconciliation.xml`, `get_person_insurance_history.xml`,
and every `upload_transaction_*template.xml` are, unlike the domain-style templates above, the
**full SOAP envelope itself** (root `soapenv:Envelope` → `soapenv:Body` → the request element, e.g.
`v2:SearchTransactions`). Paths for these therefore start with `Body.<RequestElementName>.`, e.g.:

```
Body.SearchTransactions.login=...;Body.SearchTransactions.direction=2
```

(confirmed by `utils/request_sender/send_request.py`, which sets upload-transaction file content via
`Body.UploadTransaction.fileContent=...;Body.UploadTransaction.fileName=...`). Search Transactions'
own fields, for reference: `login, pwd, direction, callerLicense, ePartner, transactionID,
transactionStatus, transactionFileName, transactionFromDate, transactionToDate, minRecordCount,
maxRecordCount`. In practice these rows are populated automatically from the prerequisite
transaction named in `Precondition` (§5.2) — `Test Data` is only needed to override a specific field
on top of that.

### 11.3 Finding the exact fields for a template not listed above

For any `Transaction Type` not covered by name in §11.1/§11.2 (e.g. a specific
`prior_authorization_prescription`/`_cancellation`/`_extension`/`_eligibility` variant, or a
`*_to_tpa` variant), open the matching file directly under `xml_templates/` — the naming pattern is
`<snake_case_of_transaction_type>_template.xml` (add `_isolated` for the isolated variant). The
structure will match the closest family above with only minor field differences for that variant.

---

## 12. Where things live (for cross-referencing while generating data)

- `docs/request_mapper_transaction_flows.md` — prerequisite chain per `Transaction Type`.
- `docs/example_test_cases_sheet.xlsx` — real worked rows to imitate.
- `docs/batch-and-assertion-tabs-guide.md` — GUI/CLI operational guide (how to actually *run* what
  you generate).
- `functions/custom_functions.py` — every `{{CUSTOM.*}}` function and the `resources/*.xlsx|csv`
  reference data files backing them.
- `utils/template_generator/requests_name_enums.py` — authoritative `Transaction Type` value list.
- `xml_templates/` — the actual XML templates each transaction builds from, useful to see which
  field paths exist at all for a given transaction.
