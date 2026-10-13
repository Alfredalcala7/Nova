"""The student's profile (name, details, picture). Everything is stored on this computer."""
import sqlite3
from contextlib import closing
from pathlib import Path

from database.db_manager import get_connection, get_db_path
from services.study_service import ValidationError, _fetch_all

try:
    from PIL import Image, ImageDraw, ImageOps
except ImportError:  # Pillow is optional: without it Nova works, just without pictures
    Image = None

LABELS = {"name": "Full name", "role": "Role", "school": "School or university", "program": "Course, strand or subjects",
          "year": "Year or grade level", "goal": "Study goal"}
LIMITS = {"name": 80, "role": 20, "school": 100, "program": 100, "year": 40, "goal": 300}
ROLES = ["Student", "Teacher", "Other"]
MAX_PICTURE_MB = 10
AVATAR_SIZE = 256
PILLOW_HELP = "Profile pictures need the Pillow package. In the terminal, run: python -m pip install pillow"


def load_profile():
    profile = {key: "" for key in LIMITS}
    for row in _fetch_all("SELECT key, value FROM settings WHERE key LIKE 'profile\\_%' ESCAPE '\\'"):
        field = row["key"][len("profile_"):]
        if field in profile:
            profile[field] = row["value"]
    return profile


def save_profile(values):
    cleaned = {}
    for key, limit in LIMITS.items():
        text = str(values.get(key, ""))
        value = text.strip() if key == "goal" else " ".join(text.split())
        if len(value) > limit:
            raise ValidationError(f"{LABELS[key]} must be {limit} characters or fewer.")
        cleaned[key] = value
    if cleaned["name"] and len(cleaned["name"]) < 2:
        raise ValidationError("Enter your full name (at least 2 characters), or leave it empty.")
    if cleaned["role"] and cleaned["role"] not in ROLES:
        raise ValidationError("Choose Student, Teacher or Other.")
    with closing(get_connection()) as connection, connection:
        connection.executemany(
            """INSERT INTO settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            [(f"profile_{key}", value) for key, value in cleaned.items()])


def first_name():
    try:
        name = load_profile()["name"]
    except sqlite3.Error:
        return ""
    return name.split()[0] if name else ""


# ---- profile picture ----------------------------------------------------------------------

def pictures_available():
    return Image is not None


def avatar_path():
    return get_db_path().parent / "profile.png"


def _prepare(source):
    """Open a chosen file as a square picture. Nova only reads the pixels, and never runs the file."""
    if Image is None:
        raise ValidationError(PILLOW_HELP)
    path = Path(source)
    try:
        if path.stat().st_size > MAX_PICTURE_MB * 1024 * 1024:
            raise ValidationError(f"Choose a picture smaller than {MAX_PICTURE_MB} MB.")
        with Image.open(path) as picture:
            picture = ImageOps.exif_transpose(picture).convert("RGB")
            return ImageOps.fit(picture, (AVATAR_SIZE, AVATAR_SIZE))
    except ValidationError:
        raise
    except (OSError, ValueError, Image.DecompressionBombError):
        raise ValidationError("Nova could not open that file as a picture. Use a PNG or JPG file.") from None


def _circle(image, size):
    image = image.resize((size, size), Image.Resampling.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    image.putalpha(mask)
    return image


def preview_avatar(source, size=160):
    """A round preview of a chosen file, before it is saved."""
    return _circle(_prepare(source), size)


def save_avatar(source):
    picture = _prepare(source)
    avatar_path().parent.mkdir(parents=True, exist_ok=True)
    picture.save(avatar_path(), "PNG")  # saved again as a fresh PNG, so the original file is never kept


def remove_avatar():
    avatar_path().unlink(missing_ok=True)


def load_avatar(size=160):
    """The saved picture as a round image, or None if there is none (or Pillow is missing)."""
    if Image is None or not avatar_path().exists():
        return None
    try:
        with Image.open(avatar_path()) as stored:
            return _circle(stored.convert("RGB"), size)
    except (OSError, ValueError):
        return None
