"""Opens every screen and completes a full quiz, to catch crashes quickly. Needs a screen (it opens a window).

Run from the Nova folder:   python tests/ui_smoke_test.py
It uses a throwaway database, so your real data is not touched.
"""
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["APPDATA"] = folder.name  # must be set before the app touches the database

from tkinter import messagebox  # noqa: E402


def unexpected_popup(*args, **kwargs):
    raise RuntimeError(f"An unexpected message box appeared: {args}")


messagebox.showerror = messagebox.showinfo = unexpected_popup  # a pop-up would freeze the test

from database.db_manager import initialize_database  # noqa: E402
from services import planner_service, quiz_service, study_service  # noqa: E402
from ui.app import SCREENS, NovaApp  # noqa: E402
from ui.quizzes import ALL_TOPICS  # noqa: E402

initialize_database()
subject_id = study_service.add_subject("Math", "Numbers and equations")
study_service.add_topic(subject_id, "Algebra")
planner_service.add_task(subject_id, "Late task", "", (date.today() - timedelta(days=2)).isoformat())
planner_service.add_task(subject_id, "Soon task", "", (date.today() + timedelta(days=3)).isoformat())
quiz_service.add_sample_content()

app = NovaApp()
for name, _ in SCREENS:
    app.show_screen(name)
    app.update()
    print("opened:", name)

quizzes = app.screens["Practice Quizzes"]
quizzes.subject_name, quizzes.topic_name = quiz_service.SAMPLE_SUBJECT, ALL_TOPICS
quizzes.show_home()
quizzes.start_quiz()
answered = 0
while quizzes.mode == "taking":
    quizzes.choice.set(1)
    quizzes._advance()
    app.update()
    answered += 1
assert quizzes.mode == "results", "the quiz did not reach the results screen"
print(f"completed a quiz of {answered} questions")

quizzes.show_home()
for name, _ in SCREENS:  # open everything again, now that there is quiz history
    app.show_screen(name)
    app.update()
app.toggle_fullscreen()
app.update()
app.toggle_fullscreen()
app.update()
print("toggled full screen on and off")
from services import settings_service  # noqa: E402
from services import profile_service  # noqa: E402
profile_service.save_profile({"name": "Test Student", "role": "Student", "school": "Demo University"})
for mode in ("Dark", "Light", "System", "Custom"):  # redraw the whole app in each theme, with a bigger font and zoom
    settings_service.save({"theme_mode": mode, "text_scale": 115, "zoom": 150, "font_family": "Arial",
                           "custom_sidebar": "#7A1F3D", "custom_accent": "#F2A900", "custom_background": "#FFF8E7"})
    app._rebuild("Dashboard")
    for name in [n for n, _ in SCREENS] + ["Settings", "Account"]:
        app.show_screen(name)
        app.update()
    print("theme", mode, "OK")
app.show_toast("Test", "A toast message works.")
app.update()
app.show_reminder_now(2, True)
app.update()
print("reminder messages OK")
app.show_screen("Account")
app.profile_changed()      # redraws only the sidebar
app.reopen("Account")      # draws one screen again, as "Discard changes" does
app.apply_settings(False)  # a change that needs no redraw
app.show_screen("My Subjects")
app.show_screen("Dashboard")
app.update()
print("partial redraws OK")
app.destroy()
folder.cleanup()
print("UI SMOKE TEST PASSED")
