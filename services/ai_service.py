"""Nova's AI layer: chat, summaries, quizzes from files, and the one-shot "explain simply" helper.

There is no Nova server. The app talks straight to an AI provider with a key that lives on THIS computer
(an environment variable, or the key saved from Settings in your per-user Nova folder). Never put a key in code.
Two providers: Google Gemini (has a free tier) and Claude. Only the standard library is used.
"""
import json
import os
import random
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROVIDERS = {  # the first one with a key is used, unless NOVA_AI_PROVIDER names one
    "gemini": {"key_variable": "GEMINI_API_KEY", "default_model": "gemini-3.5-flash"},
    "anthropic": {"key_variable": "ANTHROPIC_API_KEY", "default_model": "claude-haiku-5-5"},
}
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_URL = GEMINI_BASE + "/models/{model}:generateContent"
GEMINI_STREAM_URL = GEMINI_BASE + "/models/{model}:streamGenerateContent?alt=sse"
GEMINI_MODELS_URL = GEMINI_BASE + "/models?pageSize=1000"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

MAX_INPUT_CHARS = 2000        # explain_simply: limit what is sent
MAX_CHAT_CHARS = 8000         # one chat message
MAX_FILE_TEXT = 60000         # text taken from one document
MAX_OUTPUT_TOKENS = 600       # explain_simply answer length
CHAT_OUTPUT_TOKENS = 2000
QUIZ_OUTPUT_TOKENS = 4000
GEMINI_OUTPUT_TOKENS = 1500   # Gemini models may "think" first, and that counts toward this limit
GEMINI_CHAT_TOKENS = 6000
MAX_REQUESTS_PER_SESSION = 150
TIMEOUT_SECONDS = 60

NO_KEY_MESSAGE = ("No AI key found on this computer. Open Settings > AI connection and paste a key "
                  "(Gemini has a free option), or set GEMINI_API_KEY / ANTHROPIC_API_KEY and restart Nova.")

SYSTEM_PROMPT = (  # the short one-shot helper used by Simple Terms
    "You are Nova's study helper for a beginner student. Explain the term or question in simple everyday "
    "language, using this format: 1) Simple meaning in one or two sentences, 2) A real-life comparison, "
    "3) A short example (use code only if the topic is programming), 4) A common mistake or confusion. "
    "Keep the whole answer under 200 words. Be honest: if you are unsure, say so, and never invent facts, "
    "quotes or sources. You are a study aid, not a replacement for the teacher or textbook, so end with one "
    "short reminder to double-check important details. If the student pastes homework or a quiz question, "
    "help them understand how to think about it instead of only giving the final answer."
)

CHAT_SYSTEM = """You are Nova, a calm, sharp study tutor inside a student's study app.

How you answer:
- Lead with the answer or the key idea in the first sentence, then explain. No filler, no "Great question!".
- Match the student's level. If they seem like a beginner, use plain words and one everyday comparison; if they use advanced vocabulary, be precise and brief.
- Reply in the language the student writes in (English, Filipino, Taglish are all fine).
- Format with light Markdown: short paragraphs, bullet lists for sets of facts, numbered steps for procedures, `code` and fenced blocks for code, a table only when comparing things. Write maths in plain text (3x + 2 = 11, so x = 3), not LaTeX.
- For maths, science and code, show the reasoning step by step and check the result before stating it.
- If the student seems to be doing graded homework, coach: explain the method and give a hint or a similar example first, then offer to check their attempt, instead of only handing over the final answer.
- Be honest. If you are not sure, say so. Never invent facts, quotes, page numbers or sources.
- When a file or image is attached, work from what is actually in it. Point to where things come from (page, slide, section or "the diagram") and say so when something is unreadable or missing.
- Keep answers as short as the question allows. Offer one useful next step at the end only when it truly helps (for example "Want a 5-question quiz on this?")."""

MODES = {
    "chat": "",
    "explain": ("\n\nMode: EXPLAIN SIMPLY. Use this shape: **In one line**, **Think of it like**, **Example**, "
                "**Common mistake**. Under 200 words unless the student asks for more."),
    "summarize": ("\n\nMode: SUMMARIZE. Work only from the attached material or pasted text. Use this shape: "
                  "**TL;DR** (2 sentences), **Key points** (5-8 bullets, most important first), "
                  "**Terms to know** (term: short meaning), **Check yourself** (3 short questions, no answers). "
                  "If the material is long, keep the structure and stay brief."),
    "steps": ("\n\nMode: STEP BY STEP. Break the problem into numbered steps. After each step say why it works. "
              "End with a one-line check of the final answer."),
}

