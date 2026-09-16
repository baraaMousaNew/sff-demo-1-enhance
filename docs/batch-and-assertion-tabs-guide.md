# Batch & Assertion Tabs — User Guide

## Overview

| Tab | Purpose |
|-----|---------|
| **Batch** | Validates transaction rules by generating XML from Excel data, posting to APIs, and comparing responses against expected results. Supports multiple transaction types and dual-system comparison. |
| **Assertion** | Validates search transactions by posting data and asserting it can be retrieved via search APIs with the expected content. |

---

## Batch Tab

### 1. Load an Excel File

1. Click **Browse** and select your Excel file.
2. If the file has multiple sheets, a sheet selector appears — choose the target sheet.
3. Click **Load** to display a preview of the data.
4. Use the rows-per-page dropdown (50 / 100 / 200 / 500 / 1000 / All) to control how many rows appear in the preview table.

### 2. Configure Execution

#### Execution Sequence
- **Single API** — Sends only the primary transaction request.
- **Full Scenario** — Runs the complete end-to-end scenario for each test case.

#### Execution Mode
| Option | Description |
|--------|-------------|
| System legacy only | Run against the legacy (1.0) system. |
| System 2.0 only | Run against the 2.0 system. |
| Both Systems | Run against both systems and compare results. |
| Both environments of legacy system | Run against both PTE and Production of the legacy system. |

#### Target Environments
- **1.0 Target Environment** — Select **PTE** or **Production**.
- **2.0 Target Environment** — Select **Test**, **Dev**, **UAT**, or **Stage** (available when a 2.0 mode is selected).

#### Parallel Execution
- Enable the **Parallel Execution** toggle to run test cases concurrently.
- Choose a worker count (**auto**, 2, 3, 4, 6, 8, 10, or 12). Use **auto** unless you have a specific reason to cap concurrency.

#### User Login (Optional)
- Enable the **Specific User Login** checkbox to supply custom credentials.
- Fill in the **Provider**, **Payer**, **TPA**, and/or **Pharmacy** credential fields as needed. These fields are disabled until the checkbox is enabled.

#### Assertion Options
| Option | Effect |
|--------|--------|
| Assert Error Text | Validates that the error message text in the response matches the expected value. |
| Enable Full Report Comparison | Includes a detailed field-by-field report comparison in the results. |
| Full Row Comparison | Compares every field in the response row, not just key fields. |

### 3. Run Tests

1. Click **Run Tests**.
2. Choose a test scope in the dialog that appears:

| Scope | When to use |
|-------|-------------|
| Current Sheet Only | Run the sheet you loaded in the preview. |
| All Sheets in File | Run every sheet in the Excel file sequentially. |
| Selected Sheets | Pick one or more specific sheets from a list. |
| Specific Cases | Enter or select individual TC IDs from the current sheet. |
| By Rule ID | Enter one or more Rule IDs; the tool finds all matching test cases. |

3. Click **Start** in the scope dialog to begin execution. The progress bar and status label update in real time.
4. Click **Stop** at any time to terminate the run cleanly.

### 4. Create a Template

Click **Create Template** to generate a blank Excel template for the selected transaction type. Use this as a starting point for building new test cases.

### 5. Reporting

#### Generate an HTML Report
1. Click **Generate HTML** to build an Allure report from the latest results.
2. Click **Open Last Report** to open the most recently generated report in your browser.
3. Click **Save Report** to archive the current report to a chosen location.

#### Report Failures to Azure DevOps (ADO)
1. Click **Report Failures ADO**.
2. Select which failure tags to include, then preview the failures.
3. Enter your ADO credentials (URL, Personal Access Token, Project, PBI).
4. Review the generated bug list; set priority, severity, and assignee as needed.
5. Enable **Unique Only** to create one bug per unique failure fingerprint and attach duplicates as comments.
6. Click **Submit** to create the bugs in ADO.

#### Update QA Bugs
1. Click **Update QA Bugs** to match the executed test results against existing "Ready for QA" bugs in ADO.
2. Configure the matching criteria and supply ADO credentials.
3. The tool will automatically close passing bugs and reopen failing ones.

#### Was Ever Reported
Click **Was Ever Reported** to find closed ADO bugs that match your current test cases but have no active "Ready for QA" counterpart. Results can be exported to Excel.

---

## Assertion Tab

