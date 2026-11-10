"""Token prices used by the budget hook: the active model's prices from rex.yaml.

ILLUSTRATIVE until checked: [verify] against the provider's public price list.
"""

from leash.common.config import model_settings


def cost_usd(input_tokens: int, output_tokens: int) -> float:
    settings = model_settings()
    return (input_tokens * settings.price_in + output_tokens * settings.price_out) / 1_000_000
