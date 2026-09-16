# SOAP API Test Framework — CLI Guide

Headless runner for the SOAP API test suite. Designed for CI/CD pipelines and local execution without the GUI.

---

## Prerequisites

- Python 3.11+
- Allure CLI — bundled at `dist/allure/bin/allure.bat` (used automatically); only needed separately for HTML report generation outside the packaged app

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

# 2. Install CI dependencies (no GUI packages)
pip install -r requirements-ci.txt
```

---

## Running Tests

```bash
python run_tests.py --excel "Test Cases SFF - Automation.xlsx" --sheets "Smoke-Run" --mode both_systems --env production --new-env test --sequence single_api --generate-report
```

Place the Excel file in the project root, or provide the full path to it.

---

## All Options

| Argument | Default | Description |
|---|---|---|
| `--excel` | *(required)* | Path to the Excel test file |
| `--sheets` | *(required)* | Comma-separated sheet names |
| `--mode` | `system2_only` | `system1_only` / `system2_only` / `both_systems` / `system1_both_envs` |
| `--sequence` | `full_scenario` | `single_api` / `full_scenario` |
| `--env` | `pte` | Legacy (1.0) environment: `pte` / `production` |
| `--new-env` | `test` | New (2.0) environment: `test` / `dev` / `uat` / `stage` |
| `--assert-error-text` | off | Assert error message text in response |
| `--assert-object-element` | off | Assert object/element presence |
| `--tc-ids` | *(none)* | Run only these TC IDs, e.g. `"TC001,TC002"` |
| `--rule-ids` | *(none)* | Run only these Rule IDs, e.g. `"R001,R002"` |
| `--parallel` | off | Enable parallel execution via pytest-xdist |
| `--workers` | `auto` | Worker count: `auto` or a number |
| `--allure-dir` | `allure-results` | Directory to write Allure JSON results |
| `--generate-report` | off | Generate HTML report after the run |
| `--report-dir` | `allure-report` | Output directory for the HTML report |

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | All tests passed |
| 1 | One or more tests failed |
| 2 | Run interrupted |
| 4 | pytest usage error |
| 5 | No tests collected |

CI platforms treat exit code `1` as a failed step — correct behaviour for a regression gate.

---

## Reports

Allure JSON results are written to `allure-results/` automatically during the run.

**Generate HTML report locally:**

```bash
# Via the runner flag (uses bundled allure CLI automatically)
python run_tests.py --excel "Test Cases SFF - Automation.xlsx" --sheets "Smoke-Run" ... --generate-report

# Or manually
dist\allure\bin\allure.bat generate allure-results -o allure-report --clean
# Then open allure-report/index.html in a browser
```

**Serve the report locally (recommended viewer — avoids browser file:// restrictions):**

```bash
dist\allure\bin\allure.bat serve allure-results
```

This starts a temporary local server and opens the report in your browser automatically. Use this after running tests locally, or after downloading the `allure-results` artifact from a CI pipeline run.

> `allure serve` is for **local viewing only** — CI pipelines use `allure generate` and upload the output as a downloadable artifact.

---

## CI/CD

Two pipeline configs are included in the repo root:

| File | Platform |
|---|---|
| `.github/workflows/soap-tests.yml` | GitHub Actions |
| `azure-pipelines.yml` | Azure Pipelines (ADO) |

Both install `requirements-ci.txt`, run `run_tests.py`, and upload `allure-results/` as a pipeline artifact even on test failure.

### Required secrets / variables

Set these in your CI platform before running:

| Name | Type | Description |
|---|---|---|
| `SOAP_ENDPOINT_URL` | Secret | Endpoint URL for the legacy (1.0) system |
| `SOAP_ENDPOINT_URL_NEW` | Secret | Endpoint URL for the new (2.0) system |
| `TEST_EXCEL_FILE` | Variable | Path to the Excel test file |
| `TEST_SHEETS` | Variable | Default sheet names |

**GitHub Actions:** Settings → Secrets and variables → Actions

**Azure Pipelines:** Pipelines → Library → Variable Groups → `soap-test-secrets`

> The SOAP API endpoints are on a private internal network. Use a **self-hosted runner** with network access to those endpoints.

---

## Project Structure (relevant files)

```
run_tests.py              # CLI entry point
requirements-ci.txt       # Dependencies for headless/CI use
utils/allure_wrapper.py   # pytest module (the actual test logic)
dist/allure/bin/          # Bundled Allure CLI
dist/jre/                 # Bundled JRE (used by Allure CLI)
.github/workflows/        # GitHub Actions pipeline
azure-pipelines.yml       # Azure Pipelines config
docs/                     # Full user guide
```
