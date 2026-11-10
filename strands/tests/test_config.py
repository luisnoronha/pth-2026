import pytest

from leash.common.config import model_names, model_settings
from leash.common.pricing import cost_usd
from leash.rex.agent import build_model


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    for name in ("REX_MODEL", "REX_MODEL_ID", "REX_PRICE_IN_PER_MTOK", "REX_PRICE_OUT_PER_MTOK"):
        monkeypatch.delenv(name, raising=False)


def test_yaml_lists_the_models():
    assert {"haiku-4-5", "haiku-5-5", "gpt-mini"} <= set(model_names())


@pytest.mark.parametrize("name, cls", [("haiku-4-5", "AnthropicModel"), ("gpt-mini", "OpenAIModel")])
def test_each_provider_builds_without_calling_the_network(monkeypatch, name, cls):
    monkeypatch.setenv("REX_MODEL", name)
    model = build_model()
    assert type(model).__name__ == cls and model.config["model_id"] == model_settings().model_id


def test_openai_reasoning_model_gets_no_temperature_and_minimal_reasoning(monkeypatch):
    monkeypatch.setenv("REX_MODEL", "gpt-mini")
    params = build_model().config["params"]
    assert "temperature" not in params and params["reasoning_effort"] == "minimal"


def test_switching_by_name_changes_the_model_id(monkeypatch):
    monkeypatch.setenv("REX_MODEL", "haiku-5-5")
    assert build_model().config["model_id"] == "claude-haiku-5-5"


def test_raw_id_beats_the_name(monkeypatch):
    monkeypatch.setenv("REX_MODEL", "haiku-5-5")
    monkeypatch.setenv("REX_MODEL_ID", "some-other-model")
    assert model_settings().model_id == "some-other-model"


def test_unknown_name_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("REX_MODEL", "gpt-9")
    with pytest.raises(ValueError, match="rex.yaml"):
        model_settings()


def test_prices_follow_the_yaml_and_env_wins(monkeypatch):
    assert cost_usd(1_000_000, 0) == model_settings().price_in
    monkeypatch.setenv("REX_PRICE_IN_PER_MTOK", "3")
    assert cost_usd(1_000_000, 0) == 3


def test_haiku_5_5_sends_no_temperature_and_no_thinking(monkeypatch):
    monkeypatch.setenv("REX_MODEL", "haiku-5-5")
    params = build_model().config["params"]
    assert "temperature" not in params and params["thinking"] == {"type": "disabled"}


def test_haiku_4_5_keeps_temperature_zero(monkeypatch):
    monkeypatch.setenv("REX_MODEL", "haiku-4-5")
    assert build_model().config["params"] == {"temperature": 0.0}
