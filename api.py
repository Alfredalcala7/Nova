"""The bridge between Nova's screens and its services. Every function here returns plain data (dicts, lists, text)
that the screen can show. Errors raise ValidationError / AIError / FileError, and the server turns them into messages."""
import base64
import os
import tempfile
from contextlib import closing
from pathlib import Path

from database.db_manager import get_connection
from services import (ai_service, chat_service, dashboard_service, file_service, glossary_service, notification_service,
                      planner_service, profile_service, progress_service, quiz_service, settings_service, study_service)
from services.study_service import ValidationError
from ui import colors

UI_PREFS = {"ui_sidebar": ("0", "1"), "ui_glass": tuple(str(n) for n in range(0, 101)), "ui_motion": ("0", "1"), "ui_solid": ("0", "1")}
UI_DEFAULTS = {"ui_sidebar": "1", "ui_glass": "60", "ui_motion": "1", "ui_solid": "0"}
_session_files = {}  # (thread_id, message_id) -> picture/PDF attachments, kept in memory only, for follow-up questions
MAX_HISTORY = 24
QUIZ_FENCE = "```nova-quiz\n"


# ---- settings and look ------------------------------------------------------------------------

def get_settings():
    settings = settings_service.load_all()
    palette = None
    if settings["theme_mode"] == "Custom":
        palette = colors.custom_palette(settings["custom_sidebar"], settings["custom_accent"], settings["custom_background"])
    prefs = dict(UI_DEFAULTS)
    with closing(get_connection()) as connection:
        for key, value in connection.execute("SELECT key, value FROM settings WHERE key LIKE 'ui\\_%' ESCAPE '\\'"):
            if key in UI_PREFS and value in UI_PREFS[key]:
                prefs[key] = value
    return {"settings": settings, "palette": palette, "prefs": prefs, "choices": settings_service.CHOICES,
            "fonts": settings_service.FONT_CHOICES, "threshold": progress_service.get_review_threshold()}


def set_pref(key, value):
    value = str(value)
    if key not in UI_PREFS or value not in UI_PREFS[key]:
        raise ValidationError("Unknown preference.")
    with closing(get_connection()) as connection, connection:
        connection.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


def save_settings(values):
    settings_service.save(values)
    return get_settings()


def reset_settings():
    settings_service.reset()
    return get_settings()


# ---- home -------------------------------------------------------------------------------------

def dashboard():
    data = dashboard_service.get_dashboard_data()
    for task in data["upcoming"]:
        task["label"] = planner_service.due_label(task["due_date"])
    data["first_name"] = profile_service.first_name()
    return data


def reminder(days, include_overdue):
    return notification_service.build_reminder(int(days), bool(include_overdue))


# ---- planner ----------------------------------------------------------------------------------

def tasks_overview():
    tasks = planner_service.list_tasks()
    for task in tasks:
        task["label"] = planner_service.due_label(task["due_date"])
    return {"groups": planner_service.group_tasks(tasks), "summary": planner_service.summarize(tasks)}


# ---- quizzes ----------------------------------------------------------------------------------

def _with_choices(question):
    question["choices"] = [question[f"choice_{n}"] for n in range(1, 5)]
    return question


def questions(subject_id, topic_id=None):
    return [_with_choices(q) for q in quiz_service.list_questions(subject_id, topic_id)]


def quiz_start(subject_id, topic_id=None, limit=quiz_service.QUIZ_LENGTH):
    return [_with_choices(q) for q in quiz_service.build_quiz(subject_id, topic_id, limit)]


def quiz_finish(subject_id, topic_id, quiz_questions, answers):
    result = quiz_service.score_quiz(quiz_questions, {int(k): int(v) for k, v in answers.items()})
    quiz_service.save_attempt(subject_id, topic_id, result)
    return result


