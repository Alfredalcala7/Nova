"""Reusable widgets shared by several screens."""
import sqlite3
import tkinter as tk

import customtkinter as ctk

from services.study_service import ValidationError
from ui import colors, theme


def font(size=14, bold=False, family=None):
    return ctk.CTkFont(family=family or theme.FONT, size=max(8, round(size * theme.TEXT_SCALE)),
                       weight="bold" if bold else "normal")


def run_service(action, *args):
    """Call a service function; return (True, result) or (False, message) instead of crashing."""
    try:
        return True, action(*args)
    except ValidationError as error:
        return False, str(error)
    except sqlite3.Error as error:
        return False, f"A database error occurred: {error}"


BUTTON_HEIGHT = 40
BUTTON_RADIUS = 12


def primary_button(parent, text, command, width=120):
    """The main action on a screen: a solid accent color."""
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=BUTTON_HEIGHT, corner_radius=BUTTON_RADIUS,
                         border_width=0, fg_color=theme.BLUE, hover_color=theme.BLUE_HOVER, text_color=theme.ON_ACCENT,
                         font=font(14, True))


def secondary_button(parent, text, command, width=120):
    """A quieter action: a soft fill with a thin border."""
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=BUTTON_HEIGHT, corner_radius=BUTTON_RADIUS,
                         border_width=1, border_color=theme.LINE, fg_color=theme.INPUT, hover_color=theme.BLUE_SOFT,
                         text_color=theme.HEADING, font=font(14, True))


def danger_button(parent, text, command, width=120):
    """For deleting: a soft red fill, clear without being alarming."""
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=BUTTON_HEIGHT, corner_radius=BUTTON_RADIUS,
                         border_width=0, fg_color=theme.RED_SOFT, hover_color=colors.mix(theme.RED_SOFT, theme.RED, 0.18),
                         text_color=theme.RED, font=font(14, True))


def menu_style():
    """Colors that make a drop-down look like a form field instead of a bright button, in any theme."""
    return dict(fg_color=theme.INPUT, button_color=theme.INPUT, button_hover_color=theme.BLUE_SOFT, text_color=theme.TEXT,
                dropdown_fg_color=theme.CARD, dropdown_text_color=theme.TEXT, dropdown_hover_color=theme.BLUE_SOFT,
                corner_radius=10)


WHEEL_INCREMENT = 3  # pixels in one scroll unit
WHEEL_NOTCH = 60     # pixels moved by one notch of the mouse wheel


