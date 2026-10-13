"""Practice Quizzes screen: choose a quiz and manage questions, answer one at a time, see results."""
from textwrap import shorten
from tkinter import messagebox

import customtkinter as ctk

from services import quiz_service as service
from services import study_service
from ui import theme
from ui.components import FormDialog, danger_button, font, primary_button, run_service, secondary_button
from ui.components import SmoothScrollFrame, menu_style

ALL_TOPICS = "All topics"


def plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


class QuizzesScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=theme.BACKGROUND, corner_radius=0)
        self.mode = "home"  # home, taking or results
        self.subjects, self.topics = [], []
        self.subject_name, self.topic_name = None, ALL_TOPICS
        self.questions, self.answers, self.index, self.scope = [], {}, 0, None
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self):
        if self.mode != "taking":  # never interrupt a quiz in progress
            self.show_home()

    def _reset(self):
        for child in self.body.winfo_children():
            child.destroy()

    def _header(self, title, subtitle):
        header = ctk.CTkFrame(self.body, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(32, 8))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text=title, text_color=theme.HEADING, font=font(28, True)).pack(anchor="w")
        ctk.CTkLabel(titles, text=subtitle, text_color=theme.MUTED, font=font(14)).pack(anchor="w")
        return header

    # ---- home: choose a quiz and manage questions ---------------------------------------

    def show_home(self):
        self.mode = "home"
        self._reset()
        ok, subjects = run_service(study_service.list_subjects)
        self.subjects = subjects if ok else []
        header = self._header("Practice Quizzes", "Test yourself with your own questions, then review what you missed.")
        if self.subjects:
            secondary_button(header, "Load sample questions", self.load_samples, width=180).pack(side="right")

        if not self.subjects:
            card = ctk.CTkFrame(self.body, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
            card.pack(fill="x", padx=40, pady=24)
            ctk.CTkLabel(card, text="No quiz questions yet", text_color=theme.HEADING, font=font(20, True)).pack(
                anchor="w", padx=28, pady=(24, 4))
            ctk.CTkLabel(card, wraplength=620, justify="left", text_color=theme.MUTED, font=font(15),
                         text="To make your own quiz, create a subject and topics in My Subjects, then add "
                              "questions here. To try a quiz right away, load the sample questions.").pack(anchor="w", padx=28)
            primary_button(card, "Load sample questions", self.load_samples, width=200).pack(anchor="w", padx=28, pady=(16, 24))
            return

        names = [subject["name"] for subject in self.subjects]
        if self.subject_name not in names:
            self.subject_name, self.topic_name = names[0], ALL_TOPICS
        grid = ctk.CTkFrame(self.body, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=32, pady=(8, 24))
        grid.grid_columnconfigure(1, weight=1)
        grid.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(grid, width=320, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        left.grid(row=0, column=0, sticky="ns", padx=(8, 12))
        left.pack_propagate(False)
        right = ctk.CTkFrame(grid, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 8))

        ctk.CTkLabel(left, text="Take a quiz", text_color=theme.HEADING, font=font(18, True)).pack(anchor="w", padx=20, pady=(20, 8))
        ctk.CTkLabel(left, text="Subject", text_color=theme.TEXT, font=font(13)).pack(anchor="w", padx=20)
        self.subject_menu = ctk.CTkOptionMenu(left, values=names, width=280, height=36, font=font(14),
                                              **menu_style(),
                                              command=self._on_subject)
        self.subject_menu.set(self.subject_name)
        self.subject_menu.pack(padx=20, pady=(2, 10))
        ctk.CTkLabel(left, text="Topic", text_color=theme.TEXT, font=font(13)).pack(anchor="w", padx=20)
        self.topic_menu = ctk.CTkOptionMenu(left, values=[ALL_TOPICS], width=280, height=36, font=font(14),
                                            **menu_style(),
                                            command=self._on_topic)
        self.topic_menu.pack(padx=20, pady=(2, 10))
        self.count_label = ctk.CTkLabel(left, text="", text_color=theme.MUTED, font=font(13), wraplength=270, justify="left")
        self.count_label.pack(anchor="w", padx=20, pady=(4, 12))
        self.start_button = primary_button(left, "Start quiz", self.start_quiz, width=280)
        self.start_button.pack(padx=20)

        top = ctk.CTkFrame(right, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(20, 8))
        ctk.CTkLabel(top, text="Questions", text_color=theme.HEADING, font=font(18, True)).pack(side="left")
        primary_button(top, "Add question", self.add_question, width=130).pack(side="right")
        self.q_list = SmoothScrollFrame(right, fg_color="transparent")
        self.q_list.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._load_topics()

    def _on_subject(self, name):
        self.subject_name, self.topic_name = name, ALL_TOPICS
        self._load_topics()

    def _on_topic(self, name):
        self.topic_name = name
        self._update_scope()

    def _load_topics(self):
        subject_id = next(s["id"] for s in self.subjects if s["name"] == self.subject_name)
        ok, topics = run_service(study_service.list_topics, subject_id)
        self.topics = topics if ok else []
        if self.topic_name not in [t["name"] for t in self.topics]:
            self.topic_name = ALL_TOPICS
        self.topic_menu.configure(values=[ALL_TOPICS] + [t["name"] for t in self.topics])
        self.topic_menu.set(self.topic_name)
        self._update_scope()

    def _scope_ids(self):
        subject_id = next(s["id"] for s in self.subjects if s["name"] == self.subject_name)
        topic = next((t for t in self.topics if t["name"] == self.topic_name), None)
        return subject_id, (topic["id"] if topic else None)

    def _update_scope(self):
        ok, questions = run_service(service.list_questions, *self._scope_ids())
        questions = questions if ok else []
        self.count_label.configure(
            text=f"{plural(len(questions), 'question')} available. A quiz uses up to {service.QUIZ_LENGTH}.")
        self.start_button.configure(state="normal" if questions else "disabled")
        for child in self.q_list.winfo_children():
            child.destroy()
        if not questions:
            ctk.CTkLabel(self.q_list, text="No questions here yet. Click Add question.",
                         text_color=theme.MUTED, font=font(14)).pack(anchor="w", padx=8, pady=12)
        for question in questions:
            row = ctk.CTkFrame(self.q_list, fg_color=theme.BACKGROUND, corner_radius=10)
            row.pack(fill="x", pady=4, padx=4)
            text = ctk.CTkFrame(row, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            ctk.CTkLabel(text, text=shorten(question["question_text"], width=55, placeholder="..."),
                         text_color=theme.TEXT, font=font(14)).pack(anchor="w")
            meta = question["topic_name"] + ("   Sample content" if question["is_sample"] else "")
            ctk.CTkLabel(text, text=meta, text_color=theme.BLUE_HOVER if question["is_sample"] else theme.MUTED,
                         font=font(12)).pack(anchor="w")
            danger_button(row, "Delete", lambda q=question: self.delete_question(q), width=64).pack(side="right", padx=(4, 10))
            secondary_button(row, "Edit", lambda q=question: self.edit_question(q), width=54).pack(side="right", padx=4)

    # ---- managing questions -------------------------------------------------------------

    def _question_fields(self, question=None):
        names = [t["name"] for t in self.topics]
        default_topic = self.topic_name if self.topic_name in names else names[0]
        fields = [("topic", "Topic", question["topic_name"] if question else default_topic, names),
                  ("question", "Question", question["question_text"] if question else "", True)]
        for n in range(1, 5):
            fields.append((f"c{n}", f"Choice {n}", question[f"choice_{n}"] if question else "", False))
        fields.append(("correct", "Correct choice number", str(question["correct_choice"]) if question else "1",
                       ["1", "2", "3", "4"]))
        return fields

    def add_question(self):
        if not self.topics:
            messagebox.showinfo("Nova", "Add a topic to this subject in My Subjects first.")
            return
        FormDialog(self, "Add question", self._question_fields(), lambda v: self._save_question(None, v), compact=True)

    def edit_question(self, question):
        FormDialog(self, "Edit question", self._question_fields(question),
                   lambda v: self._save_question(question["id"], v), compact=True)

    def _save_question(self, question_id, values):
        topic_id = next(t["id"] for t in self.topics if t["name"] == values["topic"])
        choices = [values[f"c{n}"] for n in range(1, 5)]
        if question_id is None:
            ok, result = run_service(service.add_question, topic_id, values["question"], choices, values["correct"])
        else:
            ok, result = run_service(service.update_question, question_id, topic_id, values["question"],
                                     choices, values["correct"])
        if not ok:
            return result
        self._update_scope()

    def delete_question(self, question):
        if messagebox.askyesno("Delete question", "Delete this question?", icon="warning"):
            ok, error = run_service(service.delete_question, question["id"])
            if not ok:
                messagebox.showerror("Nova", error)
            self._update_scope()

    def load_samples(self):
        ok, result = run_service(service.add_sample_content)
        if not ok:
            messagebox.showinfo("Nova", result)
            return
        self.subject_name, self.topic_name = service.SAMPLE_SUBJECT, ALL_TOPICS
        self.show_home()

    # ---- taking a quiz ------------------------------------------------------------------

    def start_quiz(self, scope=None):
        scope = scope or self._scope_ids()
        ok, questions = run_service(service.build_quiz, *scope)
        if not ok:
            messagebox.showinfo("Nova", questions)
            return
        self.scope, self.questions, self.answers, self.index = scope, questions, {}, 0
        self.mode = "taking"
        self.show_question()

    def show_question(self):
        self._reset()
        question = self.questions[self.index]
        total, last = len(self.questions), self.index == len(self.questions) - 1
        self._header(f"Question {self.index + 1} of {total}", "Choose one answer. You will see the results at the end.")
        card = ctk.CTkFrame(self.body, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        card.pack(fill="both", expand=True, padx=40, pady=(8, 32))
        bar = ctk.CTkProgressBar(card, height=8, progress_color=theme.BLUE, fg_color=theme.LINE)
        bar.set(self.index / total)
        bar.pack(fill="x", padx=28, pady=(24, 16))
        ctk.CTkLabel(card, text=question["question_text"], text_color=theme.HEADING, font=font(20, True),
                     wraplength=720, justify="left").pack(anchor="w", padx=28, pady=(0, 16))

        self.choice = ctk.IntVar(value=0)
        for n in range(1, 5):
            box = ctk.CTkFrame(card, fg_color=theme.BACKGROUND, corner_radius=10)
            box.pack(fill="x", padx=28, pady=5)
            ctk.CTkRadioButton(box, text=question[f"choice_{n}"], variable=self.choice, value=n, font=font(15),
                               text_color=theme.TEXT, fg_color=theme.BLUE, hover_color=theme.BLUE_HOVER,
                               command=lambda: self.next_button.configure(state="normal")).pack(anchor="w", padx=16, pady=12)

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=28, pady=20)
        self.next_button = primary_button(buttons, "Finish quiz" if last else "Next", self._advance, width=130)
        self.next_button.configure(state="disabled")  # enabled once an answer is chosen
        self.next_button.pack(side="right")
        secondary_button(buttons, "Quit quiz", self.quit_quiz, width=110).pack(side="left")

    def quit_quiz(self):
        if messagebox.askyesno("Quit quiz", "Quit this quiz? Your answers so far will not be saved."):
            self.mode = "home"
            self.show_home()

    def _advance(self):
        if self.mode != "taking" or self.choice.get() == 0:
            return
        self.answers[self.questions[self.index]["id"]] = self.choice.get()
        if self.index < len(self.questions) - 1:
            self.index += 1
            self.show_question()
        else:
            self._finish()

    def _finish(self):
        self.next_button.configure(state="disabled")  # a second click cannot score the quiz twice
        ok, result = run_service(service.score_quiz, self.questions, self.answers)
        if ok:
            ok, saved = run_service(service.save_attempt, *self.scope, result)
        if not ok:
            messagebox.showerror("Nova", result if isinstance(result, str) else saved)
            self.next_button.configure(state="normal")
            return
        self.mode = "results"
        self.show_results(result)

    # ---- results ------------------------------------------------------------------------

    def show_results(self, result):
        self._reset()
        score, total = result["score"], result["total"]
        header = self._header("Quiz results", "Your result has been saved.")
        primary_button(header, "Back to quizzes", self.show_home, width=150).pack(side="right")
        secondary_button(header, "Retake quiz", lambda: self.start_quiz(self.scope), width=120).pack(side="right", padx=8)

        card = ctk.CTkFrame(self.body, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        card.pack(fill="x", padx=40, pady=(8, 12))
        ctk.CTkLabel(card, text=f"{score} / {total}  ({round(100 * score / total)}%)", text_color=theme.HEADING,
                     font=font(32, True)).pack(anchor="w", padx=28, pady=(20, 0))
        ctk.CTkLabel(card, text=f"{score} correct, {total - score} incorrect", text_color=theme.MUTED,
                     font=font(15)).pack(anchor="w", padx=28, pady=(0, 20))

        review = SmoothScrollFrame(self.body, fg_color="transparent")
        review.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        ctk.CTkLabel(review, text="Review your answers", text_color=theme.HEADING, font=font(18, True)).pack(anchor="w", padx=8, pady=(4, 8))
        for number, item in enumerate(result["items"], start=1):
            box = ctk.CTkFrame(review, fg_color=theme.CARD, corner_radius=10)
            box.pack(fill="x", pady=5, padx=8)
            ctk.CTkLabel(box, text=f'{number}. {item["question_text"]}', text_color=theme.HEADING, font=font(15, True),
                         wraplength=740, justify="left").pack(anchor="w", padx=18, pady=(14, 4))
            color = theme.GREEN if item["is_correct"] else theme.RED
            ctk.CTkLabel(box, text="Your answer: " + item["choice_" + str(item["chosen"])],
                         text_color=color, font=font(14), wraplength=740, justify="left").pack(anchor="w", padx=18)
            if not item["is_correct"]:
                ctk.CTkLabel(box, text="Correct answer: " + item["choice_" + str(item["correct_choice"])],
                             text_color=theme.GREEN, font=font(14), wraplength=740, justify="left").pack(anchor="w", padx=18)
            ctk.CTkLabel(box, text="").pack(pady=2)
