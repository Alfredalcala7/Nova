"""Automated tests for the service layer (rules and database). Each test uses its own empty database.

Run from the Nova folder:   python -m unittest discover -s tests -v
"""
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db_manager import get_connection, initialize_database  # noqa: E402
from services import dashboard_service, planner_service as planner  # noqa: E402
from services import progress_service as progress, quiz_service as quiz, study_service as study  # noqa: E402
from services import ai_service, glossary_service as glossary, notification_service, profile_service, settings_service  # noqa: E402
from ui import colors  # noqa: E402
from database.db_manager import ChangeWatcher  # noqa: E402
from services.study_service import ValidationError  # noqa: E402


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.old_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self.folder.name  # keeps tests away from your real data
        initialize_database()

    def tearDown(self):
        if self.old_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self.old_appdata
        self.folder.cleanup()

    def sample_subject_id(self):
        quiz.add_sample_content()
        return study.list_subjects()[0]["id"]


class SubjectAndTopicTests(DatabaseTestCase):
    def test_names_are_trimmed_and_validated(self):
        sid = study.add_subject("  Biology  ", "")
        self.assertEqual(study.list_subjects()[0]["name"], "Biology")
        for bad in ("", "   ", "biology", "x" * 81):
            with self.assertRaises(ValidationError):
                study.add_subject(bad, "")
        self.assertEqual(len(study.list_subjects()), 1)
        self.assertIsNotNone(sid)

    def test_topic_rules(self):
        a, b = study.add_subject("A", ""), study.add_subject("B", "")
        study.add_topic(a, "Cells")
        with self.assertRaises(ValidationError):
            study.add_topic(a, "cells")      # duplicate in the same subject
        study.add_topic(b, "Cells")          # the same name in another subject is fine
        with self.assertRaises(ValidationError):
            study.set_topic_status(study.list_topics(a)[0]["id"], "bogus")

    def test_deleting_a_subject_removes_its_data(self):
        sid = study.add_subject("Math", "")
        study.add_topic(sid, "Algebra")
        planner.add_task(sid, "Homework", "", "2026-12-01")
        counts = study.count_subject_contents(sid)
        self.assertEqual((counts["topics"], counts["tasks"]), (1, 1))
        study.delete_subject(sid)
        self.assertEqual(study.list_subjects(), [])
        self.assertEqual(planner.list_tasks(), [])

    def test_foreign_keys_are_enforced(self):
        with get_connection() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO topics (subject_id, name) VALUES (999, 'x')")

    def test_setup_is_safe_to_repeat_and_keeps_data(self):
        study.add_subject("Keep me", "")
        initialize_database()
        initialize_database()
        self.assertEqual([s["name"] for s in study.list_subjects()], ["Keep me"])


class PlannerTests(DatabaseTestCase):
    def test_date_validation(self):
        for bad in ("2026-13-40", "10/12/2026", "", "tomorrow"):
            with self.assertRaises(ValidationError):
                planner.parse_due_date(bad)
        self.assertEqual(planner.parse_due_date("2026-10-12"), date(2026, 10, 12))

    def test_required_fields(self):
        sid = study.add_subject("Math", "")
        with self.assertRaises(ValidationError):
            planner.add_task(sid, "   ", "", "2026-10-12")
        with self.assertRaises(ValidationError):
            planner.add_task(999, "No such subject", "", "2026-10-12")

    def test_grouping_labels_and_completion(self):
        sid = study.add_subject("Math", "")
        today = date(2026, 10, 10)
        ids = {title: planner.add_task(sid, title, "", due) for title, due in
               [("Late", "2026-10-08"), ("Today", "2026-10-10"), ("Soon", "2026-10-11"), ("Later", "2026-11-02")]}
        planner.set_task_completed(ids["Later"], True)
        groups = planner.group_tasks(planner.list_tasks(), today)
        self.assertEqual([t["title"] for t in groups["overdue"]], ["Late"])
        self.assertEqual([t["title"] for t in groups["upcoming"]], ["Today", "Soon"])
        self.assertEqual([t["title"] for t in groups["completed"]], ["Later"])
        self.assertEqual(planner.due_label("2026-10-08", today), "Overdue by 2 days")
        self.assertEqual(planner.due_label("2026-10-11", today), "Due tomorrow")
        planner.delete_task(ids["Late"])
        self.assertEqual(len(planner.list_tasks()), 3)


