"""Nova entry point: prepare the database, then open the window."""
import sqlite3
import sys
import tkinter as tk
from tkinter import messagebox

from database.db_manager import initialize_database
from ui.app import NovaApp


def main():
    try:
        initialize_database()
    except (sqlite3.Error, OSError) as error:
        root = tk.Tk()
        root.withdraw()  # hide the empty window; we only want the message box
        messagebox.showerror("Nova", f"Nova could not open its database.\n\n{error}")
        sys.exit(1)

    NovaApp().mainloop()


if __name__ == "__main__":
    main()