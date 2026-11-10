"""Level 5: loop breakers.

ToolCallLimitHook: at most N calls per tool name per run; the cancel message
tells the model to use what it already has.

StructuredOutputRetryHook: if the output tool keeps failing validation, stop
after N failures instead of looping forever.
(Strands also has a native `limits={"structured_output_attempts": N}` per call.)
"""

import logging
from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from leash.common.state import hook_state

log = logging.getLogger("leash.hooks")

DEFAULT_LIMITS = {"search": 5, "fetch_page": 5, "check_link": 8, "read_notes": 2}


class ToolCallLimitHook(HookProvider):
    def __init__(self, limits: dict[str, int] | None = None):
        self.limits = dict(DEFAULT_LIMITS if limits is None else limits)

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.check)

    def check(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]
        if name not in self.limits:
            return
        counts = hook_state(event, "tool_limits", counts={})["counts"]
        counts[name] = counts.get(name, 0) + 1
        if counts[name] > self.limits[name]:
            log.warning("tool limit: %s called %d times (max %d)", name, counts[name], self.limits[name])
            event.cancel_tool = (
                f"You have called {name} {counts[name] - 1} times. DO NOT call {name} again. "
                "Use what you already have and produce your answer."
            )


class StructuredOutputRetryHook(HookProvider):
    def __init__(self, max_failures: int = 3, output_tool: str = "Briefing"):
        self.max_failures, self.output_tool = max_failures, output_tool

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self.count_failure)

    def count_failure(self, event: AfterToolCallEvent) -> None:
        if event.tool_use["name"] != self.output_tool or event.result.get("status") != "error":
            return
        state = hook_state(event, "output_retry", failures=0)
        state["failures"] += 1
        if state["failures"] >= self.max_failures:
            log.error("output tool failed %d times, stopping the run", state["failures"])
            event.agent.cancel(message="Rex could not produce a valid briefing.")
