"""Hack Rex Lambda behind API Gateway (REST, proxy): the whole site on one https address.

  /api/...                      the game API (leash.hackrex.api, shared with the local server)
  everything else               pages from the private S3 bucket: the attack page, scoreboard,
                                admin, Demo 1 board and pages, poisoned pages, config.js

Fast requests only: an attack is stored and Rex is started in the background
(the rex Lambda); the phone polls for the result.

Cold starts: serving a page needs only boto3, so the game modules load on the
first /api request, and Rex himself never loads here. A scheduled
{"warmup": true} event keeps an instance alive between visits.
"""

import base64
import json
import os
import re

import boto3

ALIASES = {"/": "index.html", "/scoreboard": "scoreboard.html", "/admin": "admin.html"}
PAGE_KEY = re.compile(r"^((index|scoreboard|admin)\.html|config\.js|board/index\.html|demo/[\w.-]+\.html|p/[0-9a-f]{12}\.html)$")
TYPES = {".html": "text/html; charset=utf-8", ".js": "application/javascript"}

_api = None
_s3 = None


def _build():
    from leash.hackrex.api import Api, RateLimiter
    from leash.hackrex.aws import DynamoAttemptStore, LambdaRunner, S3PageHost, SsmSwitch, secure_parameter
    from leash.hackrex.gate import Gate

    gate = Gate(
        store=DynamoAttemptStore(os.environ["ATTEMPTS_TABLE"]),
        pages=S3PageHost(os.environ["SITE_BUCKET"], os.environ["PAGES_BASE_URL"]),
        switch=SsmSwitch(os.environ["SWITCH_PARAM"]),
    )
    return Api(gate, secure_parameter(os.environ["ADMIN_TOKEN_PARAM"]),
               RateLimiter(int(os.getenv("HACKREX_RATE_PER_MINUTE", "5"))),
               start_run=LambdaRunner(os.environ["REX_FUNCTION"]))


def _response(code: int, body: str, content_type: str) -> dict:
    return {"statusCode": code, "headers": {"Content-Type": content_type, "Cache-Control": "no-store"}, "body": body}


def _page(path: str) -> dict:
    global _s3
    key = ALIASES.get(path, path.lstrip("/"))
    if not PAGE_KEY.match(key):
        return _response(404, "Not found", "text/plain")
    _s3 = _s3 or boto3.client("s3")
    try:
        body = _s3.get_object(Bucket=os.environ["SITE_BUCKET"], Key=key)["Body"].read().decode("utf-8")
    except _s3.exceptions.NoSuchKey:
        return _response(404, "Not found", "text/plain")
    return _response(200, body, TYPES[os.path.splitext(key)[1]])


def handler(event, context):
    global _api
    if event.get("warmup"):
        return {"warm": True}
    path = event["path"]
    if not path.startswith("/api/"):
        return _page(path) if event["httpMethod"] == "GET" else _response(405, "Method not allowed", "text/plain")
    _api = _api or _build()
    body = event.get("body") or ""
    raw = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode("utf-8")
    code, payload = _api.handle(event["httpMethod"], path, event.get("headers") or {}, raw)
    return _response(code, json.dumps(payload, ensure_ascii=False), "application/json")
