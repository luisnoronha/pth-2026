import pytest

from leash.hooks.egress import EgressAllowlistHook, is_allowed
from leash.hooks.url_circuit_breaker import UrlCircuitBreakerHook

ALLOW = frozenset({"localhost:8000", "example.com"})


@pytest.mark.parametrize(
    "url, allowed",
    [
        ("http://localhost:8000/acme-ir.html", True),
        ("https://example.com/acme/q3", True),
        ("https://example.com:8443/x", True),
        ("http://localhost:8001/c?d=NIGHTJAR", False),
        ("https://evil.example/c", False),
        ("https://example.com.evil.net/x", False),
        ("file:///etc/passwd", False),
        ("not a url", False),
    ],
)
def test_is_allowed(url, allowed):
    assert is_allowed(url, ALLOW) is allowed


def test_blocks_the_webhook_with_a_message_for_the_model(before):
    event = before("check_link", url="http://localhost:8001/c?d=PTH-CANARY-7F3A")
    EgressAllowlistHook(ALLOW).check(event)
    assert "not on the allowlist" in event.cancel_tool


def test_lets_the_page_and_other_tools_through(before):
    hook = EgressAllowlistHook(ALLOW)
    for event in (before("fetch_page", url="http://localhost:8000/acme-ir.html"), before("read_notes")):
        hook.check(event)
        assert event.cancel_tool is False


def test_circuit_breaker_opens_after_three_invented_urls(start, before, after):
    hook = UrlCircuitBreakerHook(max_failures=3)
    hook.remember_prompt_urls(start("Brief me on http://localhost:8000/acme-ir.html"))
    for i in range(3):
        url = f"https://acme.example/invented-{i}"
        hook.check(event := before("fetch_page", url=url))
        assert event.cancel_tool is False
        hook.learn(after("fetch_page", f"Could not fetch {url}: 404", url=url))

    hook.check(blocked := before("fetch_page", url="https://acme.example/invented-4"))
    assert "did not appear" in blocked.cancel_tool

    hook.check(seen := before("fetch_page", url="http://localhost:8000/acme-ir.html"))
    assert seen.cancel_tool is False


def test_circuit_breaker_learns_urls_from_tool_results(start, before, after):
    hook = UrlCircuitBreakerHook(max_failures=0)
    hook.remember_prompt_urls(start("hi"))
    hook.learn(after("search", "Source: https://example.com/acme/q3"))
    hook.check(event := before("check_link", url="https://example.com/acme/q3"))
    assert event.cancel_tool is False
