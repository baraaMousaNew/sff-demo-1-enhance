"""
Error Report Validator - Validates SOAP error reports against expected errors
"""
import csv
from io import StringIO

import pandas as pd
import base64
import io
import re
from typing import List, Dict, Tuple, Optional

class ErrorValidator:
    def __init__(self):
        self.validation_columns = ['Transaction', 'Type', 'RuleID', 'Object Name', 'HAAD Field', 'Error Text']

    def extract_and_validate_errors(self, response_content: str, expected_errors_str: str, test_id: str) -> Dict:
        """
        Main validation function - extracts errorReport and validates against expected errors

        Args:
            response_content (str): SOAP response content
            expected_errors_str (str): Expected errors string from Excel
            test_id (str): Test identifier

        Returns:
            Dict: Validation results
        """
        try:
            # Step 1: Extract errorReport from response
            error_report_base64 = self.extract_error_report(response_content)

            if not error_report_base64:
                # No error report in response
                if not expected_errors_str.strip():
                    return self.create_validation_result('PASS', 'No errors expected and none found', [], [], [], [])
                else:
                    expected_errors = self.parse_expected_errors(expected_errors_str)
                    return self.create_validation_result('FAIL', 'Expected errors but no errorReport found', expected_errors, [], expected_errors, [])

            # Step 2: Decode and parse error report
            found_errors = self.decode_and_parse_error_report(error_report_base64)

            # Step 3: Parse expected errors
            expected_errors = self.parse_expected_errors(expected_errors_str) if expected_errors_str.strip() else []

            # Step 4: Validate
            validation_result = self.validate_errors(expected_errors, found_errors, test_id)

            return validation_result

        except Exception as e:
            return self.create_validation_result('ERROR', f'Validation failed: {str(e)}', [], [], [], [])

    def extract_error_report(self, soap_response: str) -> Optional[str]:
        """Extract Base64 errorReport content from SOAP response"""
        try:
            # Look for errorReport tag
            pattern = r'<errorReport>(.*?)</errorReport>'
            match = re.search(pattern, soap_response, re.DOTALL | re.IGNORECASE)

            if match:
                base64_content = match.group(1).strip()
                return base64_content

            return None

        except Exception as e:
            print(f"Error extracting errorReport: {e}")
            return None

    def extract_response_code(self, soap_response: str) -> Optional[str]:
        try:
            # Look for errorReport tag
            pattern = r"<(\w+Result)>(.*?)</\1>"
            match = re.search(pattern, soap_response, re.DOTALL | re.IGNORECASE)

            if match:
                code = match.group(2).strip()
                return code

            return None

        except Exception as e:
            print(f"Error extracting errorReport: {e}")
            return None

    def decode_and_parse_error_report(self, base64_content: str) -> List[Dict]:
        """Decode Base64 content and parse as CSV"""

        # Decode Base64
        decoded_bytes = base64.b64decode(base64_content)

        # Check if it's a ZIP file (common format)
        if decoded_bytes.startswith(b'PK'):
            return self.parse_zip_content(decoded_bytes)
        else:
            # Try as direct CSV
            csv_content = decoded_bytes.decode('utf-8')
            return self.parse_csv_content(csv_content)

    def parse_zip_content(self, zip_bytes: bytes) -> List[Dict]:
        """Parse ZIP file containing CSV error report"""
        import zipfile

        zip_buffer = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
            # Look for CSV files
            csv_files = [f for f in zip_file.namelist() if f.endswith('.csv')]

            if csv_files:
                # Use the first CSV file found
                csv_filename = csv_files[0]
                csv_content = zip_file.read(csv_filename).decode('utf-8')
                return self.parse_csv_content(csv_content)
            else:
                print("No CSV files found in ZIP")
                return []


    def parse_csv_content(self, csv_content: str) -> List[Dict]:
        """Parse CSV content into list of error dictionaries"""
        try:
            print(f"DEBUG: Parsing CSV content (first 200 chars): {csv_content[:200]}")

            # Use pandas to parse CSV
            # csv_io = io.StringIO(csv_content)
            # df = pd.read_csv(csv_io)

            csv_reader = csv.reader(StringIO(csv_content))

            data = list(csv_reader)

            data = [sublist for sublist in data if sublist]

            print(f"DEBUG: CSV columns found: {data[0]}")
            print(f"DEBUG: CSV rows count: {len(data) - 1}")

            if len(data) == 1:
                raise Exception("The CSV should have at least two rows (headers and data)")
            errors = []
            for row in data[1:]:
                errors_dict = {}
                for i, column in enumerate(data[0]):
                    if column.strip() in self.validation_columns:
                        try:
                            errors_dict[column] = row[i]
                        except IndexError:
                            errors_dict[column] = ''
                errors.append(errors_dict)
            return errors


            # print(f"DEBUG: CSV columns found: {list(df.columns)}")
            # print(f"DEBUG: CSV rows count: {len(df)}")
            #
            # # Convert to list of dictionaries, focusing on validation columns
            # errors = []
            # for idx, row in df.iterrows():
            #     error_dict = {}
            #     for col in self.validation_columns:
            #         if col in df.columns:
            #             value = row[col]
            #             # Convert to string and handle NaN
            #             error_dict[col] = str(value) if pd.notna(value) else ''
            #         else:
            #             print(f"DEBUG: Column '{col}' not found in CSV")
            #             error_dict[col] = ''
            #
            #     # # Add the complete row for reference
            #     # error_dict['_full_row'] = dict(row)
            #     errors.append(error_dict)
            #
            #     print(f"DEBUG: Parsed error {idx}: {error_dict}")
            #
            # return errors

        except Exception as e:
            print(f"Error parsing CSV content: {e}")
            raise Exception(f"Error parsing CSV content of: {csv_content}\n\nError: {e}")

    def parse_expected_errors(self, expected_errors_str: str) -> List[Dict]:
        """
        Parse expected errors string into list of error dictionaries
        Format: Transaction|Type|RuleID|ObjectName|HAADField;Transaction|Type|RuleID|ObjectName|HAADField
        """
        try:
            print(f"DEBUG: Parsing expected errors: {expected_errors_str}")

            if not expected_errors_str.strip():
                return []

            expected_errors = []

            # Split by semicolon for multiple errors
            error_strings = expected_errors_str.split(';')
            print(f"DEBUG: Split into {len(error_strings)} error strings")

            for error_str in error_strings:
                error_str = error_str.strip()
                if not error_str:
                    continue

                # Split by pipe for error components
                parts = error_str.split('|')
                print(f"DEBUG: Processing error string: {error_str} -> {parts}")

                if len(parts) >= 5:
                    error_dict = {
                        'Transaction': parts[0].strip(),
                        'Type': parts[1].strip(),
                        'RuleID': parts[2].strip(),
                        'Object Name': parts[3].strip(),
                        'HAAD Field': parts[4].strip()
                    }
                    expected_errors.append(error_dict)
                    print(f"DEBUG: Added expected error: {error_dict}")
                else:
                    print(f"Invalid expected error format: {error_str}")

            return expected_errors

        except Exception as e:
            print(f"Error parsing expected errors: {e}")
            return []

    def validate_errors(self, expected_errors: List[Dict], found_errors: List[Dict], test_id: str) -> Dict:
        """Compare expected errors with found errors"""
        try:
            print(f"DEBUG: Validating {len(expected_errors)} expected vs {len(found_errors)} found errors")

            missing_errors = []
            unexpected_errors = []
            matched_errors = []

            # Check each expected error
            for expected in expected_errors:
                print(f"DEBUG: Looking for expected error: {expected}")
                match_found = False
                for found in found_errors:
                    if self.errors_match(expected, found):
                        matched_errors.append({
                            'expected': expected,
                            'found': found,
                            'status': 'MATCHED'
                        })
                        match_found = True
                        print(f"DEBUG: Found match: {found}")
                        break

                if not match_found:
                    missing_errors.append(expected)
                    print(f"DEBUG: No match found for expected error: {expected}")

            # Check for unexpected errors (errors found but not expected)
            for found in found_errors:
                is_expected = False
                for expected in expected_errors:
                    if self.errors_match(expected, found):
                        is_expected = True
                        break

                if not is_expected:
                    unexpected_errors.append(found)
                    print(f"DEBUG: Unexpected error found: {found}")

            # Determine overall status
            if len(missing_errors) == 0 and len(unexpected_errors) == 0:
                if len(expected_errors) > 0:
                    status = 'PASS'
                    message = f'All {len(expected_errors)} expected errors found correctly'
                else:
                    status = 'PASS'
                    message = 'No errors expected and validation completed'
            elif len(missing_errors) == 0 and len(unexpected_errors) > 0:
                status = 'FAIL'
                message = f'All expected errors found, but {len(unexpected_errors)} unexpected errors occurred'
            elif len(missing_errors) > 0 and len(unexpected_errors) == 0:
                status = 'FAIL'
                message = f'{len(missing_errors)} expected errors missing'
            else:
                status = 'FAIL'
                message = f'{len(missing_errors)} expected errors missing, {len(unexpected_errors)} unexpected errors found'

            print(f"DEBUG: Validation result: {status} - {message}")

            return self.create_validation_result(status, message, expected_errors, found_errors, missing_errors, unexpected_errors, matched_errors)

        except Exception as e:
            print(f"DEBUG: Validation comparison failed: {str(e)}")
            return self.create_validation_result('ERROR', f'Validation comparison failed: {str(e)}', expected_errors, found_errors, [], [])

    def errors_match(self, expected: Dict, found: Dict) -> bool:
        """Check if an expected error matches a found error"""
        try:
            print(f"DEBUG: Comparing expected: {expected}")
            print(f"DEBUG: With found: {found}")

            # Compare the 5 key columns
            for col in self.validation_columns:
                expected_val = str(expected.get(col, '')).strip()
                found_val = str(found.get(col, '')).strip()

                print(f"DEBUG: Comparing {col}: '{expected_val}' vs '{found_val}'")

                # Handle RuleID as both string and int comparison
                if col == 'RuleID':
                    try:
                        if int(expected_val) != int(found_val):
                            print(f"DEBUG: RuleID mismatch: {expected_val} != {found_val}")
                            return False
                    except ValueError:
                        if expected_val != found_val:
                            print(f"DEBUG: RuleID string mismatch: '{expected_val}' != '{found_val}'")
                            return False
                else:
                    # Case-insensitive comparison for other fields
                    if expected_val != found_val:
                        print(f"DEBUG: {col} mismatch: '{expected_val}' != '{found_val}'")
                        return False

            print(f"DEBUG: MATCH FOUND!")
            return True

        except Exception as e:
            print(f"Error comparing errors: {e}")
            return False

    def create_validation_result(self, status: str, message: str, expected: List[Dict],
                               found: List[Dict], missing: List[Dict], unexpected: List[Dict],
                               matched: List[Dict] = None) -> Dict:
        """Create standardized validation result"""
        if matched is None:
            matched = []

        return {
            'validation_status': status,
            'validation_message': message,
            'expected_errors_count': len(expected),
            'found_errors_count': len(found),
            'matched_errors_count': len(matched),
            'missing_errors_count': len(missing),
            'unexpected_errors_count': len(unexpected),
            'expected_errors': expected,
            'found_errors': found,
            'missing_errors': missing,
            'unexpected_errors': unexpected,
            'matched_errors': matched
        }

    def format_validation_summary(self, validation_result: Dict) -> str:
        """Create a human-readable validation summary"""
        try:
            status = validation_result['validation_status']
            message = validation_result['validation_message']
            expected_count = validation_result['expected_errors_count']
            found_count = validation_result['found_errors_count']
            matched_count = validation_result['matched_errors_count']
            missing_count = validation_result['missing_errors_count']
            unexpected_count = validation_result['unexpected_errors_count']

            summary = f"Status: {status}\n"
            summary += f"Message: {message}\n\n"
            summary += f"Expected Errors: {expected_count}\n"
            summary += f"Found Errors: {found_count}\n"
            summary += f"Matched Errors: {matched_count}\n"
            summary += f"Missing Errors: {missing_count}\n"
            summary += f"Unexpected Errors: {unexpected_count}\n"

            if missing_count > 0:
                summary += f"\nMissing Errors:\n"
                for i, error in enumerate(validation_result['missing_errors'], 1):
                    summary += f"  {i}. {error.get_template_request('Transaction', '')}, {error.get_template_request('Type', '')}, {error.get_template_request('RuleID', '')}, {error.get_template_request('Object Name', '')}, {error.get_template_request('HAAD Field', '')}\n"

            if unexpected_count > 0:
                summary += f"\nUnexpected Errors:\n"
                for i, error in enumerate(validation_result['unexpected_errors'], 1):
                    summary += f"  {i}. {error.get_template_request('Transaction', '')}, {error.get_template_request('Type', '')}, {error.get_template_request('RuleID', '')}, {error.get_template_request('Object Name', '')}, {error.get_template_request('HAAD Field', '')}\n"

            return summary

        except Exception as e:
            return f"Error formatting validation summary: {str(e)}"