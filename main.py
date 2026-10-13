"""Nova entry point. Prepares the database, starts the local server, and opens the Nova window.

The window is a native app window: pywebview if it is installed, otherwise an app-style window of Microsoft Edge or
Google Chrome (both give the real glass look), otherwise your default browser. The old CustomTkinter version still
works: run `python classic_main.py`.
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from database.db_manager import get_db_path, initialize_database
from services import ai_service, settings_service

TITLE = "Nova"
SIZE = (1360, 860)


def fail(message):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(TITLE, message)
    except Exception:  # no dialog available: print instead
        print(message)
    sys.exit(1)


def find_browser():
    candidates = []
    for root_name in ("ProgramFiles(x86)", "ProgramFiles", "LocalAppData"):
        base = os.environ.get(root_name)
        if base:
            candidates += [Path(base) / "Microsoft/Edge/Application/msedge.exe", Path(base) / "Google/Chrome/Application/chrome.exe"]
    candidates += [Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                   Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    candidates += [Path(p) for name in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser") if (p := shutil.which(name))]
    return next((str(path) for path in candidates if path.exists()), None)


def open_window(url, stop, maximized):
    """Show Nova. Returns when the window is closed (or sets `stop` from a helper thread)."""
    try:
        import webview  # optional: pip install pywebview
        webview.create_window(TITLE, url, width=SIZE[0], height=SIZE[1], min_size=(900, 600), background_color="#0B1524",
                              maximized=bool(maximized))
        webview.start(private_mode=False, storage_path=str(get_db_path().parent / "webview"))
        return
    except ImportError:
        pass
    except Exception as error:  # pywebview is installed but cannot start (for example a missing runtime)
        print(f"pywebview could not start ({error}); using a browser window instead.")
    browser = find_browser()
    if browser:
        profile = get_db_path().parent / "window"
        args = [browser, f"--app={url}", f"--user-data-dir={profile}", f"--window-size={SIZE[0]},{SIZE[1]}",
                "--no-first-run", "--no-default-browser-check"] + (["--start-maximized"] if maximized else [])
        subprocess.Popen(args)  # the window tells the server when it closes, so there is no need to wait on it
    else:
        webbrowser.open(url)
    stop.wait()


def main():
    try:
        initialize_database()
        settings = settings_service.load_all()
    except (sqlite3.Error, OSError) as error:
        fail(f"Nova could not open its database.\n\n{error}")
    ai_service.load_saved_keys()

    import server
    httpd = server.make_server()
    server.start(httpd)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    stop = threading.Event()
    threading.Thread(target=server.idle_watch, args=(stop,), daemon=True).start()
    print(f"Nova is running at {url}  (close the Nova window to quit)")
    open_window(url, stop, settings.get("start_maximized"))
    httpd.shutdown()


if __name__ == "__main__":
    main()
