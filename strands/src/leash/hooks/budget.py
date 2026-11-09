"""Level 5: budgets that tell the truth.

CostBudgetHook: prices this run's real token usage before every tool call and
cancels tools once the budget is spent (the output tool always gets through).
Pass a SharedBudget to make several agents working on the same job draw from
one pot: "budget per agent is a lie when you run 6 agents at once".

PreSpendGuardHook: refuses an oversized model call BEFORE paying for it.
"""

import logging
import threading
from typing import Any

from strands.hooks import (
    AfterInvocationEvent,
    BeforeInvocationEvent,
    BeforeModelCallEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

from leash.common.pricing import cost_usd
from leash.common.state import hook_state

log = logging.getLogger("leash.hooks")

OVER_BUDGET = "Budget reached. DO NOT call any more tools. Produce your final answer now with what you have."


class SharedBudget:
    """One pot of money for many agents running at once. Thread-safe."""

    def __init__(self, max_usd: float):
        self.max_usd, self.spent_usd = max_usd, 0.0
        self._lock = threading.Lock()

    def charge(self, usd: float) -> None:
        with self._lock:
            self.spent_usd += usd


class CostBudgetHook(HookProvider):
    def __init__(self, max_usd: float = 0.06, output_tool: str = "Briefing", shared: SharedBudget | None = None):
        self.max_usd, self.output_tool, self.shared = max_usd, output_tool, shared

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self.baseline)
        registry.add_callback(BeforeToolCallEvent, self.check)
        registry.add_callback(AfterInvocationEvent, self.settle)

    def baseline(self, event: BeforeInvocationEvent) -> None:
        usage = event.agent.event_loop_metrics.accumulated_usage  # lifetime totals: remember the start
        hook_state(event, "budget").update(start_in=usage["inputTokens"], start_out=usage["outputTokens"])

    def run_cost(self, event: Any) -> float:
        usage = event.agent.event_loop_metrics.accumulated_usage
        state = hook_state(event, "budget", start_in=0, start_out=0)
        return cost_usd(usage["inputTokens"] - state["start_in"], usage["outputTokens"] - state["start_out"])

    def check(self, event: BeforeToolCallEvent) -> None:
        if event.tool_use["name"] == self.output_tool:
            return
        spent = self.run_cost(event)
        over_run = spent >= self.max_usd
        over_shared = self.shared is not None and self.shared.spent_usd + spent >= self.shared.max_usd
        if over_run or over_shared:
            log.warning("budget: $%.4f spent, cancelled %s", spent, event.tool_use["name"])
            event.cancel_tool = OVER_BUDGET

    def settle(self, event: AfterInvocationEvent) -> None:
        spent = self.run_cost(event)
        hook_state(event, "budget")["spent_usd"] = spent
        if self.shared is not None:
            self.shared.charge(spent)


class PreSpendGuardHook(HookProvider):
    def __init__(self, max_input_tokens: int = 50_000):
        self.max_input_tokens = max_input_tokens

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeModelCallEvent, self.check)

    def check(self, event: BeforeModelCallEvent) -> None:
        projected = event.projected_input_tokens
        if projected is not None and projected > self.max_input_tokens:
            log.error("pre-spend: %d input tokens projected, model call refused", projected)
            event.cancel = f"Input too large ({projected} tokens > {self.max_input_tokens}); call refused before paying."
