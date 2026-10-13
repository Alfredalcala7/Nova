"""Color math for custom themes. Pure Python, so it can be tested without opening a window."""
import re

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def check_hex(value):
    if not HEX.match(value):
        raise ValueError(f"Not a color: {value!r}")
    return value.upper()


def to_rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def to_hex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(c))) for c in rgb)


def mix(first, second, amount):
    """Blend two colors. amount 0 gives the first color, 1 gives the second."""
    return to_hex(tuple(a + (b - a) * amount for a, b in zip(to_rgb(first), to_rgb(second))))


def luminance(color):
    """How bright a color looks, from 0 (black) to 1 (white)."""
    r, g, b = (((c / 255) / 12.92) if c / 255 <= 0.03928 else (((c / 255) + 0.055) / 1.055) ** 2.4 for c in to_rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(first, second):
    """Readability of text on a background: 1 is unreadable, 21 is black on white. 4.5 is a common target."""
    brighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (brighter + 0.05) / (darker + 0.05)


def best_text(background, dark="#1B2430", light="#F4F7FB"):
    return dark if contrast(dark, background) >= contrast(light, background) else light


def custom_palette(sidebar, accent, background):
    """Build every color Nova needs from the three the student picked, keeping text readable."""
    sidebar, accent, background = check_hex(sidebar), check_hex(accent), check_hex(background)
    is_dark = luminance(background) < 0.179  # the point where white text becomes easier to read than black
    card = mix(background, "#FFFFFF", 0.07 if is_dark else 0.7)
    text = best_text(card)
    on_accent = best_text(accent, "#10151F", "#FFFFFF")
    sidebar_fg = best_text(sidebar, "#10151F", "#FFFFFF")
    red = "#F07167" if is_dark else "#C0392B"
    return {
        "IS_DARK": is_dark,
        "SIDEBAR": sidebar, "SIDEBAR_FG": sidebar_fg, "SIDEBAR_TEXT": mix(sidebar_fg, sidebar, 0.3),
        "SIDEBAR_ACTIVE": mix(sidebar, "#FFFFFF" if sidebar_fg == "#FFFFFF" else "#000000", 0.16),
        "BLUE": accent, "ON_ACCENT": on_accent,
        "BLUE_HOVER": mix(accent, "#000000", 0.18) if luminance(accent) > 0.25 else mix(accent, "#FFFFFF", 0.18),
        "BLUE_SOFT": mix(accent, background, 0.82),
        "GREEN": "#3DBE8B" if is_dark else "#22A06B", "RED": red, "RED_SOFT": mix(red, card, 0.85),
        "BACKGROUND": background, "CARD": card, "HEADING": text, "TEXT": text,
        "MUTED": mix(text, card, 0.4), "LINE": mix(card, text, 0.15), "INPUT": mix(card, text, 0.06),
    }
