"""Account screen: your name, a few details about you, and an optional profile picture."""
from tkinter import filedialog, messagebox

import customtkinter as ctk

from services import profile_service as service
from services.study_service import ValidationError
from ui import theme
from ui.components import font, primary_button, run_service, secondary_button
from ui.components import SmoothScrollFrame, menu_style

NOT_SET = "Not set"


class AccountScreen(ctk.CTkFrame):
    def __init__(self, parent, on_saved, on_discard):
        super().__init__(parent, fg_color=theme.BACKGROUND, corner_radius=0)
        self.on_saved = on_saved      # updates the sidebar and greeting
        self.on_discard = on_discard  # draws this screen again without the unsaved changes
        self.pending_path = None  # a picture chosen but not saved yet
        self.remove_picture = False
        ok, profile = run_service(service.load_profile)
        profile = profile if ok else {key: "" for key in service.LIMITS}

        ctk.CTkLabel(self, text="Account", text_color=theme.HEADING, font=font(28, True)).pack(anchor="w", padx=40, pady=(32, 0))
        ctk.CTkLabel(self, text="Tell Nova a little about you. This stays on this computer. Press Save to keep your changes.",
                     text_color=theme.MUTED, font=font(14)).pack(anchor="w", padx=40, pady=(0, 8))
        bar = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=0)
        bar.pack(side="bottom", fill="x")
        primary_button(bar, "Save", self.save, width=120).pack(side="left", padx=(40, 8), pady=14)
        secondary_button(bar, "Discard changes", self.on_discard, width=160).pack(side="left", pady=14)
        body = SmoothScrollFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=(0, 8))

        card = self._card(body, "Profile picture")
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(0, 18))
        self.avatar_box = ctk.CTkFrame(top, fg_color="transparent", width=130, height=130)
        self.avatar_box.pack(side="left")
        buttons = ctk.CTkFrame(top, fg_color="transparent")
        buttons.pack(side="left", padx=24)
        primary_button(buttons, "Choose picture", self.choose_picture, width=160).pack(anchor="w")
        secondary_button(buttons, "Remove picture", self.remove, width=160).pack(anchor="w", pady=8)
        note = "PNG or JPG, up to 10 MB. It is shown as a circle." if service.pictures_available() else service.PILLOW_HELP
        ctk.CTkLabel(buttons, text=note, text_color=theme.MUTED, font=font(12), wraplength=360, justify="left").pack(anchor="w")

        card = self._card(body, "About you")
        self.name = self._entry(card, "Full name", profile["name"])
        self.name.bind("<KeyRelease>", lambda event: self._show_avatar())
        label = ctk.CTkLabel(card, text="I am a", text_color=theme.TEXT, font=font(14))
        label.pack(anchor="w", padx=24, pady=(10, 2))
        self.role = ctk.CTkOptionMenu(card, values=[NOT_SET] + service.ROLES, width=200, height=36, font=font(14),
                                      dropdown_font=font(14), **menu_style())
        self.role.set(profile["role"] or NOT_SET)
        self.role.pack(anchor="w", padx=24)
        self.school = self._entry(card, "School or university", profile["school"])
        self.program = self._entry(card, "Course, strand, or subjects you teach", profile["program"])
        self.year = self._entry(card, "Year or grade level", profile["year"])
        ctk.CTkLabel(card, text="My study goal (optional)", text_color=theme.TEXT, font=font(14)).pack(anchor="w", padx=24, pady=(10, 2))
        self.goal = ctk.CTkTextbox(card, width=440, height=80, border_width=1, border_color=theme.LINE,
                                   fg_color=theme.CARD, text_color=theme.TEXT, font=font(14))
        self.goal.insert("1.0", profile["goal"])
        self.goal.pack(anchor="w", padx=24, pady=(0, 20))
        self._show_avatar()

    def _card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        card.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(card, text=title, text_color=theme.HEADING, font=font(18, True)).pack(anchor="w", padx=24, pady=(18, 8))
        ctk.CTkFrame(card, height=1, fg_color=theme.LINE).pack(fill="x", padx=24, pady=(0, 8))
        return card

    def _entry(self, card, label, value):
        ctk.CTkLabel(card, text=label, text_color=theme.TEXT, font=font(14)).pack(anchor="w", padx=24, pady=(10, 2))
        entry = ctk.CTkEntry(card, width=440, height=38, border_color=theme.LINE, fg_color=theme.CARD,
                             text_color=theme.TEXT, font=font(14))
        entry.insert(0, value)
        entry.pack(anchor="w", padx=24)
        return entry

    # ---- the picture --------------------------------------------------------------------

    def _show_avatar(self):
        for child in self.avatar_box.winfo_children():
            child.destroy()
        image = None
        if not self.remove_picture:
            try:
                image = service.preview_avatar(self.pending_path) if self.pending_path else service.load_avatar()
            except ValidationError:
                image = None
        if image is not None:
            ctk.CTkLabel(self.avatar_box, text="", image=ctk.CTkImage(light_image=image, dark_image=image, size=(120, 120))).pack()
        else:  # no picture: show the first letter of the name instead
            ctk.CTkLabel(self.avatar_box, text=(self.name.get().strip()[:1] or "N").upper(), width=120, height=120,
                         corner_radius=60, fg_color=theme.BLUE_SOFT, text_color=theme.HEADING, font=font(44, True)).pack()

    def choose_picture(self):
        if not service.pictures_available():
            messagebox.showinfo("Nova", service.PILLOW_HELP)
            return
        path = filedialog.askopenfilename(title="Choose a profile picture",
                                          filetypes=[("Pictures", "*.png *.jpg *.jpeg"), ("All files", "*.*")])
        if not path:
            return
        try:
            service.preview_avatar(path)  # check now that it really is a picture
        except ValidationError as error:
            messagebox.showerror("Nova", str(error))
            return
        self.pending_path, self.remove_picture = path, False
        self._show_avatar()

    def remove(self):
        self.pending_path, self.remove_picture = None, True
        self._show_avatar()

    # ---- saving -------------------------------------------------------------------------

    def save(self):
        role = self.role.get()
        values = {"name": self.name.get(), "role": "" if role == NOT_SET else role, "school": self.school.get(),
                  "program": self.program.get(), "year": self.year.get(), "goal": self.goal.get("1.0", "end-1c")}
        ok, error = run_service(service.save_profile, values)
        if ok and self.remove_picture:
            ok, error = run_service(service.remove_avatar)
        elif ok and self.pending_path:
            ok, error = run_service(service.save_avatar, self.pending_path)
        if not ok:
            messagebox.showerror("Nova", error)
            return
        self.on_saved()
