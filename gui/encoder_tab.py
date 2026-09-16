"""
XML Encoder Tab - Base64 encoding/decoding for XML
"""

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import base64
from utils.xml_utils import format_xml
from .theme import FONTS


class EncoderTab:
    def __init__(self, parent):
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.pack(fill="both", expand=True)
        self.create_widgets()

    def create_widgets(self):
        """Create encoder widgets"""
        main_frame = ctk.CTkFrame(self.frame)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Raw XML section
        ctk.CTkLabel(main_frame, text="Raw XML Input:", anchor="w", font=FONTS["main_bold"]).pack(anchor="w", padx=5, pady=5)
        self.raw_xml = ctk.CTkTextbox(main_frame, height=150)
        self.raw_xml.pack(fill="both", expand=True, padx=5, pady=(0, 10))

        # Buttons
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(0, 10), padx=5)

        ctk.CTkButton(button_frame, text="Encode to Base64", command=self.encode_xml, font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(button_frame, text="Format XML", command=self.format_xml, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(button_frame, text="Clear", command=self.clear_all, fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(button_frame, text="Copy to Clipboard", command=self.copy_raw_to_clipboard, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), font=FONTS["button"]).pack(side="left")

        # Base64 output section
        ctk.CTkLabel(main_frame, text="Base64 Output:", anchor="w", font=FONTS["main_bold"]).pack(anchor="w", padx=5, pady=5)
        self.base64_output = ctk.CTkTextbox(main_frame, height=150)
        self.base64_output.pack(fill="both", expand=True, padx=5, pady=(0, 10))

        # Output buttons
        output_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        output_frame.pack(fill="x", padx=5)

        ctk.CTkButton(output_frame, text="Decode from Base64", command=self.decode_xml, fg_color="green", hover_color="#006400", font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(output_frame, text="Copy to Clipboard", command=self.copy_to_clipboard, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), font=FONTS["button"]).pack(side="left", padx=(0, 5))
        ctk.CTkButton(output_frame, text="Clear", command=lambda: self.base64_output.delete("1.0", "end"), fg_color="gray", hover_color="#404040", font=FONTS["button"]).pack(side="left")

    def encode_xml(self):
        """Encode XML to Base64"""
        raw_xml = self.raw_xml.get("1.0", "end").strip()

        if not raw_xml:
            messagebox.showwarning("Warning", "Please enter XML to encode")
            return

        try:
            encoded = base64.b64encode(raw_xml.encode('utf-8')).decode('utf-8')
            self.base64_output.delete("1.0", "end")
            self.base64_output.insert("1.0", encoded)

        except Exception as e:
            messagebox.showerror("Encoding Error", str(e))

    def decode_xml(self):
        """Decode Base64 to XML"""
        base64_content = self.base64_output.get("1.0", "end").strip()

        if not base64_content:
            messagebox.showwarning("Warning", "Please enter Base64 content to decode")
            return

        try:
            decoded = base64.b64decode(base64_content).decode('utf-8')
            self.raw_xml.delete("1.0", "end")
            self.raw_xml.insert("1.0", decoded)

        except Exception as e:
            messagebox.showerror("Decoding Error", str(e))

    def format_xml(self):
        """Format XML in raw input"""
        xml_content = self.raw_xml.get("1.0", "end").strip()

        if xml_content:
            formatted = format_xml(xml_content)
            if formatted:
                self.raw_xml.delete("1.0", "end")
                self.raw_xml.insert("1.0", formatted)

    def clear_all(self):
        """Clear all text areas"""
        self.raw_xml.delete("1.0", "end")
        self.base64_output.delete("1.0", "end")

    def copy_raw_to_clipboard(self):
        """Copy Raw XML input to clipboard"""
        content = self.raw_xml.get("1.0", "end").strip()
        if content:
            self.frame.clipboard_clear()
            self.frame.clipboard_append(content)
            messagebox.showinfo("Success", "Content copied to clipboard")
        else:
            messagebox.showwarning("Warning", "No content to copy")

    def copy_to_clipboard(self):
        """Copy Base64 output to clipboard"""
        content = self.base64_output.get("1.0", "end").strip()

        if content:
            self.frame.clipboard_clear()
            self.frame.clipboard_append(content)
            messagebox.showinfo("Success", "Content copied to clipboard")
        else:
            messagebox.showwarning("Warning", "No content to copy")
