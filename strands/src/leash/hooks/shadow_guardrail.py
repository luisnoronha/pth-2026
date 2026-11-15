"""Level 1: Bedrock guardrail on the USER message, in shadow mode (the front door).

Evaluates every new user message with ApplyGuardrail and logs WOULD BLOCK, but
never blocks. Verdicts are kept so you can measure false positives before you
enforce. On the Acme attack it says "NONE": the user's prompt was innocent.
"""

import logging
from typing import Any

from strands.hooks import BeforeInvocationEvent, HookProvider, HookRegistry

from leash.common.guardrail import bedrock_runtime_client, guardrail_config, shadow_check
from leash.common.state import hook_state

log = logging.getLogger("leash.hooks")


class ShadowGuardrailHook(HookProvider):
    def __init__(self, guardrail_id: str | None = None, version: str | None = None, client: Any = None):
        env_id, env_version = guardrail_config()
        self.guardrail_id, self.version = guardrail_id or env_id, version or env_version
        self.client = client

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self.check_user_message)

    def check_user_message(self, event: BeforeInvocationEvent) -> None:
        if not self.guardrail_id:
            log.warning("ShadowGuardrailHook: no guardrail configured (REX_GUARDRAIL_ID), skipped")
            return
        text = " ".join(
            block["text"] for message in event.messages or [] if message["role"] == "user"
            for block in message["content"] if "text" in block
        )
        if text:
            self.client = self.client or bedrock_runtime_client()
            verdict = shadow_check(self.client, self.guardrail_id, self.version, text, "user message")
            hook_state(event, "guardrail", verdicts=[])["verdicts"].append(verdict)
