"""Table definitions. Every statement uses IF NOT EXISTS, so running them again never erases data.

Deleting a subject also deletes its topics, tasks, questions and quiz history (ON DELETE CASCADE).
The app must ask for confirmation first. Deleting a topic or question keeps old quiz attempts
but clears the link to it (ON DELETE SET NULL).
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS subjects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS topics (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    name       TEXT NOT NULL COLLATE NOCASE,
    status     TEXT NOT NULL DEFAULT 'not_started'
               CHECK (status IN ('not_started', 'reviewed', 'completed')),
    UNIQUE (subject_id, name)
);

CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id   INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    due_date     TEXT NOT NULL,                     -- stored as YYYY-MM-DD
    is_completed INTEGER NOT NULL DEFAULT 0 CHECK (is_completed IN (0, 1))
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id       INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    question_text  TEXT NOT NULL,
    choice_1       TEXT NOT NULL,
    choice_2       TEXT NOT NULL,
    choice_3       TEXT NOT NULL,
    choice_4       TEXT NOT NULL,
    correct_choice INTEGER NOT NULL CHECK (correct_choice BETWEEN 1 AND 4),
    is_sample      INTEGER NOT NULL DEFAULT 0 CHECK (is_sample IN (0, 1))
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    topic_id   INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    score      INTEGER NOT NULL,
    total      INTEGER NOT NULL CHECK (total > 0),
    taken_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS attempt_answers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id    INTEGER NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    question_id   INTEGER REFERENCES quiz_questions(id) ON DELETE SET NULL,
    chosen_choice INTEGER NOT NULL CHECK (chosen_choice BETWEEN 1 AND 4),
    is_correct    INTEGER NOT NULL CHECK (is_correct IN (0, 1))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS glossary_terms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    term        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    explanation TEXT NOT NULL,
    example     TEXT NOT NULL DEFAULT '',
    is_starter  INTEGER NOT NULL DEFAULT 0 CHECK (is_starter IN (0, 1))
);

CREATE TABLE IF NOT EXISTS chat_threads (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL DEFAULT 'New chat',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id  INTEGER NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    files      TEXT NOT NULL DEFAULT '[]',   -- JSON: name, kind and extracted text only, never file bytes
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

# Columns added after version 1.0. Each is added only if the table does not have it yet.
MIGRATIONS = [("quiz_questions", "explanation", "TEXT NOT NULL DEFAULT ''")]

# The review threshold is a starting point, not a universal definition of mastery.
DEFAULT_SETTINGS = [("review_threshold", "70")]