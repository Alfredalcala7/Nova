"""Study Planner screen: tasks grouped as Overdue, Upcoming and Completed."""
from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from services import planner_service as service
from services import study_service
from ui import theme
from ui.components import FormDialog, danger_button, font, primary_button, run_service, secondary_button
from ui.components import SmoothScrollFrame


class PlannerScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=theme.BACKGROUND, corner_radius=0)
        self.subjects = []

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(32, 8))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Study Planner", text_color=theme.HEADING, font=font(28, True)).pack(anchor="w")
        self.summary = ctk.CTkLabel(titles, text="", text_color=theme.MUTED, font=font(14))
        self.summary.pack(anchor="w")
        primary_button(header, "Add task", self.add_task).pack(side="right")

        self.listing = SmoothScrollFrame(self, fg_color="transparent")
        self.listing.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        self.refresh()

    def refresh(self):
        """Reload tasks and subjects from the database. Called whenever this screen is shown."""
        ok, tasks = run_service(service.list_tasks)
        if not ok:
            messagebox.showerror("Nova", tasks)
            tasks = []
        ok, subjects = run_service(study_service.list_subjects)
        self.subjects = subjects if ok else []

        for child in self.listing.winfo_children():
            child.destroy()

        if not tasks:
            self.summary.configure(text="Plan what to study and when.")
            text = ("No tasks yet. Add a task to plan what you will study." if self.subjects
                    else "Create a subject in My Subjects first, then add tasks for it.")
            ctk.CTkLabel(self.listing, text=text, text_color=theme.MUTED, font=font(15)).pack(anchor="w", padx=8, pady=24)
            return

        counts = service.summarize(tasks)
        self.summary.configure(
            text=f'{counts["pending"]} pending, {counts["overdue"]} overdue, {counts["completed"]} completed')
        groups = service.group_tasks(tasks)
        for title, key, color in (("Overdue", "overdue", theme.RED),
                                  ("Upcoming", "upcoming", theme.HEADING),
                                  ("Completed", "completed", theme.GREEN)):
            if groups[key]:
                ctk.CTkLabel(self.listing, text=f"{title} ({len(groups[key])})", text_color=color,
                             font=font(16, True)).pack(anchor="w", padx=8, pady=(16, 4))
                for task in groups[key]:
                    self._task_row(task)

    def _task_row(self, task):
        done = bool(task["is_completed"])
        overdue = not done and service.due_label(task["due_date"]).startswith("Overdue")
        row = ctk.CTkFrame(self.listing, fg_color=theme.CARD, corner_radius=10)
        row.pack(fill="x", pady=4, padx=4)

        checked = ctk.BooleanVar(value=done)
        ctk.CTkCheckBox(row, text="", variable=checked, width=28, checkbox_width=22, checkbox_height=22,
                        corner_radius=6, fg_color=theme.GREEN, hover_color=theme.GREEN,
                        command=lambda t=task, v=checked: self.toggle(t, v.get())).pack(side="left", padx=(14, 4), pady=14)

        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, pady=10)
        title_font = ctk.CTkFont(family=theme.FONT, size=round(15 * theme.TEXT_SCALE), overstrike=done)
        ctk.CTkLabel(text, text=task["title"], font=title_font, anchor="w",
                     text_color=theme.MUTED if done else theme.TEXT).pack(anchor="w")
        meta = ctk.CTkFrame(text, fg_color="transparent")
        meta.pack(anchor="w")
        ctk.CTkLabel(meta, text=task["subject_name"], text_color=theme.MUTED, font=font(13)).pack(side="left")
        ctk.CTkLabel(meta, text="   " + service.due_label(task["due_date"]), font=font(13, overdue),
                     text_color=theme.RED if overdue else theme.MUTED).pack(side="left")
        if task["description"]:
            ctk.CTkLabel(text, text=task["description"], text_color=theme.MUTED, font=font(13),
                         wraplength=480, justify="left").pack(anchor="w")

        danger_button(row, "Delete", lambda t=task: self.delete_task(t), width=70).pack(side="right", padx=(4, 12))
        secondary_button(row, "Edit", lambda t=task: self.edit_task(t), width=60).pack(side="right", padx=4)

    # ---- actions ------------------------------------------------------------------------

    def _fields(self, task=None):
        names = [subject["name"] for subject in self.subjects]
        return [
            ("subject", "Subject", task["subject_name"] if task else names[0], names),
            ("title", "Task title", task["title"] if task else "", False),
            ("due", "Due date (YYYY-MM-DD)", task["due_date"] if task else date.today().isoformat(), False),
            ("description", "Description (optional)", task["description"] if task else "", True),
        ]

    def _subject_id(self, name):
        return next(subject["id"] for subject in self.subjects if subject["name"] == name)

    def add_task(self):
        if not self.subjects:
            messagebox.showinfo("Nova", "Create a subject in My Subjects first, then add tasks for it.")
            return
        FormDialog(self, "Add task", self._fields(), self._save_new)

    def _save_new(self, values):
        ok, result = run_service(service.add_task, self._subject_id(values["subject"]),
                                 values["title"], values["description"], values["due"])
        if not ok:
            return result
        self.refresh()

    def edit_task(self, task):
        FormDialog(self, "Edit task", self._fields(task), lambda v: self._save_edit(task["id"], v))

    def _save_edit(self, task_id, values):
        ok, result = run_service(service.update_task, task_id, self._subject_id(values["subject"]),
                                 values["title"], values["description"], values["due"])
        if not ok:
            return result
        self.refresh()

    def toggle(self, task, checked):
        ok, error = run_service(service.set_task_completed, task["id"], checked)
        if not ok:
            messagebox.showerror("Nova", error)
        self.refresh()

    def delete_task(self, task):
        if messagebox.askyesno("Delete task", f'Delete the task "{task["title"]}"?', icon="warning"):
            ok, error = run_service(service.delete_task, task["id"])
            if not ok:
                messagebox.showerror("Nova", error)
            self.refresh()
