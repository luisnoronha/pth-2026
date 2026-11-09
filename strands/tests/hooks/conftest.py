"""Fake events: every hook is unit-tested without a model, without AWS."""

from unittest.mock import MagicMock

import pytest
from strands.hooks import AfterToolCallEvent, BeforeInvocationEvent, BeforeToolCallEvent


@pytest.fixture
def agent():
    fake = MagicMock()
    fake.event_loop_metrics.accumulated_usage = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}
    return fake


@pytest.fixture
def state():
    return {}


@pytest.fixture
def before(agent, state):
    def make(name: str, **tool_input):
        tool_use = {"name": name, "toolUseId": f"id-{name}", "input": tool_input}
        return BeforeToolCallEvent(agent=agent, selected_tool=None, tool_use=tool_use, invocation_state=state)
    return make


@pytest.fixture
def after(agent, state):
    def make(name: str, text: str, status: str = "success", cancel_message: str | None = None, **tool_input):
        tool_use = {"name": name, "toolUseId": f"id-{name}", "input": tool_input}
        result = {"toolUseId": tool_use["toolUseId"], "status": status, "content": [{"text": text}]}
        return AfterToolCallEvent(agent=agent, selected_tool=None, tool_use=tool_use, invocation_state=state,
                                  result=result, cancel_message=cancel_message)
    return make


@pytest.fixture
def start(agent, state):
    def make(prompt: str = "Brief me on http://localhost:8000/acme-ir.html"):
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        return BeforeInvocationEvent(agent=agent, invocation_state=state, messages=messages)
    return make
