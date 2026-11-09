"""Records every tool call Rex TRIED, with its input, and whether the leash cancelled it.

Not a leash hook: it only watches (like the CLI's ConsoleHook). Register it after
the leash hooks, so "before" sees the leash's veto and "after" sees the raw result.
"""

from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry


class AttemptRecorderHook(HookProvider):
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._by_id: dict[str, dict[str, Any]] = {}

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.before)
        registry.add_callback(AfterToolCallEvent, self.after)

    def before(self, event: BeforeToolCallEvent) -> None:
        call = {"tool": event.tool_use["name"], "input": dict(event.tool_use.get("input") or {}),
                "cancelled": event.cancel_tool if isinstance(event.cancel_tool, str) else None,
                "status": "pending"}
        self.calls.append(call)
        self._by_id[event.tool_use["toolUseId"]] = call

    def after(self, event: AfterToolCallEvent) -> None:
        call = self._by_id.get(event.tool_use["toolUseId"])
        if call is None:
            return
        if event.cancel_message:
            call["cancelled"], call["status"] = event.cancel_message, "cancelled"
        else:
            call["status"] = event.result.get("status", "success")
