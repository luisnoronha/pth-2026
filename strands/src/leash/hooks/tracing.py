"""Level 5: record what actually ran, including what the leash cancelled.

One span per tool call (name, duration, status, cancel reason) in
invocation_state["leash"]["trace"]["spans"]: the raw material for the Hack Rex
judge ("which layer stopped it?") and for observability.
"""

import logging
import time
from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from leash.common.state import hook_state

log = logging.getLogger("leash.hooks")


class TracingHook(HookProvider):
    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.start)
        registry.add_callback(AfterToolCallEvent, self.end)

    def start(self, event: BeforeToolCallEvent) -> None:
        state = hook_state(event, "trace", spans=[], open={})
        state["open"][event.tool_use["toolUseId"]] = time.perf_counter()

    def end(self, event: AfterToolCallEvent) -> None:
        state = hook_state(event, "trace", spans=[], open={})
        started = state["open"].pop(event.tool_use["toolUseId"], time.perf_counter())
        span = {
            "tool": event.tool_use["name"],
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "status": "cancelled" if event.cancel_message else event.result.get("status", "success"),
            "cancel_reason": event.cancel_message,
        }
        state["spans"].append(span)
        log.debug("span %s", span)
