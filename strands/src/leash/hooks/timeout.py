"""Level 5: kill the run, keep the answer.

Graceful degradation after a wall-clock timeout:
1. The clock starts when the RUN starts (not when the agent is built: the "time bomb" bug).
2. Once time is up, every tool is cancelled EXCEPT the output tool, with a message
   written for the model: answer now.
3. A capped number of attempts after time-up; then a hard agent.cancel() as last resort.
"""

import logging
import time
from typing import Any

from strands.hooks import BeforeInvocationEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from leash.common.state import hook_state

log = logging.getLogger("leash.hooks")

TIME_UP = "Time is up. DO NOT call any more tools. Produce your final answer now with what you have."
GAVE_UP = "Rex ran out of time and could not produce a briefing."


class GracefulTimeoutHook(HookProvider):
    def __init__(self, timeout_s: float = 60.0, output_tool: str = "Briefing", max_attempts_after_timeout: int = 5):
        self.timeout_s, self.output_tool = timeout_s, output_tool
        self.max_attempts = max_attempts_after_timeout

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self.start_clock)
        registry.add_callback(BeforeToolCallEvent, self.check)

    def start_clock(self, event: BeforeInvocationEvent) -> None:
        state = hook_state(event, "timeout")
        state.update(started_at=time.monotonic(), attempts=0)

    def check(self, event: BeforeToolCallEvent) -> None:
        state = hook_state(event, "timeout", started_at=time.monotonic(), attempts=0)
        if time.monotonic() - state["started_at"] < self.timeout_s:
            return
        state["attempts"] += 1
        if state["attempts"] > self.max_attempts:
            log.error("timeout: %d attempts after time-up, hard cancel", state["attempts"] - 1)
            event.agent.cancel(message=GAVE_UP)  # last resort
            return
        if event.tool_use["name"] == self.output_tool:
            return  # let the answer through
        log.warning("timeout: cancelled %s, asking for the answer", event.tool_use["name"])
        event.cancel_tool = TIME_UP
