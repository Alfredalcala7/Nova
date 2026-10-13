"""My Progress screen: summary numbers, topics to review, subject progress and quiz history."""
from tkinter import messagebox

import customtkinter as ctk

from services import progress_service as service
from ui import theme
from ui.components import font, run_service
from ui.components import SmoothScrollFrame, menu_style

HISTORY_LIMIT = 20


class ProgressScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=theme.BACKGROUND, corner_radius=0)
        ctk.CTkLabel(self, text="My Progress", text_color=theme.HEADING, font=font(28, True)).pack(
            anchor="w", padx=40, pady=(32, 0))
        ctk.CTkLabel(self, text="See how your practice is going and what to review next.",
                     text_color=theme.MUTED, font=font(14)).pack(anchor="w", padx=40, pady=(0, 8))
        self.body = SmoothScrollFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        self.refresh()

    def refresh(self):
        for child in self.body.winfo_children():
            child.destroy()
        ok, data = run_service(service.get_progress_overview)
        if not ok:
            messagebox.showerror("Nova", data)
            return
        self._stat_cards(data)
        self._review_section(data)
        self._subjects_section(data)
        self._history_section(data)

    # ---- sections -----------------------------------------------------------------------

    def _card(self, title=None):
        card = ctk.CTkFrame(self.body, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        card.pack(fill="x", padx=8, pady=8)
        if title:
            ctk.CTkLabel(card, text=title, text_color=theme.HEADING, font=font(18, True)).pack(
                anchor="w", padx=24, pady=(18, 6))
        ctk.CTkFrame(card, height=1, fg_color=theme.LINE).pack(fill="x", padx=24, pady=(0, 8))
        return card

    def _note(self, parent, text, color=None):
        ctk.CTkLabel(parent, text=text, text_color=color or theme.MUTED, font=font(14),
                     wraplength=700, justify="left").pack(anchor="w", padx=24, pady=(0, 14))

    def _stat_cards(self, data):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", padx=8)
        for column in range(3):
            row.grid_columnconfigure(column, weight=1, uniform="stats")
        flagged = len(data["recommendations"]["items"])
        average = data["average"]
        stats = [
            ("Quizzes taken", str(data["attempts"]), theme.HEADING, "Saved on this computer"),
            ("Average score", f"{round(average)}%" if average is not None else "Not enough data",
             theme.HEADING, "" if average is not None else f"Needs {service.MIN_ATTEMPTS_FOR_AVERAGE}+ quizzes"),
            ("Topics to review", str(flagged), theme.RED if flagged else theme.GREEN,
             f"Below {data['threshold']}% correct"),
        ]
        for column, (label, value, color, hint) in enumerate(stats):
            card = ctk.CTkFrame(row, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
            card.grid(row=0, column=column, sticky="nsew", padx=8)
            ctk.CTkLabel(card, text=label, text_color=theme.MUTED, font=font(13)).pack(anchor="w", padx=20, pady=(16, 0))
            ctk.CTkLabel(card, text=value, text_color=color,
                         font=font(26 if len(value) < 6 else 18, True)).pack(anchor="w", padx=20)
            ctk.CTkLabel(card, text=hint, text_color=theme.MUTED, font=font(12)).pack(anchor="w", padx=20, pady=(0, 14))

    def _review_section(self, data):
        card = self._card("Topics to review")
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(0, 10))
        ctk.CTkLabel(top, text="Review threshold", text_color=theme.TEXT, font=font(14)).pack(side="left")
        values = [f"{v}%" for v in sorted({50, 60, 70, 80, 90, data["threshold"]})]
        menu = ctk.CTkOptionMenu(top, values=values, width=90, height=30, font=font(13),
                                 **menu_style(), command=self._set_threshold)
        menu.set(f"{data['threshold']}%")
        menu.pack(side="left", padx=10)

        recommendations = data["recommendations"]
        if recommendations["items"]:
            for item in recommendations["items"]:
                box = ctk.CTkFrame(card, fg_color=theme.RED_SOFT, corner_radius=10)
                box.pack(fill="x", padx=24, pady=4)
                ctk.CTkLabel(box, text=f'{item["topic_name"]}   ({item["subject_name"]})', text_color=theme.HEADING,
                             font=font(15, True)).pack(anchor="w", padx=16, pady=(10, 0))
                ctk.CTkLabel(box, text=item["reason"], text_color=theme.TEXT, font=font(13),
                             wraplength=680, justify="left").pack(anchor="w", padx=16, pady=(0, 10))
        elif data["attempts"] == 0:
            self._note(card, "No quiz results yet. Take a practice quiz and Nova will suggest topics to review.")
        elif recommendations["judged_topics"] == 0:
            self._note(card, f"More practice is needed. A topic needs at least {service.MIN_ANSWERS_FOR_TOPIC} "
                             "answered questions before Nova can judge it.")
        else:
            self._note(card, "No topics are below your threshold. Keep practicing.", theme.GREEN)
        self._note(card, "How this works: Nova adds up your correct answers for each topic and compares the "
                         "percentage with the threshold. It is a simple rule, not artificial intelligence, and "
                         "the threshold is a starting point, not a measure of mastery.")

    def _subjects_section(self, data):
        card = self._card("Subject progress")
        if not data["subjects"]:
            self._note(card, "No subjects yet. Add one in My Subjects.")
        for subject in data["subjects"]:
            row = ctk.CTkFrame(card, fg_color=theme.BACKGROUND, corner_radius=10)
            row.pack(fill="x", padx=24, pady=4)
            ctk.CTkLabel(row, text=subject["name"], text_color=theme.TEXT, font=font(15, True)).pack(
                side="left", padx=14, pady=10)
            quizzes = f'{subject["attempts"]} quiz{"" if subject["attempts"] == 1 else "zes"}'
            if subject["attempts"] >= service.MIN_ATTEMPTS_FOR_AVERAGE:
                quizzes += f', average {round(subject["average"])}%'
            ctk.CTkLabel(row, text=f'{subject["completed_count"]} of {subject["topic_count"]} topics completed   |   {quizzes}',
                         text_color=theme.MUTED, font=font(13)).pack(side="right", padx=14)
        ctk.CTkLabel(card, text="").pack(pady=4)

    def _history_section(self, data):
        card = self._card("Quiz history")
        history = data["history"]
        if not history:
            self._note(card, "Your finished quizzes will appear here.")
            return
        for item in history[:HISTORY_LIMIT]:
            row = ctk.CTkFrame(card, fg_color=theme.BACKGROUND, corner_radius=10)
            row.pack(fill="x", padx=24, pady=4)
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", padx=14, pady=8)
            ctk.CTkLabel(left, text=f'{item["subject_name"]}   |   {item["topic_name"]}', text_color=theme.TEXT,
                         font=font(14, True)).pack(anchor="w")
            ctk.CTkLabel(left, text=item["when"], text_color=theme.MUTED, font=font(12)).pack(anchor="w")
            good = item["percent"] >= data["threshold"]
            ctk.CTkLabel(row, text=f'{item["score"]} / {item["total"]}   ({round(item["percent"])}%)',
                         text_color=theme.GREEN if good else theme.RED, font=font(15, True)).pack(side="right", padx=14)
        if len(history) > HISTORY_LIMIT:
            self._note(card, f"Showing the {HISTORY_LIMIT} most recent of {len(history)} quizzes.")
        else:
            ctk.CTkLabel(card, text="").pack(pady=4)

    def _set_threshold(self, label):
        ok, error = run_service(service.set_review_threshold, label.rstrip("%"))
        if not ok:
            messagebox.showerror("Nova", error)
        self.refresh()
