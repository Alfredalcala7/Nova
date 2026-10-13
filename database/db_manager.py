"""Database connection and first-run setup. No screen code belongs here."""
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from database.schema import DEFAULT_SETTINGS, MIGRATIONS, SCHEMA_SQL


def get_db_path() -> Path:
    """Return the database file path, e.g. C:\\Users\\You\\AppData\\Roaming\\Nova\\nova.db.

    A fixed per-user folder keeps the data safe no matter where the app is started from.
    """
    base = os.environ.get("APPDATA") or str(Path.home())
    folder = Path(base) / "Nova"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "nova.db"


def get_connection() -> sqlite3.Connection:
    """Open a connection that returns rows by column name and enforces foreign keys."""
    connection = sqlite3.connect(get_db_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")  # SQLite ignores foreign keys unless asked
    return connection


def initialize_database() -> None:
    """Create any missing tables and default settings. Safe to run on every start."""
    # 'closing' closes the connection; the second 'with' commits (or rolls back on error).
    with closing(get_connection()) as connection, connection:
        connection.executescript(SCHEMA_SQL)
        for table, column, definition in MIGRATIONS:  # upgrade a database made by an older version of Nova
            existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        connection.executemany(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", DEFAULT_SETTINGS
        )


class ChangeWatcher:
    """Notices when anything saves a change to the database, so screens redraw only when they have to.

    SQLite's data_version number changes whenever a different connection commits a change. Every service
    function opens its own connection, so this long-lived connection notices all of their saves.
    """

    def __init__(self):
        self._connection = get_connection()

    def version(self):
        try:
            return self._connection.execute("PRAGMA data_version").fetchone()[0]
        except sqlite3.Error:
            return None  # unknown, so the caller redraws to be safe

    def close(self):
        self._connection.close()
