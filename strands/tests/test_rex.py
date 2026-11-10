import pytest

from leash.hooks.levels import hooks_for
from leash.rex.agent import build_rex


def test_level_zero_has_no_hooks():
    assert hooks_for(0) == []


@pytest.mark.parametrize("level", [-1, 6])
def test_rejects_unknown_levels(level):
    with pytest.raises(ValueError):
        hooks_for(level)


def test_build_rex_at_level_zero_without_calling_aws():
    rex = build_rex(0)
    assert rex.name == "Rex"
    assert {"fetch_page", "search", "read_notes", "check_link"} <= set(rex.tool_names)
