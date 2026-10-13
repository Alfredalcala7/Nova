"""Quiz history, averages and review suggestions. The rules are simple on purpose, so they can be explained."""
from datetime import datetime

from services.study_service import ValidationError, _fetch_all, _write

DEFAULT_THRESHOLD = 70
MIN_ATTEMPTS_FOR_AVERAGE = 3   # fewer quizzes than this is too little data for a meaningful average
MIN_ANSWERS_FOR_TOPIC = 3      # a topic needs this many answered questions before it can be judged


def get_review_threshold():
    rows = _fetch_all("SELECT value FROM settings WHERE key = 'review_threshold'")
    try:
        return int(rows[0]["value"])
    except (IndexError, ValueError):
        return DEFAULT_THRESHOLD


def set_review_threshold(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError("The threshold must be a whole number.") from None
    if not 1 <= value <= 100:
        raise ValidationError("The threshold must be between 1 and 100.")
    _write("""INSERT INTO settings (key, value) VALUES ('review_threshold', ?)
              ON CONFLICT(key) DO UPDATE SET value = excluded.value""", (str(value),))


def quiz_history():
    rows = _fetch_all(
        """SELECT a.id, a.taken_at, a.score, a.total, s.name AS subject_name, t.name AS topic_name
           FROM quiz_attempts a JOIN subjects s ON s.id = a.subject_id
           LEFT JOIN topics t ON t.id = a.topic_id
           ORDER BY a.taken_at DESC, a.id DESC""")
    for row in rows:
        row["percent"] = 100 * row["score"] / row["total"]
        row["topic_name"] = row["topic_name"] or "Mixed topics"
        taken = datetime.strptime(row["taken_at"], "%Y-%m-%d %H:%M:%S")
        row["when"] = f"{taken:%b} {taken.day}, {taken.year}  {taken:%I:%M %p}"
    return rows


def subject_progress():
    return _fetch_all(
        """SELECT s.id, s.name,
             (SELECT COUNT(*) FROM topics WHERE subject_id = s.id) AS topic_count,
             (SELECT COUNT(*) FROM topics WHERE subject_id = s.id AND status = 'completed') AS completed_count,
             (SELECT COUNT(*) FROM quiz_attempts WHERE subject_id = s.id) AS attempts,
             (SELECT AVG(100.0 * score / total) FROM quiz_attempts WHERE subject_id = s.id) AS average
           FROM subjects s ORDER BY s.name""")


def topic_recommendations(threshold):
    """Suggest topics whose share of correct answers is below the threshold.

    Rule: add up every saved answer for each topic. If the topic has at least MIN_ANSWERS_FOR_TOPIC
    answers and the percentage correct is below the threshold, suggest reviewing it.
    """
    rows = _fetch_all(
        """SELECT t.name AS topic_name, s.name AS subject_name,
                  COUNT(*) AS answered, SUM(aa.is_correct) AS correct
           FROM attempt_answers aa
           JOIN quiz_questions q ON q.id = aa.question_id
           JOIN topics t ON t.id = q.topic_id
           JOIN subjects s ON s.id = t.subject_id
           GROUP BY t.id""")
    judged = [r for r in rows if r["answered"] >= MIN_ANSWERS_FOR_TOPIC]
    items = []
    for row in judged:
        percent = 100 * row["correct"] / row["answered"]
        if percent < threshold:
            row["percent"] = percent
            row["reason"] = (f'{row["correct"]} of {row["answered"]} answers correct ({round(percent)}%), '
                             f"below your {threshold}% review threshold.")
            items.append(row)
    items.sort(key=lambda r: r["percent"])
    return {"items": items, "judged_topics": len(judged)}


def get_progress_overview():
    """Everything the My Progress screen needs, gathered in one call."""
    threshold = get_review_threshold()
    history = quiz_history()
    scores = [h["percent"] for h in history]
    return {
        "threshold": threshold,
        "history": history,
        "attempts": len(history),
        "average": sum(scores) / len(scores) if len(scores) >= MIN_ATTEMPTS_FOR_AVERAGE else None,
        "subjects": subject_progress(),
        "recommendations": topic_recommendations(threshold),
    }