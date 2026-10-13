"""Dashboard: a summary of subjects, tasks, deadlines, quizzes and progress."""
from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from services import dashboard_service as service
from services import planner_service, profile_service
from ui import theme
from ui.components import font, primary_button, run_service, secondary_button
from ui.components import SmoothScrollFrame


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, parent, navigate):
        super().__init__(parent, fg_color=theme.BACKGROUND, corner_radius=0)
        self.navigate = navigate  # function that opens another screen by name
        self.body = SmoothScrollFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        self.refresh()

    def refresh(self):
        for child in self.body.winfo_children():
            child.destroy()
        ok, data = run_service(service.get_dashboard_data)
        if not ok:
            messagebox.showerror("Nova", data)
            return
        empty = data["counts"]["subjects"] == 0
        self._header(empty)
        if empty:
            self._onboarding()
            return
        self._stats(data)
        columns = ctk.CTkFrame(self.body, fg_color="transparent")
        columns.pack(fill="x")
        for column in range(2):
            columns.grid_columnconfigure(column, weight=1, uniform="cols")
        self._deadlines(columns, data)
        self._recent_quizzes(columns, data)
        self._progress(data)

    # ---- pieces -------------------------------------------------------------------------

    def _card(self, parent, title, column=None):
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        if column is None:
            card.pack(fill="x", padx=8, pady=8)
        else:
            card.grid(row=0, column=column, sticky="nsew", padx=8, pady=8)
        ctk.CTkLabel(card, text=title, text_color=theme.HEADING, font=font(18, True)).pack(anchor="w", padx=24, pady=(18, 8))
        ctk.CTkFrame(card, height=1, fg_color=theme.LINE).pack(fill="x", padx=24, pady=(0, 8))
        return card

    def _header(self, empty):
        header = ctk.CTkFrame(self.body, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(32, 12))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        today = date.today()
        who = profile_service.first_name()
        ctk.CTkLabel(titles, text="Welcome to Nova" if empty else (f"Welcome back, {who}" if who else "Welcome back"), text_color=theme.HEADING,
                     font=font(28, True)).pack(anchor="w")
        ctk.CTkLabel(titles, text=f"{today:%A}, {today:%B} {today.day}, {today.year}", text_color=theme.MUTED,
                     font=font(14)).pack(anchor="w")
        if empty:
            primary_button(header, "Add your first subject", lambda: self.navigate("My Subjects"), width=190).pack(side="right")
        else:
            primary_button(header, "Start a practice quiz", lambda: self.navigate("Practice Quizzes"), width=190).pack(side="right")

    def _onboarding(self):
        card = self._card(self.body, "Get started in three steps")
        steps = ["Step 1: Add a subject and its topics in My Subjects.",
                 "Step 2: Plan a study task with a due date in Study Planner.",
                 "Step 3: Write questions (or load the sample ones) and take a Practice Quiz."]
        for step in steps:
            ctk.CTkLabel(card, text=step, text_color=theme.TEXT, font=font(15)).pack(anchor="w", padx=24, pady=3)
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(anchor="w", padx=24, pady=(14, 20))
        primary_button(buttons, "Go to My Subjects", lambda: self.navigate("My Subjects"), width=170).pack(side="left")
        secondary_button(buttons, "Try the sample quiz", lambda: self.navigate("Practice Quizzes"), width=170).pack(side="left", padx=10)

    def _stats(self, data):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x")
        for column in range(4):
            row.grid_columnconfigure(column, weight=1, uniform="stats")
        counts, tasks = data["counts"], data["task_summary"]
        overdue = tasks["overdue"]
        stats = [
            ("Subjects", counts["subjects"], theme.HEADING, ""),
            ("Study topics", counts["topics"], theme.HEADING, f'{counts["topics_done"]} completed'),
            ("Pending tasks", tasks["pending"], theme.RED if overdue else theme.HEADING, f"{overdue} overdue" if overdue else "None overdue"),
            ("Completed tasks", tasks["completed"], theme.GREEN, ""),
        ]
        for column, (label, value, color, hint) in enumerate(stats):
            card = ctk.CTkFrame(row, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
            card.grid(row=0, column=column, sticky="nsew", padx=8, pady=8)
            ctk.CTkLabel(card, text=label, text_color=theme.MUTED, font=font(13)).pack(anchor="w", padx=20, pady=(16, 0))
            ctk.CTkLabel(card, text=str(value), text_color=color, font=font(28, True)).pack(anchor="w", padx=20)
            ctk.CTkLabel(card, text=hint or " ", text_color=theme.RED if overdue and "overdue" in hint else theme.MUTED,
                         font=font(12)).pack(anchor="w", padx=20, pady=(0, 14))

    def _deadlines(self, parent, data):
        card = self._card(parent, "Upcoming deadlines", column=0)
        if not data["upcoming"]:
            ctk.CTkLabel(card, text="No pending tasks. Add one in the Study Planner.", text_color=theme.MUTED,
                         font=font(14), wraplength=360, justify="left").pack(anchor="w", padx=24, pady=(0, 12))
        for task in data["upcoming"]:
            label = planner_service.due_label(task["due_date"])
            late = label.startswith("Overdue")
            row = ctk.CTkFrame(card, fg_color=theme.BACKGROUND, corner_radius=10)
            row.pack(fill="x", padx=24, pady=4)
            ctk.CTkLabel(row, text=task["title"], text_color=theme.TEXT, font=font(14, True)).pack(anchor="w", padx=14, pady=(8, 0))
            ctk.CTkLabel(row, text=f'{task["subject_name"]}   {label}', text_color=theme.RED if late else theme.MUTED,
                         font=font(12)).pack(anchor="w", padx=14, pady=(0, 8))
        secondary_button(card, "Open Study Planner", lambda: self.navigate("Study Planner"), width=170).pack(anchor="w", padx=24, pady=(10, 20))

    def _recent_quizzes(self, parent, data):
        card = self._card(parent, "Recent quiz results", column=1)
        if not data["recent_quizzes"]:
            ctk.CTkLabel(card, text="No quizzes yet. Take a practice quiz to see your results here.",
                         text_color=theme.MUTED, font=font(14), wraplength=360, justify="left").pack(anchor="w", padx=24, pady=(0, 12))
        for quiz in data["recent_quizzes"]:
            row = ctk.CTkFrame(card, fg_color=theme.BACKGROUND, corner_radius=10)
            row.pack(fill="x", padx=24, pady=4)
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", padx=14, pady=8)
            ctk.CTkLabel(left, text=f'{quiz["subject_name"]}   |   {quiz["topic_name"]}', text_color=theme.TEXT,
                         font=font(14, True)).pack(anchor="w")
            ctk.CTkLabel(left, text=quiz["when"], text_color=theme.MUTED, font=font(12)).pack(anchor="w")
            good = quiz["percent"] >= data["threshold"]
            ctk.CTkLabel(row, text=f'{quiz["score"]} / {quiz["total"]}', text_color=theme.GREEN if good else theme.RED,
                         font=font(15, True)).pack(side="right", padx=14)
        secondary_button(card, "Open My Progress", lambda: self.navigate("My Progress"), width=170).pack(anchor="w", padx=24, pady=(10, 20))

    def _progress(self, data):
        card = self._card(self.body, "Your progress")
        counts, tasks = data["counts"], data["task_summary"]
        bars = [("Topics completed", counts["topics_done"], counts["topics"]),
                ("Tasks completed", tasks["completed"], data["total_tasks"])]
        for label, done, total in bars:
            ctk.CTkLabel(card, text=f"{label}: {done} of {total}" if total else f"{label}: nothing added yet",
                         text_color=theme.TEXT, font=font(14)).pack(anchor="w", padx=24, pady=(4, 2))
            bar = ctk.CTkProgressBar(card, height=10, progress_color=theme.GREEN, fg_color=theme.LINE)
            bar.set(done / total if total else 0)
            bar.pack(fill="x", padx=24, pady=(0, 8))
        review = data["review_count"]
        message = (f"{review} topic{'' if review == 1 else 's'} may need review (below {data['threshold']}% correct)."
                   if review else "No topics are flagged for review right now.")
        ctk.CTkLabel(card, text=message, text_color=theme.RED if review else theme.MUTED, font=font(14)).pack(
            anchor="w", padx=24, pady=(6, 20))
