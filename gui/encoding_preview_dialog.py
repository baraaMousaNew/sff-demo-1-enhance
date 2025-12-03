"""
Encoding Preview Dialog - Shows encoding process step by step
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from utils.variable_processor import VariableProcessor


class EncodingPreviewDialog:
    def __init__(self, parent, excel_row_data):
        self.parent = parent
        self.excel_row_data = excel_row_data
        self.variable_processor = VariableProcessor()
        self.window = None

    def show_preview(self):
        """Show the encoding preview dialog"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("Encoding Preview - Raw_XML_* Columns Processing")
        self.window.geometry("1400x800")

        # Set up variable processor
        self.variable_processor.set_batch_context()
        self.variable_processor.set_test_context(1)

        # Get encoding column info
        encoding_info = self.variable_processor.get_encoding_columns_info(self.excel_row_data)

        if not encoding_info['columns']:
            messagebox.showinfo("No Encoding Columns", "No Raw_XML_* columns found in this row.")
            self.window.destroy()
            return

        self.create_widgets(encoding_info)

    def create_widgets(self, encoding_info):
        """Create the preview widgets"""
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text=f"Found {len(encoding_info['columns'])} Raw_XML_* columns",
                                font=('Arial', 12, 'bold'))
        title_label.pack(anchor=tk.W, pady=(0, 10))

        # Create notebook for each encoding column
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        for col_info in encoding_info['columns']:
            if col_info['has_content']:
                tab_frame = ttk.Frame(notebook)
                notebook.add(tab_frame, text=f"{col_info['suffix']} ({col_info['content_length']} chars)")
                self.create_encoding_tab(tab_frame, col_info)

        # Main XML preview
        if self.excel_row_data.get_template_request('XML_Body'):
            main_xml_frame = ttk.Frame(notebook)
            notebook.add(main_xml_frame, text="Main XML_Body")
            self.create_main_xml_tab(main_xml_frame, encoding_info)

        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Process All Again", command=lambda: self.refresh_preview(encoding_info)).pack(
            side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT)

    def create_encoding_tab(self, parent, col_info):
        """Create tab for individual encoding column"""
        # Create three sections: Original, Processed, Encoded
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Original XML with variables
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text=f"Original {col_info['name']} (with variables):",
                  font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        original_text = scrolledtext.ScrolledText(left_frame, height=25, wrap=tk.WORD)
        original_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        original_xml = str(self.excel_row_data.get_template_request(col_info['name'], ''))
        original_text.insert("1.0", original_xml)
        original_text.configure(state='disabled')

        # Processed XML (variables replaced)
        middle_frame = ttk.Frame(paned)
        paned.add(middle_frame, weight=1)

        ttk.Label(middle_frame, text="Processed XML (variables replaced):",
                  font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        processed_text = scrolledtext.ScrolledText(middle_frame, height=25, wrap=tk.WORD)
        processed_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        try:
            processed_xml = self.variable_processor.process_raw_xml_variables(original_xml)
            processed_text.insert("1.0", processed_xml)
        except Exception as e:
            processed_text.insert("1.0", f"Error processing variables: {str(e)}")
        processed_text.configure(state='disabled')

        # Base64 encoded result
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        ttk.Label(right_frame, text="Base64 Encoded Result:",
                  font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        encoded_text = scrolledtext.ScrolledText(right_frame, height=25, wrap=tk.WORD)
        encoded_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        try:
            processed_xml = self.variable_processor.process_raw_xml_variables(original_xml)
            import base64
            encoded_result = base64.b64encode(processed_xml.encode('utf-8')).decode('utf-8')
            encoded_text.insert("1.0", encoded_result)

            # Add info about the encoding
            info_text = f"Placeholder: {col_info['placeholder']}\nEncoded Length: {len(encoded_result)} characters\n\n"
            encoded_text.insert("1.0", info_text)
        except Exception as e:
            encoded_text.insert("1.0", f"Error encoding: {str(e)}")
        encoded_text.configure(state='disabled')

        # Copy button for encoded result
        copy_frame = ttk.Frame(right_frame)
        copy_frame.pack(fill=tk.X)

        def copy_encoded():
            try:
                processed_xml = self.variable_processor.process_raw_xml_variables(original_xml)
                import base64
                encoded_result = base64.b64encode(processed_xml.encode('utf-8')).decode('utf-8')
                self.window.clipboard_clear()
                self.window.clipboard_append(encoded_result)
                messagebox.showinfo("Copied",
                                    f"Base64 encoded content copied to clipboard\n({len(encoded_result)} characters)")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy: {str(e)}")

        ttk.Button(copy_frame, text="Copy Encoded", command=copy_encoded).pack(side=tk.LEFT)

    def create_main_xml_tab(self, parent, encoding_info):
        """Create tab showing main XML with encoded placeholders"""
        # Create two sections: Before and After
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Original main XML with placeholders
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Original XML_Body (with {{ENCODED_XML_*}} placeholders):",
                  font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        original_main_text = scrolledtext.ScrolledText(left_frame, height=30, wrap=tk.WORD)
        original_main_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        main_xml = str(self.excel_row_data.get_template_request('XML_Body', ''))
        original_main_text.insert("1.0", main_xml)
        original_main_text.configure(state='disabled')

        # Processed main XML with encoded content
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        ttk.Label(right_frame, text="Final XML (with encoded content and all variables processed):",
                  font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        final_main_text = scrolledtext.ScrolledText(right_frame, height=30, wrap=tk.WORD)
        final_main_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        try:
            # Process the complete XML including encoding
            final_xml = self.variable_processor.process_variables(main_xml, self.excel_row_data)
            final_main_text.insert("1.0", final_xml)
        except Exception as e:
            final_main_text.insert("1.0", f"Error processing main XML: {str(e)}")
        final_main_text.configure(state='disabled')

        # Copy button for final XML
        copy_frame = ttk.Frame(right_frame)
        copy_frame.pack(fill=tk.X)

        def copy_final():
            try:
                final_xml = self.variable_processor.process_variables(main_xml, self.excel_row_data)
                self.window.clipboard_clear()
                self.window.clipboard_append(final_xml)
                messagebox.showinfo("Copied", f"Final processed XML copied to clipboard\n({len(final_xml)} characters)")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy: {str(e)}")

        ttk.Button(copy_frame, text="Copy Final XML", command=copy_final).pack(side=tk.LEFT)

        # Show placeholder mapping
        info_frame = ttk.Frame(right_frame)
        info_frame.pack(fill=tk.X, pady=(5, 0))

        info_text = "Placeholder Mappings:\n"
        for col_info in encoding_info['columns']:
            if col_info['has_content']:
                info_text += f"• {col_info['placeholder']} → {col_info['name']}\n"

        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT,
                               font=('Arial', 9), foreground='blue')
        info_label.pack(anchor=tk.W)

    def refresh_preview(self, encoding_info):
        """Refresh the preview with new variable values"""
        # Set up fresh variable processor context
        self.variable_processor.set_batch_context()
        self.variable_processor.set_test_context(1)

        # Close and recreate the window
        self.window.destroy()
        self.show_preview()