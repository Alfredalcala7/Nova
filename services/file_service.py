"""Reads files a student attaches to the AI chat, using only the standard library.

Images and PDFs are passed to the AI as they are (it can read them). Word, PowerPoint, Excel and plain-text
files are turned into text here. Nova only reads the bytes. It never opens or runs a file.
"""
import base64
import html
import io
import re
import zipfile

from services.ai_service import MAX_FILE_TEXT

MAX_FILE_BYTES = 12 * 1024 * 1024
MAX_FILES = 5
MAX_TOTAL_BYTES = 20 * 1024 * 1024
IMAGES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".tsv", ".json", ".log", ".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp",
                   ".cs", ".sql", ".xml", ".yml", ".yaml", ".ini", ".tex", ".rtf"}
ACCEPT = ",".join(sorted([*IMAGES, ".pdf", ".docx", ".pptx", ".xlsx", *TEXT_EXTENSIONS]))


class FileError(Exception):
    """A file Nova cannot use. The message is written to be shown to the student."""


def _extension(name):
    return ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""


def _xml_text(xml, paragraph_tag, text_tag):
    xml = xml.replace(f"</{paragraph_tag}>", "\n")
    pieces = re.findall(rf"<{text_tag}(?: [^>]*)?>([^<]*)</{text_tag}>|\n", xml)
    out, line = [], []
    for piece in pieces:
        if piece == "":
            out.append("".join(line))
            line = []
        else:
            line.append(html.unescape(piece))
    out.append("".join(line))
    return "\n".join(x for x in (s.strip() for s in out) if x)


def _read_zip(data, name):
    try:
        return zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise FileError(f"{name} looks damaged or is not a real Office file.") from None


def _docx_text(data, name):
    archive = _read_zip(data, name)
    try:
        xml = archive.read("word/document.xml").decode("utf-8", "replace")
    except KeyError:
        raise FileError(f"{name} does not contain a readable document.") from None
    xml = re.sub(r"<w:tab/>", "\t", xml)
    pieces = re.sub(r"</w:p>", "\n", xml)
    text = html.unescape(re.sub(r"<[^>]+>", "", pieces))
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _pptx_text(data, name):
    archive = _read_zip(data, name)
    slides = sorted((n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                    key=lambda n: int(re.findall(r"\d+", n)[0]))
    if not slides:
        raise FileError(f"{name} has no slides Nova can read.")
    parts = []
    for number, slide in enumerate(slides, start=1):
        text = _xml_text(archive.read(slide).decode("utf-8", "replace"), "a:p", "a:t")
        parts.append(f"## Slide {number}\n{text}")
    return "\n\n".join(parts)


def _xlsx_text(data, name):
    archive = _read_zip(data, name)
    try:
        strings = re.findall(r"<t(?: [^>]*)?>([^<]*)</t>", archive.read("xl/sharedStrings.xml").decode("utf-8", "replace"))
    except KeyError:
        raise FileError(f"{name} has no text cells Nova can read.") from None
    return "Cell text from the spreadsheet:\n" + "\n".join(html.unescape(s) for s in strings if s.strip())


def read_material(name, data):
    """Turn one uploaded file into an attachment dict for the AI, or raise FileError."""
    name = (name or "file").strip()[:120]
    ext = _extension(name)
    if not data:
        raise FileError(f"{name} is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise FileError(f"{name} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB. Try a smaller file.")
    if ext in IMAGES:
        return {"kind": "image", "mime": IMAGES[ext], "data": base64.b64encode(data).decode("ascii"), "text": None, "name": name}
    if ext == ".pdf":
        if not data.startswith(b"%PDF"):
            raise FileError(f"{name} is not a real PDF.")
        return {"kind": "pdf", "mime": "application/pdf", "data": base64.b64encode(data).decode("ascii"), "text": None, "name": name}
    if ext == ".docx":
        text = _docx_text(data, name)
    elif ext == ".pptx":
        text = _pptx_text(data, name)
    elif ext == ".xlsx":
        text = _xlsx_text(data, name)
    elif ext in TEXT_EXTENSIONS:
        text = data.decode("utf-8", "replace")
    elif ext in (".doc", ".ppt", ".xls"):
        raise FileError(f"Old Office files ({ext}) are not supported. Save {name} as .docx, .pptx or .xlsx, or as a PDF.")
    else:
        raise FileError(f"Nova cannot read {ext or 'this kind of'} files yet. Try a PDF, image, Word, PowerPoint or text file.")
    text = text.strip()
    if not text:
        raise FileError(f"Nova found no readable text in {name}.")
    note = ""
    if len(text) > MAX_FILE_TEXT:
        text, note = text[:MAX_FILE_TEXT], "\n\n[Nova cut the file here because it is very long.]"
    return {"kind": "text", "mime": "text/plain", "data": None, "text": text + note, "name": name}


def read_many(files):
    """`files` is a list of {name, data(base64)}. Returns attachments. Enforces the count and total size."""
    if len(files) > MAX_FILES:
        raise FileError(f"Attach up to {MAX_FILES} files at a time.")
    attachments, total = [], 0
    for item in files:
        try:
            raw = base64.b64decode(item.get("data", ""), validate=False)
        except (ValueError, TypeError):
            raise FileError(f"{item.get('name', 'A file')} could not be read.") from None
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise FileError("Those files are too large together. Attach fewer or smaller files.")
        attachments.append(read_material(item.get("name", "file"), raw))
    return attachments