class QuizTests(DatabaseTestCase):
    def test_question_validation(self):
        sid = study.add_subject("Math", "")
        tid = study.add_topic(sid, "Algebra")
        good = ["a", "b", "c", "d"]
        for args in [("  ", good, 1), ("Q?", ["a", "A", "c", "d"], 1), ("Q?", ["a", "b", "c", ""], 1),
                     ("Q?", good, 7), ("Q?", good, "x")]:
            with self.assertRaises(ValidationError):
                quiz.add_question(tid, *args)
        with self.assertRaises(ValidationError):
            quiz.add_question(999, "Q?", good, 1)
        quiz.add_question(tid, "Q?", good, "2")
        self.assertEqual(len(quiz.list_questions(sid)), 1)

    def test_scoring_and_saving(self):
        sid = self.sample_subject_id()
        questions = quiz.build_quiz(sid, limit=4)
        self.assertEqual(len(questions), 4)
        answers = {q["id"]: q["correct_choice"] for q in questions}
        self.assertEqual(quiz.score_quiz(questions, answers)["score"], 4)
        answers[questions[0]["id"]] = questions[0]["correct_choice"] % 4 + 1  # make exactly one wrong
        result = quiz.score_quiz(questions, answers)
        self.assertEqual((result["score"], result["total"]), (3, 4))
        attempt_id = quiz.save_attempt(sid, None, result)
        with get_connection() as connection:
            saved = connection.execute("SELECT score, total FROM quiz_attempts WHERE id = ?", (attempt_id,)).fetchone()
            rows = connection.execute("SELECT COUNT(*) FROM attempt_answers WHERE attempt_id = ?", (attempt_id,)).fetchone()[0]
        self.assertEqual(tuple(saved), (3, 4))
        self.assertEqual(rows, 4)

    def test_unanswered_questions_are_rejected(self):
        sid = self.sample_subject_id()
        with self.assertRaises(ValidationError):
            quiz.score_quiz(quiz.build_quiz(sid, limit=3), {})

    def test_sample_content_loads_once(self):
        quiz.add_sample_content()
        with self.assertRaises(ValidationError):
            quiz.add_sample_content()
        self.assertEqual(len(quiz.list_questions(study.list_subjects()[0]["id"])), 6)


class ProgressTests(DatabaseTestCase):
    def take_quiz(self, sid, wrong_topic=None, times=1):
        questions = quiz.build_quiz(sid, limit=6)
        answers = {q["id"]: (q["correct_choice"] % 4 + 1 if q["topic_name"] == wrong_topic else q["correct_choice"])
                   for q in questions}
        for _ in range(times):
            quiz.save_attempt(sid, None, quiz.score_quiz(questions, answers))

    def test_average_needs_three_quizzes(self):
        sid = self.sample_subject_id()
        self.take_quiz(sid, times=2)
        self.assertIsNone(progress.get_progress_overview()["average"])
        self.take_quiz(sid)
        self.assertEqual(progress.get_progress_overview()["average"], 100)

    def test_recommendation_rule_and_threshold(self):
        sid = self.sample_subject_id()
        self.take_quiz(sid, wrong_topic="Planning and Time")          # 0 of 3 correct on that topic
        items = progress.get_progress_overview()["recommendations"]["items"]
        self.assertEqual([i["topic_name"] for i in items], ["Planning and Time"])
        self.assertIn("0 of 3 answers correct", items[0]["reason"])
        self.take_quiz(sid, times=3)                                   # now 9 of 12 correct = 75%
        flagged = lambda: [i["topic_name"] for i in progress.get_progress_overview()["recommendations"]["items"]]
        self.assertEqual(flagged(), [])                                # 75% is not below the default 70%
        progress.set_review_threshold(90)
        self.assertEqual(flagged(), ["Planning and Time"])             # 75% is below a 90% threshold

    def test_perfect_quiz_flags_nothing(self):
        self.take_quiz(self.sample_subject_id())
        self.assertEqual(progress.get_progress_overview()["recommendations"]["items"], [])

    def test_too_few_answers_are_not_judged(self):
        sid = self.sample_subject_id()
        two = [q for q in quiz.list_questions(sid) if q["topic_name"] == "Planning and Time"][:2]
        wrong = {q["id"]: q["correct_choice"] % 4 + 1 for q in two}
        quiz.save_attempt(sid, None, quiz.score_quiz(two, wrong))
        overview = progress.get_progress_overview()
        self.assertEqual(overview["recommendations"]["items"], [])
        self.assertEqual(overview["recommendations"]["judged_topics"], 0)

    def test_threshold_validation_and_persistence(self):
        for bad in ("0", "101", "abc"):
            with self.assertRaises(ValidationError):
                progress.set_review_threshold(bad)
        self.assertEqual(progress.get_review_threshold(), 70)
        progress.set_review_threshold("85")
        self.assertEqual(progress.get_review_threshold(), 85)


