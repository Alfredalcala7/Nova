"""Simple Terms screen: a searchable list of plain-language terms plus an optional AI helper."""
import queue
import threading
from tkinter import messagebox

import customtkinter as ctk

from services import ai_service
from services import glossary_service as service
from ui import theme
from ui.components import FormDialog, danger_button, font, primary_button, run_service, secondary_button
from ui.components import SmoothScrollFrame


class TermsScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=theme.BACKGROUND, corner_radius=0)
        self.selected_id = None
        self.terms = []
        self.term_buttons = {}
        self.answer_text = ""
        self.disclosed = False  # the student confirms once per session that text is sent to the AI service
        self.busy = False
        self.results = queue.Queue()  # the background thread hands its answer to the screen through this
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, width=300, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        left.grid(row=0, column=0, sticky="ns", padx=(32, 12), pady=32)
        left.pack_propagate(False)
        header = ctk.CTkFrame(left, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(header, text="Simple Terms", text_color=theme.HEADING, font=font(18, True)).pack(side="left")
        primary_button(header, "Add", self.add_term, width=64).pack(side="right")
        self.search = ctk.CTkEntry(left, placeholder_text="Search terms", height=36, border_color=theme.LINE,
                                   fg_color=theme.CARD, text_color=theme.TEXT, font=font(14))
        self.search.pack(fill="x", padx=16, pady=(0, 8))
        self.search.bind("<KeyRelease>", lambda event: self.refresh())
        self.listing = SmoothScrollFrame(left, fg_color="transparent")
        self.listing.pack(fill="both", expand=True, padx=8)
        secondary_button(left, "Load starter terms", self.load_starters, width=268).pack(padx=16, pady=(4, 16))

        right = SmoothScrollFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 32), pady=32)
        self.term_card = ctk.CTkFrame(right, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        self.term_card.pack(fill="x", pady=(0, 12))
        self._build_ai_card(right)
        self.refresh()

    # ---- the term list and the selected term --------------------------------------------

    def refresh(self):
        ok, terms = run_service(service.list_terms, self.search.get())
        if not ok:
            messagebox.showerror("Nova", terms)
            terms = []
        self.terms = terms
        if self.selected_id not in [t["id"] for t in terms]:
            self.selected_id = terms[0]["id"] if terms else None
        for child in self.listing.winfo_children():
            child.destroy()
        self.term_buttons = {}
        if not terms:
            ctk.CTkLabel(self.listing, text="No terms found. Load the starter terms or add your own.",
                         text_color=theme.MUTED, font=font(13), wraplength=240, justify="left").pack(anchor="w", padx=8, pady=12)
        for term in terms:
            selected = term["id"] == self.selected_id
            self.term_buttons[term["id"]] = button = ctk.CTkButton(self.listing, text=term["term"], anchor="w", height=38, corner_radius=10, font=font(14),
                          text_color=theme.HEADING, fg_color=theme.BLUE_SOFT if selected else "transparent",
                          hover_color=theme.BLUE_SOFT,
                          command=lambda tid=term["id"]: self.select(tid))
            button.pack(fill="x", pady=2)
        self._show_term()

    def select(self, term_id):
        if term_id == self.selected_id:
            return
        previous, self.selected_id = self.selected_id, term_id
        for tid in (previous, term_id):  # only the two affected buttons change, the list is not rebuilt
            button = self.term_buttons.get(tid)
            if button is not None:
                button.configure(fg_color=theme.BLUE_SOFT if tid == term_id else "transparent")
        self._show_term()

    def _show_term(self):
        for child in self.term_card.winfo_children():
            child.destroy()
        term = next((t for t in self.terms if t["id"] == self.selected_id), None)
        if term is None:
            ctk.CTkLabel(self.term_card, text="Pick a term on the left, or ask Nova AI below.",
                         text_color=theme.MUTED, font=font(15)).pack(anchor="w", padx=24, pady=28)
            return
        ctk.CTkLabel(self.term_card, text=term["term"], text_color=theme.HEADING, font=font(24, True)).pack(
            anchor="w", padx=24, pady=(20, 0))
        if term["is_starter"]:
            ctk.CTkLabel(self.term_card, text="Starter term written for Nova. Check it against your textbook.",
                         text_color=theme.BLUE_HOVER, font=font(12)).pack(anchor="w", padx=24)
        ctk.CTkLabel(self.term_card, text=term["explanation"], text_color=theme.TEXT, font=font(15),
                     wraplength=620, justify="left").pack(anchor="w", padx=24, pady=(10, 8))
        if term["example"]:
            ctk.CTkLabel(self.term_card, text="Example", text_color=theme.MUTED, font=font(13)).pack(anchor="w", padx=24)
            ctk.CTkLabel(self.term_card, text=term["example"], text_color=theme.TEXT, fg_color=theme.BACKGROUND,
                         corner_radius=8, font=font(13, family="Consolas"), justify="left",
                         anchor="w").pack(fill="x", padx=24, pady=(2, 8), ipady=8, ipadx=8)
        buttons = ctk.CTkFrame(self.term_card, fg_color="transparent")
        buttons.pack(anchor="w", padx=24, pady=(6, 20))
        secondary_button(buttons, "Edit", lambda: self.edit_term(term), width=80).pack(side="left")
        danger_button(buttons, "Delete", lambda: self.delete_term(term), width=80).pack(side="left", padx=8)

    # ---- managing terms -----------------------------------------------------------------

    def _fields(self, term="", explanation="", example=""):
        return [("term", "Term", term, False), ("explanation", "Explanation in simple words", explanation, True),
                ("example", "Example (optional)", example, True)]

    def add_term(self):
        FormDialog(self, "Add term", self._fields(), lambda v: self._save(None, v), compact=True)

    def edit_term(self, term):
        FormDialog(self, "Edit term", self._fields(term["term"], term["explanation"], term["example"]),
                   lambda v: self._save(term["id"], v), compact=True)

    def _save(self, term_id, values):
        if term_id is None:
            ok, result = run_service(service.add_term, values["term"], values["explanation"], values["example"])
        else:
            ok, result = run_service(service.update_term, term_id, values["term"], values["explanation"], values["example"])
        if not ok:
            return result
        self.selected_id = result if term_id is None else term_id
        self.search.delete(0, "end")
        self.refresh()

    def delete_term(self, term):
        if messagebox.askyesno("Delete term", f'Delete the term "{term["term"]}"?', icon="warning"):
            ok, error = run_service(service.delete_term, term["id"])
            if not ok:
                messagebox.showerror("Nova", error)
            self.refresh()

    def load_starters(self):
        ok, added = run_service(service.load_starter_terms)
        if not ok:
            messagebox.showerror("Nova", added)
            return
        messagebox.showinfo("Nova", f"Added {added} starter terms." if added else "All starter terms are already loaded.")
        self.refresh()

    # ---- the optional AI helper ---------------------------------------------------------

    def _build_ai_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        card.pack(fill="x")
        ctk.CTkLabel(card, text="Ask Nova AI", text_color=theme.HEADING, font=font(18, True)).pack(anchor="w", padx=24, pady=(18, 2))
        ctk.CTkLabel(card, text="Type a term or a question to get a beginner-friendly explanation. This needs internet "
                                "and an AI key on this computer. What you type is sent to the AI provider, and AI can "
                                "make mistakes, so double-check important facts.",
                     text_color=theme.MUTED, font=font(12), wraplength=620, justify="left").pack(anchor="w", padx=24)
        self.prompt = ctk.CTkTextbox(card, height=80, border_width=1, border_color=theme.LINE, fg_color=theme.CARD,
                                     text_color=theme.TEXT, font=font(14))
        self.prompt.pack(fill="x", padx=24, pady=(10, 8))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=24)
        self.ask_button = primary_button(row, "Explain simply", self.ask_ai, width=150)
        self.ask_button.pack(side="left")
        self.status = ctk.CTkLabel(row, text="", text_color=theme.MUTED, font=font(13), wraplength=420, justify="left")
        self.status.pack(side="left", padx=12)
        self.answer_box = ctk.CTkTextbox(card, height=240, border_width=1, border_color=theme.LINE, wrap="word",
                                         fg_color=theme.BACKGROUND, text_color=theme.TEXT, font=font(14))
        self.answer_box.pack(fill="x", padx=24, pady=(12, 0))
        self.answer_box.configure(state="disabled")
        self.save_button = secondary_button(card, "Save to my terms", self.save_answer, width=170)
        self.save_button.pack(anchor="w", padx=24, pady=(10, 20))
        self.save_button.configure(state="disabled")

    def _set_status(self, text, error=False):
        self.status.configure(text=text, text_color=theme.RED if error else theme.MUTED)

    def ask_ai(self):
        if self.busy:
            return
        text = self.prompt.get("1.0", "end-1c").strip()
        if not text:
            self._set_status("Type a term or a question first.", error=True)
            return
        if not ai_service.is_configured():
            self._set_status(ai_service.NO_KEY_MESSAGE, error=True)
            return
        if not self.disclosed:
            if not messagebox.askokcancel("Send to AI?", ai_service.disclosure()):
                return
            self.disclosed = True
        self.busy = True
        self.ask_button.configure(state="disabled", text="Thinking...")
        self._set_status("Asking the AI...")
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()
        self.after(150, self._poll)

    def _worker(self, text):
        """Runs in the background so the window does not freeze while waiting for the internet."""
        try:
            self.results.put(("ok", ai_service.explain_simply(text)))
        except ai_service.AIError as error:
            self.results.put(("error", str(error)))
        except Exception as error:  # last resort, so the screen never stays stuck on Thinking
            self.results.put(("error", f"Something went wrong: {error}"))

    def _poll(self):
        try:
            kind, payload = self.results.get_nowait()
        except queue.Empty:
            self.after(150, self._poll)
            return
        self.busy = False
        self.ask_button.configure(state="normal", text="Explain simply")
        if kind == "error":
            self._set_status(payload, error=True)
            return
        self.answer_text = payload
        self.answer_box.configure(state="normal")
        self.answer_box.delete("1.0", "end")
        self.answer_box.insert("1.0", payload)
        self.answer_box.configure(state="disabled")
        self.save_button.configure(state="normal")
        self._set_status("AI-generated. It can be wrong, so check it against your notes or textbook.")

    def save_answer(self):
        question = " ".join(self.prompt.get("1.0", "end-1c").split())[:service.MAX_TERM_LENGTH]
        fields = self._fields(question, self.answer_text[:service.MAX_EXPLANATION_LENGTH])
        FormDialog(self, "Save to my terms", fields, lambda v: self._save(None, v), compact=True)
