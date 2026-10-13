"""Automated tests for the service layer (rules and database). Each test uses its own empty database.

Run from the Nova folder:   python -m unittest discover -s tests -v
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db_manager import get_connection, initialize_database  # noqa: E402
from services import dashboard_service, planner_service as planner  # noqa: E402
from services import progress_service as progress, quiz_service as quiz, study_service as study  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()