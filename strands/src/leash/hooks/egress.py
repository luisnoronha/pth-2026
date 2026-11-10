"""Level 4: build fences, not filters.

EgressAllowlistHook: tools that reach the network may only talk to allowlisted
hosts (and only over http/https). The injection may get past every filter, but
the stolen data has nowhere to go.

Entries are "host" (any port) or "host:port".
"""

import logging
import os
from typing import Any
from urllib.parse import urlsplit

from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry

log = logging.getLogger("leash.hooks")

NETWORK_TOOLS = frozenset({"fetch_page", "check_link"})
DEFAULT_ALLOWLIST = "localhost:8000"


def allowlist_from_env() -> frozenset[str]:
    raw = os.getenv("REX_EGRESS_ALLOWLIST", DEFAULT_ALLOWLIST)
    return frozenset(entry.strip().lower() for entry in raw.split(",") if entry.strip())


def is_allowed(url: str, allowlist: frozenset[str]) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    host = parts.hostname.lower()
    return host in allowlist or (parts.port is not None and f"{host}:{parts.port}" in allowlist)


class EgressAllowlistHook(HookProvider):
    def __init__(self, allowlist=None, tools=NETWORK_TOOLS):
        self.allowlist = frozenset(allowlist) if allowlist is not None else allowlist_from_env()
        self.tools = frozenset(tools)

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.check)

    def check(self, event: BeforeToolCallEvent) -> None:
        if event.tool_use["name"] not in self.tools:
            return
        url = str(event.tool_use["input"].get("url", ""))
        if not is_allowed(url, self.allowlist):
            host = urlsplit(url).netloc or url
            log.warning("egress blocked: %s -> %s", event.tool_use["name"], host)
            event.cancel_tool = (
                f"Blocked: {host} is not on the allowlist. Do not try other URLs for this; "
                "continue with the information you already have."
            )
