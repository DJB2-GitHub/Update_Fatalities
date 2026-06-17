import tkinter as tk
from tkinter import messagebox
import traceback

# Import the main application class from main.py
from main import App

if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        # In a .pyw file, there is no console to print to.
        # If a fatal error occurs during startup, we show it in a standard Tkinter dialog instead.
        err_msg = traceback.format_exc()
        
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Fatal Application Error", 
            f"The application encountered a critical error and must close:\n\n{err_msg}"
        )