### 1. Load an Excel File

Follow the same steps as the Batch tab:
1. Click **Browse** → select file.
2. Select a sheet if prompted.
3. Click **Load** to preview data.

### 2. Configure Execution

#### Execution Sequence
- **Single API** — Posts the transaction and asserts the immediate response.
- **Full Scenario** — Posts the transaction and then performs search retrieval assertions.

#### Execution Mode
| Option | Description |
|--------|-------------|
| System legacy (Collect Results) | Run against the legacy system and collect results for comparison. |
| System 2.0 | Run against the 2.0 system. |

- **2.0 Target Environment** (Test / Dev / UAT / Stage) is enabled only when **System 2.0** mode is selected.

#### Parallel Execution
Same as the Batch tab — enable the toggle and select a worker count.

#### User Login (Optional)
Same as the Batch tab — enable the checkbox and fill in credential fields as needed.

### 3. Run Tests

1. Click **Run Tests**.
2. Choose a test scope:

| Scope | When to use |
|-------|-------------|
| Current Sheet Only | Run only the loaded sheet. |
| All Sheets in File | Run every sheet in the file. |
| Selected Sheets | Pick specific sheets from a list. |
| Specific Cases | Select individual TC IDs. |

3. Click **Start** to begin. Monitor progress via the progress bar and status label.
4. Click **Stop** to cancel.

### 4. Create a Template

Click **Create Template** to generate a blank Excel template for assertion test cases.

### 5. Reporting

The Assertion tab offers the same reporting tools as the Batch tab:

- **Generate HTML / Open Last Report / Save Report** — Allure report management (same workflow as Batch).
- **Report Failures ADO** — Create ADO bugs from assertion failures. Fingerprinting is based on transaction type, rule ID, scenario, object, element, failure reason, error text, and bug title.
- **Update QA Bugs** — Sync test results with "Ready for QA" ADO bugs. When using failure tags, you can scope the sync to only assertions that carry a failure tag.
- **Was Ever Reported** — Find closed ADO bugs with no active counterpart.

---

## Tips

- **Pagination** — For large Excel files, set rows-per-page to a smaller value during preview to keep the UI responsive.
- **Worker count** — Start with **auto** for parallel execution. Reduce the worker count if you see API rate-limit errors.
- **Unique Only** (ADO reporting) — Always enable this to avoid filing duplicate bugs for the same root-cause failure.
- **Full Scenario vs. Single API** — Use Full Scenario for end-to-end regression; use Single API when you need a fast sanity check on one specific call.

---

## CI/CD Integration

The tool can run in a fully headless mode without the GUI. The GUI itself already works by setting environment variables and invoking `pytest utils/allure_wrapper.py` internally — `run_tests.py` does exactly the same thing from the command line.

### How it works

```
run_tests.py  →  sets env vars  →  pytest utils/allure_wrapper.py  →  allure-results/
```

No test logic was duplicated. The same `allure_wrapper.py` that the GUI calls is what runs in CI.

---

### Quick start

```bash
# Install CI dependencies (no GUI packages)
pip install -r requirements-ci.txt

# Run tests
python run_tests.py --excel path/to/tests.xlsx --sheets "Sheet1"
```

---

### `run_tests.py` — all options

| Argument | Default | Description |
|---|---|---|
| `--excel` | *(required)* | Path to the Excel test file |
| `--sheets` | *(required)* | Comma-separated sheet names, e.g. `"Sheet1, Sheet2"` |
| `--mode` | `system2_only` | `system1_only` / `system2_only` / `both_systems` / `system1_both_envs` |
| `--sequence` | `full_scenario` | `single_api` / `full_scenario` |
| `--env` | `pte` | Legacy system environment: `pte` / `production` |
| `--new-env` | `test` | New system environment: `test` / `dev` / `uat` / `stage` |
| `--assert-error-text` | off | Enable error text assertion |
| `--assert-object-element` | off | Enable object/element assertion |
| `--tc-ids` | *(none)* | Run only these TC IDs, e.g. `"TC001,TC002"` |
| `--rule-ids` | *(none)* | Run only these Rule IDs, e.g. `"R001,R002"` |
| `--parallel` | off | Enable parallel execution via pytest-xdist |
| `--workers` | `auto` | Worker count: `auto` or a number |
| `--allure-dir` | `allure-results` | Directory to write Allure JSON results |
| `--generate-report` | off | Generate an HTML report after the run (requires Allure CLI) |
| `--report-dir` | `allure-report` | Output directory for the HTML report |

