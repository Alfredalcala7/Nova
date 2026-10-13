"""My Subjects screen: subject list on the left, the selected subject's topics on the right."""
import sqlite3
from tkinter import messagebox

import customtkinter as ctk

from services import study_service as service
from ui import theme
from ui.components import danger_button, font, primary_button, secondary_button, FormDialog
from ui.components import SmoothScrollFrame

def status_color(status):
    return {"not_started": theme.MUTED, "reviewed": theme.BLUE, "completed": theme.GREEN}[status]


STATUS_BY_LABEL = {label: key for key, label in service.STATUS_LABELS.items()}


def plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


class SubjectsScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=theme.BACKGROUND, corner_radius=0)
        self.selected_id = None
        self.subjects = []
        self.subject_buttons = {}
        self.right_body = None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.left = ctk.CTkFrame(self, width=300, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        self.left.grid(row=0, column=0, sticky="ns", padx=(32, 12), pady=32)
        self.left.pack_propagate(False)  # keep the fixed width
        self.right = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        self.right.grid(row=0, column=1, sticky="nsew", padx=(12, 32), pady=32)
        self.refresh()

    # ---- helpers ------------------------------------------------------------------------

    def _run(self, action, *args):
        """Call a service function; return (True, result) or (False, message) instead of crashing."""
        try:
            return True, action(*args)
        except service.ValidationError as error:
            return False, str(error)
        except sqlite3.Error as error:
            return False, f"A database error occurred: {error}"

    @staticmethod
    def _clear(frame):
        for child in frame.winfo_children():
            child.destroy()

    def refresh(self):
        """Reload everything from the database. Called whenever this screen is shown."""
        ok, result = self._run(service.list_subjects)
        if not ok:
            messagebox.showerror("Nova", result)
        self.subjects = result if ok else []
        ids = [subject["id"] for subject in self.subjects]
        if self.selected_id not in ids:
            self.selected_id = ids[0] if ids else None
        self._build_left()
        self._build_right()

    def select(self, subject_id):
        if subject_id == self.selected_id:
            return
        previous, self.selected_id = self.selected_id, subject_id
        for sid in (previous, subject_id):  # only the two affected buttons change, the list is not rebuilt
            button = self.subject_buttons.get(sid)
            if button is not None:
                button.configure(fg_color=theme.BLUE_SOFT if sid == subject_id else "transparent")
        self._build_right()

    # ---- layout -------------------------------------------------------------------------

    def _build_left(self):
        self._clear(self.left)
        self.subject_buttons = {}
        header = ctk.CTkFrame(self.left, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(header, text="Subjects", text_color=theme.HEADING, font=font(18, True)).pack(side="left")
        primary_button(header, "Add", self.add_subject, width=64).pack(side="right")

        listing = SmoothScrollFrame(self.left, fg_color="transparent")
        listing.pack(fill="both", expand=True, padx=8, pady=(0, 12))
        if not self.subjects:
            ctk.CTkLabel(listing, text="No subjects yet.\nClick Add to create your first one.",
                         text_color=theme.MUTED, font=font(13), justify="left").pack(anchor="w", padx=8, pady=12)
        for subject in self.subjects:
            selected = subject["id"] == self.selected_id
            self.subject_buttons[subject["id"]] = button = ctk.CTkButton(
                listing, text=f'{subject["name"]}\n{plural(subject["topic_count"], "topic")}',
                anchor="w", height=54, corner_radius=10, font=font(14), text_color=theme.HEADING,
                fg_color=theme.BLUE_SOFT if selected else "transparent", hover_color=theme.BLUE_SOFT,
                command=lambda sid=subject["id"]: self.select(sid),
            )
            button.pack(fill="x", pady=2)

    def _build_right(self):
        body = ctk.CTkFrame(self.right, fg_color="transparent")  # built while hidden, then swapped in, so nothing flashes
        self._fill_right(body)
        body.pack(fill="both", expand=True)
        if self.right_body is not None:
            self.right_body.destroy()
        self.right_body = body

    def _fill_right(self, body):
        subject = next((s for s in self.subjects if s["id"] == self.selected_id), None)
        if subject is None:
            box = ctk.CTkFrame(body, fg_color="transparent")
            box.place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(box, text="Start with a subject", text_color=theme.HEADING, font=font(22, True)).pack()
            ctk.CTkLabel(box, text="A subject holds the topics you study, such as Biology with Photosynthesis.",
                         text_color=theme.MUTED, font=font(14), wraplength=360).pack(pady=(6, 16))
            primary_button(box, "Add your first subject", self.add_subject, width=200).pack()
            return

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x", padx=28, pady=(24, 0))
        ctk.CTkLabel(top, text=subject["name"], text_color=theme.HEADING, font=font(24, True),
                     wraplength=560, justify="left").pack(anchor="w")
        ctk.CTkLabel(top, text=subject["description"] or "No description.", text_color=theme.MUTED,
                     font=font(14), wraplength=560, justify="left").pack(anchor="w", pady=(2, 0))
        total, done = subject["topic_count"], subject["completed_count"]
        summary = f"{done} of {plural(total, 'topic')} completed" if total else "No topics yet"
        ctk.CTkLabel(top, text=summary, text_color=theme.GREEN if total and done == total else theme.TEXT,
                     font=font(14, True)).pack(anchor="w", pady=(10, 10))
        actions = ctk.CTkFrame(top, fg_color="transparent")
        actions.pack(anchor="w")
        secondary_button(actions, "Edit subject", self.edit_subject).pack(side="left")
        danger_button(actions, "Delete subject", self.delete_subject, width=130).pack(side="left", padx=8)

        header = ctk.CTkFrame(body, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(24, 8))
        ctk.CTkLabel(header, text="Topics", text_color=theme.HEADING, font=font(18, True)).pack(side="left")
        primary_button(header, "Add topic", self.add_topic, width=100).pack(side="right")

        listing = SmoothScrollFrame(body, fg_color="transparent")
        listing.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        ok, topics = self._run(service.list_topics, subject["id"])
        if not ok:
            messagebox.showerror("Nova", topics)
            topics = []
        if not topics:
            ctk.CTkLabel(listing, text="No topics yet. Add the lessons you want to study.",
                         text_color=theme.MUTED, font=font(14)).pack(anchor="w", padx=8, pady=12)
        for topic in topics:
            self._topic_row(listing, topic)

    def _topic_row(self, parent, topic):
        row = ctk.CTkFrame(parent, fg_color=theme.BACKGROUND, corner_radius=10)
        row.pack(fill="x", pady=4, padx=8)
        ctk.CTkLabel(row, text=topic["name"], text_color=theme.TEXT, font=font(15), anchor="w").pack(
            side="left", padx=14, pady=10)
        danger_button(row, "Delete", lambda t=topic: self.delete_topic(t), width=70).pack(side="right", padx=(4, 10))
        secondary_button(row, "Edit", lambda t=topic: self.edit_topic(t), width=60).pack(side="right", padx=4)
        menu = ctk.CTkOptionMenu(
            row, values=list(service.STATUS_LABELS.values()), width=130, height=32, font=font(13),
            fg_color=status_color(topic["status"]), button_color=status_color(topic["status"]),
            command=lambda label, t=topic: self.change_status(t, label),
        )
        menu.set(service.STATUS_LABELS[topic["status"]])
        menu.pack(side="right", padx=4)

    # ---- subject actions ----------------------------------------------------------------

    def add_subject(self):
        fields = [("name", "Subject name", "", False), ("description", "Description (optional)", "", True)]
        FormDialog(self, "Add subject", fields, self._save_new_subject)

    def _save_new_subject(self, values):
        ok, result = self._run(service.add_subject, values["name"], values["description"])
        if not ok:
            return result
        self.selected_id = result
        self.refresh()

    def edit_subject(self):
        subject = next(s for s in self.subjects if s["id"] == self.selected_id)
        fields = [("name", "Subject name", subject["name"], False),
                  ("description", "Description (optional)", subject["description"], True)]
        FormDialog(self, "Edit subject", fields, lambda v: self._save_subject(subject["id"], v))

    def _save_subject(self, subject_id, values):
        ok, result = self._run(service.update_subject, subject_id, values["name"], values["description"])
        if not ok:
            return result
        self.refresh()

    def delete_subject(self):
        subject = next(s for s in self.subjects if s["id"] == self.selected_id)
        ok, counts = self._run(service.count_subject_contents, subject["id"])
        if not ok:
            messagebox.showerror("Nova", counts)
            return
        message = (f'Delete "{subject["name"]}"?\n\nThis will also permanently delete '
                   f'{plural(counts["topics"], "topic")}, {plural(counts["tasks"], "task")}, '
                   f'{plural(counts["questions"], "quiz question")} and '
                   f'{plural(counts["attempts"], "quiz attempt")}.')
        if messagebox.askyesno("Delete subject", message, icon="warning"):
            ok, error = self._run(service.delete_subject, subject["id"])
            if not ok:
                messagebox.showerror("Nova", error)
            self.refresh()

    # ---- topic actions ------------------------------------------------------------------

    def add_topic(self):
        FormDialog(self, "Add topic", [("name", "Topic name", "", False)], self._save_new_topic)

    def _save_new_topic(self, values):
        ok, result = self._run(service.add_topic, self.selected_id, values["name"])
        if not ok:
            return result
        self.refresh()

    def edit_topic(self, topic):
        FormDialog(self, "Edit topic", [("name", "Topic name", topic["name"], False)],
                   lambda v: self._save_topic(topic["id"], v))

    def _save_topic(self, topic_id, values):
        ok, result = self._run(service.update_topic, topic_id, values["name"])
        if not ok:
            return result
        self.refresh()

    def change_status(self, topic, label):
        ok, error = self._run(service.set_topic_status, topic["id"], STATUS_BY_LABEL[label])
        if not ok:
            messagebox.showerror("Nova", error)
        self.refresh()

    def delete_topic(self, topic):
        ok, questions = self._run(service.count_topic_questions, topic["id"])
        if not ok:
            messagebox.showerror("Nova", questions)
            return
        message = f'Delete the topic "{topic["name"]}"?'
        if questions:
            message += f'\n\nIts {plural(questions, "quiz question")} will also be deleted.'
        if messagebox.askyesno("Delete topic", message, icon="warning"):
            ok, error = self._run(service.delete_topic, topic["id"])
            if not ok:
                messagebox.showerror("Nova", error)
            self.refresh()
