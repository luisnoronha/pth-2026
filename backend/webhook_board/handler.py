"""Demo 1 webhook board: the attacker's endpoint (a Lambda Function URL).

  GET /c?d=<anything>   records the hit; this is where a hijacked Rex sends the secret
  GET /hits             the latest hits, for the big-screen board (frontend/board)

Only the canary values found are shown on the board, never the full payload.
"""

import json
import os
import time
import uuid
from urllib.parse import parse_qs

import boto3

from leash.common.canary import CODENAME, TOKEN, contains_canary

KEEP_DAYS = 7
_db = None


def _client():
    global _db
    _db = _db or boto3.client("dynamodb")
    return _db


def _response(code: int, payload, content_type="application/json"):
    body = payload if isinstance(payload, str) else json.dumps(payload)
    return {"statusCode": code, "headers": {"Content-Type": content_type, "Cache-Control": "no-store"}, "body": body}


def _record(data: str) -> dict:
    leaked = contains_canary(data)  # also catches encoded leaks (base64, reversed, spaced)
    hit = {"id": uuid.uuid4().hex[:12], "ts": time.time(), "leaked": leaked,
           "secret": f"{CODENAME} / {TOKEN}" if leaked else None}
    _client().put_item(TableName=os.environ["HITS_TABLE"], Item={
        "id": {"S": hit["id"]}, "doc": {"S": json.dumps(hit)},
        "expires_at": {"N": str(int(time.time()) + KEEP_DAYS * 86400)}})
    return hit


def _latest(limit: int = 20) -> list[dict]:
    pages = _client().get_paginator("scan").paginate(TableName=os.environ["HITS_TABLE"])
    hits = [json.loads(item["doc"]["S"]) for page in pages for item in page["Items"]]
    return sorted(hits, key=lambda h: h["ts"], reverse=True)[:limit]


def handler(event, context):
    path = event.get("rawPath", "/")
    if path == "/hits":
        return _response(200, {"hits": _latest()})
    if path.startswith("/c"):
        query = parse_qs(event.get("rawQueryString", ""))
        _record(" ".join(v for values in query.values() for v in values))
        return _response(200, "ok", "text/plain")
    return _response(404, {"error": "not found"})
