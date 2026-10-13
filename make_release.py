"""Builds the downloadable zip for the website's Download page.

Run from the Nova folder:   python make_release.py
The zip holds only the app's source files: no .venv, no database, no cache files, and no API keys.
"""
import hashlib
import re
import sys
import zipfile
from pathlib import Path

VERSION = "1.5"
ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "website" / "downloads" / f"Nova-app-v{VERSION}.zip"
FILES = ["main.py", "classic_main.py", "api.py", "server.py", "requirements.txt", "README.md", "TEST_CHECKLIST.md"]
FOLDERS = ["database", "services", "ui", "web", "tests"]
SKIP_PARTS = {"__pycache__", ".venv"}
SKIP_SUFFIXES = {".pyc", ".db", ".sqlite", ".sqlite3"}
SECRET_PATTERNS = [re.compile(r"AIza[0-9A-Za-z_\-]{35}"), re.compile(r"sk-ant-[0-9A-Za-z_\-]{20,}")]


def collect():
    paths = [ROOT / name for name in FILES if (ROOT / name).exists()]
    for folder in FOLDERS:
        paths += [p for p in sorted((ROOT / folder).rglob("*")) if p.is_file()]
    return [p for p in paths if not (SKIP_PARTS & set(p.relative_to(ROOT).parts)) and p.suffix not in SKIP_SUFFIXES]


def find_secrets(paths):
    """Safety check: refuse to package anything that looks like a pasted API key."""
    found = []
    for path in paths:
        if path.suffix in {".py", ".md", ".txt"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                found.append(path)
    return found


def main():
    missing = [name for name in ("main.py", "database", "services", "ui") if not (ROOT / name).exists()]
    if missing:
        sys.exit(f"Run this from the Nova folder. Missing: {', '.join(missing)}")
    paths = collect()
    leaks = find_secrets(paths)
    if leaks:
        sys.exit("Stopped: something that looks like an API key was found in:\n"
                 + "\n".join(f"  {p.relative_to(ROOT)}" for p in leaks)
                 + "\nRemove it, delete that key on its provider's website, and try again.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, Path("Nova") / path.relative_to(ROOT))  # everything unzips into one Nova folder
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    print(f"Created {OUTPUT}")
    print(f"{len(paths)} files, {OUTPUT.stat().st_size / 1024:.0f} KB")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()