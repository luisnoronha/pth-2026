"""The AWS versions of the Hack Rex pieces (same methods as the local ones).

  DynamoAttemptStore  attempts table        (local: AttemptStore)
  S3PageHost          poisoned pages in S3  (local: LocalPageHost)
  SsmSwitch           kill switch in SSM    (local: LocalSwitch)
  LambdaRunner        starts the Rex Lambda for an attempt, without waiting

Each attempt is one DynamoDB item: the key `id` plus the whole record as JSON in
`doc` (no Decimal juggling), and `expires_at` so DynamoDB deletes it by itself
after the event.
"""

import json
import os
import time
from typing import Any

import boto3

from leash.hackrex.gate import page_html

KEEP_DAYS = int(os.getenv("HACKREX_KEEP_DAYS", "7"))
API_KEY_NAMES = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


class DynamoAttemptStore:
    def __init__(self, table_name: str, client=None):
        self.table, self.db = table_name, client or boto3.client("dynamodb")

    def add(self, attempt: dict[str, Any]) -> None:
        self.db.put_item(TableName=self.table, Item={
            "id": {"S": attempt["id"]},
            "player": {"S": attempt["player"]},
            "doc": {"S": json.dumps(attempt, ensure_ascii=False)},
            "expires_at": {"N": str(int(time.time()) + KEEP_DAYS * 86400)},
        })

    def get(self, attempt_id: str) -> dict[str, Any] | None:
        item = self.db.get_item(TableName=self.table, Key={"id": {"S": attempt_id}}, ConsistentRead=True).get("Item")
        return json.loads(item["doc"]["S"]) if item else None

    def _update(self, attempt_id: str, **changes: Any) -> bool:
        attempt = self.get(attempt_id)
        if attempt is None:
            return False
        self.add({**attempt, **changes})
        return True

    def complete(self, attempt_id: str, answer: Any, verdict: dict[str, Any]) -> None:
        self._update(attempt_id, status="done", answer=answer, verdict=verdict)

    def set_approved(self, attempt_id: str, approved: bool) -> bool:
        return self._update(attempt_id, approved=approved)

    def _scan(self, **kwargs: Any):
        for page in self.db.get_paginator("scan").paginate(TableName=self.table, **kwargs):
            yield page

    def count(self) -> int:
        return sum(page["Count"] for page in self._scan(Select="COUNT"))

    def count_for(self, player: str) -> int:
        return sum(page["Count"] for page in self._scan(
            Select="COUNT", FilterExpression="player = :p", ExpressionAttributeValues={":p": {"S": player}}))

    def all(self) -> list[dict[str, Any]]:
        docs = [json.loads(item["doc"]["S"]) for page in self._scan() for item in page["Items"]]
        return sorted(docs, key=lambda a: a["ts"])

    def clear(self) -> None:
        for page in self._scan(ProjectionExpression="id"):
            for item in page["Items"]:
                self.db.delete_item(TableName=self.table, Key={"id": item["id"]})


class S3PageHost:
    """Poisoned pages go to s3://<bucket>/p/<id>.html, served by the api Lambda at <base_url>/<id>.html."""

    def __init__(self, bucket: str, base_url: str, prefix: str = "p/", client=None):
        self.bucket, self.base_url, self.prefix = bucket, base_url.rstrip("/"), prefix
        self.s3 = client or boto3.client("s3")

    def publish(self, attempt_id: str, text: str) -> str:
        self.s3.put_object(Bucket=self.bucket, Key=f"{self.prefix}{attempt_id}.html", Body=page_html(text).encode(),
                           ContentType="text/html; charset=utf-8", CacheControl="no-store")
        return f"{self.base_url}/{attempt_id}.html"


class SsmSwitch:
    """Kill switch: an SSM parameter holding "open" or "closed". Cached for a few seconds."""

    def __init__(self, name: str, client=None, cache_s: float = 3.0):
        self.name, self.ssm, self.cache_s = name, client or boto3.client("ssm"), cache_s
        self._value, self._read_at = True, float("-inf")

    def is_open(self) -> bool:
        if time.monotonic() - self._read_at > self.cache_s:
            self._value = self.ssm.get_parameter(Name=self.name)["Parameter"]["Value"] == "open"
            self._read_at = time.monotonic()
        return self._value

    def set_open(self, value: bool) -> None:
        self.ssm.put_parameter(Name=self.name, Value="open" if value else "closed", Type="String", Overwrite=True)
        self._value, self._read_at = value, time.monotonic()


class LambdaRunner:
    """Starts the Rex Lambda for one attempt (async invoke: returns at once, retries are off in Terraform)."""

    def __init__(self, function_name: str, client=None):
        self.function, self.lambda_ = function_name, client or boto3.client("lambda")

    def __call__(self, attempt_id: str) -> None:
        self.lambda_.invoke(FunctionName=self.function, InvocationType="Event",
                            Payload=json.dumps({"id": attempt_id}).encode())


def secure_parameter(name: str, client=None) -> str:
    ssm = client or boto3.client("ssm")
    return ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]


def load_api_keys(secret_id: str, client=None) -> list[str]:
    """Puts the model API keys from Secrets Manager into the environment. Returns which ones were set."""
    secrets = client or boto3.client("secretsmanager")
    values = json.loads(secrets.get_secret_value(SecretId=secret_id)["SecretString"] or "{}")
    loaded = []
    for name in API_KEY_NAMES:
        if values.get(name):
            os.environ[name] = values[name]
            loaded.append(name)
    return loaded
