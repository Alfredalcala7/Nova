"""Rules and queries for study tasks and deadlines."""
import sqlite3
from datetime import date, datetime

from services.study_service import ValidationError, _fetch_all, _write

MAX_TITLE_LENGTH = 100
DATE_FORMAT = "%Y-%m-%d"


def parse_due_date(text):
    """Turn 'YYYY-MM-DD' text into a date, or raise a message the user can act on."""
    try:
        return datetime.strptime(text.strip(), DATE_FORMAT).date()
    except ValueError:
        raise ValidationError("Enter the due date as YYYY-MM-DD, for example 2026-10-12.") from None


def _clean_title(value):
    title = " ".join(value.split())
    if not title:
        raise ValidationError("The task title cannot be empty.")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValidationError(f"The task title must be {MAX_TITLE_LENGTH} characters or fewer.")
    return title


def list_tasks():
    return _fetch_all(
        """SELECT t.id, t.subject_id, s.name AS subject_name, t.title, t.description,
                  t.due_date, t.is_completed
           FROM tasks t JOIN subjects s ON s.id = t.subject_id
           ORDER BY t.due_date, t.title"""
    )


def add_task(subject_id, title, description, due_text):
    title, due = _clean_title(title), parse_due_date(due_text)
    try:
        return _write(
            "INSERT INTO tasks (subject_id, title, description, due_date) VALUES (?, ?, ?, ?)",
            (subject_id, title, description.strip(), due.isoformat()),
        )
    except sqlite3.IntegrityError:
        raise ValidationError("Choose a subject for this task.") from None


def update_task(task_id, subject_id, title, description, due_text):
    title, due = _clean_title(title), parse_due_date(due_text)
    try:
        _write(
            "UPDATE tasks SET subject_id = ?, title = ?, description = ?, due_date = ? WHERE id = ?",
            (subject_id, title, description.strip(), due.isoformat(), task_id),
        )
    except sqlite3.IntegrityError:
        raise ValidationError("Choose a subject for this task.") from None


def set_task_completed(task_id, completed):
    _write("UPDATE tasks SET is_completed = ? WHERE id = ?", (1 if completed else 0, task_id))


def delete_task(task_id):
    _write("DELETE FROM tasks WHERE id = ?", (task_id,))


def group_tasks(tasks, today=None):
    """Split tasks into overdue (pending and past due), upcoming (pending), and completed."""
    today = today or date.today()
    groups = {"overdue": [], "upcoming": [], "completed": []}
    for task in tasks:
        if task["is_completed"]:
            groups["completed"].append(task)
        elif date.fromisoformat(task["due_date"]) < today:
            groups["overdue"].append(task)
        else:
            groups["upcoming"].append(task)
    groups["completed"].reverse()  # most recent deadline first
    return groups


def summarize(tasks, today=None):
    groups = group_tasks(tasks, today)
    overdue, upcoming = len(groups["overdue"]), len(groups["upcoming"])
    return {"pending": overdue + upcoming, "overdue": overdue, "completed": len(groups["completed"])}


def due_label(due_iso, today=None):
    """A friendly deadline description, e.g. 'Due tomorrow' or 'Overdue by 2 days'."""
    today = today or date.today()
    due = date.fromisoformat(due_iso)
    days = (due - today).days
    if days == 0:
        return "Due today"
    if days == 1:
        return "Due tomorrow"
    if days < 0:
        return f"Overdue by {-days} day{'' if days == -1 else 's'}"
    return f"Due {due:%b} {due.day}, {due.year}"