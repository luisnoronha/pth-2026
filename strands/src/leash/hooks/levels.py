"""Single source of truth: which hooks run at each leash level.

The CLI, the Rex Lambda and the tests all read this file. Levels are
cumulative: level N runs every hook whose level is <= N.

The list is in RUN ORDER, not in level order:
  1. state first, 2. cheap vetoes, 3. observe what actually runs,
  4. clean what came back, 5. expensive checks last.
"Before" callbacks run top to bottom; Strands runs "After" callbacks bottom to
top, so the tool-output guardrail sees the RAW tool output, before the sanitiser.

Every limit is configurable through environment variables.
"""

import os
from collections.abc import Callable

from strands.hooks import HookProvider

from leash.hooks.budget import CostBudgetHook, PreSpendGuardHook
from leash.hooks.egress import EgressAllowlistHook
from leash.hooks.loop_breakers import StructuredOutputRetryHook, ToolCallLimitHook
from leash.hooks.output_guard import OutputSecretGuardHook
from leash.hooks.sanitizer import ContentSanitizationHook
from leash.hooks.shadow_guardrail import ShadowGuardrailHook
from leash.hooks.state_init import StateInitHook
from leash.hooks.timeout import GracefulTimeoutHook
from leash.hooks.tool_output_guardrail import ToolOutputGuardrailHook
from leash.hooks.tracing import TracingHook
from leash.hooks.url_circuit_breaker import UrlCircuitBreakerHook

MAX_LEVEL = 5


DEFAULT_LIMITS = {"REX_TIMEOUT_S": 60, "REX_MAX_USD": 0.06, "REX_MAX_INPUT_TOKENS": 50_000}


def limit(name: str) -> float:
    """A run limit: the environment variable if set, else the default above."""
    return float(os.getenv(name, DEFAULT_LIMITS[name]))


# (level it joins at, factory) in run order.
HOOKS: list[tuple[int, Callable[[], HookProvider]]] = [
    (5, StateInitHook),                                                          # 1. state
    (5, lambda: GracefulTimeoutHook(timeout_s=limit("REX_TIMEOUT_S"))),       # 2. cheap vetoes
    (5, lambda: CostBudgetHook(max_usd=limit("REX_MAX_USD"))),
    (5, lambda: PreSpendGuardHook(max_input_tokens=int(limit("REX_MAX_INPUT_TOKENS")))),
    (4, EgressAllowlistHook),
    (4, UrlCircuitBreakerHook),
    (4, OutputSecretGuardHook),
    (5, ToolCallLimitHook),
    (5, StructuredOutputRetryHook),
    (5, TracingHook),                                                            # 3. observe
    (3, ContentSanitizationHook),                                                # 4. clean
    (2, ToolOutputGuardrailHook),                                                # 5. expensive, last
    (1, ShadowGuardrailHook),
]


def hooks_for(level: int) -> list[HookProvider]:
    """Fresh hook instances for a leash level."""
    if not 0 <= level <= MAX_LEVEL:
        raise ValueError(f"leash level must be 0-{MAX_LEVEL}, got {level}")
    return [factory() for joins_at, factory in HOOKS if joins_at <= level]
