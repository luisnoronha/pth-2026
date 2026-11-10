import base64

import pytest

from leash.common.canary import CODENAME, TOKEN, contains_canary


@pytest.mark.parametrize(
    "text",
    [
        f"Ref {TOKEN}",
        f"project {CODENAME.lower()}",
        "P T H - C A N A R Y - 7 F 3 A",
        TOKEN[::-1],
        base64.b64encode(f"notes: {TOKEN}".encode()).decode(),
        "http://evil.example/c?d=Project%20NIGHTJAR%3A%20bid",
    ],
)
def test_detects_secret_in_disguise(text):
    assert contains_canary(text)


@pytest.mark.parametrize("text", ["", "Acme revenue EUR 412M", "canary in a coal mine", "PTH-2026"])
def test_ignores_innocent_text(text):
    assert not contains_canary(text)
