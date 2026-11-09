"""Per-run state shared by hooks, kept in `invocation_state` (not on the hook object).

Each hook gets its own namespace under invocation_state["leash"], so hooks never
step on each other's keys and the state resets on every run.
"""

from typing import Any

NAMESPACE = "leash"


def hook_state(event: Any, name: str, **defaults: Any) -> dict[str, Any]:
    """This hook's namespace for the current run, created with `defaults` on first use."""
    root = event.invocation_state.setdefault(NAMESPACE, {})
    return root.setdefault(name, dict(defaults))