def save_generated_quiz(subject_id, new_subject, topic_name, generated):
    """Save AI-made questions into a subject and topic (creating them if needed). Returns how many were saved."""
    if not subject_id:
        subject_id = study_service.add_subject(new_subject or "AI quizzes", "Questions made by Nova AI from your files.")
    topic_name = " ".join((topic_name or "From my file").split())
    found = [t for t in study_service.list_topics(subject_id) if t["name"].lower() == topic_name.lower()]
    topic_id = found[0]["id"] if found else study_service.add_topic(subject_id, topic_name)
    saved = 0
    for item in ai_service.clean_questions(generated):
        try:
            question_id = quiz_service.add_question(topic_id, item["question"], item["choices"], item["correct"])
        except ValidationError:
            continue
        quiz_service.set_explanation(question_id, item.get("explanation", ""))
        saved += 1
    if not saved:
        raise ValidationError("None of those questions could be saved.")
    return {"saved": saved, "subject_id": subject_id, "topic_id": topic_id}


# ---- account ----------------------------------------------------------------------------------

def get_profile():
    profile = profile_service.load_profile()
    return {"profile": profile, "roles": profile_service.ROLES, "limits": profile_service.LIMITS, "labels": profile_service.LABELS,
            "has_avatar": profile_service.avatar_path().exists(), "pictures": profile_service.pictures_available(),
            "pillow_help": profile_service.PILLOW_HELP, "stamp": int(profile_service.avatar_path().stat().st_mtime) if profile_service.avatar_path().exists() else 0}


def save_avatar(file_name, data_b64):
    raw = base64.b64decode(data_b64)
    if len(raw) > profile_service.MAX_PICTURE_MB * 1024 * 1024:
        raise ValidationError(f"Choose a picture under {profile_service.MAX_PICTURE_MB} MB.")
    suffix = Path(file_name).suffix.lower() or ".png"
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / f"upload{suffix}"
        path.write_bytes(raw)
        profile_service.save_avatar(str(path))


# ---- AI ---------------------------------------------------------------------------------------

def ai_status():
    return ai_service.status()


def ai_save_key(provider, key):
    ai_service.save_key(provider, key)
    return ai_service.status()


def ai_explain(text):
    return ai_service.explain_simply(text)


def student_context():
    parts = []
    try:
        profile = profile_service.load_profile()
        who = ", ".join(x for x in (profile["name"].split(" ")[0] if profile["name"] else "", profile["role"], profile["program"], profile["school"]) if x)
        if who:
            parts.append(who)
        if profile["goal"]:
            parts.append("goal: " + profile["goal"])
        subjects = [s["name"] for s in study_service.list_subjects()][:12]
        if subjects:
            parts.append("subjects in Nova: " + ", ".join(subjects))
    except Exception:  # context is a nicety; never let it break a chat
        pass
    return "; ".join(parts)


def _history_turns(thread_id):
    turns = []
    for message in chat_service.get_messages(thread_id)[-MAX_HISTORY:]:
        text = message["content"]
        if QUIZ_FENCE in text:  # a saved quiz card: tell the model it exists, without the bulky JSON
            text = text.split(QUIZ_FENCE)[0].strip() + "\n[Nova made a practice quiz here.]"
        attachments = []
        if message["role"] == "user":
            for item in message["files"]:
                if item.get("kind") == "text" and item.get("text"):
                    attachments.append({"kind": "text", "mime": "text/plain", "data": None, "text": item["text"], "name": item["name"]})
            attachments += _session_files.get((thread_id, message["id"]), [])
        turns.append({"role": message["role"], "text": text, "attachments": attachments})
    return turns


def _remember(thread_id, message_id, attachments):
    binaries = [a for a in attachments if a["kind"] in ("image", "pdf")]
    if binaries:
        _session_files[(thread_id, message_id)] = binaries
        mine = sorted(k for k in _session_files if k[0] == thread_id)
        for old in mine[:-4]:  # keep only the latest few, so memory stays small
            _session_files.pop(old, None)