#### Examples

```bash
# Run one sheet, System 2.0, test environment, with error text assertion
python run_tests.py \
  --excel tests/rules.xlsx \
  --sheets "Sheet1" \
  --mode system2_only \
  --new-env test \
  --assert-error-text

# Run multiple sheets in parallel
python run_tests.py \
  --excel tests/rules.xlsx \
  --sheets "Sheet1, Sheet2, Sheet3" \
  --parallel --workers 4

# Filter to specific Rule IDs only
python run_tests.py \
  --excel tests/rules.xlsx \
  --sheets "Sheet1" \
  --rule-ids "R001,R002,R005"

# Run and immediately generate the HTML report
python run_tests.py \
  --excel tests/rules.xlsx \
  --sheets "Sheet1" \
  --generate-report \
  --report-dir allure-report
```

---

### Environment variables

`run_tests.py` translates its arguments into the same environment variables the GUI uses. You can also set them directly if calling pytest without the script:

| Environment variable | Set by argument |
|---|---|
| `SOAP_EXCEL_FILE` | `--excel` |
| `EXCEL_FILE_TEST_SHEETS` | `--sheets` |
| `SOAP_EXECUTION_MODE` | `--mode` |
| `SOAP_EXECUTION_SEQUENCE` | `--sequence` |
| `TARGET_ENVIRONMENT` | `--env` |
| `NEW_TARGET_ENVIRONMENT` | `--new-env` |
| `ASSERT_ERROR_TEXT` | `--assert-error-text` |
| `ASSERT_OBJECT_ELEMENT` | `--assert-object-element` |
| `SPECIFIC_TEST_CASES` | `--tc-ids` |
| `SPECIFIC_RULE_IDS` | `--rule-ids` |

Store sensitive values (endpoint URLs, credentials) as secrets in your CI platform and inject them as environment variables at pipeline runtime — never commit them to the repository.

---

### Generating the HTML report

The Allure **results** (JSON files in `allure-results/`) are generated automatically by pytest. Converting them to a browsable HTML report requires the Allure CLI, which is a separate install:

| Platform | Install command |
|---|---|
| npm | `npm install -g allure-commandline` |
| Homebrew (macOS) | `brew install allure` |
| Scoop (Windows) | `scoop install allure` |

Once installed, generate the report manually:

```bash
allure generate allure-results -o allure-report --clean
# Open allure-report/index.html in a browser
```

Or pass `--generate-report` to `run_tests.py` and it will run the command for you.

In CI pipelines, use a dedicated reporting step or action that runs after the test step so the report is always generated even when tests fail.

---

### CI pipeline files

Two ready-to-use pipeline configs are included in the repository root:

| File | Platform |
|---|---|
| `.github/workflows/soap-tests.yml` | GitHub Actions |
| `azure-pipelines.yml` | Azure Pipelines (ADO) |

Both pipelines:
- Install `requirements-ci.txt` (no GUI packages)
- Run `run_tests.py` with configurable parameters
- Upload `allure-results/` as a pipeline artifact even when tests fail
- Generate and upload the HTML report

#### Configuring secrets

Create the following secrets/variables in your CI platform before running the pipeline:

| Name | What it holds |
|---|---|
| `SOAP_ENDPOINT_URL` | Endpoint URL for the legacy (1.0) system |
| `SOAP_ENDPOINT_URL_NEW` | Endpoint URL for the new (2.0) system |
| `TEST_EXCEL_FILE` | Path to the Excel test file (variable, not secret) |
| `TEST_SHEETS` | Default sheet names (variable, not secret) |

**GitHub Actions:** Settings → Secrets and variables → Actions

**Azure Pipelines:** Pipelines → Library → Variable Groups → `soap-test-secrets`

---

### Exit codes

`run_tests.py` exits with pytest's standard exit codes, which CI platforms interpret automatically:

| Code | Meaning |
|---|---|
| 0 | All tests passed |
| 1 | One or more tests failed |
| 2 | Test run was interrupted |
| 4 | pytest usage error |
| 5 | No tests were collected |

A code of `1` (test failures) will mark the pipeline step as failed, which is the correct behaviour for a regression gate.
