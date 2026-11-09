"""Rex's model settings, read from `strands/rex.yaml`.

Precedence (first wins):
  model:  REX_MODEL (a name in the yaml) > yaml `active`;  REX_MODEL_ID overrides that entry's id
  prices: REX_PRICE_IN_PER_MTOK / REX_PRICE_OUT_PER_MTOK > the model's prices
Another file: REX_CONFIG=path/to/file.yaml. API keys never live here: the
Anthropic and OpenAI clients read ANTHROPIC_API_KEY / OPENAI_API_KEY themselves.
"""

import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "rex.yaml"
PROVIDERS = ("anthropic", "openai")


@dataclass(frozen=True)
class ModelSettings:
    name: str
    provider: str
    model_id: str
    temperature: float | None
    max_tokens: int
    price_in: float
    price_out: float
    params: dict


@cache
def _load(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def config() -> dict:
    return _load(os.getenv("REX_CONFIG", str(DEFAULT_PATH)))


def model_names() -> list[str]:
    return list(config().get("models", {}))


def model_settings() -> ModelSettings:
    cfg = config()
    name = os.getenv("REX_MODEL") or cfg["active"]
    if name not in cfg.get("models", {}):
        raise ValueError(f"unknown model {name!r}; choose one of {model_names()} (rex.yaml)")
    entry = cfg["models"][name]
    provider = entry.get("provider")
    if provider not in PROVIDERS:
        raise ValueError(f"model {name!r}: provider must be one of {PROVIDERS} (rex.yaml)")
    temperature = entry["temperature"] if "temperature" in entry else cfg.get("temperature", 0.0)
    return ModelSettings(
        name=name,
        provider=provider,
        model_id=os.getenv("REX_MODEL_ID") or entry["id"],
        temperature=None if temperature is None else float(temperature),
        max_tokens=int(entry.get("max_tokens", cfg.get("max_tokens", 2048))),
        price_in=float(os.getenv("REX_PRICE_IN_PER_MTOK") or entry["price_in"]),
        price_out=float(os.getenv("REX_PRICE_OUT_PER_MTOK") or entry["price_out"]),
        params=dict(entry.get("params") or {}),
    )