class SmoothScrollFrame(ctk.CTkScrollableFrame):
    """A scrolling area that glides at a steady pace.

    The standard one scrolls once for every wheel event, so spinning the wheel fast floods the window with redraws,
    and text smears. This one adds up the wheel movement and applies it in small eased steps about 100 times a second.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._wheel_pending = 0.0
        self._wheel_job = None
        canvas = getattr(self, "_parent_canvas", None)
        if canvas is not None:
            canvas.configure(yscrollincrement=WHEEL_INCREMENT, xscrollincrement=WHEEL_INCREMENT)

    def _pointer_inside(self, widget):
        canvas = getattr(self, "_parent_canvas", None)
        while widget is not None:
            if widget is self or widget is canvas:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _mouse_wheel_all(self, event):  # replaces the standard handler that CustomTkinter attaches to the whole window
        if self._pointer_inside(event.widget):
            self._wheel_pending += -event.delta / 120 * WHEEL_NOTCH
            if self._wheel_job is None:
                self._wheel_job = self.after(10, self._wheel_step)

    def _wheel_step(self):
        self._wheel_job = None
        canvas = getattr(self, "_parent_canvas", None)
        if canvas is None or canvas.yview() == (0.0, 1.0):  # everything already fits, so there is nothing to scroll
            self._wheel_pending = 0.0
            return
        units = round(self._wheel_pending * 0.4 / WHEEL_INCREMENT) or (1 if self._wheel_pending > 0 else -1)
        canvas.yview_scroll(units, "units")  # each step covers 40% of the distance left, so movement eases out
        self._wheel_pending -= units * WHEEL_INCREMENT
        if abs(self._wheel_pending) >= WHEEL_INCREMENT:
            self._wheel_job = self.after(10, self._wheel_step)
        else:
            self._wheel_pending = 0.0

    def destroy(self):
        if self._wheel_job is not None:
            self.after_cancel(self._wheel_job)
            self._wheel_job = None
        super().destroy()


class SegmentedControl(ctk.CTkFrame):
    """A row of choices with one selected: a soft rounded track, and the chosen option in the accent color."""

    def __init__(self, parent, values, command=None):
        super().__init__(parent, fg_color=theme.INPUT, corner_radius=14, border_width=1, border_color=theme.LINE)
        self.command, self.selected, self.buttons = command, None, {}
        for value in values:
            button = ctk.CTkButton(self, text=value, width=84, height=36, corner_radius=10, font=font(14, True),
                                   fg_color="transparent", hover_color=theme.BLUE_SOFT, text_color=theme.TEXT,
                                   command=lambda v=value: self._choose(v))
            button.pack(side="left", padx=3, pady=3)
            self.buttons[value] = button

    def get(self):
        return self.selected

    def set(self, value):
        self.selected = value
        for name, button in self.buttons.items():
            on = name == value
            button.configure(fg_color=theme.BLUE if on else "transparent", hover_color=theme.BLUE_HOVER if on else theme.BLUE_SOFT,
                             text_color=theme.ON_ACCENT if on else theme.TEXT)

    def _choose(self, value):
        self.set(value)
        if self.command:
            self.command(value)


def modern_switch(parent):
    """An on/off switch with a white knob and a soft track."""
    return ctk.CTkSwitch(parent, text="", progress_color=theme.BLUE, fg_color=theme.LINE, button_color="#FFFFFF",
                         button_hover_color="#F1F5F9")


class FormDialog(ctk.CTkToplevel):
    """A small pop-up form.

    fields:  list of (key, label, initial_text, kind); kind is False (one line), True (text box)
             or a list of choices (drop-down)
    on_save: called with {key: text}; return an error message to keep the form open, or None to close it.
    """

    def __init__(self, parent, title, fields, on_save, compact=False):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=theme.CARD)
        self.transient(parent.winfo_toplevel())
        self.on_save = on_save
        self.inputs = {}
        self.first_input = None

        for key, label, initial, multiline in fields:
            ctk.CTkLabel(self, text=label, text_color=theme.TEXT, font=font(13)).pack(
                anchor="w", padx=24, pady=(8, 2) if compact else (16, 4))
            if isinstance(multiline, list):
                box = ctk.CTkOptionMenu(self, values=multiline, width=380, height=38, font=font(14),
                                        **menu_style())
                box.set(initial)
            elif multiline:
                box = ctk.CTkTextbox(self, width=380, height=70 if compact else 90, border_width=1,
                                     border_color=theme.LINE, fg_color=theme.CARD,
                                     text_color=theme.TEXT, font=font(14))
                box.insert("1.0", initial)
            else:
                box = ctk.CTkEntry(self, width=380, height=38, border_color=theme.LINE,
                                   fg_color=theme.CARD, text_color=theme.TEXT, font=font(14))
                box.insert(0, initial)
                box.bind("<Return>", lambda event: self._submit())
            box.pack(padx=24)
            self.inputs[key] = (box, multiline)
            self.first_input = self.first_input or box

        self.error = ctk.CTkLabel(self, text="", text_color=theme.RED, font=font(13),
                                  wraplength=380, justify="left")
        self.error.pack(anchor="w", padx=24, pady=(10, 0))
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=24, pady=(8, 20))
        primary_button(buttons, "Save", self._submit, width=100).pack(side="right")
        secondary_button(buttons, "Cancel", self.destroy, width=100).pack(side="right", padx=8)
        self.bind("<Escape>", lambda event: self.destroy())

        self.update_idletasks()  # center over the main window
        root = parent.winfo_toplevel()
        x = root.winfo_x() + (root.winfo_width() - self.winfo_reqwidth()) // 2
        y = root.winfo_y() + (root.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{x}+{y}")
        self.after(150, self._take_focus)  # a short delay avoids a CustomTkinter focus glitch

    def _take_focus(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except tk.TclError:
            return  # the dialog was closed before it finished opening
        if self.first_input is not None:
            self.first_input.focus_set()

    def _submit(self):
        values = {key: (box.get("1.0", "end-1c") if multiline is True else box.get())
                  for key, (box, multiline) in self.inputs.items()}
        message = self.on_save(values)
        if message:
            self.error.configure(text=message)
        else:
            self.destroy()


class PlaceholderScreen(ctk.CTkFrame):
    """Stand-in shown until a screen's real milestone is built."""

    def __init__(self, parent, title, description):
        super().__init__(parent, fg_color=theme.BACKGROUND, corner_radius=0)
        ctk.CTkLabel(self, text=title, text_color=theme.HEADING, font=font(28, True)).pack(
            anchor="w", padx=40, pady=(36, 4))
        ctk.CTkLabel(self, text=description, text_color=theme.MUTED, font=font(15)).pack(
            anchor="w", padx=40)
        card = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=20, border_width=1, border_color=theme.LINE)
        card.pack(fill="x", padx=40, pady=28)
        ctk.CTkLabel(card, text="This screen is built in a later milestone.",
                     text_color=theme.TEXT, font=font(15)).pack(padx=24, pady=28)
