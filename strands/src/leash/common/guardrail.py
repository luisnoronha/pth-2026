"""Shadow-mode call to Bedrock ApplyGuardrail: evaluate, log, never block."""

import logging
import os
from typing import Any

import boto3

log = logging.getLogger("leash.guardrail")


def guardrail_config() -> tuple[str | None, str]:
    return os.getenv("REX_GUARDRAIL_ID"), os.getenv("REX_GUARDRAIL_VERSION", "DRAFT")


def bedrock_runtime_client() -> Any:
    return boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "eu-north-1"))


def shadow_check(client: Any, guardrail_id: str, version: str, text: str, where: str) -> dict[str, Any]:
    """Run the guardrail on `text`. Returns a verdict; on error, fails open (shadow mode)."""
    try:
        response = client.apply_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion=version,
            source="INPUT",
            content=[{"text": {"text": text}}],
        )
    except Exception as error:  # shadow mode must never break the run
        log.warning("guardrail error on %s, skipped: %s", where, error)
        return {"where": where, "action": "ERROR", "error": str(error)}

    action = response.get("action", "NONE")
    if action == "GUARDRAIL_INTERVENED":
        log.warning("WOULD BLOCK %s", where)  # never blocks
    else:
        log.info("guardrail on %s: %s", where, action)
    return {"where": where, "action": action, "assessments": response.get("assessments", [])}
