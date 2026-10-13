"""Adds realistic demo data to Nova, for screenshots and for your presentation demo.

Run from the Nova folder:   python tests/make_demo_data.py
WARNING: this writes to your real Nova database. Delete the demo subjects in the app afterwards if you
want a clean start.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db_manager import get_db_path, initialize_database  # noqa: E402
from services import planner_service, quiz_service, study_service  # noqa: E402
from services.study_service import ValidationError  # noqa: E402


def days_from_today(days):
    return (date.today() + timedelta(days=days)).isoformat()


def main():
    initialize_database()
    print(f"This adds demo data to: {get_db_path()}")
    if input("Type YES to continue: ").strip() != "YES":
        print("Cancelled. Nothing was changed.")
        return
    try:
        biology = study_service.add_subject("Biology", "Cells, plants and heredity")
        math = study_service.add_subject("Mathematics", "Algebra and geometry")
    except ValidationError:
        print("Demo subjects already exist, so nothing was added.")
        return

    photosynthesis = study_service.add_topic(biology, "Photosynthesis")
    cells = study_service.add_topic(biology, "Cell Structure")
    study_service.add_topic(biology, "Genetics")
    study_service.add_topic(math, "Algebra")
    study_service.add_topic(math, "Geometry")
    study_service.set_topic_status(photosynthesis, "completed")
    study_service.set_topic_status(cells, "reviewed")

    for subject, title, offset in [
        (biology, "Photosynthesis worksheet", -2),
        (math, "Review Algebra chapter 3", 1),
        (biology, "Prepare for the Cell Structure quiz", 4),
        (math, "Geometry problem set", 9),
        (biology, "Genetics reading", -5),
    ]:
        task_id = planner_service.add_task(subject, title, "", days_from_today(offset))
        if title == "Genetics reading":
            planner_service.set_task_completed(task_id, True)

    # Four quizzes on the sample questions: one topic is answered badly three times, so a review suggestion appears.
    try:
        quiz_service.add_sample_content()
    except ValidationError:
        pass  # the sample content was already loaded
    sample = next(s for s in study_service.list_subjects() if s["name"] == quiz_service.SAMPLE_SUBJECT)
    questions = quiz_service.build_quiz(sample["id"], limit=6)
    for round_number in range(4):
        answers = {q["id"]: (q["correct_choice"] % 4 + 1 if q["topic_name"] == "Planning and Time" and round_number < 3
                             else q["correct_choice"]) for q in questions}
        quiz_service.save_attempt(sample["id"], None, quiz_service.score_quiz(questions, answers))
    print("Demo data added. Start Nova with: python main.py")


if __name__ == "__main__":
    main()