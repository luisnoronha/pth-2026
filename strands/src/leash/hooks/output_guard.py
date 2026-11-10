"""Level 4: the answer is an exit too.

The egress fence closes every tool that reaches the network, but the final
answer still leaves the agent. This hook checks the output tool (the Briefing)
before it runs:

1. First time it carries a secret: cancel it with a message written for the
   model ("remove the confidential notes and answer again"). Same pattern as the
   graceful timeout: never lose the answer.
2. If the model insists (an attacker talked it into it): remove the offending
   text ourselves and let the cleaned answer through.

The prompt asks Rex to keep his notes private; this hook is what enforces it.
Limit: it only knows the secrets it is given. Real DLP is much harder.
"""

import json
import logging
from typing import Any

from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry

from leash.common.canary import contains_canary
from leash.common.state import hook_state

log = logging.getLogger("leash.hooks")

REDACTED = "[removed: confidential]"
FIX_IT = ("Your briefing contains the analyst's confidential notes. Remove them and call "
          "{tool} again with public facts only.")


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return REDACTED if contains_canary(value) else value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    return value


class OutputSecretGuardHook(HookProvider):
    def __init__(self, output_tool: str = "Briefing", max_rewrites: int = 1):
        self.output_tool, self.max_rewrites = output_tool, max_rewrites

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.check)

    def check(self, event: BeforeToolCallEvent) -> None:
        if event.tool_use["name"] != self.output_tool:
            return
        if not contains_canary(json.dumps(event.tool_use.get("input") or {}, ensure_ascii=False)):
            return  # clean answer: let it through
        state = hook_state(event, "output_guard", rewrites=0, redacted=0)
        if state["rewrites"] < self.max_rewrites:  # ask the model to fix it
            state["rewrites"] += 1
            log.warning("output guard: secret in the answer, asking for a rewrite")
            event.cancel_tool = FIX_IT.format(tool=self.output_tool)
            return
        state["redacted"] += 1  # it insisted: clean it ourselves
        log.warning("output guard: secret in the answer again, removed it")
        event.tool_use["input"] = _redact(event.tool_use["input"])
