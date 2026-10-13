"""Colors, font and sizes. apply() sets them from the saved settings; screens read them when they are built."""
import customtkinter as ctk

from ui import colors

LIGHT = dict(
    SIDEBAR="#1E3A5F", SIDEBAR_ACTIVE="#2D4F7C", SIDEBAR_FG="#FFFFFF", SIDEBAR_TEXT="#CBD5E1",
    BLUE="#4F8EF7", BLUE_HOVER="#2F6FDB", BLUE_SOFT="#E8F0FE", GREEN="#22A06B", RED="#C0392B", RED_SOFT="#FDECEC",
    BACKGROUND="#F1F5F9", CARD="#FFFFFF", HEADING="#1E3A5F", TEXT="#334155", MUTED="#64748B", LINE="#D9E2EC",
    ON_ACCENT="#FFFFFF", INPUT="#F4F7FB")
DARK = dict(
    SIDEBAR="#0A1424", SIDEBAR_ACTIVE="#1B2E4B", SIDEBAR_FG="#FFFFFF", SIDEBAR_TEXT="#9FB1C9",
    BLUE="#3B82F6", BLUE_HOVER="#5B9BFF", BLUE_SOFT="#1E3355", GREEN="#3DBE8B", RED="#F07167", RED_SOFT="#3A1F22",
    BACKGROUND="#0F1826", CARD="#172334", HEADING="#E6EEF9", TEXT="#CBD5E1", MUTED="#8FA0B8", LINE="#2A3850",
    ON_ACCENT="#FFFFFF", INPUT="#1F2D44")

FONT = "Segoe UI"
TEXT_SCALE = 1.0
_zoom = _mode = None  # what is applied now, so unchanged values are not applied again
globals().update(LIGHT)  # so every name exists before apply() is called


def _set_mode(name):
    """Tell CustomTkinter the mode, but only when it really changed, because each change re-colors every widget."""
    global _mode
    if name != _mode:
        ctk.set_appearance_mode(name)
        _mode = name


def apply(settings):
    """Choose the palette for the saved theme mode, and set the font, text size and zoom."""
    global FONT, TEXT_SCALE, _zoom
    mode = settings.get("theme_mode", "System")
    if mode == "Custom":  # the student picked their own sidebar, accent and background colors
        palette = colors.custom_palette(settings.get("custom_sidebar", "#1E3A5F"), settings.get("custom_accent", "#4F8EF7"),
                                        settings.get("custom_background", "#F1F5F9"))
        _set_mode("Dark" if palette["IS_DARK"] else "Light")  # also colors CustomTkinter's own parts
    else:
        _set_mode(mode)
        palette = DARK if ctk.get_appearance_mode() == "Dark" else LIGHT
    globals().update(palette)
    globals()["NAVY"], globals()["WHITE"] = globals()["HEADING"], globals()["CARD"]  # old names, kept as a safety net
    FONT = settings.get("font_family", "Segoe UI")
    TEXT_SCALE = settings.get("text_scale", 100) / 100
    zoom = settings.get("zoom", 125)
    if zoom != _zoom:  # changing the zoom re-sizes every widget, so skip it when nothing changed
        ctk.set_widget_scaling(zoom / 100)
        _zoom = zoom