class DashboardTests(DatabaseTestCase):
    def test_numbers_match_saved_data(self):
        empty = dashboard_service.get_dashboard_data()
        self.assertEqual(empty["counts"]["subjects"], 0)
        sid = study.add_subject("Math", "")
        study.add_topic(sid, "Algebra")
        today = date.today()
        planner.add_task(sid, "Late", "", (today - timedelta(days=1)).isoformat())
        done = planner.add_task(sid, "Done", "", today.isoformat())
        planner.set_task_completed(done, True)
        data = dashboard_service.get_dashboard_data()
        self.assertEqual((data["counts"]["subjects"], data["counts"]["topics"]), (1, 1))
        self.assertEqual(data["task_summary"], {"pending": 1, "overdue": 1, "completed": 1})
        self.assertEqual([t["title"] for t in data["upcoming"]], ["Late"])


class GlossaryTests(DatabaseTestCase):
    def test_starter_terms_load_once_and_can_be_searched(self):
        self.assertEqual(glossary.load_starter_terms(), len(glossary.STARTER_TERMS))
        self.assertEqual(glossary.load_starter_terms(), 0)
        self.assertEqual([t["term"] for t in glossary.list_terms("instan")], ["Instantiate"])
        self.assertEqual(glossary.list_terms("100%"), [])  # the percent sign is searched literally

    def test_own_terms_are_validated_edited_and_deleted(self):
        glossary.add_term("  API ", "A way for programs to talk to each other.")
        for args in [("", "x"), ("api", "duplicate"), ("Term", "   "), ("x" * 61, "y")]:
            with self.assertRaises(ValidationError):
                glossary.add_term(*args)
        term = glossary.list_terms()[0]
        glossary.update_term(term["id"], "API", "Updated", "example")
        self.assertEqual(glossary.list_terms()[0]["explanation"], "Updated")
        glossary.delete_term(term["id"])
        self.assertEqual(glossary.list_terms(), [])


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class AIServiceTests(unittest.TestCase):
    NAMES = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "NOVA_AI_PROVIDER", "NOVA_AI_MODEL")

    def setUp(self):
        self.saved = {name: os.environ.pop(name, None) for name in self.NAMES}  # start from a clean slate
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        ai_service._requests_made = 0
        ai_service._discovered.clear()

    def tearDown(self):
        for name, value in self.saved.items():
            os.environ.pop(name, None)
            if value is not None:
                os.environ[name] = value

    def raising(self, error):
        def opener(request, timeout):
            raise error
        return opener

    def test_successful_request(self):
        seen = {}

        def opener(request, timeout):
            seen["key"] = request.get_header("X-api-key")
            seen["body"] = json.loads(request.data)
            return FakeResponse({"content": [{"type": "text", "text": "Simple answer"}]})

        self.assertEqual(ai_service.explain_simply("What is a class?", opener=opener), "Simple answer")
        self.assertEqual(seen["key"], "test-key")
        self.assertEqual(seen["body"]["messages"][0]["content"], "What is a class?")
        self.assertLessEqual(seen["body"]["max_tokens"], 600)

    def test_bad_input_and_missing_key(self):
        with self.assertRaises(ai_service.AIError):
            ai_service.explain_simply("   ")
        with self.assertRaises(ai_service.AIError):
            ai_service.explain_simply("x" * (ai_service.MAX_INPUT_CHARS + 1))
        os.environ.pop("ANTHROPIC_API_KEY")
        with self.assertRaises(ai_service.AIError) as caught:
            ai_service.explain_simply("What is a loop?")
        self.assertIn("No AI key", str(caught.exception))

    def test_provider_and_network_errors_become_friendly_messages(self):
        unauthorized = urllib.error.HTTPError("url", 401, "Unauthorized", {}, io.BytesIO(b"{}"))
        with self.assertRaises(ai_service.AIError) as caught:
            ai_service.explain_simply("hi", opener=self.raising(unauthorized))
        self.assertIn("key", str(caught.exception))
        with self.assertRaises(ai_service.AIError) as caught:
            ai_service.explain_simply("hi", opener=self.raising(urllib.error.URLError("offline")))
        self.assertIn("internet", str(caught.exception))
        with self.assertRaises(ai_service.AIError):
            ai_service.explain_simply("hi", opener=lambda request, timeout: FakeResponse({"content": []}))

    def test_session_limit(self):
        ai_service._requests_made = ai_service.MAX_REQUESTS_PER_SESSION
        with self.assertRaises(ai_service.AIError):
            ai_service.explain_simply("What is a loop?")

    def test_gemini_request_and_answer(self):
        os.environ["GEMINI_API_KEY"] = "gem-key"
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["key"] = request.get_header("X-goog-api-key")
            seen["body"] = json.loads(request.data)
            return FakeResponse({"candidates": [{"content": {"parts": [{"text": "Gemini answer"}]}}]})

        self.assertEqual(ai_service.explain_simply("What is a loop?", opener=opener), "Gemini answer")
        self.assertIn("generativelanguage.googleapis.com", seen["url"])
        self.assertTrue(seen["url"].endswith(":generateContent"))
        self.assertEqual(seen["key"], "gem-key")
        self.assertEqual(seen["body"]["contents"][0]["parts"][0]["text"], "What is a loop?")
        self.assertIn("Google", ai_service.disclosure())

    def test_model_name_can_be_set_and_may_start_with_models_prefix(self):
        os.environ["GEMINI_API_KEY"] = "gem-key"
        os.environ["NOVA_AI_MODEL"] = "models/gemini-2.5-flash"
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            return FakeResponse({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

        ai_service.explain_simply("What is a loop?", opener=opener)
        self.assertTrue(seen["url"].endswith("/models/gemini-2.5-flash:generateContent"))

    def test_gemini_finds_a_working_model_when_the_default_is_missing(self):
        os.environ["GEMINI_API_KEY"] = "gem-key"
        urls = []

        def opener(request, timeout):
            urls.append(request.full_url)
            if request.full_url.endswith("/models?pageSize=1000"):
                method = ["generateContent"]
                return FakeResponse({"models": [
                    {"name": "models/gemini-2.5-flash-image", "supportedGenerationMethods": method},
                    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": method},
                    {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": method},
                    {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]}]})
            if "gemini-3.5-flash" in request.full_url:
                raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO(b"{}"))
            return FakeResponse({"candidates": [{"content": {"parts": [{"text": "Found it"}]}}]})

        self.assertEqual(ai_service.explain_simply("What is a loop?", opener=opener), "Found it")
        self.assertTrue(urls[-1].endswith("/models/gemini-2.5-flash:generateContent"))
        self.assertEqual(ai_service._discovered["gemini"], "gemini-2.5-flash")

    def test_missing_model_with_no_replacement_gives_a_clear_message(self):
        os.environ["GEMINI_API_KEY"] = "gem-key"

        def opener(request, timeout):
            if request.full_url.endswith("/models?pageSize=1000"):
                return FakeResponse({"models": []})
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO(b"{}"))

        with self.assertRaises(ai_service.AIError) as caught:
            ai_service.explain_simply("hi", opener=opener)
        self.assertIn("model was not found", str(caught.exception))

    def test_gemini_blocked_or_empty_answer(self):
        os.environ["GEMINI_API_KEY"] = "gem-key"
        for payload in ({"candidates": []}, {}, {"candidates": [{"content": {"parts": []}}]}):
            with self.assertRaises(ai_service.AIError):
                ai_service.explain_simply("hi", opener=lambda request, timeout, p=payload: FakeResponse(p))

    def test_provider_choice(self):
        self.assertEqual(ai_service.active_provider(), "anthropic")
        os.environ["GEMINI_API_KEY"] = "g"
        self.assertEqual(ai_service.active_provider(), "gemini")
        os.environ["NOVA_AI_PROVIDER"] = "anthropic"
        self.assertEqual(ai_service.active_provider(), "anthropic")


