"""Level 2: the same guardrail pointed at TOOL OUTPUT, in shadow mode (the back door).

The Bedrock prompt-attack filter does not evaluate tool results on its own, so
we call ApplyGuardrail ourselves on what untrusted tools bring back. Still
shadow mode: it logs WOULD BLOCK and the injection still reaches the model.
"""

import logging
from typing import Any

from strands.hooks import AfterToolCallEvent, HookProvider, HookRegistry

from leash.common.guardrail import bedrock_runtime_client, guardrail_config, shadow_check
from leash.common.state import hook_state

log = logging.getLogger("leash.hooks")

UNTRUSTED_TOOLS = frozenset({"fetch_page", "search"})


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
        text = " ".join(block.get("text", "") for block in event.result.get("content", []))
        if text.strip():
            self.client = self.client or bedrock_runtime_client()
            verdict = shadow_check(self.client, self.guardrail_id, self.version, text, f"{name} output")
            hook_state(event, "guardrail", verdicts=[])["verdicts"].append(verdict)
