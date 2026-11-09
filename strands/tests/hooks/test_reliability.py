from unittest.mock import MagicMock

from strands.hooks import BeforeModelCallEvent

from leash.hooks.budget import CostBudgetHook, PreSpendGuardHook, SharedBudget
from leash.hooks.loop_breakers import StructuredOutputRetryHook, ToolCallLimitHook
from leash.hooks.state_init import StateInitHook
from leash.hooks.timeout import TIME_UP, GracefulTimeoutHook
from leash.hooks.tracing import TracingHook


def test_state_init_wipes_stale_state(start, state):
    state["leash"] = {"budget": {"spent_usd": 99}}
    StateInitHook().reset(start())
    assert set(state["leash"]) == {"run"}


def test_timeout_clock_starts_with_the_run_not_the_agent(start, before):
    hook = GracefulTimeoutHook(timeout_s=60)
    hook.start_clock(start())
    hook.check(event := before("search", query="x"))
    assert event.cancel_tool is False


def test_timeout_cancels_tools_but_lets_the_answer_through(start, before, agent):
    hook = GracefulTimeoutHook(timeout_s=0, max_attempts_after_timeout=5)
    hook.start_clock(start())
    hook.check(search := before("search", query="x"))
    hook.check(answer := before("Briefing"))
    assert search.cancel_tool == TIME_UP
    assert answer.cancel_tool is False
    agent.cancel.assert_not_called()


def test_timeout_hard_cancels_after_the_cap(start, before, agent):
    hook = GracefulTimeoutHook(timeout_s=0, max_attempts_after_timeout=2)
    hook.start_clock(start())
    for _ in range(3):
        hook.check(before("Briefing"))
    agent.cancel.assert_called_once()


def test_budget_cancels_tools_once_spent_but_not_the_answer(start, before, agent):
    hook = CostBudgetHook(max_usd=0.01)
    hook.baseline(start())
    agent.event_loop_metrics.accumulated_usage = {"inputTokens": 10_000, "outputTokens": 1_000}  # ~$0.015
    hook.check(search := before("search", query="x"))
    hook.check(answer := before("Briefing"))
    assert "Budget reached" in search.cancel_tool
    assert answer.cancel_tool is False


def test_budget_only_counts_this_run(start, before, agent):
    agent.event_loop_metrics.accumulated_usage = {"inputTokens": 1_000_000, "outputTokens": 0}  # earlier runs
    hook = CostBudgetHook(max_usd=0.01)
    hook.baseline(start())
    hook.check(event := before("search", query="x"))
    assert event.cancel_tool is False


def test_shared_budget_is_one_pot_for_many_agents(start, before):
    pot = SharedBudget(max_usd=1.0)
    pot.charge(1.0)  # another agent already spent it all
    hook = CostBudgetHook(max_usd=10, shared=pot)
    hook.baseline(start())
    hook.check(event := before("search", query="x"))
    assert "Budget reached" in event.cancel_tool


def test_pre_spend_refuses_oversized_model_calls():
    event = BeforeModelCallEvent(agent=MagicMock(), projected_input_tokens=60_000)
    PreSpendGuardHook(max_input_tokens=50_000).check(event)
    assert "refused" in event.cancel


def test_tool_limit_per_tool_name(before):
    hook = ToolCallLimitHook({"search": 2})
    events = [before("search", query=str(i)) for i in range(3)]
    for event in events:
        hook.check(event)
    assert [bool(e.cancel_tool) for e in events] == [False, False, True]
    assert "DO NOT call search again" in events[2].cancel_tool


def test_output_retry_stops_after_n_failures(after, agent):
    hook = StructuredOutputRetryHook(max_failures=3)
    for _ in range(3):
        hook.count_failure(after("Briefing", "validation error", status="error"))
    agent.cancel.assert_called_once()


def test_tracing_records_cancelled_calls(before, after, state):
    hook = TracingHook()
    hook.start(before("check_link", url="http://evil"))
    hook.end(after("check_link", "Blocked", status="error", cancel_message="Blocked: evil", url="http://evil"))
    span = state["leash"]["trace"]["spans"][0]
    assert span["tool"] == "check_link" and span["status"] == "cancelled"
