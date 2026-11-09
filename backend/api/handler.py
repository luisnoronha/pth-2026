"""Hack Rex API Lambda, behind API Gateway (REST, proxy integration).

Fast requests only: it validates and stores an attack, then starts the Rex
Lambda in the background and answers with an id. The phone polls for the result.
Routes and checks live in leash.hackrex.api (shared with the local server).
"""

import base64
import json
import os

from leash.hackrex.api import Api, RateLimiter
from leash.hackrex.aws import DynamoAttemptStore, LambdaRunner, S3PageHost, SsmSwitch, secure_parameter
from leash.hackrex.gate import Gate

_api: Api | None = None


def _build() -> Api:
    gate = Gate(
        store=DynamoAttemptStore(os.environ["ATTEMPTS_TABLE"]),
        pages=S3PageHost(os.environ["SITE_BUCKET"], os.environ["PAGES_BASE_URL"]),
        switch=SsmSwitch(os.environ["SWITCH_PARAM"]),
    )
    return Api(gate, secure_parameter(os.environ["ADMIN_TOKEN_PARAM"]),
               RateLimiter(int(os.getenv("HACKREX_RATE_PER_MINUTE", "5"))),
               start_run=LambdaRunner(os.environ["REX_FUNCTION"]))


def _cors() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": os.getenv("ALLOWED_ORIGIN", "*"),
        "Access-Control-Allow-Headers": "Content-Type,X-Admin-Token",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Cache-Control": "no-store",
    }


def handler(event, context):
    global _api
    _api = _api or _build()
    body = event.get("body") or ""
    raw = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode("utf-8")
    code, payload = _api.handle(event["httpMethod"], event["path"], event.get("headers") or {}, raw)
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json", **_cors()},
        "body": "" if payload is None else json.dumps(payload, ensure_ascii=False),
    }
