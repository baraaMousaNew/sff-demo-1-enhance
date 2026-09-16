import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

# Define colors globally or in a getter to share
COLORS = {
    "primary": "#1f538d",       # Default CTk Blue
    "primary_hover": "#14375e",
    "bg_main": "#2b2b2b",       # Dark Grey
    "bg_card": "#333333",       # Slightly lighter for cards
    "text": "#ffffff",
    "text_sub": "#d1d1d1",
    "success": "#2cc985",
    "danger": "#ff4d4d",
    "warning": "#ffc107"
}

# Define luxurious fonts
# Increasing sizes for "luxurious" feel and readability
FONTS = {
    "main": ("Roboto Medium", 14),
    "main_bold": ("Roboto Medium", 14, "bold"),
    "button": ("Roboto Medium", 14, "bold"), 
    "sub_header": ("Roboto Medium", 16, "bold"),
    "header": ("Roboto Medium", 20, "bold"),
    "title": ("Roboto Medium", 24, "bold"),
    "code": ("Courier New", 15),
    "small": ("Roboto Medium", 12)
}

def setup_theme():
    """
    Deprecated: Use setup_app_config() before root creation and apply_styles() after.
    Kept for backward compatibility if needed, but will cause the ghost window issue if called before root.
    """
    setup_app_config()
    # If we call apply_styles here without a root, it creates a ghost window.
    # So we simply return the colors. The user must call apply_styles explicitly if they want ttk styling.
    return COLORS

def setup_app_config():
    """
    Configures CTk appearance settings. call this BEFORE creating the root window.
    """
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

def apply_styles(root=None):
    """
    Applies ttk styles. Call this AFTER creating the root window.
    """
    # Apply ttk styles for widgets that don't have CTk equivalents (like Treeview)
    style = ttk.Style(root)
    style.theme_use('default')
    
    style.configure("Treeview",
                    background=COLORS["bg_card"],
                    foreground=COLORS["text"],
                    rowheight=35, # Increased row height
                    fieldbackground=COLORS["bg_card"],
                    borderwidth=0,
                    font=('Arial', 12)) # Increased font
    
    style.map('Treeview', background=[('selected', COLORS["primary"])], foreground=[('selected', 'white')])
    
    style.configure("Treeview.Heading",
                    background="#1a1a1a",
                    foreground=COLORS["text"],
                    relief="flat",
                    font=('Arial', 13, 'bold')) # Increased font
                    
    style.map("Treeview.Heading",
              background=[('active', COLORS["primary"])])
              
    return COLORS