def prepare_chat(thread_id, text, files):
    """Save the student's message and build everything the AI needs. Returns (thread_id, turns)."""
    attachments = file_service.read_many(files) if files else []
    text = text.strip()
    if not text and not attachments:
        raise ai_service.AIError("Type a message or attach a file first.")
    if not thread_id:
        thread_id = chat_service.create_thread(chat_service.title_from(text, attachments))
    history = _history_turns(thread_id)
    saved = [{"name": a["name"], "kind": a["kind"], **({"text": a["text"]} if a["kind"] == "text" else {})} for a in attachments]
    message_id = chat_service.add_message(thread_id, "user", text, saved)
    _remember(thread_id, message_id, attachments)
    return thread_id, history + [{"role": "user", "text": text, "attachments": attachments}]


def finish_chat(thread_id, answer):
    if answer.strip():
        chat_service.add_message(thread_id, "assistant", answer)


def make_quiz(thread_id, text, files, count, difficulty):
    """Turn a file, image or pasted notes into quiz questions. Also saved into the chat so it is there next time."""
    thread_id, turns = prepare_chat(thread_id, text or "Make a quiz from this.", files)
    last = turns[-1]
    # Use the whole conversation's files if this message has none (for example "quiz me on that").
    if not last["attachments"]:
        for earlier in reversed(turns[:-1]):
            if earlier["role"] == "user" and earlier["attachments"]:
                last = {**last, "attachments": earlier["attachments"]}
                break
        else:
            history_text = "\n".join(t["text"] for t in turns[:-1])[-12000:]
            if history_text.strip():
                last = {**last, "text": last["text"] + "\n\nMaterial:\n" + history_text}
    generated = ai_service.generate_quiz(last, count, difficulty)
    import json
    chat_service.add_message(thread_id, "assistant", f"Here is a {len(generated)}-question quiz.\n\n{QUIZ_FENCE}{json.dumps(generated)}\n```")
    return {"thread_id": thread_id, "questions": generated}


# ---- the list of functions a screen may call --------------------------------------------------

CALLS = {
    "get_settings": get_settings, "save_settings": save_settings, "reset_settings": reset_settings, "set_pref": set_pref,
    "dashboard": dashboard, "reminder": reminder, "tasks_overview": tasks_overview,
    "list_subjects": study_service.list_subjects, "add_subject": study_service.add_subject,
    "update_subject": study_service.update_subject, "delete_subject": study_service.delete_subject,
    "count_subject_contents": study_service.count_subject_contents, "list_topics": study_service.list_topics,
    "add_topic": study_service.add_topic, "update_topic": study_service.update_topic,
    "set_topic_status": study_service.set_topic_status, "delete_topic": study_service.delete_topic,
    "count_topic_questions": study_service.count_topic_questions,
    "add_task": planner_service.add_task, "update_task": planner_service.update_task,
    "set_task_completed": planner_service.set_task_completed, "delete_task": planner_service.delete_task,
    "questions": questions, "add_question": quiz_service.add_question, "update_question": quiz_service.update_question,
    "delete_question": quiz_service.delete_question, "quiz_start": quiz_start, "quiz_finish": quiz_finish,
    "add_sample_content": quiz_service.add_sample_content, "save_generated_quiz": save_generated_quiz,
    "progress": progress_service.get_progress_overview, "set_review_threshold": progress_service.set_review_threshold,
    "list_terms": glossary_service.list_terms, "add_term": glossary_service.add_term, "update_term": glossary_service.update_term,
    "delete_term": glossary_service.delete_term, "load_starter_terms": glossary_service.load_starter_terms,
    "get_profile": get_profile, "save_profile": profile_service.save_profile, "save_avatar": save_avatar,
    "remove_avatar": profile_service.remove_avatar,
    "ai_status": ai_status, "ai_save_key": ai_save_key, "ai_explain": ai_explain,
    "list_threads": chat_service.list_threads, "get_messages": chat_service.get_messages,
    "rename_thread": chat_service.rename_thread, "delete_thread": chat_service.delete_thread, "clear_chats": chat_service.clear_all,
}