QUIZ_SYSTEM = """You write multiple-choice study quizzes from the material you are given.
Return ONLY a JSON array, with no prose and no code fences. Each item has exactly these keys:
  "question": string,
  "choices": array of exactly 4 short strings,
  "correct": integer 1-4 (position of the right choice),
  "explanation": one or two sentences saying why the answer is right.
Rules: base every question on the material (never on outside trivia); test understanding, not word-matching;
make the wrong choices plausible but clearly wrong; never use "all of the above" or "none of the above";
make all four choices similar in length; cover different parts of the material; do not repeat questions;
write in the same language as the material."""

_saved_keys = {}   # keys saved from Settings; the server loads them at start (tests never do)
_discovered = {}   # provider -> a model that worked when the default was missing
_requests_made = 0


class AIError(Exception):
    """A problem with the AI request. The message is written to be shown to the student."""


# ---- keys, provider, model --------------------------------------------------------------------

def _keys_file():
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "Nova" / "ai_keys.json"


def load_saved_keys():
    try:
        data = json.loads(_keys_file().read_text(encoding="utf-8"))
        _saved_keys.update({k: v for k, v in data.items() if k in PROVIDERS and isinstance(v, str)})
    except (OSError, ValueError):
        pass


def save_key(provider, key):
    """Save (or, with an empty key, remove) a key for this computer only."""
    if provider not in PROVIDERS:
        raise AIError("Choose Gemini or Claude.")
    key = (key or "").strip()
    if key and not re.fullmatch(r"[A-Za-z0-9_\-\.]{16,300}", key):
        raise AIError("That does not look like an API key. Copy it again without spaces.")
    if key:
        _saved_keys[provider] = key
    else:
        _saved_keys.pop(provider, None)
    path = _keys_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_saved_keys), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _key(provider):
    return os.environ.get(PROVIDERS[provider]["key_variable"], "").strip() or _saved_keys.get(provider, "")


def active_provider():
    """The provider Nova will use, or None if no key is set."""
    choice = os.environ.get("NOVA_AI_PROVIDER", "").strip().lower()
    if choice in PROVIDERS and _key(choice):
        return choice
    return next((name for name in PROVIDERS if _key(name)), None)


def is_configured():
    return active_provider() is not None


def _model(provider):
    model = os.environ.get("NOVA_AI_MODEL", "").strip() or _discovered.get(provider) or PROVIDERS[provider]["default_model"]
    return model.removeprefix("models/")  # Google's model list shows names as models/<name>


def status():
    provider = active_provider()
    return {"configured": provider is not None, "provider": provider, "model": _model(provider) if provider else "",
            "saved": sorted(_saved_keys), "disclosure": disclosure()}


def disclosure():
    """What the student should know before their text or files are sent."""
    provider = active_provider()
    if provider == "gemini":
        return ("Nova sends your messages and attached files to Google's Gemini service over the internet. On Google's "
                "free plan, Google may use what you send to improve its products, so do not share personal "
                "information or private schoolwork. Continue?")
    if provider == "anthropic":
        return ("Nova sends your messages and attached files to Anthropic's Claude service over the internet. "
                "Do not share personal information. Continue?")
    return "Nova sends your messages and attached files to an AI service over the internet. Continue?"


# ---- errors -----------------------------------------------------------------------------------

def _http_message(error):
    code = error.code
    if code in (401, 403):
        return "The AI service rejected the key. Check that it is correct and active."
    if code == 404:
        return "The AI model was not found. Set NOVA_AI_MODEL to a model your key can use."
    if code == 413:
        return "That file is too large for the AI service. Try a smaller file or fewer pages."
    if code == 429:
        return "Too many requests or a usage limit was reached. Wait a minute and try again."
    if code >= 500:
        return "The AI service is busy or having problems. Try again soon."
    try:
        detail = json.loads(error.read().decode("utf-8"))["error"]["message"]
        return f"The AI service could not process the request: {detail[:200]}"
    except (ValueError, KeyError, TypeError, OSError):
        return f"The AI service returned an error (code {code})."


def _guard_session():
    global _requests_made
    if _requests_made >= MAX_REQUESTS_PER_SESSION:
        raise AIError("You have reached this session's limit of AI requests. Restart Nova to ask more.")
    provider = active_provider()
    if provider is None:
        raise AIError(NO_KEY_MESSAGE)
    _requests_made += 1
    return provider


# ---- building requests ------------------------------------------------------------------------
# A "turn" is {"role": "user" | "assistant", "text": str, "attachments": [attachment, ...]}.
# An attachment is {"kind": "image" | "pdf" | "text", "mime": str, "data": base64 or None, "text": str or None, "name": str}.

