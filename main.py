"""
SOAP API Testing Tool - Entry Point
Simple GUI for testing SOAP APIs manually and in batch mode
"""
import customtkinter as ctk
import os
import sys
from gui.main_window import MainWindow
from gui.theme import setup_app_config, apply_styles

def main():
    # 1. Configuration (Pre-Root)
    setup_app_config()
    
    # 2. Create Root Window
    root = ctk.CTk()
    root.title("SOAP API Testing Tool")
    root.geometry("1600x1000")
    
    # 3. Apply Styles (Post-Root) to avoid ghost window
    apply_styles(root)
    
    # 4. Initialize App
    app = MainWindow(root)
    
    # Handle closing properly to kill all threads/processes.
    # os._exit() is required (not sys.exit) because jaydebeapi starts a JVM via
    # JPype whose non-daemon threads would keep the process alive after the window
    # closes, locking files inside the dist folder.
    def on_closing():
        root.destroy()
        os._exit(0)
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    root.mainloop()

if __name__ == "__main__":
    main()