"""Level 2: the same guardrail pointed at TOOL OUTPUT, in shadow mode (the back door).

The Bedrock prompt-attack filter does not evaluate tool results on its own, so
we call ApplyGuardrail ourselves on what untrusted tools bring back. Still
shadow mode: it logs WOULD BLOCK and the injection still reaches the model.

Lesson from the real test (2026-11-09): sent the raw HTML page, the filter said
NONE; sent the same page as plain text (tags and styles removed, HTML comments
kept as text), it flagged the hidden note. Give the guardrail the words, not
the markup.
"""

import html
import logging
import re
from typing import Any

from strands.hooks import AfterToolCallEvent, HookProvider, HookRegistry

from leash.common.guardrail import bedrock_runtime_client, guardrail_config, shadow_check
from leash.common.state import hook_state

log = logging.getLogger("leash.hooks")

UNTRUSTED_TOOLS = frozenset({"fetch_page", "search"})
_STYLE_OR_SCRIPT = re.compile(r"<(style|script)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")


def as_plain_text(text: str) -> str:
    """What a reader (or a model) would take as words: no tags, no styles, comments kept as text."""
    text = _STYLE_OR_SCRIPT.sub(" ", text)
    text = _COMMENT.sub(lambda m: " " + m.group(1) + " ", text)
    text = html.unescape(_TAG.sub(" ", text))
    return re.sub(r"\s+", " ", text).strip()


class ToolOutputGuardrailHook(HookProvider):
    def __init__(self, tools=UNTRUSTED_TOOLS, guardrail_id: str | None = None, version: str | None = None,
                 client: Any = None):
        env_id, env_version = guardrail_config()
        self.tools = frozenset(tools)
        self.guardrail_id, self.version = guardrail_id or env_id, version or env_version
        self.client = client

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self.check_tool_output)

    def check_tool_output(self, event: AfterToolCallEvent) -> None:
        name = event.tool_use["name"]
        if name not in self.tools or event.cancel_message:
            return
        if not self.guardrail_id:
            log.warning("ToolOutputGuardrailHook: no guardrail configured (REX_GUARDRAIL_ID), skipped")
            return
        text = as_plain_text(" ".join(block.get("text", "") for block in event.result.get("content", [])))
        if text.strip():
            self.client = self.client or bedrock_runtime_client()
            verdict = shadow_check(self.client, self.guardrail_id, self.version, text, f"{name} output")
            hook_state(event, "guardrail", verdicts=[])["verdicts"].append(verdict)
