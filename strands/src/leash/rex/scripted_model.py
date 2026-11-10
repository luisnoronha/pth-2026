"""A fake Strands model that follows a script. No network, fully deterministic.

Two uses:
- tests: run the real agent loop (tools, hooks, structured output) without a real model;
- stage fallback: replay the hijack if the venue has no network.

A step is {"tool": name, "input": {...}} or {"text": "..."}, or a callable that
gets the conversation and returns a step. When the script runs out, the last
step repeats (handy for simulating a runaway loop).

Like a well-behaved model, it gives up and answers with `final` as soon as a
tool call comes back as an error (e.g. cancelled by a hook), or when Strands
forces the structured-output tool.
"""

import json
from collections.abc import AsyncIterable, Callable
from typing import Any

from strands.models.model import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent

Step = dict[str, Any] | Callable[[Messages], dict[str, Any]]


class ScriptedModel(Model):
    def __init__(self, steps: list[Step], final: dict[str, Any] | None = None, output_tool: str = "Briefing",
                 usage_per_call: tuple[int, int] = (1000, 200)):
        self.steps, self.final, self.output_tool = list(steps), final, output_tool
        self.usage_per_call = usage_per_call
        self.calls = 0
        self.config: dict[str, Any] = {"model_id": "scripted"}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError("ScriptedModel answers through the structured-output tool")

    def _next_step(self, messages: Messages, tool_choice: dict | None) -> dict[str, Any]:
        forced = (tool_choice or {}).get("tool", {}).get("name") == self.output_tool
        if self.final is not None and (forced or _last_tool_failed(messages)):
            return {"tool": self.output_tool, "input": self.final}
        step = self.steps[min(self.calls, len(self.steps) - 1)]
        return step(messages) if callable(step) else step

    async def stream(self, messages: Messages, tool_specs=None, system_prompt=None, *,
                     tool_choice=None, **kwargs: Any) -> AsyncIterable[StreamEvent]:
        step = self._next_step(messages, tool_choice)
        self.calls += 1
        yield {"messageStart": {"role": "assistant"}}
        if "tool" in step:
            tool_use_id = f"scripted-{self.calls}"
            yield {"contentBlockStart": {"start": {"toolUse": {"name": step["tool"], "toolUseId": tool_use_id}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(step["input"])}}}}
            stop_reason = "tool_use"
        else:
            yield {"contentBlockDelta": {"delta": {"text": step["text"]}}}
            stop_reason = "end_turn"
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": stop_reason}}
        tokens_in, tokens_out = self.usage_per_call
        yield {"metadata": {"usage": {"inputTokens": tokens_in, "outputTokens": tokens_out,
                                      "totalTokens": tokens_in + tokens_out}, "metrics": {"latencyMs": 1}}}


def _last_tool_failed(messages: Messages) -> bool:
    if not messages or messages[-1]["role"] != "user":
        return False
    results = [block["toolResult"] for block in messages[-1]["content"] if "toolResult" in block]
    return any(result.get("status") == "error" for result in results)


def last_tool_text(messages: Messages) -> str:
    """Text of the most recent tool result (for steps that react to what a tool returned)."""
    for message in reversed(messages):
        for block in message["content"]:
            if "toolResult" in block:
                return " ".join(c.get("text", "") for c in block["toolResult"]["content"])
    return ""