class SettingsTests(DatabaseTestCase):
    def test_defaults_save_load_and_reset(self):
        self.assertEqual(settings_service.load_all(), settings_service.DEFAULTS)
        settings_service.save({"theme_mode": "Dark", "zoom": "150", "text_scale": 115, "font_family": "Arial", "start_maximized": 0})
        loaded = settings_service.load_all()
        self.assertEqual((loaded["theme_mode"], loaded["zoom"], loaded["text_scale"], loaded["start_maximized"]),
                         ("Dark", 150, 115, 0))
        settings_service.reset()
        self.assertEqual(settings_service.load_all(), settings_service.DEFAULTS)

    def test_bad_values_are_rejected_and_nothing_is_saved(self):
        for bad in ({"theme_mode": "Purple"}, {"zoom": 999}, {"text_scale": "big"}, {"font_family": "  "}, {"nonsense": 1}):
            with self.assertRaises(ValidationError):
                settings_service.save(bad)
        with self.assertRaises(ValidationError):
            settings_service.save({"theme_mode": "Dark", "zoom": 999})  # one bad value stops the whole save
        self.assertEqual(settings_service.load_all()["theme_mode"], "System")

    def test_review_threshold_is_not_touched_by_reset(self):
        progress.set_review_threshold(85)
        settings_service.save({"zoom": 150})
        settings_service.reset()
        self.assertEqual(progress.get_review_threshold(), 85)


