"""User preferences (appearance and display), saved in the settings table next to the review threshold."""
import re
from contextlib import closing

from database.db_manager import get_connection
from services.study_service import ValidationError, _fetch_all

DEFAULTS = {"theme_mode": "System", "font_family": "Segoe UI", "text_scale": 100, "zoom": 125, "start_maximized": 1,
            "custom_sidebar": "#1E3A5F", "custom_accent": "#4F8EF7", "custom_background": "#F1F5F9",
            "notify_enabled": 1, "notify_days": 2, "notify_overdue": 1, "notify_interval": 0}
CHOICES = {
    "theme_mode": ["Light", "Dark", "System", "Custom"],
    "text_scale": [90, 100, 115, 130],
    "zoom": [100, 110, 125, 150, 175, 200],
    "start_maximized": [0, 1],
    "notify_enabled": [0, 1],
    "notify_days": [1, 2, 3, 7],
    "notify_overdue": [0, 1],
    "notify_interval": [0, 30, 60],  # minutes between checks; 0 means only when Nova starts
}
FONT_CHOICES = ["Segoe UI", "Calibri", "Arial", "Verdana", "Tahoma", "Trebuchet MS", "Georgia", "Cambria"]
INT_KEYS = {"text_scale", "zoom", "start_maximized", "notify_enabled", "notify_days", "notify_overdue", "notify_interval"}
COLOR_KEYS = {"custom_sidebar", "custom_accent", "custom_background"}
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _clean(key, value):
    if key not in DEFAULTS:
        raise ValidationError(f"Unknown setting: {key}")
    if key in COLOR_KEYS:
        value = str(value).strip()
        if not HEX_COLOR.match(value):
            raise ValidationError("Choose a color with the color picker.")
        return value.upper()
    if key == "font_family":
        value = str(value).strip()
        if not value or len(value) > 60:
            raise ValidationError("Choose a font.")
        return value
    if key in INT_KEYS:
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValidationError(f"Invalid value for {key}.") from None
    if value not in CHOICES[key]:
        raise ValidationError(f"Invalid value for {key}.")
    return value


def load_all():
    saved = {row["key"]: row["value"] for row in _fetch_all("SELECT key, value FROM settings")}
    result = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in saved:
            try:
                result[key] = _clean(key, saved[key])
            except ValidationError:
                pass  # a damaged value falls back to the default
    return result


def save(values):
    cleaned = {key: _clean(key, value) for key, value in values.items()}  # check everything before saving anything
    with closing(get_connection()) as connection, connection:
        connection.executemany(
            """INSERT INTO settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            [(key, str(value)) for key, value in cleaned.items()])


def reset():
    with closing(get_connection()) as connection, connection:
        connection.executemany("DELETE FROM settings WHERE key = ?", [(key,) for key in DEFAULTS])
