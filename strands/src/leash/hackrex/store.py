"""Where attempts live, and the scoreboard built from them.

Two implementations, same methods: `AttemptStore` (memory, optional JSON file,
for the laptop) and `DynamoAttemptStore` (in `leash.hackrex.aws`, for AWS).

An attempt is one record: status "running" while Rex works, then "done" with
the answer and the judge's verdict.

Privacy: raw attack text is stored for the host's review, but the public
scoreboard only shows it once the host approves it.
"""

import json
import threading
from collections import Counter
from pathlib import Path
from typing import Any

from leash.hackrex.layers import LABELS, LAYERS

SNIPPET_CHARS = 140


class AttemptStore:
    def __init__(self, path: Path | None = None):
        self.path = path
        self._lock = threading.Lock()
        self._attempts: dict[str, dict[str, Any]] = {}
        if path and path.exists():
            self._attempts = {a["id"]: a for a in json.loads(path.read_text(encoding="utf-8"))}

    def _save(self) -> None:
        if self.path:
            self.path.write_text(json.dumps(list(self._attempts.values()), ensure_ascii=False, indent=1),
                                 encoding="utf-8")

    def add(self, attempt: dict[str, Any]) -> None:
        with self._lock:
            self._attempts[attempt["id"]] = dict(attempt)
            self._save()

    def get(self, attempt_id: str) -> dict[str, Any] | None:
        with self._lock:
            attempt = self._attempts.get(attempt_id)
            return dict(attempt) if attempt else None

    def complete(self, attempt_id: str, answer: Any, verdict: dict[str, Any]) -> None:
        with self._lock:
            self._attempts[attempt_id].update(status="done", answer=answer, verdict=verdict)
            self._save()

    def count(self) -> int:
        with self._lock:
            return len(self._attempts)

    def count_for(self, player: str) -> int:
        with self._lock:
            return sum(1 for a in self._attempts.values() if a["player"] == player)

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return sorted((dict(a) for a in self._attempts.values()), key=lambda a: a["ts"])

    def set_approved(self, attempt_id: str, approved: bool) -> bool:
        with self._lock:
            if attempt_id not in self._attempts:
                return False
            self._attempts[attempt_id]["approved"] = approved
            self._save()
            return True

    def clear(self) -> None:
        with self._lock:
            self._attempts = {}
            self._save()


def public_view(attempt: dict[str, Any]) -> dict[str, Any]:
    """What the attacker's own phone may see about its attempt (never anyone else's text)."""
    return {"id": attempt["id"], "status": attempt["status"],
            "answer": attempt.get("answer"), "verdict": attempt.get("verdict")}


def scoreboard(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """Everything the big screen shows. Never contains unapproved attack text."""
    done = [a for a in attempts if a.get("status") == "done"]
    funnel = Counter(a["verdict"]["stopped_by"] for a in done)
    winners = [{"nickname": a["nickname"] or "anonymous", "won": a["verdict"]["won"], "mode": a["mode"]}
               for a in done if a["verdict"]["won"]]
    fame = [{"nickname": a["nickname"] or "anonymous", "mode": a["mode"],
             "snippet": a["text"][:SNIPPET_CHARS] + ("…" if len(a["text"]) > SNIPPET_CHARS else ""),
             "stopped_by": a["verdict"]["stopped_by_label"]}
            for a in done if a.get("approved")]
    return {
        "attempts": len(attempts),
        "running": len(attempts) - len(done),
        "players": len({a["player"] for a in attempts}),
        "by_mode": dict(Counter(a["mode"] for a in attempts)),
        "funnel": [{"layer": layer, "label": LABELS[layer], "count": funnel.get(layer, 0)}
                   for layer in ["got_through", *LAYERS]],
        "winners": winners,
        "wall_of_fame": fame,
    }
