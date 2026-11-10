"""The AWS adapters against moto (a fake AWS in memory). No real account is touched."""

import json
import os
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from leash.hackrex.aws import DynamoAttemptStore, LambdaRunner, S3PageHost, SsmSwitch, load_api_keys
from leash.hackrex.store import scoreboard

REGION = "eu-north-1"


@pytest.fixture
def aws(monkeypatch):
    for name in ("AWS_PROFILE", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    with mock_aws():
        yield


@pytest.fixture
def store(aws):
    db = boto3.client("dynamodb", region_name=REGION)
    db.create_table(TableName="attempts", BillingMode="PAY_PER_REQUEST",
                    AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                    KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}])
    return DynamoAttemptStore("attempts", client=db)


def attempt(attempt_id, ts=1.0):
    return {"id": attempt_id, "ts": ts, "status": "running", "player": "p", "nickname": "neo", "mode": "talk",
            "text": "hi", "prompt": "hi", "approved": False}


def test_dynamo_store_round_trip(store):
    store.add(attempt("a1", ts=2.5))
    store.add(attempt("a0", ts=1.0))
    assert store.count() == 2 and [a["id"] for a in store.all()] == ["a0", "a1"]
    store.complete("a1", {"company": "Acme"}, {"stopped_by": "model", "stopped_by_label": "x", "won": None})
    assert store.get("a1")["status"] == "done" and store.get("a1")["ts"] == 2.5
    assert store.set_approved("a1", True) and not store.set_approved("nope", True)
    assert scoreboard(store.all())["running"] == 1
    store.clear()
    assert store.count() == 0 and store.get("a1") is None


def test_s3_page_host_writes_a_page_and_returns_its_url(aws):
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket="site", CreateBucketConfiguration={"LocationConstraint": REGION})
    url = S3PageHost("site", "https://abc123.execute-api.eu-north-1.amazonaws.com/live/p/", client=s3).publish("abc", "<p>poison</p>")
    assert url == "https://abc123.execute-api.eu-north-1.amazonaws.com/live/p/abc.html"
    body = s3.get_object(Bucket="site", Key="p/abc.html")["Body"].read().decode()
    assert "<p>poison</p>" in body


def test_ssm_switch(aws):
    ssm = boto3.client("ssm", region_name=REGION)
    ssm.put_parameter(Name="/hackrex/open", Value="open", Type="String")
    switch = SsmSwitch("/hackrex/open", client=ssm, cache_s=0)
    assert switch.is_open()
    switch.set_open(False)
    assert not switch.is_open() and ssm.get_parameter(Name="/hackrex/open")["Parameter"]["Value"] == "closed"


def test_api_keys_come_from_the_secret(aws):
    sm = boto3.client("secretsmanager", region_name=REGION)
    sm.create_secret(Name="keys", SecretString=json.dumps({"OPENAI_API_KEY": "sk-test", "ANTHROPIC_API_KEY": ""}))
    assert load_api_keys("keys", client=sm) == ["OPENAI_API_KEY"]
    assert os.environ["OPENAI_API_KEY"] == "sk-test"
    os.environ.pop("OPENAI_API_KEY")


def test_lambda_runner_invokes_async():
    client = MagicMock()
    LambdaRunner("rex", client=client)("abc")
    kwargs = client.invoke.call_args.kwargs
    assert kwargs["InvocationType"] == "Event" and json.loads(kwargs["Payload"]) == {"id": "abc"}
