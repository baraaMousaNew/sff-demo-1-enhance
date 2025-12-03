"""
XML Encoder Tab - Base64 encoding/decoding for XML
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import base64
from utils.xml_utils import format_xml


class EncoderTab:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.create_widgets()

    def create_widgets(self):
        """Create encoder widgets"""
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Raw XML section
        ttk.Label(main_frame, text="Raw XML Input:").pack(anchor=tk.W)
        self.raw_xml = scrolledtext.ScrolledText(main_frame, height=12)
        self.raw_xml.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(button_frame, text="Encode to Base64", command=self.encode_xml).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Decode from Base64", command=self.decode_xml).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Format XML", command=self.format_xml).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Clear", command=self.clear_all).pack(side=tk.LEFT)

        # Base64 output section
        ttk.Label(main_frame, text="Base64 Output:").pack(anchor=tk.W)
        self.base64_output = scrolledtext.ScrolledText(main_frame, height=12)
        self.base64_output.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Output buttons
        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill=tk.X)

        ttk.Button(output_frame, text="Copy to Clipboard", command=self.copy_to_clipboard).pack(side=tk.LEFT)

    def encode_xml(self):
        """Encode XML to Base64"""
        raw_xml = self.raw_xml.get("1.0", tk.END).strip()

        if not raw_xml:
            messagebox.showwarning("Warning", "Please enter XML to encode")
            return

        try:
            encoded = base64.b64encode(raw_xml.encode('utf-8')).decode('utf-8')
            self.base64_output.delete("1.0", tk.END)
            self.base64_output.insert("1.0", encoded)

        except Exception as e:
            messagebox.showerror("Encoding Error", str(e))

    def decode_xml(self):
        """Decode Base64 to XML"""
        base64_content = self.base64_output.get("1.0", tk.END).strip()

        if not base64_content:
            messagebox.showwarning("Warning", "Please enter Base64 content to decode")
            return

        try:
            decoded = base64.b64decode(base64_content).decode('utf-8')
            self.raw_xml.delete("1.0", tk.END)
            self.raw_xml.insert("1.0", decoded)

        except Exception as e:
            messagebox.showerror("Decoding Error", str(e))

    def format_xml(self):
        """Format XML in raw input"""
        xml_content = self.raw_xml.get("1.0", tk.END).strip()

        if xml_content:
            formatted = format_xml(xml_content)
            if formatted:
                self.raw_xml.delete("1.0", tk.END)
                self.raw_xml.insert("1.0", formatted)

    def clear_all(self):
        """Clear all text areas"""
        self.raw_xml.delete("1.0", tk.END)
        self.base64_output.delete("1.0", tk.END)

    def copy_to_clipboard(self):
        """Copy Base64 output to clipboard"""
        content = self.base64_output.get("1.0", tk.END).strip()

        if content:
            self.frame.clipboard_clear()
            self.frame.clipboard_append(content)
            messagebox.showinfo("Success", "Content copied to clipboard")
        else:
            messagebox.showwarning("Warning", "No content to copy")