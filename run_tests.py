"""
Headless CLI runner for SOAP API tests (CI/CD mode).
Mirrors the environment variables the GUI sets before launching pytest.

Usage:
    python run_tests.py --excel path/to/tests.xlsx --sheets "Sheet1, Sheet2"
    python run_tests.py --excel tests.xlsx --sheets "Sheet1" --mode system2_only --new-env test
    python run_tests.py --excel tests.xlsx --sheets "Sheet1" --parallel --workers 4
    python run_tests.py --excel tests.xlsx --sheets "Sheet1" --rule-ids "R001,R002"
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from utils.env_vars import EnvVar
from utils.execution_mode import ExecutionMode


def parse_args():
    parser = argparse.ArgumentParser(
        description="SOAP API Test Runner — headless CI/CD mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Required
    parser.add_argument("--excel", required=True,
                        help="Path to the Excel test file")
    parser.add_argument("--sheets", required=True,
                        help="Comma-separated sheet names (e.g. \"Sheet1, Sheet2\")")

    # Execution config
    parser.add_argument("--mode", default=ExecutionMode.SYSTEM2_ONLY,
                        choices=[ExecutionMode.SYSTEM1_ONLY, ExecutionMode.SYSTEM2_ONLY,
                                 ExecutionMode.BOTH_SYSTEMS, ExecutionMode.SYSTEM1_BOTH_ENVS],
                        help="Execution mode (default: system2_only)")
    parser.add_argument("--sequence", default="full_scenario",
                        choices=["single_api", "full_scenario"],
                        help="Execution sequence (default: full_scenario)")
    parser.add_argument("--env", default="pte",
                        choices=["pte", "production"],
                        help="Legacy system target environment (default: pte)")
    parser.add_argument("--new-env", default="test",
                        choices=["test", "dev", "uat", "stage"],
                        help="New system target environment (default: test)")

    # Assertions
    parser.add_argument("--assert-error-text", action="store_true",
                        help="Enable error text assertion")
    parser.add_argument("--assert-object-element", action="store_true",
                        help="Enable object/element assertion")
    parser.add_argument("--assert-field-additional", action="store_true",
                        help="Enable field value/additional reference assertion")

    # Filters
    parser.add_argument("--tc-ids", default=None,
                        help="Run only these TC IDs (comma-separated, e.g. \"TC001,TC002\")")
    parser.add_argument("--rule-ids", default=None,
                        help="Run only these Rule IDs (comma-separated, e.g. \"R001,R002\")")

    # Parallelism
    parser.add_argument("--parallel", action="store_true",
                        help="Enable parallel test execution via pytest-xdist")
    parser.add_argument("--workers", default="auto",
                        help="Worker count for parallel mode: auto or a number (default: auto)")

    # Reporting
    parser.add_argument("--allure-dir", default="allure-results",
                        help="Directory to write Allure JSON results (default: allure-results)")
    parser.add_argument("--generate-report", action="store_true",
                        help="Generate HTML report after tests using the allure CLI")
    parser.add_argument("--report-dir", default="allure-report",
                        help="Directory for the generated HTML report (default: allure-report)")

    return parser.parse_args()


def set_env(args):
    """Set the same environment variables the GUI sets before launching pytest."""
    os.environ[EnvVar.SOAP_EXCEL_FILE] = args.excel
    os.environ[EnvVar.EXCEL_FILE_TEST_SHEETS] = args.sheets
    os.environ[EnvVar.SOAP_EXECUTION_MODE] = args.mode
    os.environ[EnvVar.SOAP_EXECUTION_SEQUENCE] = args.sequence
    os.environ[EnvVar.TARGET_ENVIRONMENT] = args.env
    os.environ[EnvVar.NEW_TARGET_ENVIRONMENT] = args.new_env
    os.environ[EnvVar.ASSERT_ERROR_TEXT] = "true" if args.assert_error_text else "false"
    os.environ[EnvVar.ASSERT_OBJECT_ELEMENT] = "true" if args.assert_object_element else "false"
    os.environ[EnvVar.ASSERT_FIELD_ADDITIONAL] = "true" if args.assert_field_additional else "false"
    os.environ[EnvVar.FULL_REPORT_COMPARISON] = "false"
    os.environ[EnvVar.FULL_ROW_COMPARISON] = "false"
    os.environ[EnvVar.SOAP_GENERATE_RULES_SUMMARY] = "false"
    os.environ[EnvVar.SOAP_GENERATE_LEGACY_RULES_SUMMARY] = "false"
    os.environ[EnvVar.SOAP_GENERATE_SYSTEM_RULES_SUMMARY] = "false"

    if args.tc_ids:
        os.environ[EnvVar.SPECIFIC_TEST_CASES] = args.tc_ids
    if args.rule_ids:
        os.environ[EnvVar.SPECIFIC_RULE_IDS] = args.rule_ids


def build_pytest_cmd(args, project_root):
    wrapper = project_root / "utils" / "allure_wrapper.py"
    cmd = [
        sys.executable, "-m", "pytest",
        str(wrapper),
        "--alluredir", args.allure_dir,
        "--tb=short", "-v",
    ]
    if args.parallel:
        cmd.extend(["-n", args.workers])
    return cmd


def find_allure_executable(project_root):
    """Mirror the GUI's _find_allure_executable logic.
    Checks the bundled allure in dist/allure/bin/ first, then falls back to PATH.
    """
    import shutil
    bundled = project_root / "dist" / "allure" / "bin" / "allure.bat"
    if bundled.exists():
        jre = project_root / "dist" / "jre"
        if jre.exists():
            os.environ["JAVA_HOME"] = str(jre)
        return str(bundled)
    for name in ("allure", "allure.bat", "allure.cmd"):
        path = shutil.which(name)
        if path:
            return path
    return None


def generate_html_report(results_dir, report_dir, project_root):
    allure_cmd = find_allure_executable(project_root)
    if not allure_cmd:
        print("\nWarning: 'allure' CLI not found — skipping HTML generation.")
        print("It is bundled in dist/allure/bin/ when using the packaged app.")
        print("For standalone use, install via: scoop install allure  (or npm/brew).")
        return
    try:
        subprocess.run(
            [allure_cmd, "generate", results_dir, "-o", report_dir, "--clean"],
            check=True,
        )
        print(f"\nAllure HTML report: {Path(report_dir).resolve() / 'index.html'}")
    except subprocess.CalledProcessError as e:
        print(f"\nWarning: allure report generation failed: {e}")


def main():
    args = parse_args()

    if not Path(args.excel).exists():
        print(f"Error: Excel file not found: {args.excel}")
        sys.exit(2)

    set_env(args)

    project_root = Path(__file__).resolve().parent
    cmd = build_pytest_cmd(args, project_root)

    print("=" * 60)
    print(f"Excel file : {args.excel}")
    print(f"Sheets     : {args.sheets}")
    print(f"Mode       : {args.mode}")
    print(f"Env (1.0)  : {args.env}")
    print(f"Env (2.0)  : {args.new_env}")
    print(f"Parallel   : {args.parallel} (workers={args.workers})")
    print(f"Allure dir : {args.allure_dir}")
    print("=" * 60)

    result = subprocess.run(cmd, cwd=str(project_root))

    if args.generate_report:
        generate_html_report(args.allure_dir, args.report_dir, project_root)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
