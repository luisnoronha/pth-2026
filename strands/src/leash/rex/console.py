"""Prints Rex's tool calls in colour, so the audience can follow the hijack.

Not a leash hook: it only watches. Lives with the CLI, not in leash.hooks.
"""

import json

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from leash.common.canary import contains_canary

RESET, DIM, BOLD = "\033[0m", "\033[2m", "\033[1m"
CYAN, YELLOW, RED, GREEN = "\033[36m", "\033[33m", "\033[31m", "\033[32m"
TOOL_COLOURS = {"fetch_page": CYAN, "read_notes": YELLOW, "check_link": RED}


def _short(value: object, limit: int = 110) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class ConsoleHook(HookProvider):
    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeToolCallEvent, self.before)
        registry.add_callback(AfterToolCallEvent, self.after)

    def before(self, event: BeforeToolCallEvent) -> None:
        name, args = event.tool_use["name"], event.tool_use["input"]
        colour = TOOL_COLOURS.get(name, GREEN)
        leak = f"  {BOLD}{RED}<- carries the secret!{RESET}" if contains_canary(json.dumps(args)) else ""
        print(f"{colour}{BOLD}-> {name}{RESET}{colour}({_short(args)}){RESET}{leak}")

    def after(self, event: AfterToolCallEvent) -> None:
        if event.cancel_message:
            print(f"   {RED}x cancelled: {_short(event.cancel_message)}{RESET}")
            return
        texts = [block.get("text", "") for block in event.result.get("content", [])]
        print(f"   {DIM}<- {_short(' '.join(texts))}{RESET}")
