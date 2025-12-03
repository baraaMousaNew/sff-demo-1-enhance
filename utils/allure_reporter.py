"""
Allure Reporter - Integration layer for SOAP API test reporting
Enhanced with response extraction support
"""

import allure
import json
import os
from datetime import datetime
from pathlib import Path


class AllureReporter:
    def __init__(self, results_dir="allure-results"):
        self.results_dir = results_dir
        self.current_test_id = None
        self.ensure_results_dir()

    def ensure_results_dir(self):
        """Create allure results directory if it doesn't exist"""
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)

    def start_test_case(self, test_id, description="", test_type="dual_system"):
        """Start a new test case with Allure annotations"""
        self.current_test_id = test_id

        # Set dynamic properties
        allure.dynamic.title(f"Test Case: {description}")
        allure.dynamic.description(description or f"Dual-system regression test for {test_id}")
        allure.dynamic.tag("soap_api")
        allure.dynamic.tag("regression_test")
        allure.dynamic.tag(test_type)

        # Add test metadata
        allure.dynamic.label("framework", "custom_soap_tester")
        allure.dynamic.label("layer", "integration")

        with allure.step(f"Initializing test case {test_id}"):
            allure.attach(
                f"Test ID: {test_id}\nDescription: {description}\nTimestamp: {datetime.now()}",
                "Test Initialization",
                allure.attachment_type.TEXT
            )

    def add_test_case_step(self, step_num):
        with allure.step(f"Step #{step_num}"):
            allure.attach(
                "Starting New Step",
                f"Starting step number #{step_num}",
                allure.attachment_type.TEXT
            )

    def add_step(self, step_name, step_content):
        with allure.step(step_name):
            allure.attach(
                step_content,
                name=step_name,
                attachment_type=allure.attachment_type.TEXT
            )

    def add_attachment(self, attachment_title, attachment_content):
        allure.attach(
            attachment_content,
            name=attachment_title,
            attachment_type=allure.attachment_type.TEXT
        )

    def add_variable_processing_step(self, original_xml, processed_xml, variables_defined=None):
        """Add variable processing as an Allure step"""
        with allure.step("Variable Processing & XML Transformation"):
            # Attach original XML
            allure.attach(
                original_xml,
                "Original XML (with variables)",
                allure.attachment_type.XML
            )

            # Attach processed XML
            allure.attach(
                processed_xml,
                "Processed XML (variables resolved)",
                allure.attachment_type.XML
            )

            # Attach variable definitions if provided
            if variables_defined:
                allure.attach(
                    json.dumps(variables_defined, indent=2),
                    "Variables Defined",
                    allure.attachment_type.JSON
                )

    def add_encoding_step(self, raw_xml_sections):
        """Add Raw XML encoding step"""
        if not raw_xml_sections:
            return

        with allure.step("Raw XML Encoding (Base64)"):
            for section_name, content in raw_xml_sections.items():
                if content.get_template_request('original'):
                    allure.attach(
                        content['original'],
                        f"Raw XML - {section_name} (Original)",
                        allure.attachment_type.XML
                    )

                if content.get_template_request('processed'):
                    allure.attach(
                        content['processed'],
                        f"Raw XML - {section_name} (Processed)",
                        allure.attachment_type.XML
                    )

                if content.get_template_request('encoded'):
                    allure.attach(
                        content['encoded'][:500] + "..." if len(content['encoded']) > 500 else content['encoded'],
                        f"Raw XML - {section_name} (Base64 Encoded - Preview)",
                        allure.attachment_type.TEXT
                    )

    def add_system_execution(self, system_name, request_data, response_data, execution_mode="dual_system", extracted_variables=None):
        """Add system execution as an Allure step with response extraction details"""
        step_title = f"{system_name} Execution"
        if execution_mode == "system1_only":
            step_title += " (Baseline Collection)"
        elif execution_mode == "both_systems":
            step_title += " (Regression Testing)"

        with allure.step(step_title):
            # Request details
            allure.attach(
                json.dumps(request_data.get_template_request('headers', {}), indent=2),
                f"{system_name} - Request Headers",
                allure.attachment_type.JSON
            )

            allure.attach(
                request_data.get_template_request('xml_body', 'No XML body available'),
                f"{system_name} - Request XML",
                allure.attachment_type.XML
            )

            allure.attach(
                request_data.get_template_request('url', 'No URL available'),
                f"{system_name} - Endpoint URL",
                allure.attachment_type.TEXT
            )

            # Response details
            allure.attach(
                json.dumps({
                    'status_code': response_data.get_template_request('status_code'),
                    'response_time': f"{response_data.get_template_request('response_time', 0):.2f}ms",
                    'timestamp': response_data.get_template_request('timestamp'),
                    'success': response_data.get_template_request('success')
                }, indent=2),
                f"{system_name} - Response Metadata",
                allure.attachment_type.JSON
            )

            allure.attach(
                response_data.get_template_request('content', 'No response content'),
                f"{system_name} - Response XML",
                allure.attachment_type.XML
            )

            # Add response headers if available
            if response_data.get_template_request('response_headers'):
                allure.attach(
                    json.dumps(dict(response_data['response_headers']), indent=2),
                    f"{system_name} - Response Headers",
                    allure.attachment_type.JSON
                )

            # Add response extraction details if variables were extracted
            if extracted_variables:
                self.add_response_extraction_details(system_name, extracted_variables, response_data.get_template_request('content', ''))

    def add_response_extraction_details(self, system_name, extracted_variables, response_content):
        """Add response extraction details as a sub-step"""
        if not extracted_variables:
            return

        with allure.step(f"{system_name} - Response Value Extraction"):
            # Summary of extracted variables
            extraction_summary = {
                'extracted_count': len(extracted_variables),
                'variables': extracted_variables
            }

            allure.attach(
                json.dumps(extraction_summary, indent=2),
                f"{system_name} - Extraction Summary",
                allure.attachment_type.JSON
            )

            # Detailed extraction information
            extraction_details = f"Response Extraction Results for {system_name}:\n\n"
            extraction_details += f"Total variables extracted: {len(extracted_variables)}\n\n"

            for var_name, var_value in extracted_variables.items():
                extraction_details += f"Variable: {var_name}\n"
                extraction_details += f"Value: {var_value}\n"
                extraction_details += f"Available as: {{{{EXTRACT.{var_name}}}}}\n"
                extraction_details += "-" * 40 + "\n"

            if extracted_variables:
                extraction_details += f"\nThese variables can be used in subsequent test steps using the {{{{EXTRACT.variable_name}}}} syntax.\n"
                extraction_details += f"Variables persist within the current test case but reset for new test cases.\n"

            allure.attach(
                extraction_details,
                f"{system_name} - Extraction Details",
                allure.attachment_type.TEXT
            )

            # Show relevant parts of response that were extracted from
            if response_content:
                # Try to highlight the extracted portions in the response
                highlighted_response = self._highlight_extracted_values(response_content, extracted_variables)
                allure.attach(
                    highlighted_response,
                    f"{system_name} - Response with Extraction Highlights",
                    allure.attachment_type.TEXT
                )

    def _highlight_extracted_values(self, response_content, extracted_variables):
        """Highlight extracted values in the response content for better visualization"""
        highlighted = response_content

        try:
            # Add markers around values that were extracted
            for var_name, var_value in extracted_variables.items():
                if var_value and str(var_value).strip():
                    # Try to find and highlight the value in the response
                    value_str = str(var_value)
                    if value_str in response_content:
                        highlighted = highlighted.replace(
                            value_str,
                            f">>> {value_str} <<< [EXTRACTED AS: {var_name}]"
                        )

            # Add header explaining the highlighting
            header = "RESPONSE WITH EXTRACTION HIGHLIGHTS\n"
            header += "=" * 50 + "\n"
            header += ">>> value <<< [EXTRACTED AS: variable_name] - indicates extracted values\n\n"

            return header + highlighted

        except Exception as e:
            # If highlighting fails, return original with note
            return f"Original Response (highlighting failed: {str(e)}):\n\n{response_content}"

    def add_extraction_comparison_step(self, system1_extracted, system2_extracted):
        """Add comparison of extracted variables between systems"""
        if not system1_extracted and not system2_extracted:
            return

        with allure.step("Response Extraction Comparison"):
            # Compare extracted variables
            comparison_result = self._compare_extracted_variables(system1_extracted, system2_extracted)

            allure.attach(
                json.dumps(comparison_result, indent=2),
                "Extraction Comparison Summary",
                allure.attachment_type.JSON
            )

            # Detailed comparison report
            comparison_details = "RESPONSE EXTRACTION COMPARISON REPORT\n"
            comparison_details += "=" * 50 + "\n\n"

            comparison_details += f"System 1 extracted {len(system1_extracted)} variables\n"
            comparison_details += f"System 2 extracted {len(system2_extracted)} variables\n\n"

            # Show matching variables
            if comparison_result['matching_variables']:
                comparison_details += "MATCHING EXTRACTIONS:\n"
                for var_name in comparison_result['matching_variables']:
                    sys1_val = system1_extracted.get_template_request(var_name, 'N/A')
                    sys2_val = system2_extracted.get_template_request(var_name, 'N/A')
                    match_status = "✓ MATCH" if sys1_val == sys2_val else "✗ DIFFERENT VALUES"
                    comparison_details += f"  {var_name}: {match_status}\n"
                    comparison_details += f"    System 1: {sys1_val}\n"
                    comparison_details += f"    System 2: {sys2_val}\n\n"

            # Show variables only in System 1
            if comparison_result['only_in_system1']:
                comparison_details += "ONLY IN SYSTEM 1:\n"
                for var_name in comparison_result['only_in_system1']:
                    comparison_details += f"  {var_name}: {system1_extracted[var_name]}\n"
                comparison_details += "\n"

            # Show variables only in System 2
            if comparison_result['only_in_system2']:
                comparison_details += "ONLY IN SYSTEM 2:\n"
                for var_name in comparison_result['only_in_system2']:
                    comparison_details += f"  {var_name}: {system2_extracted[var_name]}\n"
                comparison_details += "\n"

            # Overall assessment
            comparison_details += "ASSESSMENT:\n"
            if comparison_result['identical']:
                comparison_details += "✓ Both systems extracted identical variables and values\n"
            elif comparison_result['same_variables_different_values']:
                comparison_details += "⚠ Same variables extracted but with different values\n"
            elif comparison_result['different_variables']:
                comparison_details += "✗ Different variables extracted between systems\n"
            else:
                comparison_details += "? Mixed results - manual review recommended\n"

            allure.attach(
                comparison_details,
                "Detailed Extraction Comparison",
                allure.attachment_type.TEXT
            )

    def _compare_extracted_variables(self, system1_extracted, system2_extracted):
        """Compare extracted variables between two systems"""
        system1_vars = set(system1_extracted.keys()) if system1_extracted else set()
        system2_vars = set(system2_extracted.keys()) if system2_extracted else set()

        matching_variables = system1_vars.intersection(system2_vars)
        only_in_system1 = system1_vars - system2_vars
        only_in_system2 = system2_vars - system1_vars

        # Check if values match for common variables
        value_matches = 0
        value_differences = 0
        for var_name in matching_variables:
            if system1_extracted.get_template_request(var_name) == system2_extracted.get_template_request(var_name):
                value_matches += 1
            else:
                value_differences += 1

        return {
            'matching_variables': list(matching_variables),
            'only_in_system1': list(only_in_system1),
            'only_in_system2': list(only_in_system2),
            'value_matches': value_matches,
            'value_differences': value_differences,
            'identical': (
                len(system1_vars) == len(system2_vars) and
                len(matching_variables) == len(system1_vars) and
                value_differences == 0
            ),
            'same_variables_different_values': (
                len(only_in_system1) == 0 and
                len(only_in_system2) == 0 and
                value_differences > 0
            ),
            'different_variables': (
                len(only_in_system1) > 0 or
                len(only_in_system2) > 0
            )
        }

    def add_error_extraction_step(self, system_name, errors_found, error_report_base64=None):
        """Add error extraction and parsing step"""
        with allure.step(f"{system_name} - Error Analysis"):
            if errors_found:
                # Format errors for display
                error_summary = self.format_errors_for_display(errors_found)
                allure.attach(
                    error_summary,
                    f"{system_name} - Extracted Errors",
                    allure.attachment_type.TEXT
                )

                # Attach errors as JSON for detailed analysis
                # allure.attach(
                #     json.dumps(errors_found, indent=2),
                #     f"{system_name} - Errors (JSON)",
                #     allure.attachment_type.JSON
                # )
            else:
                allure.attach(
                    "No errors found in response",
                    f"{system_name} - Error Status",
                    allure.attachment_type.TEXT
                )

            # Attach raw error report if available
            if error_report_base64:
                allure.attach(
                    error_report_base64[:1000] + "..." if len(error_report_base64) > 1000 else error_report_base64,
                    f"{system_name} - Raw Error Report (Base64 Preview)",
                    allure.attachment_type.TEXT
                )

    def add_regression_comparison_step(self, comparison_result):
        """Add regression comparison as final step"""
        with allure.step("Regression Analysis & Comparison"):
            # Overall comparison result
            comparison_summary = {
                'regression_status': comparison_result.get_template_request('regression_status'),
                'summary': comparison_result.get_template_request('summary'),
                'error_match_rate': comparison_result.get_template_request('match_rate'),
                'missing_errors_count': len(
                    comparison_result.get_template_request('missing_errors_str', '').split(';')) if comparison_result.get_template_request(
                    'missing_errors_str') else 0,
                'unexpected_errors_count': len(
                    comparison_result.get_template_request('unexpected_errors_str', '').split(';')) if comparison_result.get_template_request(
                    'unexpected_errors_str') else 0
            }

            allure.attach(
                json.dumps(comparison_summary, indent=2),
                "Regression Comparison Summary",
                allure.attachment_type.JSON
            )

            # Missing errors
            if comparison_result.get_template_request('missing_errors_str'):
                allure.attach(
                    comparison_result['missing_errors_str'],
                    "Missing Errors (Expected but not found in System 2)",
                    allure.attachment_type.TEXT
                )

            # Unexpected errors
            if comparison_result.get_template_request('unexpected_errors_str'):
                allure.attach(
                    comparison_result['unexpected_errors_str'],
                    "Unexpected Errors (Found in System 2 but not expected)",
                    allure.attachment_type.TEXT
                )

            # Set test result based on regression status
            status = comparison_result.get_template_request('regression_status', 'UNKNOWN')
            if status == 'PASSED':
                pass  # Test will pass naturally
            elif status == 'WARNING':
                allure.attach(
                    "Minor differences detected between systems",
                    "Warning Details",
                    allure.attachment_type.TEXT
                )
            elif status == 'FAILED':
                # This will mark the test as failed in Allure
                assert False, f"Regression detected: {comparison_result.get_template_request('summary', 'Unknown failure')}"
            else:
                assert False, f"Regression comparison error: {comparison_result.get_template_request('summary', 'Unknown error')}"

    def add_baseline_collection_step(self, system1_errors, expected_errors_str):
        """Add baseline collection step for System 1 only mode"""
        with allure.step("Baseline Error Collection (System 1)"):
            if system1_errors:
                error_summary = self.format_errors_for_display(system1_errors)
                allure.attach(
                    error_summary,
                    "Collected Baseline Errors",
                    allure.attachment_type.TEXT
                )

                allure.attach(
                    expected_errors_str,
                    "Expected Errors String (for future comparisons)",
                    allure.attachment_type.TEXT
                )
            else:
                allure.attach(
                    "No baseline errors collected",
                    "Baseline Collection Result",
                    allure.attachment_type.TEXT
                )

    def format_errors_for_display(self, errors_list):
        """Format errors list for human-readable display"""
        if not errors_list:
            return "No errors found"

        formatted = f"Total Errors: {len(errors_list)}\n\n"
        for i, error in enumerate(errors_list, 1):
            formatted += f"Error #{i}:\n"
            formatted += f"  Transaction: {error.get_template_request('Transaction', 'N/A')}\n"
            formatted += f"  Type: {error.get_template_request('Type', 'N/A')}\n"
            formatted += f"  Rule ID: {error.get_template_request('RuleID', 'N/A')}\n"
            formatted += f"  Object: {error.get_template_request('Object Name', 'N/A')}\n"
            formatted += f"  Field: {error.get_template_request('HAAD Field', 'N/A')}\n"
            formatted += "\n"

        return formatted

    def set_environment_info(self, system1_url, system2_url=None):
        """Set environment information for the Allure report"""
        env_info = {
            'System 1 (Legacy)': system1_url,
            'Test Framework': 'Custom SOAP API Tester',
            'Execution Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        if system2_url:
            env_info['System 2 (Re-engineered)'] = system2_url

        # Write environment properties file
        env_file_path = os.path.join(self.results_dir, "environment.properties")
        with open(env_file_path, "w") as f:
            for key, value in env_info.items():
                f.write(f"{key.replace(' ', '_')}={value}\n")

    def finalize_test(self, overall_result):
        """Finalize test with overall result"""
        with allure.step("Test Completion"):
            allure.attach(
                json.dumps(overall_result, indent=2),
                "Final Test Results",
                allure.attachment_type.JSON
            )

    """
    Enhanced Allure Reporter methods for assertion testing
    Add these methods to the existing allure_reporter.py file
    """

    def add_assertion_validation_step(self, system_name, assertion_results, assertions_str):
        """Add assertion validation as an Allure step with detailed breakdown"""
        if not assertion_results:
            with allure.step(f"{system_name} - No Assertions"):
                allure.attach("No assertions defined for this test step",
                              "Assertion Status", allure.attachment_type.TEXT)
            return

        passed = len([r for r in assertion_results if r['status'] == 'PASS'])
        failed = len([r for r in assertion_results if r['status'] == 'FAIL'])
        errors = len([r for r in assertion_results if r['status'] == 'ERROR'])
        total = len(assertion_results)

        step_title = f"{system_name} - Assertion Validation ({passed}/{total} passed)"

        with allure.step(step_title):
            # Overall summary
            summary = f"Assertion Validation Summary for {system_name}:\n"
            summary += f"Total Assertions: {total}\n"
            summary += f"Passed: {passed}\n"
            summary += f"Failed: {failed}\n"
            summary += f"Errors: {errors}\n"
            summary += f"Success Rate: {(passed / total * 100):.1f}%\n\n"

            # Original assertion string
            summary += f"Original Assertions:\n{assertions_str}\n\n"

            # Detailed results
            summary += "Detailed Results:\n"
            summary += "=" * 50 + "\n"

            for i, result in enumerate(assertion_results, 1):
                status_symbol = self._get_status_symbol(result['status'])
                summary += f"{status_symbol} {i}. {result['assertion_type'].upper()}\n"
                summary += f"    Message: {result['message']}\n"
                summary += f"    Expected: {result.get_template_request('expected', 'N/A')}\n"
                summary += f"    Actual: {result.get_template_request('actual', 'N/A')}\n"

                if result['status'] in ['FAIL', 'ERROR'] and result.get_template_request('details'):
                    summary += f"    Details: {result['details']}\n"

                summary += "\n"

            allure.attach(summary, f"{system_name} Assertion Results", allure.attachment_type.TEXT)

            # Attach individual assertion details as JSON
            import json
            allure.attach(json.dumps(assertion_results, indent=2),
                          f"{system_name} Assertion Data (JSON)", allure.attachment_type.JSON)

            # Create individual sub-steps for failed/error assertions
            for result in assertion_results:
                if result['status'] in ['FAIL', 'ERROR']:
                    self._add_failed_assertion_substep(result)

    def _add_failed_assertion_substep(self, assertion_result):
        """Add detailed sub-step for failed assertions"""
        assertion_type = assertion_result['assertion_type']
        status = assertion_result['status']

        substep_title = f"❌ {assertion_type.upper()} - {status}"

        with allure.step(substep_title):
            failure_details = f"Assertion Type: {assertion_type}\n"
            failure_details += f"Status: {status}\n"
            failure_details += f"Message: {assertion_result['message']}\n"
            failure_details += f"Expected: {assertion_result.get_template_request('expected', 'N/A')}\n"
            failure_details += f"Actual: {assertion_result.get_template_request('actual', 'N/A')}\n"

            if assertion_result.get_template_request('details'):
                failure_details += f"Additional Details: {assertion_result['details']}\n"

            # Add debugging information
            failure_details += "\nDebugging Information:\n"
            failure_details += "- Check if target element exists in response\n"
            failure_details += "- Verify expected value format and casing\n"
            failure_details += "- Consider using 'contains' instead of 'equals' for partial matches\n"

            allure.attach(failure_details, "Assertion Failure Details", allure.attachment_type.TEXT)

    def add_assertion_comparison_step(self, system1_results, system2_results):
        """Add assertion comparison between systems"""
        with allure.step("Assertion Comparison Between Systems"):
            comparison_analysis = self._analyze_assertion_differences(system1_results, system2_results)

            # Summary comparison
            summary = "ASSERTION COMPARISON ANALYSIS\n"
            summary += "=" * 50 + "\n\n"

            summary += f"System 1 Assertions: {len(system1_results)}\n"
            summary += f"System 2 Assertions: {len(system2_results)}\n"
            summary += f"Comparison Status: {comparison_analysis['overall_status']}\n\n"

            # Detailed comparison
            if comparison_analysis['matching_assertions']:
                summary += "MATCHING ASSERTIONS:\n"
                for match in comparison_analysis['matching_assertions']:
                    summary += f"✓ {match['assertion_type']}: Both systems {match['status']}\n"
                summary += "\n"

            if comparison_analysis['differing_assertions']:
                summary += "DIFFERING ASSERTIONS:\n"
                for diff in comparison_analysis['differing_assertions']:
                    summary += f"⚠ {diff['assertion_type']}: System1={diff['sys1_status']}, System2={diff['sys2_status']}\n"
                    summary += f"   System1 Message: {diff['sys1_message']}\n"
                    summary += f"   System2 Message: {diff['sys2_message']}\n\n"

            if comparison_analysis['system_differences']:
                summary += "SYSTEM-SPECIFIC DIFFERENCES:\n"
                summary += comparison_analysis['system_differences'] + "\n"

            allure.attach(summary, "Assertion Comparison Report", allure.attachment_type.TEXT)

            # Attach detailed comparison data
            import json
            comparison_data = {
                'system1_results': system1_results,
                'system2_results': system2_results,
                'analysis': comparison_analysis
            }
            allure.attach(json.dumps(comparison_data, indent=2),
                          "Complete Comparison Data", allure.attachment_type.JSON)

            # Add regression warning if needed
            if not comparison_analysis['systems_match']:
                with allure.step("⚠️ Regression Warning"):
                    warning = f"Assertion behavior differs between systems!\n"
                    warning += f"Differences found: {len(comparison_analysis['differing_assertions'])}\n"
                    warning += "This may indicate regression issues or environmental differences."
                    allure.attach(warning, "Regression Alert", allure.attachment_type.TEXT)

    def _analyze_assertion_differences(self, system1_results, system2_results):
        """Analyze differences between system assertion results"""
        analysis = {
            'overall_status': 'MATCH',
            'systems_match': True,
            'matching_assertions': [],
            'differing_assertions': [],
            'system_differences': ''
        }

        # Check if assertion counts match
        if len(system1_results) != len(system2_results):
            analysis['systems_match'] = False
            analysis['overall_status'] = 'COUNT_MISMATCH'
            analysis[
                'system_differences'] = f"Assertion count mismatch: System1({len(system1_results)}) vs System2({len(system2_results)})"
            return analysis

        # Compare individual assertions
        for i, (sys1, sys2) in enumerate(zip(system1_results, system2_results)):
            if sys1['assertion_type'] != sys2['assertion_type']:
                analysis['systems_match'] = False
                analysis['overall_status'] = 'TYPE_MISMATCH'
                continue

            if sys1['status'] == sys2['status']:
                analysis['matching_assertions'].append({
                    'assertion_type': sys1['assertion_type'],
                    'status': sys1['status'],
                    'position': i + 1
                })
            else:
                analysis['systems_match'] = False
                analysis['overall_status'] = 'RESULT_MISMATCH'
                analysis['differing_assertions'].append({
                    'assertion_type': sys1['assertion_type'],
                    'position': i + 1,
                    'sys1_status': sys1['status'],
                    'sys2_status': sys2['status'],
                    'sys1_message': sys1.get_template_request('message', ''),
                    'sys2_message': sys2.get_template_request('message', '')
                })

        return analysis

    def add_assertion_performance_metrics(self, assertion_results, execution_time):
        """Add performance metrics for assertion validation"""
        with allure.step("Assertion Performance Metrics"):
            metrics = f"Assertion Execution Metrics:\n"
            metrics += f"Total Assertions: {len(assertion_results)}\n"
            metrics += f"Execution Time: {execution_time:.3f} seconds\n"
            metrics += f"Average Time per Assertion: {(execution_time / len(assertion_results)):.3f} seconds\n\n"

            # Breakdown by assertion type
            type_counts = {}
            for result in assertion_results:
                assertion_type = result['assertion_type']
                type_counts[assertion_type] = type_counts.get(assertion_type, 0) + 1

            metrics += "Assertion Type Distribution:\n"
            for assertion_type, count in sorted(type_counts.items()):
                metrics += f"  {assertion_type}: {count}\n"

            allure.attach(metrics, "Performance Metrics", allure.attachment_type.TEXT)

    def add_assertion_test_summary(self, test_results):
        """Add comprehensive test summary with assertion focus"""
        with allure.step("Test Execution Summary"):
            total_tests = len(test_results)
            passed_tests = len([t for t in test_results if t.get_template_request('overall_status') == 'PASS'])
            failed_tests = total_tests - passed_tests

            total_assertions = sum(t.get_template_request('total_assertions', 0) for t in test_results)
            passed_assertions = sum(t.get_template_request('passed_assertions', 0) for t in test_results)
            failed_assertions = sum(t.get_template_request('failed_assertions', 0) for t in test_results)

            summary = "ASSERTION TEST EXECUTION SUMMARY\n"
            summary += "=" * 50 + "\n\n"
            summary += f"Test Cases: {total_tests} (Passed: {passed_tests}, Failed: {failed_tests})\n"
            summary += f"Assertions: {total_assertions} (Passed: {passed_assertions}, Failed: {failed_assertions})\n"
            summary += f"Test Success Rate: {(passed_tests / total_tests * 100):.1f}%\n"
            summary += f"Assertion Success Rate: {(passed_assertions / total_assertions * 100):.1f}%\n\n"

            # Most common assertion types
            all_assertion_types = []
            for test in test_results:
                if test.get_template_request('assertion_details'):
                    all_assertion_types.extend([a['assertion_type'] for a in test['assertion_details']])

            if all_assertion_types:
                from collections import Counter
                type_counter = Counter(all_assertion_types)
                summary += "Most Common Assertion Types:\n"
                for assertion_type, count in type_counter.most_common(5):
                    summary += f"  {assertion_type}: {count}\n"

            allure.attach(summary, "Execution Summary", allure.attachment_type.TEXT)

    def _get_status_symbol(self, status):
        """Get appropriate symbol for assertion status"""
        symbols = {
            'PASS': '✓',
            'FAIL': '✗',
            'ERROR': '⚠',
            'SKIP': '⊝'
        }
        return symbols.get(status, '?')

    def finalize_assertion_test(self, test_summary):
        """Finalize assertion test with comprehensive summary"""
        with allure.step("Test Finalization"):
            # Determine overall test result
            overall_status = test_summary.get_template_request('overall_status', 'UNKNOWN')

            final_summary = f"FINAL TEST RESULTS\n"
            final_summary += "=" * 30 + "\n"
            final_summary += f"Overall Status: {overall_status}\n"
            final_summary += f"Execution Mode: {test_summary.get_template_request('execution_mode', 'unknown')}\n"

            if test_summary.get_template_request('total_assertions'):
                final_summary += f"Total Assertions: {test_summary['total_assertions']}\n"
                final_summary += f"Passed: {test_summary.get_template_request('passed_assertions', 0)}\n"
                final_summary += f"Failed: {test_summary.get_template_request('failed_assertions', 0)}\n"
                final_summary += f"Success Rate: {test_summary.get_template_request('success_rate', '0%')}\n"

            if test_summary.get_template_request('execution_mode') == 'dual_system':
                final_summary += f"\nDual System Results:\n"
                final_summary += f"Systems Match: {test_summary.get_template_request('systems_match', 'Unknown')}\n"
                final_summary += f"Comparison: {test_summary.get_template_request('comparison_summary', 'N/A')}\n"

            allure.attach(final_summary, "Final Results", allure.attachment_type.TEXT)

            # Set dynamic properties based on results
            if overall_status == 'PASSED':
                allure.dynamic.label("testType", "assertion_validation_passed")
            elif overall_status == 'FAILED':
                allure.dynamic.label("testType", "assertion_validation_failed")
            else:
                allure.dynamic.label("testType", "assertion_validation_error")

            # Add assertion count as a label
            if test_summary.get_template_request('total_assertions'):
                allure.dynamic.label("assertion_count", str(test_summary['total_assertions']))

            # Add execution mode as tag
            allure.dynamic.tag(f"mode_{test_summary.get_template_request('execution_mode', 'unknown')}")

            if test_summary.get_template_request('failed_assertions', 0) > 0:
                allure.dynamic.tag("has_assertion_failures")