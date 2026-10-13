"""Rules and queries for quiz questions, scoring and saved attempts."""
import random
import sqlite3
from contextlib import closing

from database.db_manager import get_connection
from services.study_service import ValidationError, _fetch_all, _write

QUIZ_LENGTH = 10
SAMPLE_SUBJECT = "Sample: Study Skills"
DESCRIPTION_SAMPLE = "Sample content for trying Nova. You can edit or delete it."

# topic -> list of (question, [four choices], number of the correct choice)
SAMPLE_QUESTIONS = {
    "Retrieval Practice": [
        ("What is retrieval practice?",
         ["Rereading your notes several times", "Trying to recall information from memory",
          "Highlighting key sentences", "Copying a textbook word for word"], 2),
        ("Which approach is linked to better long-term retention in research on test-enhanced learning?",
         ["Rereading the same passage", "Skimming only the headings",
          "Testing yourself after studying", "Highlighting without reviewing"], 3),
        ("Why is feedback after a practice quiz useful?",
         ["It replaces the need to study", "It guarantees a perfect score next time",
          "It makes the quiz shorter", "It shows what you still need to review"], 4),
    ],
    "Planning and Time": [
        ("Why break a big assignment into smaller tasks?",
         ["It makes progress easier to plan and see", "It makes the work harder to track",
          "It removes the need for deadlines", "It lets you skip the hardest part"], 1),
        ("What is a sensible first step when you receive a new deadline?",
         ["Ignore it until the last day", "Ask a classmate to do it",
          "Write it down and plan when to work on it", "Wait for a reminder"], 3),
        ("Which habit best supports healthy technology use while studying?",
         ["Keeping every notification on", "Studying only on a phone at night",
          "Skipping sleep to finish", "Taking short breaks away from screens"], 4),
    ],
}


def _validate_question(text, choices, correct):
    text = " ".join(text.split())
    choices = [" ".join(choice.split()) for choice in choices]
    if not text:
        raise ValidationError("The question cannot be empty.")
    if any(not choice for choice in choices):
        raise ValidationError("All four answer choices need text.")
    if len({choice.lower() for choice in choices}) < 4:
        raise ValidationError("Each answer choice must be different.")
    try:
        correct = int(correct)
    except (TypeError, ValueError):
        raise ValidationError("Choose which answer is correct.") from None
    if correct not in (1, 2, 3, 4):
        raise ValidationError("The correct choice must be 1, 2, 3 or 4.")
    return text, choices, correct


def list_questions(subject_id, topic_id=None):
    sql = """SELECT q.*, t.name AS topic_name FROM quiz_questions q
             JOIN topics t ON t.id = q.topic_id WHERE t.subject_id = ?"""
    params = [subject_id]
    if topic_id is not None:
        sql += " AND q.topic_id = ?"
        params.append(topic_id)
    return _fetch_all(sql + " ORDER BY t.name, q.id", params)


def add_question(topic_id, text, choices, correct):
    text, choices, correct = _validate_question(text, choices, correct)
    try:
        return _write(
            """INSERT INTO quiz_questions
               (topic_id, question_text, choice_1, choice_2, choice_3, choice_4, correct_choice)
               VALUES (?, ?, ?, ?, ?, ?, ?)""", (topic_id, text, *choices, correct))
    except sqlite3.IntegrityError:
        raise ValidationError("Choose a topic for this question.") from None


def update_question(question_id, topic_id, text, choices, correct):
    text, choices, correct = _validate_question(text, choices, correct)
    try:
        _write(
            """UPDATE quiz_questions SET topic_id = ?, question_text = ?, choice_1 = ?, choice_2 = ?,
               choice_3 = ?, choice_4 = ?, correct_choice = ?, is_sample = 0 WHERE id = ?""",
            (topic_id, text, *choices, correct, question_id))
    except sqlite3.IntegrityError:
        raise ValidationError("Choose a topic for this question.") from None


def set_explanation(question_id, text):
    """Save the short 'why this is right' note that AI-made questions come with."""
    _write("UPDATE quiz_questions SET explanation = ? WHERE id = ?", (" ".join(str(text).split())[:600], question_id))


def delete_question(question_id):
    _write("DELETE FROM quiz_questions WHERE id = ?", (question_id,))


def build_quiz(subject_id, topic_id=None, limit=QUIZ_LENGTH):
    """Pick up to `limit` random questions for a subject (or one topic of it)."""
    questions = list_questions(subject_id, topic_id)
    if not questions:
        raise ValidationError("There are no questions here yet. Add some first.")
    random.shuffle(questions)
    return questions[:limit]


def score_quiz(questions, answers):
    """Mark the quiz. `answers` maps question id to the chosen number (1-4)."""
    if not questions:
        raise ValidationError("There are no questions to score.")
    items = []
    for question in questions:
        chosen = answers.get(question["id"])
        if chosen not in (1, 2, 3, 4):
            raise ValidationError("Answer every question before finishing.")
        items.append({**question, "chosen": chosen, "is_correct": chosen == question["correct_choice"]})
    return {"score": sum(item["is_correct"] for item in items), "total": len(items), "items": items}


def save_attempt(subject_id, topic_id, result):
    """Save one finished quiz and its answers in a single transaction (all rows or none)."""
    with closing(get_connection()) as connection, connection:
        attempt_id = connection.execute(
            "INSERT INTO quiz_attempts (subject_id, topic_id, score, total) VALUES (?, ?, ?, ?)",
            (subject_id, topic_id, result["score"], result["total"]),
        ).lastrowid
        connection.executemany(
            """INSERT INTO attempt_answers (attempt_id, question_id, chosen_choice, is_correct)
               VALUES (?, ?, ?, ?)""",
            [(attempt_id, i["id"], i["chosen"], int(i["is_correct"])) for i in result["items"]],
        )
    return attempt_id


def add_sample_content():
    """Create a clearly labelled sample subject so a quiz can be tried right away."""
    if _fetch_all("SELECT id FROM subjects WHERE name = ?", (SAMPLE_SUBJECT,)):
        raise ValidationError("The sample questions are already loaded.")
    with closing(get_connection()) as connection, connection:
        subject_id = connection.execute(
            "INSERT INTO subjects (name, description) VALUES (?, ?)", (SAMPLE_SUBJECT, DESCRIPTION_SAMPLE)
        ).lastrowid
        for topic_name, questions in SAMPLE_QUESTIONS.items():
            topic_id = connection.execute(
                "INSERT INTO topics (subject_id, name) VALUES (?, ?)", (subject_id, topic_name)).lastrowid
            for text, choices, correct in questions:
                connection.execute(
                    """INSERT INTO quiz_questions (topic_id, question_text, choice_1, choice_2, choice_3,
                       choice_4, correct_choice, is_sample) VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                    (topic_id, text, *choices, correct))