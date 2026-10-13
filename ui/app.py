"""Main window: sidebar navigation, a content area that swaps screens, full screen, zoom and theme."""
import time
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from database.db_manager import ChangeWatcher
from services import notification_service, profile_service, settings_service
from ui import theme
from ui.account import AccountScreen
from ui.components import PlaceholderScreen, font, run_service
from ui.dashboard import DashboardScreen
from ui.planner import PlannerScreen
from ui.progress import ProgressScreen
from ui.quizzes import QuizzesScreen
from ui.settings import SettingsScreen
from ui.subjects import SubjectsScreen
from ui.terms import TermsScreen

# (sidebar label, one-line description). Screens not listed in REAL_SCREENS show a placeholder.
SCREENS = [
    ("Dashboard", "Your study overview and recent activity."),
    ("My Subjects", "Organize your subjects and the topics inside them."),
    ("Study Planner", "Track study tasks and deadlines."),
    ("Practice Quizzes", "Test yourself with multiple-choice questions."),
    ("My Progress", "See your quiz history and which topics to review."),
    ("Simple Terms", "Hard words explained in plain language, with an optional AI helper."),
]
REAL_SCREENS = {"My Subjects": SubjectsScreen, "Study Planner": PlannerScreen, "Practice Quizzes": QuizzesScreen,
                "My Progress": ProgressScreen, "Simple Terms": TermsScreen}
STALE_SECONDS = 300  # a screen is also redrawn after this long, so dates such as "due tomorrow" stay right


class NovaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings = dict(settings_service.DEFAULTS)
        self.nav_buttons, self.screens, self.drawn, self.current = {}, {}, {}, None
        self.fullscreen = False
        self.toast, self.last_reminder, self.reminder_job = None, None, None
        try:
            self.watcher = ChangeWatcher()
        except Exception:  # without it Nova still works, it just redraws screens more often
            self.watcher = None
        self._load_settings()
        self.title("Nova")
        self.geometry("1280x800")
        self.minsize(1000, 650)
        if self.settings["start_maximized"]:
            self.after(50, self._maximize)
        self.grid_columnconfigure(1, weight=1)  # the content column takes all spare width
        self.grid_rowconfigure(0, weight=1)
        self._bind_keys()
        self._build_layout()
        self.show_screen("Dashboard")
        self._schedule_reminders(first=True)

    def destroy(self):
        """Close the database watcher when the window closes, so Windows lets go of the database file."""
        if self.watcher is not None:
            self.watcher.close()
            self.watcher = None
        super().destroy()

    # ---- settings, full screen and zoom -------------------------------------------------

    def _load_settings(self):
        ok, data = run_service(settings_service.load_all)
        self.settings = data if ok else dict(settings_service.DEFAULTS)
        theme.apply(self.settings)
        self.configure(fg_color=theme.BACKGROUND)

    def _maximize(self):
        try:
            self.state("zoomed")  # Windows only
        except tk.TclError:
            pass

    def _bind_keys(self):
        self.bind("<F11>", lambda event: self.toggle_fullscreen())
        self.bind("<Escape>", lambda event: self.exit_fullscreen())
        for combo in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.bind(combo, lambda event: self.change_zoom(1))
        for combo in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.bind(combo, lambda event: self.change_zoom(-1))
        self.bind("<Control-Key-0>", lambda event: self.change_zoom(0))
        self.bind("<Control-comma>", lambda event: self.show_screen("Settings"))
        for number, (name, _) in enumerate(SCREENS, start=1):
            self.bind(f"<Control-Key-{number}>", lambda event, n=name: self.show_screen(n))

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.attributes("-fullscreen", self.fullscreen)

    def exit_fullscreen(self):
        if self.fullscreen:
            self.toggle_fullscreen()

    def change_zoom(self, direction):
        levels, current = settings_service.CHOICES["zoom"], self.settings["zoom"]
        default = settings_service.DEFAULTS["zoom"]
        index = levels.index(current) if current in levels else levels.index(default)
        new = default if direction == 0 else levels[max(0, min(len(levels) - 1, index + direction))]
        if new != current:
            ok, error = run_service(settings_service.save, {"zoom": new})
            if ok:
                self.apply_settings()
            else:
                messagebox.showerror("Nova", error)

    def apply_settings(self, appearance=True, notice="Settings saved"):
        """After Save. Only a change to the look (theme, colors, font, size, zoom) needs the app redrawn."""
        if appearance:  # a short delay, so the button that was clicked is not destroyed in the middle of its own click
            self.after(20, lambda: self._rebuild(self.current or "Dashboard", notice))
        else:
            self._load_settings()
            self._schedule_reminders()
            self.show_toast("Saved", notice, seconds=4)

    def profile_changed(self, notice="Account saved"):
        """After the Account screen is saved: redraw only the sidebar, and let the Dashboard greet the new name."""
        self._rebuild_sidebar()
        dashboard = self.screens.pop("Dashboard", None)
        if dashboard is not None:
            dashboard.destroy()
            self.drawn.pop("Dashboard", None)
        self.show_toast("Saved", notice, seconds=4)

    def reopen(self, name):
        """Draw one screen again from scratch, for example to throw away unsaved changes."""
        screen = self.screens.pop(name, None)
        if screen is not None:
            screen.destroy()
        self.drawn.pop(name, None)
        self.current = None
        self.show_screen(name)

    def _rebuild(self, target, notice=None):
        # Destroy first, THEN change the theme and zoom, so no old widget is re-colored or re-sized for nothing.
        self.sidebar.destroy()
        self.content.destroy()
        self.nav_buttons, self.screens, self.drawn, self.current = {}, {}, {}, None
        self._load_settings()
        self._build_layout()
        self.show_screen(target)
        self._schedule_reminders()
        if notice:
            self.show_toast("Saved", notice, seconds=4)

    def _rebuild_sidebar(self):
        self.sidebar.destroy()
        self.nav_buttons = {}
        self._build_sidebar()
        self._highlight(self.current)

    # ---- layout -------------------------------------------------------------------------

    def _build_layout(self):
        self._build_sidebar()
        self.content = ctk.CTkFrame(self, fg_color=theme.BACKGROUND, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=250, fg_color=theme.SIDEBAR, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.pack_propagate(False)  # keep the fixed width
        ctk.CTkLabel(self.sidebar, text="Nova", text_color=theme.SIDEBAR_FG, font=font(30, True)).pack(
            anchor="w", padx=24, pady=(28, 0))
        ctk.CTkLabel(self.sidebar, text="Study planner and practice quizzes", text_color=theme.SIDEBAR_TEXT,
                     font=font(12), wraplength=200, justify="left").pack(anchor="w", padx=24, pady=(0, 24))
        self._profile_header()
        for name, _ in SCREENS:
            self._nav_button(name)
        ctk.CTkLabel(self.sidebar, text="SDG 4: Quality Education", text_color=theme.SIDEBAR_TEXT,
                     font=font(12)).pack(side="bottom", anchor="w", padx=24, pady=18)
        self._nav_button("Settings", side="bottom")
        self._nav_button("Account", side="bottom")

    def _profile_header(self):
        """Shows the student's picture and name at the top of the sidebar, once they have set them."""
        ok, profile = run_service(profile_service.load_profile)
        name = profile["name"] if ok else ""
        image = profile_service.load_avatar(128) if ok else None
        if not name and image is None:
            return
        row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 18))
        if image is not None:
            ctk.CTkLabel(row, text="", image=ctk.CTkImage(light_image=image, dark_image=image, size=(48, 48))).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(row, text=name or "Your profile", text_color=theme.SIDEBAR_FG, font=font(14, True),
                     wraplength=150, justify="left").pack(side="left")
        for widget in (row, *row.winfo_children()):  # clicking the profile opens the Account screen
            widget.bind("<Button-1>", lambda event: self.show_screen("Account"))

    def _nav_button(self, name, side="top"):
        row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        row.pack(fill="x", padx=(10, 14), pady=2, side=side)
        bar = ctk.CTkFrame(row, width=4, height=26, corner_radius=2, fg_color="transparent")  # shows which screen is open
        bar.pack(side="left", padx=(0, 6))
        button = ctk.CTkButton(row, text=name, anchor="w", height=44, corner_radius=12, font=font(15),
                               fg_color="transparent", hover_color=theme.SIDEBAR_ACTIVE, text_color=theme.SIDEBAR_FG,
                               command=lambda n=name: self.show_screen(n))
        button.pack(side="left", fill="x", expand=True)
        self.nav_buttons[name] = (button, bar)

    def _highlight(self, name):
        for button_name in {self.current, name}:  # only the old and the new item change, not all of them
            pair = self.nav_buttons.get(button_name)
            if pair is not None:
                button, bar = pair
                active = button_name == name
                button.configure(fg_color=theme.SIDEBAR_ACTIVE if active else "transparent")
                bar.configure(fg_color=theme.BLUE if active else "transparent")

    def _create_screen(self, name):
        if name == "Dashboard":  # the dashboard needs to open other screens
            return DashboardScreen(self.content, self.show_screen)
        if name == "Settings":
            return SettingsScreen(self.content, self.apply_settings, self.show_reminder_now)
        if name == "Account":
            return AccountScreen(self.content, self.profile_changed, lambda: self.reopen("Account"))
        if name in REAL_SCREENS:
            return REAL_SCREENS[name](self.content)
        return PlaceholderScreen(self.content, name, dict(SCREENS)[name])

    def show_screen(self, name):
        """Bring a screen to the front. All screens sit in the same place, stacked, so nothing is removed or re-laid-out.

        A screen reloads its data only if something was saved since it was last drawn. That reload happens while the
        screen is still hidden underneath, so you never see it half-built.
        """
        if name == self.current and name in self.screens:
            return
        created = name not in self.screens
        if created:  # a new screen draws itself when it is created
            self.screens[name] = self._create_screen(name)
            self.screens[name].grid(row=0, column=0, sticky="nsew")
        screen = self.screens[name]
        stamp = self.watcher.version() if self.watcher else None
        previous = self.drawn.get(name)
        stale = previous is None or stamp is None or previous[0] != stamp or time.monotonic() - previous[1] > STALE_SECONDS
        refresh = getattr(screen, "refresh", None)
        if refresh and stale and not created:
            refresh()
        if created or stale:
            self.drawn[name] = (stamp, time.monotonic())
        screen.tkraise()
        self._highlight(name)
        self.current = name

    # ---- reminders ----------------------------------------------------------------------

    def show_toast(self, title, message, seconds=9):
        """A small message in the top-right corner that goes away by itself."""
        if self.toast is not None:
            self._close(self.toast)
        toast = ctk.CTkFrame(self, fg_color=theme.CARD, border_width=1, border_color=theme.LINE, corner_radius=12)
        ctk.CTkLabel(toast, text=title, text_color=theme.HEADING, font=font(15, True)).pack(anchor="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(toast, text=message, text_color=theme.TEXT, font=font(13), wraplength=320, justify="left").pack(
            anchor="w", padx=16, pady=(2, 6))
        ctk.CTkButton(toast, text="Dismiss", width=80, height=28, font=font(12), fg_color=theme.BLUE,
                      hover_color=theme.BLUE_HOVER, text_color=theme.ON_ACCENT,
                      command=lambda: self._close(toast)).pack(anchor="e", padx=16, pady=(0, 12))
        toast.place(relx=1.0, x=-24, y=24, anchor="ne")
        toast.lift()
        self.toast = toast
        self.after(seconds * 1000, lambda: self._close(toast))

    @staticmethod
    def _close(widget):
        try:
            widget.destroy()
        except tk.TclError:
            pass  # it was already closed

    def _schedule_reminders(self, first=False):
        """Check shortly after Nova starts, then repeat only if the student chose an interval."""
        if self.reminder_job is not None:
            self.after_cancel(self.reminder_job)
            self.reminder_job = None
        if not self.settings["notify_enabled"]:
            return
        interval = self.settings["notify_interval"]
        delay = 1500 if first else (interval * 60000 if interval else None)
        if delay:
            self.reminder_job = self.after(delay, self._reminder_tick)

    def _reminder_tick(self):
        self.reminder_job = None
        ok, message = run_service(notification_service.build_reminder, self.settings["notify_days"],
                                  bool(self.settings["notify_overdue"]))
        if ok and message and message != self.last_reminder:  # never repeat the same message
            self.last_reminder = message
            self.show_toast("Study reminder", message)
        interval = self.settings["notify_interval"]
        if self.settings["notify_enabled"] and interval:
            self.reminder_job = self.after(interval * 60000, self._reminder_tick)

    def show_reminder_now(self, days, include_overdue):
        ok, message = run_service(notification_service.build_reminder, days, include_overdue)
        self.show_toast("Test reminder", message if ok and message else "Nothing is due soon or overdue right now.")
