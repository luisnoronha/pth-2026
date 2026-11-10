"""Level 3: clean what untrusted tools bring back, before the model reads it.

Six regex families. Any line that matches is replaced by a visible marker, so
the model knows something was removed. A speed bump, not a wall: a paraphrased
injection walks straight past it (Demo 1, level 3b).
"""

import logging
import re
from typing import Any

from strands.hooks import AfterToolCallEvent, HookProvider, HookRegistry

from leash.common.state import hook_state

log = logging.getLogger("leash.hooks")

MARKER = "[REDACTED: possible prompt injection]"
UNTRUSTED_TOOLS = frozenset({"fetch_page", "search"})

PATTERNS = {
    "override": r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|prior|above|earlier)\b.{0,20}\b(instructions?|prompts?|rules)\b",
    "addressing_ai": r"\b(note|message|instructions?)\s+(for|to)\s+(the\s+)?(ai|llm)?\s*(assistants?|agents?|models?)\b|\byou are now\b|\bfrom now on,? you\b",
    "prompt_leak": r"\b(reveal|show|print|repeat|output)\b.{0,20}\b(system\s+)?prompt\b",
    "tool_command": r"\b(call|invoke|run|execute|use)\s+(the\s+)?`?[a-z]+_[a-z_]+`?",
    "exfil_url": r"https?://\S+[?&](token|key|secret|password|api_key)=",
    "zero_width": r"[​-‏⁠﻿]{3,}",
}
REGEX = re.compile("|".join(f"(?P<{name}>{p})" for name, p in PATTERNS.items()), re.IGNORECASE)


def sanitize(text: str) -> tuple[str, list[str]]:
    """Redact every line that matches a family. Returns (clean text, families hit)."""
    hits, lines = [], []
    for line in text.splitlines(keepends=True):
        match = REGEX.search(line)
        if match:
            hits.append(match.lastgroup)
            line = MARKER + ("\n" if line.endswith("\n") else "")
        lines.append(line)
    return "".join(lines), hits


class ContentSanitizationHook(HookProvider):
    def __init__(self, tools=UNTRUSTED_TOOLS):
        self.tools = frozenset(tools)

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self.clean)

    def clean(self, event: AfterToolCallEvent) -> None:
        if event.tool_use["name"] not in self.tools:
            return
        content, all_hits = [], []
        for block in event.result.get("content", []):
            if "text" in block:
                text, hits = sanitize(block["text"])
                block, all_hits = {**block, "text": text}, all_hits + hits
            content.append(block)
        if all_hits:
            hook_state(event, "sanitizer", hits=[])["hits"].extend(all_hits)
            log.warning("sanitizer redacted %d line(s) from %s: %s",
                        len(all_hits), event.tool_use["name"], sorted(set(all_hits)))
            event.result = {**event.result, "content": content}  # rewrite what the model will read
