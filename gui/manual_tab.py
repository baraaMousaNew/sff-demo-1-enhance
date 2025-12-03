"""
Manual Testing Tab - Single API request testing with variable processing
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from utils.api_client import APIClient
from utils.xml_utils import format_xml
from utils.variable_processor import VariableProcessor
from datetime import datetime

class ManualTab:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.api_client = APIClient()
        self.variable_processor = VariableProcessor()
        self.create_widgets()

    def create_widgets(self):
        """Create manual testing widgets"""
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left side - Input
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # URL input
        ttk.Label(left_frame, text="Endpoint URL:").pack(anchor=tk.W)
        self.url_entry = ttk.Entry(left_frame, width=60)
        self.url_entry.pack(fill=tk.X, pady=(0, 10))

        # Custom Headers
        ttk.Label(left_frame, text="Custom Headers (one per line: Header: Value):").pack(anchor=tk.W)
        self.headers_text = scrolledtext.ScrolledText(left_frame, height=3)
        self.headers_text.pack(fill=tk.X, pady=(0, 10))
        self.headers_text.insert("1.0", "SOAPAction: \nContent-Type: text/xml; charset=utf-8")

        # Variable Definitions
        ttk.Label(left_frame, text="Variable Definitions (var_name={{FUNCTION()}};var_name2={{FUNCTION2()}}):").pack(anchor=tk.W)
        self.variables_text = scrolledtext.ScrolledText(left_frame, height=2)
        self.variables_text.pack(fill=tk.X, pady=(0, 10))
        self.variables_text.insert("1.0", "txn_ref={{CUSTOM.generate_transaction_ref()}};batch_id={{RUN_ID()}}")

        # XML Body
        ttk.Label(left_frame, text="XML Body (supports variables like {{DATE(YYYY-MM-DD)}} and declared variables like {{VAR.txn_ref}}):").pack(anchor=tk.W)
        self.xml_body = scrolledtext.ScrolledText(left_frame, height=15)
        self.xml_body.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Send Request", command=self.send_request).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Format XML", command=self.format_xml).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Clear", command=self.clear_all).pack(side=tk.LEFT)

        # Right side - Response
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Status
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(right_frame, textvariable=self.status_var).pack(anchor=tk.W)

        # Response
        ttk.Label(right_frame, text="Response:").pack(anchor=tk.W, pady=(10, 0))
        self.response_text = scrolledtext.ScrolledText(right_frame, height=20)
        self.response_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Response buttons
        resp_buttons = ttk.Frame(right_frame)
        resp_buttons.pack(fill=tk.X)
        ttk.Button(resp_buttons, text="Decode Base64", command=self.decode_response).pack(side=tk.LEFT)

    def send_request(self):
        """Send the API request with variable processing"""
        url = self.url_entry.get().strip()
        xml_data = self.xml_body.get("1.0", tk.END).strip()

        if not url or not xml_data:
            messagebox.showerror("Error", "Please fill URL and XML body")
            return

        # Parse custom headers
        headers_text = self.headers_text.get("1.0", tk.END).strip()
        soap_action = None

        for line in headers_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                if key.strip().lower() == 'soapaction':
                    soap_action = value.strip()
                    break

        self.status_var.set("Processing variables and sending request...")
        self.frame.update()

        try:
            # Set up variable processor for single test
            self.variable_processor.set_batch_context()
            self.variable_processor.set_test_context(1)

            # Create mock Excel row data for variable definitions
            variables_definition = self.variables_text.get("1.0", tk.END).strip()
            mock_excel_data = {}
            if variables_definition:
                mock_excel_data['Variable_Definitions'] = variables_definition

            # Process variables in XML (including variable definitions)
            processed_xml = self.variable_processor.process_variables(xml_data, mock_excel_data)

            response = self.api_client.send_request(
                url=url,
                xml_body=processed_xml,
                soap_action=soap_action,
                debug=True
            )

            self.status_var.set(f"Status: {response['status_code']} | Time: {response['response_time']:.2f}ms")
            self.response_text.delete("1.0", tk.END)

            # Show debug info including processed XML
            debug_info = f"=== PROCESSED XML SENT ===\n{processed_xml}\n\n"
            debug_info += f"=== REQUEST HEADERS ===\n"
            for key, value in response.get('request_headers', {}).items():
                debug_info += f"{key}: {value}\n"
            debug_info += f"\n=== RESPONSE HEADERS ===\n"
            for key, value in response.get('response_headers', {}).items():
                debug_info += f"{key}: {value}\n"
            debug_info += f"\n=== RESPONSE BODY ===\n"

            self.response_text.insert("1.0", debug_info + response['content'])


        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            messagebox.showerror("Request Error", str(e))

    def extract_soap_details_from_response(self, response_content):
        """Extract SOAP details from response for manual testing"""
        from utils.excel_handler import ExcelHandler
        excel_handler = ExcelHandler()
        return excel_handler.extract_soap_response_details(response_content)

    def has_soap_level_errors(self, soap_details):
        """Check if SOAP response has business logic errors"""
        result_code = soap_details.get_template_request('result', '').strip()
        message = soap_details.get_template_request('message', '').strip().lower()

        # Common failure indicators
        failure_indicators = ['[invalid field]', 'error', 'failed', 'invalid', 'exception']

        # Check for failure result codes or error messages
        if result_code in ['-1', '-2', '-3', '0', 'false', 'error']:
            return True

        for indicator in failure_indicators:
            if indicator in message:
                return True

        return False

    def show_processed_xml_window(self, original_xml, processed_xml):
        """Show original and processed XML side by side"""
        window = tk.Toplevel(self.frame)
        window.title("Variable Processing Results")
        window.geometry("1200x700")

        # Create two frames side by side
        left_frame = ttk.Frame(window)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 5), pady=10)

        right_frame = ttk.Frame(window)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 10), pady=10)

        # Original XML
        ttk.Label(left_frame, text="Original XML (with variables):").pack(anchor=tk.W)
        original_text = scrolledtext.ScrolledText(left_frame, height=30, wrap=tk.WORD)
        original_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        original_text.insert("1.0", original_xml)
        original_text.configure(state='disabled')  # Make read-only

        # Processed XML
        ttk.Label(right_frame, text="Processed XML (variables replaced):").pack(anchor=tk.W)
        processed_text = scrolledtext.ScrolledText(right_frame, height=30, wrap=tk.WORD)
        processed_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        processed_text.insert("1.0", processed_xml)
        processed_text.configure(state='disabled')  # Make read-only

        # Buttons
        button_frame = ttk.Frame(window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        def copy_processed():
            window.clipboard_clear()
            window.clipboard_append(processed_xml)
            messagebox.showinfo("Copied", "Processed XML copied to clipboard")

        def use_processed():
            self.xml_body.delete("1.0", tk.END)
            self.xml_body.insert("1.0", processed_xml)
            window.destroy()
            messagebox.showinfo("Updated", "XML body updated with processed version")

        def process_again():
            # Process variables again with fresh values
            try:
                self.variable_processor.set_batch_context()  # Fresh context
                self.variable_processor.set_test_context(1)
                new_processed = self.variable_processor.process_variables(original_xml)

                processed_text.configure(state='normal')
                processed_text.delete("1.0", tk.END)
                processed_text.insert("1.0", new_processed)
                processed_text.configure(state='disabled')

            except Exception as e:
                messagebox.showerror("Error", f"Failed to reprocess: {str(e)}")

        ttk.Button(button_frame, text="Copy Processed", command=copy_processed).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Use Processed", command=use_processed).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Process Again", command=process_again).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=window.destroy).pack(side=tk.RIGHT)

    def clear_all(self):
        """Clear all fields"""
        self.url_entry.delete(0, tk.END)
        self.headers_text.delete("1.0", tk.END)
        self.headers_text.insert("1.0", "SOAPAction: \nContent-Type: text/xml; charset=utf-8")
        self.variables_text.delete("1.0", tk.END)
        self.variables_text.insert("1.0", "txn_ref={{CUSTOM.generate_transaction_ref()}};batch_id={{RUN_ID()}}")
        self.xml_body.delete("1.0", tk.END)
        self.response_text.delete("1.0", tk.END)
        self.status_var.set("Ready")

    def format_xml(self):
        """Format XML in body"""
        xml_content = self.xml_body.get("1.0", tk.END).strip()
        if xml_content:
            formatted = format_xml(xml_content)
            if formatted:
                self.xml_body.delete("1.0", tk.END)
                self.xml_body.insert("1.0", formatted)

    def decode_response(self):
        """Manually decode selected Base64 content in response"""
        response_content = self.response_text.get("1.0", tk.END).strip()

        # if response_content:

        # Show input dialog to get Base64 content to decode
        decode_window = tk.Toplevel(self.frame)
        decode_window.title("Decode Base64 Content")
        decode_window.geometry("700x600")

        # Instructions
        ttk.Label(decode_window, text="Paste the Base64 content you want to decode:").pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Input area for Base64 content
        input_frame = ttk.Frame(decode_window)
        input_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        base64_input = scrolledtext.ScrolledText(input_frame, height=8)
        base64_input.pack(fill=tk.BOTH, expand=True)

        # Output area for decoded content
        ttk.Label(decode_window, text="Decoded content will appear below:").pack(anchor=tk.W, padx=10)

        decoded_output = scrolledtext.ScrolledText(decode_window, height=12)
        decoded_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        def perform_decode():
            base64_content = base64_input.get("1.0", tk.END).strip()
            if not base64_content:
                messagebox.showwarning("Warning", "Please paste Base64 content to decode")
                return

            try:
                from utils.xml_utils import decode_base64_content_manually
                decoded_result = decode_base64_content_manually(base64_content)

                decoded_output.delete("1.0", tk.END)
                decoded_output.insert("1.0", decoded_result)

            except Exception as e:
                messagebox.showerror("Decode Error", f"Failed to decode: {str(e)}")

        def save_decoded():
            content = decoded_output.get("1.0", tk.END).strip()
            if content:
                from tkinter import filedialog
                file_path = filedialog.asksaveasfilename(
                    title="Save Decoded Content",
                    defaultextension=".xlsx",
                    filetypes=[("Excel files", "*.xlsx"), ("Text files", "*.txt"), ("All files", "*.*")]
                )
                if file_path:
                    try:
                        if file_path.endswith('.xlsx'):
                            import pandas as pd
                            df = pd.DataFrame({
                                'Decoded_Content': [content],
                                'Timestamp': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                            })
                            df.to_excel(file_path, index=False)
                        else:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                        messagebox.showinfo("Success", f"Content saved to {file_path}")
                    except Exception as e:
                        messagebox.showerror("Save Error", str(e))

        # Buttons
        button_frame = ttk.Frame(decode_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(button_frame, text="Decode", command=perform_decode).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Save Decoded", command=save_decoded).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=decode_window.destroy).pack(side=tk.RIGHT)
        # else:
        #     messagebox.showwarning("Warning", "No response to decode")