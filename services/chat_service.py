"""Saves AI chat conversations on this computer, so they are still there after Nova closes."""
import json
from contextlib import closing

from database.db_manager import get_connection
from services.study_service import ValidationError, _fetch_all, _write

MAX_TITLE = 60


def list_threads():
    return _fetch_all("SELECT id, title, updated_at FROM chat_threads ORDER BY updated_at DESC, id DESC")


def create_thread(title="New chat"):
    return _write("INSERT INTO chat_threads (title) VALUES (?)", (title[:MAX_TITLE] or "New chat",))


def rename_thread(thread_id, title):
    title = " ".join(title.split())[:MAX_TITLE]
    if not title:
        raise ValidationError("Give the chat a name.")
    _write("UPDATE chat_threads SET title = ? WHERE id = ?", (title, thread_id))


def delete_thread(thread_id):
    _write("DELETE FROM chat_threads WHERE id = ?", (thread_id,))


def clear_all():
    _write("DELETE FROM chat_threads")


def get_messages(thread_id):
    rows = _fetch_all("SELECT id, role, content, files, created_at FROM chat_messages WHERE thread_id = ? ORDER BY id", (thread_id,))
    for row in rows:
        try:
            row["files"] = json.loads(row["files"])
        except ValueError:
            row["files"] = []
    return rows


def add_message(thread_id, role, content, files=None):
    """`files` is a list of {name, kind, text?}. Only the name, kind and extracted text are saved, never the bytes."""
    with closing(get_connection()) as connection, connection:
        message_id = connection.execute(
            "INSERT INTO chat_messages (thread_id, role, content, files) VALUES (?, ?, ?, ?)",
            (thread_id, role, content, json.dumps(files or []))).lastrowid
        connection.execute("UPDATE chat_threads SET updated_at = datetime('now', 'localtime') WHERE id = ?", (thread_id,))
    return message_id


def title_from(text, files):
    text = " ".join(text.split())
    if text:
        return text[:MAX_TITLE]
    return (files[0]["name"] if files else "New chat")[:MAX_TITLE]
