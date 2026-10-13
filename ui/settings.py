"""Settings screen: theme, font, text size and zoom. Changes are applied when Save is pressed."""
from tkinter import font as tkfont
from tkinter import colorchooser, messagebox

import customtkinter as ctk

from services import settings_service as service
from ui import colors, theme
from ui.components import font, primary_button, run_service, secondary_button
from ui.components import SegmentedControl, SmoothScrollFrame, menu_style, modern_switch

SHORTCUTS = [("F11", "Full screen on or off"), ("Esc", "Leave full screen"), ("Ctrl and + or -", "Zoom in or out"),
             ("Ctrl and 0", "Reset zoom"), ("Ctrl and 1 to 6", "Switch screens"), ("Ctrl and ,", "Open Settings")]


COLOR_KEYS = {"custom_sidebar": "Sidebar color", "custom_accent": "Accent color", "custom_background": "Background color"}
INTERVALS = {"When Nova starts": 0, "Every 30 minutes": 30, "Every hour": 60}
APPEARANCE_KEYS = ("theme_mode", "font_family", "text_scale", "zoom", "custom_sidebar", "custom_accent", "custom_background")


class SettingsScreen(ctk.CTkFrame):
    def __init__(self, parent, on_saved, on_test=None):
        super().__init__(parent, fg_color=theme.BACKGROUND, corner_radius=0)
        self.on_saved = on_saved  # called after Save so the whole app can redraw itself
        self.on_test = on_test    # shows a test reminder
        ok, saved = run_service(service.load_all)
        saved = saved if ok else dict(service.DEFAULTS)
        self.saved = saved

        ctk.CTkLabel(self, text="Settings", text_color=theme.HEADING, font=font(28, True)).pack(anchor="w", padx=40, pady=(32, 0))
        ctk.CTkLabel(self, text="Make Nova comfortable to read. Press Save to apply your changes.",
                     text_color=theme.MUTED, font=font(14)).pack(anchor="w", padx=40, pady=(0, 8))
        bar = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=0)
        bar.pack(side="bottom", fill="x")
        primary_button(bar, "Save", self.save, width=120).pack(side="left", padx=(40, 8), pady=14)
        secondary_button(bar, "Reset to defaults", self.reset, width=160).pack(side="left", pady=14)
        body = SmoothScrollFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=(0, 8))

        card = self._card(body, "Appearance")
        row = self._row(card, "Theme")
        self.theme_box = SegmentedControl(row, values=service.CHOICES["theme_mode"], command=self._theme_changed)
        self.theme_box.set(saved["theme_mode"])
        self.theme_box.pack(side="left")
        ctk.CTkLabel(card, text="System follows your Windows light or dark setting.", text_color=theme.MUTED,
                     font=font(12)).pack(anchor="w", padx=24)

        self.colors = {key: saved[key] for key in COLOR_KEYS}
        self.color_buttons, self.custom_widgets = {}, []
        self.custom_box = ctk.CTkFrame(card, fg_color="transparent", width=0, height=0)  # only filled when Custom is chosen
        self.custom_box.pack(fill="x")
        for key, label in COLOR_KEYS.items():
            row = self._row(self.custom_box, label)
            button = ctk.CTkButton(row, text="", width=130, height=34, font=font(13), corner_radius=8, border_width=1,
                                   border_color=theme.LINE, command=lambda k=key: self._pick(k))
            button.pack(side="left")
            self._paint(button, self.colors[key])
            self.color_buttons[key] = button
            self.custom_widgets.append((row, {"fill": "x", "padx": 24, "pady": 8}))
        hint = ctk.CTkLabel(self.custom_box, text="Pick any colors you like. Text colors adjust automatically so they stay easy to read.",
                            text_color=theme.MUTED, font=font(12))
        self.custom_widgets.append((hint, {"anchor": "w", "padx": 24}))
        self._theme_changed(saved["theme_mode"])

        installed = set(tkfont.families())
        fonts = [name for name in service.FONT_CHOICES if name in installed] or [service.DEFAULTS["font_family"]]
        if saved["font_family"] not in fonts:
            fonts.append(saved["font_family"])
        row = self._row(card, "Font")
        self.font_menu = self._menu(row, fonts, saved["font_family"], command=self._preview_font)
        self.preview = ctk.CTkLabel(card, text="Preview: The quick brown fox jumps over the lazy dog.",
                                    text_color=theme.TEXT, font=font(15))
        self.preview.pack(anchor="w", padx=24, pady=(0, 6))
        row = self._row(card, "Text size")
        self.size_menu = self._menu(row, [f"{v}%" for v in service.CHOICES["text_scale"]], f"{saved['text_scale']}%")
        row = self._row(card, "Zoom (whole layout)")
        self.zoom_menu = self._menu(row, [f"{v}%" for v in service.CHOICES["zoom"]], f"{saved['zoom']}%")
        row = self._row(card, "Start maximized")
        self.maximized = modern_switch(row)
        if saved["start_maximized"]:
            self.maximized.select()
        self.maximized.pack(side="left")
        ctk.CTkLabel(card, text="").pack(pady=2)

        card = self._card(body, "Notifications")
        row = self._row(card, "Task reminders")
        self.notify_on = self._switch(row, saved["notify_enabled"])
        row = self._row(card, "Remind me about tasks due within")
        days = [f"{d} day{'' if d == 1 else 's'}" for d in service.CHOICES["notify_days"]]
        self.days_menu = self._menu(row, days, f"{saved['notify_days']} day{'' if saved['notify_days'] == 1 else 's'}")
        row = self._row(card, "Include overdue tasks")
        self.overdue_on = self._switch(row, saved["notify_overdue"])
        row = self._row(card, "Check for reminders")
        label = next(name for name, minutes in INTERVALS.items() if minutes == saved["notify_interval"])
        self.interval_menu = self._menu(row, list(INTERVALS), label)
        row = self._row(card, "")
        secondary_button(row, "Show a test reminder", self._test, width=200).pack(side="left")
        ctk.CTkLabel(card, text="Reminders appear inside Nova while it is open. They are not Windows notifications.",
                     text_color=theme.MUTED, font=font(12)).pack(anchor="w", padx=24, pady=(0, 14))

        card = self._card(body, "Keyboard shortcuts")
        for keys, meaning in SHORTCUTS:
            row = self._row(card, keys)
            ctk.CTkLabel(row, text=meaning, text_color=theme.MUTED, font=font(14)).pack(side="left")
        ctk.CTkLabel(card, text="").pack(pady=2)

    def _card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        card.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(card, text=title, text_color=theme.HEADING, font=font(18, True)).pack(anchor="w", padx=24, pady=(18, 6))
        ctk.CTkFrame(card, height=1, fg_color=theme.LINE).pack(fill="x", padx=24, pady=(0, 8))
        return card

    def _row(self, card, label):
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(row, text=label, text_color=theme.TEXT, font=font(15), width=200, anchor="w").pack(side="left")
        return row

    def _menu(self, row, values, current, command=None):
        menu = ctk.CTkOptionMenu(row, values=values, width=200, height=36, font=font(14), dropdown_font=font(14),
                                 **menu_style(),
                                 command=command)
        menu.set(current)
        menu.pack(side="left")
        return menu

    def _theme_changed(self, mode):
        for widget, _ in self.custom_widgets:
            widget.pack_forget()
        if mode == "Custom":  # show the three color buttons, always in the same order
            for widget, options in self.custom_widgets:
                widget.pack(**options)

    def _paint(self, button, color):
        button.configure(text=color, fg_color=color, hover_color=color, text_color=colors.best_text(color))

    def _pick(self, key):
        chosen = colorchooser.askcolor(color=self.colors[key], title="Choose a color", parent=self)[1]
        if chosen:
            self.colors[key] = chosen.upper()
            self._paint(self.color_buttons[key], self.colors[key])

    def _switch(self, row, value):
        switch = modern_switch(row)
        if value:
            switch.select()
        switch.pack(side="left")
        return switch

    def _test(self):
        if self.on_test:
            self.on_test(int(self.days_menu.get().split()[0]), bool(self.overdue_on.get()))

    def _preview_font(self, family):
        self.preview.configure(font=ctk.CTkFont(family=family, size=round(15 * theme.TEXT_SCALE)))

    def save(self):
        values = {"theme_mode": self.theme_box.get(), "font_family": self.font_menu.get(),
                  "text_scale": self.size_menu.get().rstrip("%"), "zoom": self.zoom_menu.get().rstrip("%"),
                  "start_maximized": self.maximized.get(), **self.colors,
                  "notify_enabled": self.notify_on.get(), "notify_days": self.days_menu.get().split()[0],
                  "notify_overdue": self.overdue_on.get(), "notify_interval": INTERVALS[self.interval_menu.get()]}
        ok, error = run_service(service.save, values)
        if not ok:
            messagebox.showerror("Nova", error)
            return
        ok, fresh = run_service(service.load_all)
        changed = not ok or any(str(fresh[key]).lower() != str(self.saved[key]).lower() for key in APPEARANCE_KEYS)
        if ok:
            self.saved = fresh
        self.on_saved(changed)  # only a change to the look needs the whole app redrawn

    def reset(self):
        if messagebox.askyesno("Reset settings", "Go back to the default theme, font, text size and zoom?"):
            ok, error = run_service(service.reset)
            if not ok:
                messagebox.showerror("Nova", error)
                return
            self.on_saved(True)
