"""Level 5: runs first and gives every run a clean slate.

Hooks keep per-run state in invocation_state["leash"][<hook name>]. If a caller
reuses the same invocation_state dict across runs, stale counters and clocks
would leak into the next run; this hook wipes them at the start of each run.
"""

import time
from typing import Any

from strands.hooks import BeforeInvocationEvent, HookProvider, HookRegistry

from leash.common.state import NAMESPACE


class StateInitHook(HookProvider):
    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self.reset)

    def reset(self, event: BeforeInvocationEvent) -> None:
        event.invocation_state[NAMESPACE] = {"run": {"started_at": time.monotonic()}}
