"""
Excel Handler - Enhanced with multi-sheet support and Response Extraction column support
"""

import pandas as pd
import os
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

import utils.common_variables
from utils import common_variables
from utils.common_variables import tc_precondition


def validate_excel(sheets_to_test: dict):
    expected_columns = [common_variables.tc_id, common_variables.tc_description, common_variables.tc_test_data,
                        common_variables.tc_rule_id, common_variables.tc_name, common_variables.tc_request_name, tc_precondition]
    # messages = []
    for sheet in sheets_to_test:
        actual_columns = list(sheets_to_test[sheet][0].keys())
        missing_columns = set(expected_columns) - set(actual_columns)
        # extra_columns = set(actual_columns) - set(expected_columns)
        if missing_columns:
            return False, f"Sheet {sheet} has missing columns: {missing_columns}"
        # elif extra_columns:
        #     messages.append(f"Sheet {sheet} has extra columns: {extra_columns}")
    return True, None


def create_excel_template(file_path):
    """
    Create an Excel template with just the headers from the original file
    """

    # Define the headers as they appear in the original file
    headers = [
        'TC ID',
        'Transaction Type',
        'Rule ID',
        'Precondition',
        'Object',
        'Element',
        'Title ',  # Note: original has a space after Title
        'Name',
        'Description',
        'Test Data',
        'Actual Result',
        'Objective (Expected Result)',
        'Priority',
        'ScenarioType',
        'Notes'
    ]

    # Create a new workbook and select the active worksheet
    wb = Workbook()
    ws = wb.active
    ws.title = "Template"

    # Add headers to the first row
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)

        # Format headers with bold font and light blue background
        cell.font = Font(bold=True, color="000000")
        cell.fill = PatternFill(start_color="B8CCE4", end_color="B8CCE4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Auto-adjust column widths based on header length
    for col_num, header in enumerate(headers, 1):
        column_letter = ws.cell(row=1, column=col_num).column_letter
        # Set minimum width of 12, maximum of 25
        width = max(12, min(len(header) + 2, 25))
        ws.column_dimensions[column_letter].width = width

    # Save the workbook
    wb.save(file_path)
    print(f"Excel template created successfully: {file_path}")
    print(f"Template contains {len(headers)} columns with headers only")

    return file_path

class ExcelHandler:
    def __init__(self, error_folder="error_files"):
        self.error_folder = error_folder
        self.ensure_error_folder()

    def set_error_folder(self, folder_path):
        """Set custom error folder path"""
        self.error_folder = folder_path
        self.ensure_error_folder()

    def ensure_error_folder(self):
        """Create error files folder if it doesn't exist"""
        if not os.path.exists(self.error_folder):
            os.makedirs(self.error_folder)

    def get_sheet_names(self, file_path):
        """
        Get all sheet names from an Excel file

        Args:
            file_path (str): Path to Excel file

        Returns:
            list: List of sheet names
        """
        try:
            excel_file = pd.ExcelFile(file_path)
            return excel_file.sheet_names
        except Exception as e:
            raise Exception(f"Failed to read Excel file sheets: {str(e)}")

    def load_excel(self, file_path, sheet_name=None):
        """
        Load Excel file and return data as list of dictionaries

        Args:
            file_path (str): Path to Excel file
            sheet_name (str, optional): Name of sheet to load. If None, loads first sheet.

        Returns:
            list: List of row dictionaries
        """
        try:
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path)
            # Convert NaN to empty strings
            df = df.fillna('')
            return df.to_dict('records')

        except Exception as e:
            raise Exception(f"Failed to load Excel file: {str(e)}")

    def load_excel_original_format(self, file_path, sheet_name=None):
        try:
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path)
            # Convert NaN to empty strings
            df = df.fillna('')
            return df

        except Exception as e:
            raise Exception(f"Failed to load Excel file: {str(e)}")

    def save_results(self, file_path, results_data):
        """
        Save test results to Excel file

        Args:
            file_path (str): Path to save results
            results_data (list): List of result dictionaries
        """
        try:
            df = pd.DataFrame(results_data)
            df.to_excel(file_path, index=False)

        except Exception as e:
            raise Exception(f"Failed to save results: {str(e)}")

    def save_execution_report(self, test_id, response_content, request_xml=None, request_headers=None, status_code=200, expected_errors=None):
        """
        Save execution report for ALL test cases (success or failure) with error validation

        Args:
            test_id (str): Test identifier
            response_content (str): Response content to save
            request_xml (str): The final processed XML that was sent (optional)
            request_headers (dict): The headers that were sent (optional)
            status_code (int): HTTP status code
            expected_errors (str): Expected errors string for validation (optional)

        Returns:
            str: Path to saved report file
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"report_{test_id}_{timestamp}.xlsx"
            file_path = os.path.join(self.error_folder, filename)

            # Extract SOAP response details (works for both success and error)
            soap_details = self.extract_soap_response_details(response_content)

            # Determine if this is a SOAP-level success or failure
            soap_success = self.is_soap_success(soap_details)
            report_type = "SUCCESS" if (status_code == 200 and soap_success) else "FAILURE"

            # Perform error validation if expected errors are provided
            validation_result = None
            decoded_error_csv = 'N/A'

            if expected_errors and expected_errors.strip():
                from utils.error_validator import ErrorValidator
                validator = ErrorValidator()
                validation_result = validator.extract_and_validate_errors(response_content, expected_errors, test_id)

                # Also get the decoded CSV content for the report
                error_report_base64 = validator.extract_error_report(response_content)
                if error_report_base64:
                    try:
                        decoded_errors = validator.decode_and_parse_error_report(error_report_base64)
                        if decoded_errors:
                            # Convert found errors back to CSV format for display
                            csv_lines = []
                            if decoded_errors:
                                # Add header row
                                headers = list(decoded_errors[0].get('_full_row', {}).keys()) if decoded_errors[0].get('_full_row') else ['Transaction', 'Type', 'RuleID', 'Object Name', 'HAAD Field', 'Field Value', 'Additional Reference', 'Error Text']
                                csv_lines.append(','.join(headers))

                                # Add data rows
                                for error in decoded_errors:
                                    if '_full_row' in error and error['_full_row']:
                                        row_values = [str(error['_full_row'].get(h, '')) for h in headers]
                                    else:
                                        # Fallback to validation columns
                                        row_values = [
                                            error.get('Transaction', ''),
                                            error.get('Type', ''),
                                            str(error.get('RuleID', '')),
                                            error.get('Object Name', ''),
                                            error.get('HAAD Field', ''),
                                            '', '', ''  # Field Value, Additional Reference, Error Text
                                        ]
                                    csv_lines.append(','.join(f'"{v}"' for v in row_values))

                                decoded_error_csv = '\n'.join(csv_lines)
                        else:
                            decoded_error_csv = 'Error report found but could not be parsed'
                    except Exception as e:
                        decoded_error_csv = f'Error decoding report: {str(e)}'

            # Build report data
            report_data = {
                'Test_ID': [test_id],
                'Timestamp': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                'Report_Type': [report_type],
                'HTTP_Status_Code': [status_code],
                'SOAP_Result_Code': [soap_details.get('result', 'N/A')],
                'SOAP_Message': [soap_details.get('message', 'N/A')],
                'Base64_Report_Content': [soap_details.get('report_base64', 'N/A')],
                'Decoded_Error_CSV': [decoded_error_csv],
                'Final_XML_Sent': [request_xml if request_xml else 'Not available'],
                'Request_Headers': [str(request_headers) if request_headers else 'Not available'],
                'Full_Response': [response_content]
            }

            # Add validation results if available
            if validation_result:
                report_data.update({
                    'Validation_Status': [validation_result.get('validation_status', 'N/A')],
                    'Validation_Message': [validation_result.get('validation_message', 'N/A')],
                    'Expected_Errors_Count': [validation_result.get('expected_errors_count', 0)],
                    'Found_Errors_Count': [validation_result.get('found_errors_count', 0)],
                    'Missing_Errors_Count': [validation_result.get('missing_errors_count', 0)],
                    'Unexpected_Errors_Count': [validation_result.get('unexpected_errors_count', 0)],
                    'Missing_Errors_Details': [validation_result.get('missing_errors_details', 'N/A')],
                    'Unexpected_Errors_Details': [validation_result.get('unexpected_errors_details', 'N/A')]
                })

            df = pd.DataFrame(report_data)
            df.to_excel(file_path, index=False)

            return file_path

        except Exception as e:
            raise Exception(f"Failed to save execution report: {str(e)}")

    def extract_soap_response_details(self, response_content):
        """
        Extract structured details from SOAP response

        Returns:
            dict: Contains 'result', 'message', and 'report_base64' keys
        """
        import re

        details = {
            'result': 'N/A',
            'message': 'N/A',
            'report_base64': 'N/A'
        }

        # Try to extract result code
        result_match = re.search(r'<result>(\d+)</result>', response_content, re.IGNORECASE)
        if result_match:
            details['result'] = result_match.group(1)

        # Try to extract message
        message_match = re.search(r'<message>(.*?)</message>', response_content, re.IGNORECASE | re.DOTALL)
        if message_match:
            details['message'] = message_match.group(1).strip()

        # Try to extract base64 report content
        report_match = re.search(r'<report>(.*?)</report>', response_content, re.IGNORECASE | re.DOTALL)
        if report_match:
            details['report_base64'] = report_match.group(1).strip()

        return details

    def is_soap_success(self, soap_details):
        """
        Determine if SOAP response indicates success

        Args:
            soap_details (dict): Details extracted from SOAP response

        Returns:
            bool: True if success, False otherwise
        """
        result = soap_details.get('result', 'N/A')
        # Result code 0 typically indicates success
        return result == '0' or result == 0




