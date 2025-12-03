"""
Assertion Validator - Validates response assertions for API testing
Supports multiple assertion types for XML and text-based responses
"""

import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from datetime import datetime


class AssertionValidator:
    def __init__(self):
        self.supported_assertions = {
            'exists': self._assert_exists,
            'not_exists': self._assert_not_exists,
            'equals': self._assert_equals,
            'not_equals': self._assert_not_equals,
            'contains': self._assert_contains,
            'not_contains': self._assert_not_contains,
            'matches': self._assert_matches,
            'count': self._assert_count,
            'length': self._assert_length,
            'greater_than': self._assert_greater_than,
            'less_than': self._assert_less_than,
            'between': self._assert_between,
            'xpath': self._assert_xpath
        }

    def validate_assertions(self, response_content: str, assertions_str: str,
                            extracted_variables: Dict[str, str] = None,
                            response_metadata: Dict[str, Any] = None,
                            declared_variables: Dict[str, str] = None) -> List[Dict]:
        """
        Validate all assertions against response content

        Args:
            response_content (str): API response content to validate
            assertions_str (str): Semicolon-separated assertion definitions
            extracted_variables (dict): Variables extracted from response (EXTRACT.*)
            response_metadata (dict): Additional response data (status, time, etc.)
            declared_variables (dict): Variables declared in Variable_Definitions (VAR.*)

        Returns:
            List[Dict]: List of assertion validation results
        """
        results = []

        if not assertions_str or not str(assertions_str).strip():
            return results

        try:
            # CRITICAL FIX: Process variables in assertion string BEFORE parsing
            # This replaces {{EXTRACT.file_id}} and {{VAR.filename}} with actual values
            processed_assertions_str = self._process_assertion_variables(
                assertions_str, extracted_variables, declared_variables
            )

            print(f"DEBUG: Original assertions: {assertions_str}")
            print(f"DEBUG: Processed assertions: {processed_assertions_str}")

            # Parse assertions (now with processed values)
            assertions = self._parse_assertions(processed_assertions_str)

            for assertion in assertions:
                try:
                    result = self._validate_single_assertion(
                        assertion, response_content, extracted_variables, response_metadata
                    )
                    results.append(result)

                except Exception as e:
                    results.append({
                        'assertion_type': assertion.get('type', 'unknown'),
                        'status': 'ERROR',
                        'message': f"Assertion validation failed: {str(e)}",
                        'expected': assertion.get('expected', ''),
                        'actual': 'Error during validation',
                        'details': str(e)
                    })

        except Exception as e:
            results.append({
                'assertion_type': 'parsing_error',
                'status': 'ERROR',
                'message': f"Failed to parse assertions: {str(e)}",
                'expected': assertions_str,
                'actual': 'Parse error',
                'details': str(e)
            })

        return results

    def _parse_assertions(self, assertions_str: str) -> List[Dict]:
        """Parse assertion string into structured assertions"""
        assertions = []

        # Split by semicolon for multiple assertions
        assertion_parts = assertions_str.split(';')

        for assertion_part in assertion_parts:
            assertion_part = assertion_part.strip()
            if not assertion_part:
                continue

            # Parse assertion format: type:target:expected_value
            # Examples:
            # exists:FileName:test_file_abc.xml
            # equals:SearchTransactionsResult:0
            # contains:foundTransactions:FileID
            # count:File:8

            parts = assertion_part.split(':', 2)  # Split into max 3 parts

            if len(parts) >= 2:
                assertion_type = parts[0].strip().lower()
                target = parts[1].strip()
                expected = parts[2].strip() if len(parts) > 2 else ''

                assertions.append({
                    'type': assertion_type,
                    'target': target,
                    'expected': expected,
                    'original': assertion_part
                })
            else:
                # Handle malformed assertions
                assertions.append({
                    'type': 'malformed',
                    'target': assertion_part,
                    'expected': '',
                    'original': assertion_part
                })

        return assertions

    def _validate_single_assertion(self, assertion: Dict, response_content: str,
                                   extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Validate a single assertion"""
        assertion_type = assertion['type']

        if assertion_type not in self.supported_assertions:
            return {
                'assertion_type': assertion_type,
                'status': 'ERROR',
                'message': f"Unsupported assertion type: {assertion_type}",
                'expected': assertion.get('expected', ''),
                'actual': 'Unsupported assertion',
                'details': f"Supported types: {', '.join(self.supported_assertions.keys())}"
            }

        # Ensure metadata and variables are dicts, not None
        if response_metadata is None:
            response_metadata = {}

        if extracted_variables is None:
            extracted_variables = {}

        # Execute the assertion
        validator_func = self.supported_assertions[assertion_type]
        return validator_func(assertion, response_content, extracted_variables, response_metadata)

    def _process_assertion_variables(self, assertions_str: str,
                                     extracted_variables: Dict[str, str],
                                     declared_variables: Dict[str, str] = None) -> str:
        """
        Process variables in assertion string
        Replaces {{EXTRACT.variable_name}} and {{VAR.variable_name}} with actual values

        Args:
            assertions_str: Raw assertion string with variables
            extracted_variables: Dictionary of extracted variable values (EXTRACT.*)
            declared_variables: Dictionary of declared variable values (VAR.*)

        Returns:
            Processed assertion string with variables replaced
        """
        import re

        if not assertions_str:
            return assertions_str

        if not extracted_variables:
            extracted_variables = {}

        if not declared_variables:
            declared_variables = {}

        processed = assertions_str

        # Process {{EXTRACT.variable_name}} patterns
        extract_pattern = r'\{\{EXTRACT\.([^}]+)\}\}'
        extract_matches = re.findall(extract_pattern, processed)

        for var_name in extract_matches:
            placeholder = f"{{{{EXTRACT.{var_name}}}}}"

            if var_name in extracted_variables:
                # Replace with actual value
                actual_value = str(extracted_variables[var_name])
                processed = processed.replace(placeholder, actual_value)
                print(f"DEBUG: Replaced {placeholder} with '{actual_value}'")
            else:
                # Variable not found - leave as is or replace with error marker
                print(f"WARNING: Extracted variable '{var_name}' not found in extracted_variables")
                # Optionally: processed = processed.replace(placeholder, f"[UNDEFINED:{var_name}]")

        # Process {{VAR.variable_name}} patterns
        var_pattern = r'\{\{VAR\.([^}]+)\}\}'
        var_matches = re.findall(var_pattern, processed)

        for var_name in var_matches:
            placeholder = f"{{{{VAR.{var_name}}}}}"

            if var_name in declared_variables:
                # Replace with actual value
                actual_value = str(declared_variables[var_name])
                processed = processed.replace(placeholder, actual_value)
                print(f"DEBUG: Replaced {placeholder} with '{actual_value}'")
            else:
                # Variable not found - leave as is or replace with error marker
                print(f"WARNING: Declared variable '{var_name}' not found in declared_variables")
                # Optionally: processed = processed.replace(placeholder, f"[UNDEFINED:{var_name}]")

        return processed

    def _assert_exists(self, assertion: Dict, response_content: str,
                      extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert that a value exists in response"""
        target = assertion['target']
        expected_value = assertion['expected']

        # Check if target exists in response content
        if expected_value:
            # Check for specific value existence
            found = expected_value in response_content
            actual_value = "Found" if found else "Not found"
        else:
            # Check if target element/pattern exists
            found = target in response_content
            actual_value = "Found" if found else "Not found"
            expected_value = target

        return {
            'assertion_type': 'exists',
            'status': 'PASS' if found else 'FAIL',
            'message': f"Value '{expected_value}' {'found' if found else 'not found'} in response",
            'expected': expected_value,
            'actual': actual_value,
            'details': f"Searched for: {expected_value}"
        }

    def _assert_not_exists(self, assertion: Dict, response_content: str,
                          extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert that a value does not exist in response"""
        result = self._assert_exists(assertion, response_content, extracted_variables, response_metadata)

        # Flip the result
        result['status'] = 'PASS' if result['status'] == 'FAIL' else 'FAIL'
        result['assertion_type'] = 'not_exists'
        if result['status'] == 'PASS':
            result['message'] = result['message'].replace('not found', 'correctly not found')
        else:
            result['message'] = result['message'].replace('found', 'should not be found')

        return result

    def _assert_equals(self, assertion: Dict, response_content: str,
                      extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert that extracted value equals expected value"""
        target = assertion['target']
        expected_value = assertion['expected']

        # Try to extract the target value from response
        actual_value = self._extract_value_from_response(target, response_content, extracted_variables)

        if actual_value is None:
            return {
                'assertion_type': 'equals',
                'status': 'FAIL',
                'message': f"Target '{target}' not found in response",
                'expected': expected_value,
                'actual': 'Not found',
                'details': f"Could not locate '{target}' in response"
            }

        # Compare values (convert to string for comparison)
        actual_str = str(actual_value).strip()
        expected_str = str(expected_value).strip()
        match = actual_str == expected_str

        return {
            'assertion_type': 'equals',
            'status': 'PASS' if match else 'FAIL',
            'message': f"Value {'matches' if match else 'does not match'} expected",
            'expected': expected_str,
            'actual': actual_str,
            'details': f"Comparing '{target}' value"
        }

    def _assert_not_equals(self, assertion: Dict, response_content: str,
                          extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert that extracted value does not equal expected value"""
        result = self._assert_equals(assertion, response_content, extracted_variables, response_metadata)

        # Flip the result (but handle "not found" case)
        if result['actual'] == 'Not found':
            result['status'] = 'FAIL'  # If not found, not_equals should still fail
        else:
            result['status'] = 'PASS' if result['status'] == 'FAIL' else 'FAIL'

        result['assertion_type'] = 'not_equals'
        result['message'] = result['message'].replace('matches', 'should not match').replace('does not match', 'correctly does not match')

        return result

    def _assert_contains(self, assertion: Dict, response_content: str,
                        extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert that response contains expected value"""
        target = assertion['target']
        expected_value = assertion['expected']

        if expected_value:
            # Check if expected value is contained in response
            found = expected_value in response_content
            return {
                'assertion_type': 'contains',
                'status': 'PASS' if found else 'FAIL',
                'message': f"Response {'contains' if found else 'does not contain'} '{expected_value}'",
                'expected': f"Contains '{expected_value}'",
                'actual': 'Found' if found else 'Not found',
                'details': f"Searched entire response for '{expected_value}'"
            }
        else:
            # Check if target element contains any content
            extracted_value = self._extract_value_from_response(target, response_content, extracted_variables)
            has_content = extracted_value is not None and str(extracted_value).strip() != ''

            return {
                'assertion_type': 'contains',
                'status': 'PASS' if has_content else 'FAIL',
                'message': f"Target '{target}' {'has content' if has_content else 'is empty'}",
                'expected': f"'{target}' has content",
                'actual': str(extracted_value) if extracted_value else 'Empty',
                'details': f"Checked if '{target}' contains content"
            }

    def _assert_not_contains(self, assertion: Dict, response_content: str,
                            extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert that response does not contain expected value"""
        result = self._assert_contains(assertion, response_content, extracted_variables, response_metadata)

        # Flip the result
        result['status'] = 'PASS' if result['status'] == 'FAIL' else 'FAIL'
        result['assertion_type'] = 'not_contains'
        result['message'] = result['message'].replace('contains', 'should not contain').replace('does not contain', 'correctly does not contain')
        result['expected'] = result['expected'].replace('Contains', 'Does not contain')

        return result

    def _assert_matches(self, assertion: Dict, response_content: str,
                       extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert that extracted value matches regex pattern"""
        target = assertion['target']
        pattern = assertion['expected']

        # Extract target value
        actual_value = self._extract_value_from_response(target, response_content, extracted_variables)

        if actual_value is None:
            return {
                'assertion_type': 'matches',
                'status': 'FAIL',
                'message': f"Target '{target}' not found in response",
                'expected': f"Matches pattern: {pattern}",
                'actual': 'Not found',
                'details': f"Could not locate '{target}' to test pattern"
            }

        # Test regex pattern
        try:
            match = re.search(pattern, str(actual_value), re.IGNORECASE)
            matches = match is not None

            return {
                'assertion_type': 'matches',
                'status': 'PASS' if matches else 'FAIL',
                'message': f"Value {'matches' if matches else 'does not match'} pattern",
                'expected': f"Pattern: {pattern}",
                'actual': str(actual_value),
                'details': f"Regex pattern test on '{target}'"
            }

        except Exception as e:
            return {
                'assertion_type': 'matches',
                'status': 'ERROR',
                'message': f"Invalid regex pattern: {str(e)}",
                'expected': pattern,
                'actual': str(actual_value),
                'details': f"Regex error: {str(e)}"
            }

    def _assert_count(self, assertion: Dict, response_content: str,
                     extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert count of elements in response"""
        target = assertion['target']
        expected_count = assertion['expected']

        try:
            expected_num = int(expected_count)
        except ValueError:
            return {
                'assertion_type': 'count',
                'status': 'ERROR',
                'message': f"Invalid expected count: {expected_count}",
                'expected': expected_count,
                'actual': 'Invalid number',
                'details': 'Expected count must be a number'
            }

        # Count occurrences of target in response
        actual_count = response_content.count(target)
        matches = actual_count == expected_num

        return {
            'assertion_type': 'count',
            'status': 'PASS' if matches else 'FAIL',
            'message': f"Found {actual_count} occurrences, expected {expected_num}",
            'expected': str(expected_num),
            'actual': str(actual_count),
            'details': f"Counted occurrences of '{target}' in response"
        }

    def _assert_length(self, assertion: Dict, response_content: str,
                      extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert length of extracted value"""
        target = assertion['target']
        expected_length = assertion['expected']

        try:
            expected_num = int(expected_length)
        except ValueError:
            return {
                'assertion_type': 'length',
                'status': 'ERROR',
                'message': f"Invalid expected length: {expected_length}",
                'expected': expected_length,
                'actual': 'Invalid number',
                'details': 'Expected length must be a number'
            }

        # Extract value and check length
        actual_value = self._extract_value_from_response(target, response_content, extracted_variables)

        if actual_value is None:
            return {
                'assertion_type': 'length',
                'status': 'FAIL',
                'message': f"Target '{target}' not found in response",
                'expected': f"Length: {expected_num}",
                'actual': 'Not found',
                'details': f"Could not locate '{target}' to check length"
            }

        actual_length = len(str(actual_value))
        matches = actual_length == expected_num

        return {
            'assertion_type': 'length',
            'status': 'PASS' if matches else 'FAIL',
            'message': f"Length is {actual_length}, expected {expected_num}",
            'expected': str(expected_num),
            'actual': str(actual_length),
            'details': f"Checked length of '{target}' value: '{actual_value}'"
        }

    def _assert_greater_than(self, assertion: Dict, response_content: str,
                           extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert that extracted numeric value is greater than expected"""
        return self._assert_numeric_comparison(assertion, response_content, extracted_variables,
                                             response_metadata, 'greater_than', lambda a, e: a > e)

    def _assert_less_than(self, assertion: Dict, response_content: str,
                         extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert that extracted numeric value is less than expected"""
        return self._assert_numeric_comparison(assertion, response_content, extracted_variables,
                                             response_metadata, 'less_than', lambda a, e: a < e)

    def _assert_between(self, assertion: Dict, response_content: str,
                       extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert that extracted numeric value is between two values"""
        target = assertion['target']
        expected_range = assertion['expected']

        # Parse range: "min,max"
        try:
            range_parts = expected_range.split(',')
            if len(range_parts) != 2:
                raise ValueError("Range must be 'min,max'")

            min_val = float(range_parts[0].strip())
            max_val = float(range_parts[1].strip())

        except ValueError as e:
            return {
                'assertion_type': 'between',
                'status': 'ERROR',
                'message': f"Invalid range format: {expected_range}",
                'expected': expected_range,
                'actual': 'Invalid range',
                'details': f"Range format error: {str(e)}"
            }

        # Extract and convert value
        actual_value = self._extract_value_from_response(target, response_content, extracted_variables)

        if actual_value is None:
            return {
                'assertion_type': 'between',
                'status': 'FAIL',
                'message': f"Target '{target}' not found in response",
                'expected': f"Between {min_val} and {max_val}",
                'actual': 'Not found',
                'details': f"Could not locate '{target}' to check range"
            }

        try:
            actual_num = float(str(actual_value))
            in_range = min_val <= actual_num <= max_val

            return {
                'assertion_type': 'between',
                'status': 'PASS' if in_range else 'FAIL',
                'message': f"Value {actual_num} is {'within' if in_range else 'outside'} range [{min_val}, {max_val}]",
                'expected': f"Between {min_val} and {max_val}",
                'actual': str(actual_num),
                'details': f"Checked if '{target}' value is in range"
            }

        except ValueError:
            return {
                'assertion_type': 'between',
                'status': 'ERROR',
                'message': f"Cannot convert '{actual_value}' to number",
                'expected': f"Between {min_val} and {max_val}",
                'actual': str(actual_value),
                'details': 'Value is not numeric'
            }

    def _assert_numeric_comparison(self, assertion: Dict, response_content: str,
                                 extracted_variables: Dict, response_metadata: Dict,
                                 comparison_type: str, comparison_func) -> Dict:
        """Helper for numeric comparisons"""
        target = assertion['target']
        expected_value = assertion['expected']

        # Convert expected to number
        try:
            expected_num = float(expected_value)
        except ValueError:
            return {
                'assertion_type': comparison_type,
                'status': 'ERROR',
                'message': f"Invalid expected number: {expected_value}",
                'expected': expected_value,
                'actual': 'Invalid number',
                'details': 'Expected value must be numeric'
            }

        # Extract and convert actual value
        actual_value = self._extract_value_from_response(target, response_content, extracted_variables)

        if actual_value is None:
            return {
                'assertion_type': comparison_type,
                'status': 'FAIL',
                'message': f"Target '{target}' not found in response",
                'expected': f"{comparison_type.replace('_', ' ')} {expected_num}",
                'actual': 'Not found',
                'details': f"Could not locate '{target}' for comparison"
            }

        try:
            actual_num = float(str(actual_value))
            result = comparison_func(actual_num, expected_num)

            return {
                'assertion_type': comparison_type,
                'status': 'PASS' if result else 'FAIL',
                'message': f"Value {actual_num} is {'not ' if not result else ''}{comparison_type.replace('_', ' ')} {expected_num}",
                'expected': f"{comparison_type.replace('_', ' ')} {expected_num}",
                'actual': str(actual_num),
                'details': f"Numeric comparison of '{target}' value"
            }

        except ValueError:
            return {
                'assertion_type': comparison_type,
                'status': 'ERROR',
                'message': f"Cannot convert '{actual_value}' to number",
                'expected': str(expected_num),
                'actual': str(actual_value),
                'details': 'Actual value is not numeric'
            }

    def _assert_xpath(self, assertion: Dict, response_content: str,
                     extracted_variables: Dict, response_metadata: Dict) -> Dict:
        """Assert using XPath expression"""
        xpath_expr = assertion['target']
        expected_value = assertion['expected']

        try:
            # Parse XML
            root = ET.fromstring(response_content)

            # Handle namespaces
            namespaces = self._extract_namespaces(response_content)

            # Execute XPath
            if namespaces:
                elements = root.findall(xpath_expr, namespaces)
            else:
                elements = root.findall(xpath_expr)

            if expected_value:
                # Check if any element has the expected value
                found = any(elem.text == expected_value for elem in elements if elem.text)
                actual_values = [elem.text for elem in elements if elem.text]

                return {
                    'assertion_type': 'xpath',
                    'status': 'PASS' if found else 'FAIL',
                    'message': f"XPath {'found' if found else 'did not find'} expected value",
                    'expected': expected_value,
                    'actual': ', '.join(actual_values) if actual_values else 'No values found',
                    'details': f"XPath: {xpath_expr}"
                }
            else:
                # Just check if elements exist
                found = len(elements) > 0

                return {
                    'assertion_type': 'xpath',
                    'status': 'PASS' if found else 'FAIL',
                    'message': f"XPath {'found' if found else 'did not find'} {len(elements)} elements",
                    'expected': 'Elements exist',
                    'actual': f"{len(elements)} elements found",
                    'details': f"XPath: {xpath_expr}"
                }

        except ET.ParseError as e:
            return {
                'assertion_type': 'xpath',
                'status': 'ERROR',
                'message': f"XML parsing error: {str(e)}",
                'expected': expected_value,
                'actual': 'XML parse error',
                'details': f"Cannot parse response as XML for XPath: {xpath_expr}"
            }
        except Exception as e:
            return {
                'assertion_type': 'xpath',
                'status': 'ERROR',
                'message': f"XPath error: {str(e)}",
                'expected': expected_value,
                'actual': 'XPath error',
                'details': f"XPath expression error: {xpath_expr}"
            }

    def _extract_value_from_response(self, target: str, response_content: str,
                                   extracted_variables: Dict) -> str:
        """Extract value from response using various methods"""
        # First check if target is in extracted variables
        if extracted_variables and target in extracted_variables:
            return extracted_variables[target]

        # Try simple element extraction
        try:
            pattern = f'<{target}[^>]*>(.*?)</{target}>'
            match = re.search(pattern, response_content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        except Exception:
            pass

        # Try attribute extraction: target="value"
        try:
            pattern = f'{target}=["\']([^"\']*)["\']'
            match = re.search(pattern, response_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        except Exception:
            pass

        # Try simple text search
        if target in response_content:
            return "Found"

        return None

    def _extract_namespaces(self, xml_content: str) -> Dict:
        """Extract XML namespaces for XPath queries"""
        namespaces = {}
        try:
            ns_pattern = r'xmlns:?(\w*)\s*=\s*["\']([^"\']+)["\']'
            matches = re.findall(ns_pattern, xml_content)

            for prefix, uri in matches:
                if prefix:
                    namespaces[prefix] = uri
                else:
                    namespaces['default'] = uri

        except Exception:
            pass

        return namespaces

    def get_supported_assertion_types(self) -> Dict[str, str]:
        """Get documentation for supported assertion types"""
        return {
            'exists': 'Check if value exists in response: exists:target:expected_value',
            'not_exists': 'Check if value does not exist: not_exists:target:expected_value',
            'equals': 'Check exact match: equals:target:expected_value',
            'not_equals': 'Check not equal: not_equals:target:expected_value',
            'contains': 'Check if response contains value: contains:target:expected_value',
            'not_contains': 'Check if response does not contain: not_contains:target:expected_value',
            'matches': 'Check regex pattern: matches:target:regex_pattern',
            'count': 'Count occurrences: count:target:expected_number',
            'length': 'Check string length: length:target:expected_length',
            'greater_than': 'Numeric comparison: greater_than:target:number',
            'less_than': 'Numeric comparison: less_than:target:number',
            'between': 'Range check: between:target:min,max',
            'xpath': 'XPath query: xpath:xpath_expression:expected_value'
        }