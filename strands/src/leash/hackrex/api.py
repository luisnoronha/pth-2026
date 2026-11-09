"""The Hack Rex HTTP API, independent of the web server.

The local server (`server.py`) and the API Lambda (`backend/api/handler.py`)
both call `handle()`, so the routes, checks and JSON are the same everywhere.

  POST /api/attempt          {player, nickname, mode, text} -> 202 {id}   (Rex runs in the background)
  GET  /api/attempt/<id>     -> {status: running|done, answer, verdict}
  GET  /api/status           -> {open}
  GET  /api/scoreboard       -> the big-screen numbers (no unapproved text)
  GET  /api/admin/attempts   (X-Admin-Token) -> everything
  POST /api/admin/approve    (X-Admin-Token) {id, approved}
  POST /api/admin/killswitch (X-Admin-Token) {open}
  POST /api/admin/reset      (X-Admin-Token)
"""

import json
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from leash.hackrex.gate import Gate, Rejected
from leash.hackrex.store import public_view, scoreboard

MAX_BODY = 4096
ATTEMPT_PATH = re.compile(r"^/api/attempt/([0-9a-f]{12})$")


class RateLimiter:
    """Attempts per minute per player (in memory: per process, approximate on Lambda)."""

    def __init__(self, per_minute: int):
        self.per_minute, self._lock, self._seen = per_minute, threading.Lock(), defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            window = self._seen[key]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= self.per_minute:
                return False
            window.append(now)
            return True


@dataclass
class Api:
    gate: Gate
    admin_token: str
    limiter: RateLimiter
    start_run: Callable[[str], None]  # starts Rex for an attempt id, without waiting

    def handle(self, method: str, path: str, headers: dict[str, str], body: bytes) -> tuple[int, Any]:
        try:
            return self._route(method.upper(), path.rstrip("/") or "/", {k.lower(): v for k, v in headers.items()},
                               body)
        except Rejected as rejected:
            return rejected.code, {"error": str(rejected)}

    def _json(self, body: bytes) -> dict:
        if len(body) > MAX_BODY:
            raise Rejected("Request too large.", 413)
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError as error:
            raise Rejected("Invalid JSON.") from error
        if not isinstance(data, dict):
            raise Rejected("Invalid JSON.")
        return data

    def _route(self, method: str, path: str, headers: dict[str, str], body: bytes) -> tuple[int, Any]:
        if method == "OPTIONS":
            return 204, None
        if method == "GET" and path == "/api/status":
            return 200, {"open": self.gate.switch.is_open()}
        if method == "GET" and path == "/api/scoreboard":
            return 200, {**scoreboard(self.gate.store.all()), "open": self.gate.switch.is_open()}
        if method == "GET" and (match := ATTEMPT_PATH.match(path)):
            attempt = self.gate.store.get(match.group(1))
            return (200, public_view(attempt)) if attempt else (404, {"error": "not found"})
        if method == "POST" and path == "/api/attempt":
            data = self._json(body)
            player = str(data.get("player", ""))[:64]
            if not self.limiter.allow(player or "?"):
                raise Rejected(f"Slow down: {self.limiter.per_minute} attempts per minute.", 429)
            attempt_id = self.gate.submit(player, str(data.get("nickname", "")), str(data.get("mode", "")),
                                          str(data.get("text", "")))
            self.start_run(attempt_id)
            return 202, {"id": attempt_id}

        if path.startswith("/api/admin/"):
            if not secrets.compare_digest(headers.get("x-admin-token", ""), self.admin_token):
                return 401, {"error": "admin token required"}
            if method == "GET" and path == "/api/admin/attempts":
                return 200, {"attempts": self.gate.store.all(), "open": self.gate.switch.is_open()}
            if method == "POST" and path == "/api/admin/approve":
                data = self._json(body)
                ok = self.gate.store.set_approved(str(data.get("id")), bool(data.get("approved")))
                return (200 if ok else 404), {"ok": ok}
            if method == "POST" and path == "/api/admin/killswitch":
                self.gate.switch.set_open(bool(self._json(body).get("open")))
                return 200, {"open": self.gate.switch.is_open()}
            if method == "POST" and path == "/api/admin/reset":
                self.gate.store.clear()
                return 200, {"ok": True}
        return 404, {"error": "not found"}
