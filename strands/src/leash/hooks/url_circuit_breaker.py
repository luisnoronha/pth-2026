"""Level 4: your agent will invent URLs. Confidently.

A circuit breaker for hallucinated tool inputs:
1. Remember every URL the agent actually SAW (in the user's message or in tool results).
2. Count failed calls to URLs it never saw.
3. After `max_failures`, block any unknown URL for the rest of the run.
"""

import logging
import re
from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeInvocationEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from leash.common.state import hook_state

log = logging.getLogger("leash.hooks")

URL_TOOLS = frozenset({"fetch_page", "check_link"})
URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")
FAILURE_MARKERS = ("Could not fetch", "Link is dead", "HTTP 4", "HTTP 5")


def _texts(blocks: list[dict]) -> str:
    return " ".join(block.get("text", "") for block in blocks)


class UrlCircuitBreakerHook(HookProvider):
    def __init__(self, max_failures: int = 3, tools=URL_TOOLS):
        self.max_failures, self.tools = max_failures, frozenset(tools)

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self.remember_prompt_urls)
        registry.add_callback(BeforeToolCallEvent, self.check)
        registry.add_callback(AfterToolCallEvent, self.learn)

    def _state(self, event: Any) -> dict[str, Any]:
        return hook_state(event, "url_breaker", seen=set(), failures=0)

    def remember_prompt_urls(self, event: BeforeInvocationEvent) -> None:
        for message in event.messages or []:
            self._state(event)["seen"].update(URL_RE.findall(_texts(message["content"])))

    def check(self, event: BeforeToolCallEvent) -> None:
        if event.tool_use["name"] not in self.tools:
            return
        state, url = self._state(event), str(event.tool_use["input"].get("url", ""))
        if url not in state["seen"] and state["failures"] >= self.max_failures:
            log.warning("circuit open: blocked unknown URL %s", url)
            event.cancel_tool = (
                f"Blocked: {url} did not appear in any page or search result, and {state['failures']} "
                "invented URLs already failed. Only use URLs you have actually seen."
            )

    def learn(self, event: AfterToolCallEvent) -> None:
        if event.cancel_message:
            return
        state = self._state(event)
        text = _texts(event.result.get("content", []))
        if any(marker in text for marker in FAILURE_MARKERS):
            url = str(event.tool_use["input"].get("url", ""))
            if event.tool_use["name"] in self.tools and url not in state["seen"]:
                state["failures"] += 1
            return  # don't learn URLs from error messages (they echo the invented URL)
        state["seen"].update(URL_RE.findall(text))
