"""Nova's local web server. It listens only on this computer (127.0.0.1), serves the Nova screens, and answers the
screens' requests by calling api.py. Every request needs a secret token that only the Nova window knows, so no other
website or program on the computer can talk to it."""
import json
import mimetypes
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import api
from services import ai_service, file_service, profile_service
from services.study_service import ValidationError

WEB = Path(__file__).resolve().parent / "web"
MAX_BODY = 48 * 1024 * 1024
TOKEN = secrets.token_urlsafe(24)
PORTS = range(47615, 47630)
last_ping = {"time": None, "bye": None, "started": time.monotonic()}


def friendly(error):
    if isinstance(error, (ValidationError, ai_service.AIError, file_service.FileError)):
        return str(error)
    if isinstance(error, sqlite3.Error):
        return f"Nova could not read or save its data. ({error})"
    return "Something went wrong inside Nova. Please try again."


class Handler(BaseHTTPRequestHandler):
    server_version = "Nova"
    protocol_version = "HTTP/1.0"  # the connection closing marks the end of a streamed answer

    def log_message(self, *args):
        pass

    # -- safety ------------------------------------------------------------------
    def _host_ok(self):
        return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

    def _token_ok(self):
        given = self.headers.get("X-Nova-Token") or parse_qs(urlparse(self.path).query).get("t", [""])[0]
        return secrets.compare_digest(given, TOKEN)

    def _send(self, status, body, kind="application/json; charset=utf-8", extra=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload, status=200):
        self._send(status, json.dumps(payload, default=str))

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise file_service.FileError("That upload is too large.")
        return json.loads(self.rfile.read(length) or b"{}")

    # -- pages and files ---------------------------------------------------------
    def do_GET(self):
        if not self._host_ok():
            return self._send(403, "Forbidden", "text/plain")
        path = urlparse(self.path).path
        if path == "/api/avatar":
            if not self._token_ok() or not profile_service.avatar_path().exists():
                return self._send(404, "", "text/plain")
            return self._send(200, profile_service.avatar_path().read_bytes(), "image/png")
        if path in ("/", "/index.html"):
            page = (WEB / "index.html").read_text(encoding="utf-8").replace("__NOVA_TOKEN__", TOKEN)
            return self._send(200, page, "text/html; charset=utf-8",
                              {"Content-Security-Policy": "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"})
        target = (WEB / path.lstrip("/")).resolve()
        if WEB.resolve() not in target.parents or not target.is_file():
            return self._send(404, "Not found", "text/plain")
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send(200, target.read_bytes(), kind + ("; charset=utf-8" if kind.startswith("text/") or "javascript" in kind else ""))

    # -- requests from the screens -----------------------------------------------
    def do_POST(self):
        if not self._host_ok() or not self._token_ok():
            return self._json({"ok": False, "error": "Not allowed."}, 403)
        route = urlparse(self.path).path
        try:
            body = self._read_json()
            if route == "/api/ping":
                last_ping["time"], last_ping["bye"] = time.monotonic(), None
                return self._json({"ok": True})
            if route == "/api/bye":  # the window is closing (or reloading: a new ping cancels this)
                last_ping["bye"] = time.monotonic()
                return self._json({"ok": True})
            if route == "/api/call":
                function = api.CALLS.get(body.get("fn"))
                if function is None:
                    return self._json({"ok": False, "error": "Unknown action."}, 404)
                return self._json({"ok": True, "data": function(*body.get("args", []))})
            if route == "/api/quiz":
                data = api.make_quiz(body.get("thread_id"), body.get("text", ""), body.get("files", []),
                                     body.get("count", 8), body.get("difficulty", "mixed"))
                return self._json({"ok": True, "data": data})
            if route == "/api/chat":
                return self._chat(body)
            return self._json({"ok": False, "error": "Unknown action."}, 404)
        except (ValidationError, ai_service.AIError, file_service.FileError, sqlite3.Error, ValueError, TypeError) as error:
            self._json({"ok": False, "error": friendly(error)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:  # never leave the screen waiting
            self._json({"ok": False, "error": friendly(error)}, 500)

    def _line(self, payload):
        self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))
        self.wfile.flush()

    def _chat(self, body):
        """Stream the answer to the screen one line of JSON at a time: {t: thread|delta|error|done, ...}."""
        try:
            thread_id, turns = api.prepare_chat(body.get("thread_id"), body.get("text", ""), body.get("files", []))
        except (ValidationError, ai_service.AIError, file_service.FileError) as error:
            return self._json({"ok": False, "error": friendly(error)}, 400)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        answer = []
        try:
            self._line({"t": "thread", "id": thread_id})
            for piece in ai_service.stream_chat(turns, body.get("mode", "chat"), api.student_context()):
                answer.append(piece)
                self._line({"t": "delta", "text": piece})
            self._line({"t": "done"})
        except ai_service.AIError as error:
            try:
                self._line({"t": "error", "message": str(error)})
            except OSError:
                pass
        except (BrokenPipeError, ConnectionResetError):
            pass  # the student pressed Stop or closed the window; keep what was written so far
        finally:
            api.finish_chat(thread_id, "".join(answer))


def make_server():
    for port in PORTS:  # a steady port lets the window remember its own small settings
        try:
            return ThreadingHTTPServer(("127.0.0.1", port), Handler)
        except OSError:
            continue
    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


def idle_watch(stop, silent_seconds=180, bye_seconds=5, first_seconds=90):
    """Quit when the window is gone: it said goodbye, or its pings stopped, or it never opened at all."""
    while not stop.wait(1):
        now, seen, bye = time.monotonic(), last_ping["time"], last_ping["bye"]
        if bye is not None and now - bye > bye_seconds:
            stop.set()
        elif seen is None and now - last_ping["started"] > first_seconds:
            stop.set()
        elif seen is not None and now - seen > silent_seconds:
            stop.set()


def start(server):
    threading.Thread(target=server.serve_forever, daemon=True).start()
