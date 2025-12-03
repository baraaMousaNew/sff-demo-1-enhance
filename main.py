"""
SOAP API Testing Tool - Entry Point
Simple GUI for testing SOAP APIs manually and in batch mode
"""
import tkinter as tk

from gui.main_window import MainWindow


def main():
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()