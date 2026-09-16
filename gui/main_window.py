"""
Main Window - Updated with Assertion Testing Tab
"""

import customtkinter as ctk
from .manual_tab import ManualTab
from .batch_tab import BatchTab
from .assertion_tab import AssertionTab
from .encoder_tab import EncoderTab
from .help_tab import HelpTab
from .database_tab import DatabaseTab
from .request_generator_tab import RequestGeneratorTab
from .e2e_flows_tab import E2EFlowsTab
from .validator_tab import ValidatorTab

from .theme import FONTS

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.setup_window()
        self.create_tabs()

    def setup_window(self):
        """Configure main window"""
        self.root.title("SOAP API Testing Tool v2.1 - Enhanced with Assertion Testing")
        # geometry is set in main.py, but safe to set here too or just ignore
        pass

    def create_tabs(self):
        """Create the tabbed interface with new assertion tab"""
        # Create tabview
        self.tabview = ctk.CTkTabview(self.root)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Set luxurious font for tabs
        try:
            self.tabview._segmented_button.configure(font=FONTS["main_bold"])
        except:
            pass # Fallback if internal API changes

        # Create tabs
        self.tabview.add("Manual Testing")
        self.tabview.add("Batch Testing")
        self.tabview.add("Assertion Testing")
        self.tabview.add("XML Encoder")
        self.tabview.add("Database")
        self.tabview.add("Request Generator")
        self.tabview.add("E2E Flows")
        self.tabview.add("XML Validator")
        self.tabview.add("Help & Documentation")

        # Initialize tab contents
        # We pass the specific tab frame as the parent to the Tab classes
        self.manual_tab = ManualTab(self.tabview.tab("Manual Testing"))
        self.batch_tab = BatchTab(self.tabview.tab("Batch Testing"))
        self.assertion_tab = AssertionTab(self.tabview.tab("Assertion Testing"))
        self.encoder_tab = EncoderTab(self.tabview.tab("XML Encoder"))
        self.database_tab = DatabaseTab(self.tabview.tab("Database"))
        self.request_generator_tab = RequestGeneratorTab(self.tabview.tab("Request Generator"))
        self.e2e_flows_tab = E2EFlowsTab(self.tabview.tab("E2E Flows"))
        self.validator_tab = ValidatorTab(self.tabview.tab("XML Validator"))
        self.help_tab = HelpTab(self.tabview.tab("Help & Documentation"))