def _anthropic_content(turn):
    attachments = turn.get("attachments") or []
    if not attachments:
        return turn["text"]
    blocks = []
    for item in attachments:
        if item["kind"] == "image":
            blocks.append({"type": "image", "source": {"type": "base64", "media_type": item["mime"], "data": item["data"]}})
        elif item["kind"] == "pdf":
            blocks.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": item["data"]}})
        else:
            blocks.append({"type": "text", "text": f"[Attached file: {item['name']}]\n{item['text']}"})
    blocks.append({"type": "text", "text": turn["text"] or "Please look at the attached file."})
    return blocks


def _gemini_parts(turn):
    parts = []
    for item in turn.get("attachments") or []:
        if item["kind"] in ("image", "pdf"):
            parts.append({"inline_data": {"mime_type": item["mime"], "data": item["data"]}})
        else:
            parts.append({"text": f"[Attached file: {item['name']}]\n{item['text']}"})
    parts.append({"text": turn["text"] or "Please look at the attached file."})
    return parts


def _build_request(provider, key, turns, system, max_tokens, stream=False, json_mode=False, model=None):
    model = (model or _model(provider)).removeprefix("models/")
    if provider == "gemini":
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "model" if t["role"] == "assistant" else "user", "parts": _gemini_parts(t)} for t in turns],
                "generationConfig": {"maxOutputTokens": max_tokens}}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        template = GEMINI_STREAM_URL if stream else GEMINI_URL
        url = template.format(model=urllib.parse.quote(model, safe=""))
        headers = {"x-goog-api-key": key, "content-type": "application/json"}
    else:
        body = {"model": model, "max_tokens": max_tokens, "system": system,
                "messages": [{"role": t["role"], "content": _anthropic_content(t)} for t in turns]}
        if stream:
            body["stream"] = True
        url = ANTHROPIC_URL
        headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
    return urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST", headers=headers)


def _extract_answer(provider, data):
    if provider == "gemini":
        candidates = data.get("candidates") or [{}]
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "".join(part.get("text", "") for part in parts if not part.get("thought")).strip()
    return "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text").strip()


def _discover_gemini_model(key, opener, failed):
    """The default model can be retired. Ask Google which models this key can use and pick the newest Flash."""
    request = urllib.request.Request(GEMINI_MODELS_URL, headers={"x-goog-api-key": key})
    try:
        with opener(request, timeout=TIMEOUT_SECONDS) as response:
            models = json.loads(response.read().decode("utf-8")).get("models", [])
    except (urllib.error.URLError, OSError, ValueError):
        return None
    best = []
    for item in models:
        name = item.get("name", "").removeprefix("models/")
        match = re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-flash", name)
        if match and "generateContent" in item.get("supportedGenerationMethods", []) and name != failed:
            best.append((float(match.group(1)), name))
    return max(best)[1] if best else None


def _open(provider, key, turns, system, max_tokens, opener, stream=False, json_mode=False):
    """Open the connection. If Gemini says the default model does not exist, find one that does and retry once."""
    request = _build_request(provider, key, turns, system, max_tokens, stream, json_mode)
    try:
        return opener(request, timeout=TIMEOUT_SECONDS)
    except urllib.error.HTTPError as error:
        explicit = bool(os.environ.get("NOVA_AI_MODEL", "").strip())
        if not (error.code == 404 and provider == "gemini" and not explicit):
            raise
        replacement = _discover_gemini_model(key, opener, _model(provider))
        if not replacement:
            raise
        _discovered[provider] = replacement
        retry = _build_request(provider, key, turns, system, max_tokens, stream, json_mode, model=replacement)
        return opener(retry, timeout=TIMEOUT_SECONDS)


def _ask(turns, system, max_tokens, opener, json_mode=False):
    provider = _guard_session()
    try:
        with _open(provider, _key(provider), turns, system, max_tokens, opener, json_mode=json_mode) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise AIError(_http_message(error)) from None
    except OSError:
        raise AIError("Could not reach the AI service. Check your internet connection and try again.") from None
    except ValueError:
        raise AIError("The AI service sent a reply Nova could not read. Please try again.") from None
    answer = _extract_answer(provider, data)
    if not answer:
        raise AIError("The AI service returned no answer. It may have been blocked or cut off. Try rephrasing.")
    return answer


# ---- public functions -------------------------------------------------------------------------

def explain_simply(text, opener=urllib.request.urlopen):
    """Return a beginner-friendly explanation of `text`. `opener` can be replaced in tests."""
    text = text.strip()
    if not text:
        raise AIError("Type a term or a question first.")
    if len(text) > MAX_INPUT_CHARS:
        raise AIError(f"Please keep it under {MAX_INPUT_CHARS} characters.")
    max_tokens = GEMINI_OUTPUT_TOKENS if active_provider() == "gemini" else MAX_OUTPUT_TOKENS
    return _ask([{"role": "user", "text": text}], SYSTEM_PROMPT, max_tokens, opener)