class ProfileTests(DatabaseTestCase):
    def test_save_load_and_validation(self):
        self.assertEqual(profile_service.load_profile()["name"], "")
        self.assertEqual(profile_service.first_name(), "")
        profile_service.save_profile({"name": "  Ana   Reyes ", "role": "Student", "school": "Demo University", "goal": "Pass my exams"})
        loaded = profile_service.load_profile()
        self.assertEqual((loaded["name"], loaded["role"], loaded["goal"]), ("Ana Reyes", "Student", "Pass my exams"))
        self.assertEqual(profile_service.first_name(), "Ana")
        for bad in ({"name": "A"}, {"name": "x" * 81}, {"role": "Wizard"}, {"goal": "x" * 301}):
            with self.assertRaises(ValidationError):
                profile_service.save_profile(bad)
        self.assertEqual(profile_service.load_profile()["name"], "Ana Reyes")  # a failed save changes nothing

    def test_profile_and_settings_do_not_mix(self):
        profile_service.save_profile({"name": "Ana"})
        settings_service.save({"zoom": 150})
        settings_service.reset()
        self.assertEqual(profile_service.load_profile()["name"], "Ana")

    @unittest.skipUnless(profile_service.pictures_available(), "Pillow is not installed")
    def test_picture_saved_loaded_and_removed(self):
        from PIL import Image
        source = Path(self.folder.name) / "photo.jpg"
        Image.new("RGB", (400, 300), (30, 90, 200)).save(source)
        self.assertIsNone(profile_service.load_avatar())
        profile_service.save_avatar(source)
        self.assertEqual(profile_service.load_avatar(64).size, (64, 64))
        self.assertEqual(profile_service.preview_avatar(source, 80).size, (80, 80))
        profile_service.remove_avatar()
        self.assertIsNone(profile_service.load_avatar())

    @unittest.skipUnless(profile_service.pictures_available(), "Pillow is not installed")
    def test_bad_picture_files_are_rejected(self):
        fake = Path(self.folder.name) / "fake.png"
        fake.write_text("this is not a picture")
        for path in (fake, Path(self.folder.name) / "missing.png"):
            with self.assertRaises(ValidationError):
                profile_service.save_avatar(path)
        self.assertIsNone(profile_service.load_avatar())


