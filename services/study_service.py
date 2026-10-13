"""Rules and queries for subjects and topics. Screens call these functions and never write SQL."""
import sqlite3
from contextlib import closing

from database.db_manager import get_connection

STATUS_LABELS = {"not_started": "Not started", "reviewed": "Reviewed", "completed": "Completed"}
MAX_NAME_LENGTH = 80


class ValidationError(ValueError):
    """The user's input is not acceptable. The message is written to be shown to them."""


def _clean_name(value, what):
    name = " ".join(value.split())  # trims and collapses repeated spaces
    if not name:
        raise ValidationError(f"The {what} name cannot be empty.")
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError(f"The {what} name must be {MAX_NAME_LENGTH} characters or fewer.")
    return name


def _fetch_all(sql, params=()):
    with closing(get_connection()) as connection:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def _write(sql, params=()):
    """Run one INSERT/UPDATE/DELETE as a transaction and return the new row id."""
    with closing(get_connection()) as connection, connection:
        return connection.execute(sql, params).lastrowid


# ---- Subjects ----------------------------------------------------------------------------

def list_subjects():
    return _fetch_all(
        """SELECT s.id, s.name, s.description,
                  COUNT(t.id) AS topic_count,
                  COALESCE(SUM(t.status = 'completed'), 0) AS completed_count
           FROM subjects s LEFT JOIN topics t ON t.subject_id = s.id
           GROUP BY s.id ORDER BY s.name"""
    )


def add_subject(name, description):
    name = _clean_name(name, "subject")
    try:
        return _write("INSERT INTO subjects (name, description) VALUES (?, ?)",
                      (name, description.strip()))
    except sqlite3.IntegrityError:
        raise ValidationError(f'A subject named "{name}" already exists.') from None


def update_subject(subject_id, name, description):
    name = _clean_name(name, "subject")
    try:
        _write("UPDATE subjects SET name = ?, description = ? WHERE id = ?",
               (name, description.strip(), subject_id))
    except sqlite3.IntegrityError:
        raise ValidationError(f'A subject named "{name}" already exists.') from None


def count_subject_contents(subject_id):
    """What deleting this subject would also remove. Used for the confirmation message."""
    return _fetch_all(
        """SELECT
             (SELECT COUNT(*) FROM topics WHERE subject_id = ?) AS topics,
             (SELECT COUNT(*) FROM tasks WHERE subject_id = ?) AS tasks,
             (SELECT COUNT(*) FROM quiz_questions
                WHERE topic_id IN (SELECT id FROM topics WHERE subject_id = ?)) AS questions,
             (SELECT COUNT(*) FROM quiz_attempts WHERE subject_id = ?) AS attempts""",
        (subject_id,) * 4,
    )[0]


def delete_subject(subject_id):
    _write("DELETE FROM subjects WHERE id = ?", (subject_id,))  # related rows cascade


# ---- Topics ------------------------------------------------------------------------------

def list_topics(subject_id):
    return _fetch_all("SELECT id, name, status FROM topics WHERE subject_id = ? ORDER BY name",
                      (subject_id,))


def add_topic(subject_id, name):
    name = _clean_name(name, "topic")
    try:
        return _write("INSERT INTO topics (subject_id, name) VALUES (?, ?)", (subject_id, name))
    except sqlite3.IntegrityError:
        raise ValidationError(f'This subject already has a topic named "{name}".') from None


def update_topic(topic_id, name):
    name = _clean_name(name, "topic")
    try:
        _write("UPDATE topics SET name = ? WHERE id = ?", (name, topic_id))
    except sqlite3.IntegrityError:
        raise ValidationError(f'This subject already has a topic named "{name}".') from None


def set_topic_status(topic_id, status):
    if status not in STATUS_LABELS:
        raise ValidationError("Unknown topic status.")
    _write("UPDATE topics SET status = ? WHERE id = ?", (status, topic_id))


def count_topic_questions(topic_id):
    return _fetch_all("SELECT COUNT(*) AS n FROM quiz_questions WHERE topic_id = ?", (topic_id,))[0]["n"]


def delete_topic(topic_id):
    _write("DELETE FROM topics WHERE id = ?", (topic_id,))