def build_system(mode="chat", context=""):
    system = CHAT_SYSTEM + MODES.get(mode, "")
    if context:
        system += f"\n\nAbout this student (use only if relevant, never recite it): {context}"
    return system


def _check_turns(turns):
    if not turns or turns[-1]["role"] != "user":
        raise AIError("Type a message first.")
    last = turns[-1]
    if not last["text"].strip() and not last.get("attachments"):
        raise AIError("Type a message or attach a file first.")
    if len(last["text"]) > MAX_CHAT_CHARS:
        raise AIError(f"Please keep one message under {MAX_CHAT_CHARS} characters.")


def chat(turns, mode="chat", context="", opener=urllib.request.urlopen):
    """One full answer (no streaming)."""
    _check_turns(turns)
    tokens = GEMINI_CHAT_TOKENS if active_provider() == "gemini" else CHAT_OUTPUT_TOKENS
    return _ask(turns, build_system(mode, context), tokens, opener)


def stream_chat(turns, mode="chat", context="", opener=urllib.request.urlopen):
    """Yield the answer in small pieces as the provider writes it."""
    _check_turns(turns)
    provider = _guard_session()
    tokens = GEMINI_CHAT_TOKENS if provider == "gemini" else CHAT_OUTPUT_TOKENS
    try:
        response = _open(provider, _key(provider), turns, build_system(mode, context), tokens, opener, stream=True)
        got_text = False
        with response:
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if provider == "gemini":
                    piece = _extract_answer("gemini", event)
                    if not piece and (event.get("promptFeedback") or {}).get("blockReason"):
                        raise AIError("The AI service blocked that request. Try rephrasing it.")
                else:
                    if event.get("type") == "error":
                        raise AIError("The AI service reported a problem. Please try again.")
                    piece = (event.get("delta") or {}).get("text", "") if event.get("type") == "content_block_delta" else ""
                if piece:
                    got_text = True
                    yield piece
        if not got_text:
            raise AIError("The AI service returned no answer. It may have been blocked or cut off. Try rephrasing.")
    except urllib.error.HTTPError as error:
        raise AIError(_http_message(error)) from None
    except OSError:
        raise AIError("Could not reach the AI service. Check your internet connection and try again.") from None


def _parse_json_list(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    starts = [i for i in (text.find("["), text.find("{")) if i >= 0]
    if not starts:
        raise ValueError("no json")
    value, _ = json.JSONDecoder().raw_decode(text[min(starts):])
    if isinstance(value, dict):
        value = value.get("questions") or next((v for v in value.values() if isinstance(v, list)), None)
    if not isinstance(value, list):
        raise ValueError("not a list")
    return value


def clean_questions(raw):
    """Keep only well-formed questions, and shuffle the choices so the right answer is not always in one place."""
    questions = []
    for item in raw:
        try:
            text = " ".join(str(item["question"]).split())
            choices = [" ".join(str(c).split()) for c in item["choices"]]
            correct = int(item["correct"])
        except (KeyError, TypeError, ValueError):
            continue
        if not text or len(choices) != 4 or not all(choices) or len({c.lower() for c in choices}) < 4 or correct not in (1, 2, 3, 4):
            continue
        right = choices[correct - 1]
        random.shuffle(choices)
        questions.append({"question": text, "choices": choices, "correct": choices.index(right) + 1,
                          "explanation": " ".join(str(item.get("explanation", "")).split())})
    return questions


def generate_quiz(turn, count=8, difficulty="mixed", opener=urllib.request.urlopen):
    """Write `count` multiple-choice questions from the material in `turn` (text and/or attachments)."""
    count = max(3, min(15, int(count)))
    ask = (f"Write {count} multiple-choice questions ({difficulty} difficulty) from the material above/attached. "
           f"{turn.get('text', '').strip()}").strip()
    turns = [{"role": "user", "text": ask, "attachments": turn.get("attachments") or []}]
    tokens = 8000 if active_provider() == "gemini" else QUIZ_OUTPUT_TOKENS
    for _ in range(2):  # one retry: models occasionally wrap or break the JSON
        answer = _ask(turns, QUIZ_SYSTEM, tokens, opener, json_mode=True)
        try:
            questions = clean_questions(_parse_json_list(answer))
        except ValueError:
            questions = []
        if len(questions) >= min(3, count):
            return questions[:count]
    raise AIError("Nova could not turn that into a quiz. Try a file with more readable text, or a smaller one.")