class ColorTests(unittest.TestCase):
    def test_basics(self):
        self.assertAlmostEqual(colors.luminance("#FFFFFF"), 1.0)
        self.assertAlmostEqual(colors.luminance("#000000"), 0.0)
        self.assertAlmostEqual(colors.contrast("#FFFFFF", "#000000"), 21.0, places=1)
        self.assertEqual(colors.mix("#000000", "#FFFFFF", 0.5), "#808080")
        self.assertEqual(colors.check_hex("#ff8800"), "#FF8800")
        for bad in ("red", "#12345", "#GGGGGG", ""):
            with self.assertRaises(ValueError):
                colors.check_hex(bad)

    def test_custom_palettes_keep_text_readable(self):
        for sidebar in ("#1E3A5F", "#FFD400", "#FFFFFF", "#000000", "#7A1F3D"):
            for accent in ("#4F8EF7", "#F2A900", "#222222", "#FFFFFF"):
                for background in ("#F1F5F9", "#0F1826", "#808080", "#FFF8E7", "#2B0A3D"):
                    p = colors.custom_palette(sidebar, accent, background)
                    self.assertGreaterEqual(colors.contrast(p["TEXT"], p["CARD"]), 4.5, (sidebar, accent, background))
                    self.assertGreaterEqual(colors.contrast(p["SIDEBAR_FG"], p["SIDEBAR"]), 4.5)
                    self.assertGreaterEqual(colors.contrast(p["ON_ACCENT"], p["BLUE"]), 4.5)
        self.assertTrue(colors.custom_palette("#1E3A5F", "#4F8EF7", "#0F1826")["IS_DARK"])
        self.assertFalse(colors.custom_palette("#1E3A5F", "#4F8EF7", "#F1F5F9")["IS_DARK"])


class SettingsExtraTests(DatabaseTestCase):
    def test_custom_colors_and_notification_settings(self):
        settings_service.save({"theme_mode": "Custom", "custom_accent": "#ff8800", "notify_days": "7", "notify_interval": 30})
        loaded = settings_service.load_all()
        self.assertEqual((loaded["theme_mode"], loaded["custom_accent"], loaded["notify_days"], loaded["notify_interval"]),
                         ("Custom", "#FF8800", 7, 30))
        for bad in ({"custom_accent": "orange"}, {"custom_sidebar": "#12345"}, {"notify_days": 5}, {"notify_interval": 15}):
            with self.assertRaises(ValidationError):
                settings_service.save(bad)


class NotificationTests(DatabaseTestCase):
    def test_reminder_text(self):
        today = date(2026, 10, 10)
        self.assertIsNone(notification_service.build_reminder(2, True, today))
        sid = study.add_subject("Math", "")
        planner.add_task(sid, "Late task", "", "2026-10-08")
        planner.add_task(sid, "Soon task", "", "2026-10-11")
        planner.add_task(sid, "Far task", "", "2026-11-30")
        message = notification_service.build_reminder(2, True, today)
        self.assertIn("1 overdue task.", message)
        self.assertIn("1 task due within 2 days.", message)
        self.assertIn("Next: Late task - Overdue by 2 days", message)
        self.assertNotIn("overdue", notification_service.build_reminder(2, False, today))
        self.assertIsNone(notification_service.build_reminder(0, False, date(2026, 10, 5)))



class ChangeWatcherTests(DatabaseTestCase):
    def test_version_changes_only_when_something_is_saved(self):
        watcher = ChangeWatcher()
        first = watcher.version()
        self.assertEqual(watcher.version(), first)   # just looking changes nothing
        study.list_subjects()
        self.assertEqual(watcher.version(), first)   # reading changes nothing
        study.add_subject("Math", "")                # a save made through a different connection
        second = watcher.version()
        self.assertNotEqual(second, first)
        self.assertEqual(watcher.version(), second)
        settings_service.save({"zoom": 150})
        self.assertNotEqual(watcher.version(), second)
        watcher.close()



if __name__ == "__main__":
    unittest.main()
