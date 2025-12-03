"""
Main Window - Updated with Assertion Testing Tab
"""

import tkinter as tk
from tkinter import ttk
from .manual_tab import ManualTab
from .batch_tab import BatchTab
from .assertion_tab import AssertionTab
from .encoder_tab import EncoderTab
from .help_tab import HelpTab


class MainWindow:
    def __init__(self, root):
        self.root = root
        self.setup_window()
        self.create_tabs()

    def setup_window(self):
        """Configure main window"""
        self.root.title("SOAP API Testing Tool v2.1 - Enhanced with Assertion Testing")
        self.root.geometry("1600x1000")

    def create_tabs(self):
        """Create the tabbed interface with new assertion tab"""
        # Create notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self.manual_tab = ManualTab(self.notebook)
        self.batch_tab = BatchTab(self.notebook)
        self.assertion_tab = AssertionTab(self.notebook)  # New assertion tab
        self.encoder_tab = EncoderTab(self.notebook)
        self.help_tab = HelpTab(self.notebook)

        # Add tabs to notebook
        self.notebook.add(self.manual_tab.frame, text="Manual Testing")
        self.notebook.add(self.batch_tab.frame, text="Batch Testing")
        self.notebook.add(self.assertion_tab.frame, text="Assertion Testing")  # New tab
        self.notebook.add(self.encoder_tab.frame, text="XML Encoder")
        self.notebook.add(self.help_tab.frame, text="Help & Documentation")