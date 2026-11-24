"""The settings page: a small web app on 127.0.0.1, opened in the default browser.

Every API call needs the token from the page's address, sent back in a header.
Other websites open in the same browser can't read it, and a custom header can't
be sent cross-site without a CORS preflight, which this server never answers, so
they can't change config.toml (whose shortcut tiles run programs).
"""
import hashlib
import http.server
import json
import logging
import os
import pathlib
import secrets
import threading
import tomllib
from typing import Callable

from . import model

log = logging.getLogger(__name__)

STATIC = pathlib.Path(__file__).resolve().parent / "static"
# The board's fonts, so the preview looks like the board (present in a checkout of the repo).
FONTS = pathlib.Path(__file__).resolve().parents[3] / "firmware" / "main" / "fonts"
DISCOVERY = pathlib.Path.home() / ".deskhub" / "configurator.json"
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".ttf": "font/ttf", ".svg": "image/svg+xml"}
MAX_BODY = 1_000_000

# (cfg, changed sections) -> notes for the page, e.g. "restart the companion to ...".
ApplyFn = Callable[[dict, list[str]], list[str]]


def file_version(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class Configurator:
    def __init__(self, config_path: pathlib.Path, on_apply: ApplyFn | None = None, port: int = 0):
        self.config_path = pathlib.Path(config_path)
        self.on_apply = on_apply
        self.token = secrets.token_urlsafe(24)
        self._lock = threading.Lock()   # one save at a time
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/#t={self.token}"

    def start(self, advertise: bool = True):
        """Serve on a background thread. advertise: let `deskhub-config` find this one."""
        threading.Thread(target=self.httpd.serve_forever, name="configurator", daemon=True).start()
        if advertise:
            self.advertise()
        log.info("settings page on http://127.0.0.1:%d/", self.port)

    def advertise(self):
        try:
            DISCOVERY.parent.mkdir(parents=True, exist_ok=True)
            DISCOVERY.write_text(json.dumps({"port": self.port, "token": self.token, "pid": os.getpid(),
                                             "live": self.on_apply is not None}), encoding="utf-8")
        except OSError as e:
            log.warning("can't write %s: %s", DISCOVERY, e)

    def stop(self):
        self.httpd.shutdown()
        try:
            if json.loads(DISCOVERY.read_text(encoding="utf-8")).get("pid") == os.getpid():
                DISCOVERY.unlink()
        except (OSError, ValueError):
            pass

    # ---- API --------------------------------------------------------------

    def state(self) -> dict:
        text = self.config_path.read_text(encoding="utf-8")
        cfg = tomllib.loads(text)
        return {"meta": model.meta(), "state": model.read(cfg), "version": file_version(text),
                "live": self.on_apply is not None, "path": str(self.config_path)}

    def save(self, body: dict) -> tuple[int, dict]:
        sections = {k: v for k, v in (body.get("state") or {}).items() if k in model.SECTIONS}
        found = model.problems(sections)
        if found:
            return 400, {"problems": found}
        with self._lock:
            text = self.config_path.read_text(encoding="utf-8")
            if body.get("version") != file_version(text):
                return 409, {"error": "config.toml changed since this page loaded it. Reload to see the changes."}
            new_text, changed = model.apply(text, sections)
            if changed:
                tmp = self.config_path.with_suffix(".toml.tmp")
                tmp.write_text(new_text, encoding="utf-8")
                os.replace(tmp, self.config_path)
                log.info("settings page saved: %s", ", ".join(changed))
        notes: list[str] = []
        applied = False
        if changed and self.on_apply:
            try:
                notes = self.on_apply(tomllib.loads(new_text), changed) or []
                applied = True
            except Exception as e:
                log.warning("applying the new settings failed: %s", e)
                notes = [f"Saved, but sending it to the board failed ({e}). Restart the companion."]
        return 200, {"saved": changed, "applied": applied, "notes": notes, "version": file_version(new_text)}

    # ---- HTTP -------------------------------------------------------------

    def _handler(self):
        app = self

        class Handler(http.server.BaseHTTPRequestHandler):
            server_version = "deskhub"

            def log_message(self, fmt, *args):
                log.debug("http: " + fmt, *args)

            def _host_ok(self) -> bool:
                # A page on another site that points its name at 127.0.0.1 (DNS rebinding)
                # sends its own name here.
                return self.headers.get("Host", "") in (f"127.0.0.1:{app.port}", f"localhost:{app.port}")

            def _authorised(self) -> bool:
                return secrets.compare_digest(self.headers.get("X-Deskhub-Token", ""), app.token)

            def _send(self, code: int, body: bytes, ctype: str):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code: int, obj):
                self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

            def do_GET(self):
                if not self._host_ok():
                    return self._send(403, b"forbidden", "text/plain")
                path = self.path.split("?", 1)[0]
                if path.startswith("/api/"):
                    if not self._authorised():
                        return self._json(401, {"error": "This page's link is out of date. Open settings again."})
                    if path == "/api/state":
                        try:
                            return self._json(200, app.state())
                        except (OSError, tomllib.TOMLDecodeError) as e:
                            return self._json(500, {"error": f"can't read {app.config_path.name}: {e}"})
                    if path == "/api/ping":
                        return self._json(200, {"ok": True})
                    return self._json(404, {"error": "not found"})
                if path == "/":
                    path = "/index.html"
                if path.startswith("/fonts/"):
                    base, name = FONTS, path[len("/fonts/"):]
                else:
                    base, name = STATIC, path.lstrip("/")
                if "/" in name or "\\" in name or name.startswith("."):
                    return self._send(404, b"not found", "text/plain")
                f = base / name
                if not f.is_file():
                    return self._send(404, b"not found", "text/plain")
                self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))

            def do_POST(self):
                if not self._host_ok():
                    return self._send(403, b"forbidden", "text/plain")
                if not self._authorised():
                    return self._json(401, {"error": "This page's link is out of date. Open settings again."})
                if self.path != "/api/save":
                    return self._json(404, {"error": "not found"})
                n = int(self.headers.get("Content-Length") or 0)
                if n > MAX_BODY:
                    return self._json(413, {"error": "too big"})
                try:
                    body = json.loads(self.rfile.read(n) or b"{}")
                except ValueError:
                    return self._json(400, {"error": "bad request"})
                try:
                    code, out = app.save(body)
                except (OSError, tomllib.TOMLDecodeError) as e:
                    code, out = 500, {"error": f"can't save {app.config_path.name}: {e}"}
                self._json(code, out)

        return Handler
