"""Rex Lambda: runs Rex at full leash (level 5) for one Hack Rex attempt.

Invoked asynchronously by the API Lambda with {"id": "<attempt id>"}. Reads the
attempt from DynamoDB, runs Rex, judges it and writes the verdict back.
The model API key comes from Secrets Manager (never from the code or the env).
"""

import logging
import os

from leash.hackrex.aws import DynamoAttemptStore, S3PageHost, load_api_keys
from leash.hackrex.gate import Gate
from leash.rex import agent  # noqa: F401  load Strands and the model SDKs at init, so a warm instance is ready

logging.getLogger("leash").setLevel(logging.INFO)
_gate: Gate | None = None


def _build() -> Gate:
    loaded = load_api_keys(os.environ["API_KEYS_SECRET"])
    logging.getLogger("leash").info("model API keys loaded: %s", loaded or "none")
    return Gate(
        store=DynamoAttemptStore(os.environ["ATTEMPTS_TABLE"]),
        pages=S3PageHost(os.environ["SITE_BUCKET"], os.environ["PAGES_BASE_URL"]),
        moderate=lambda text: True,  # moderation already ran in the API Lambda
    )


def handler(event, context):
    global _gate
    if event.get("warmup"):  # scheduled keep-warm ping: nothing to run
        return {"warm": True}
    _gate = _gate or _build()
    result = _gate.run(event["id"])
    return {"id": result["id"], "stopped_by": result["verdict"]["stopped_by"], "won": result["verdict"]["won"]}
