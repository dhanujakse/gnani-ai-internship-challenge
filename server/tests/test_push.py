"""Push (Firebase): incoming calls wake a phone whose app is closed; tokens follow the sign-in session."""

import base64
import json
import time

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from sarvagyan_server.push import FcmSender, load_service_account
from tests.test_direct_calls import people

TOKEN = "fcm-token-" + "x" * 40


class FakePush:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict, int]] = []
        self.answer = "ok"

    async def send(self, token, data, ttl_s):
        self.sent.append((token, data, ttl_s))
        return self.answer


@pytest.fixture
def push(env):
    fake = FakePush()
    env.services.push_sender = fake
    return fake


def wait(cond, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end and not cond():
        time.sleep(0.02)
    return cond()


def friends(env):
    (ta, a), (tb, b) = people(env)
    env.client.post("/v1/contacts", json={"user_id": a["id"]}, headers=env.auth(tb))
    return ta, a, tb, b


def test_incoming_call_and_its_end_are_pushed_to_the_callee(env, push) -> None:
    ta, a, tb, b = friends(env)
    assert env.client.post("/v1/me/push-token", json={"token": TOKEN}, headers=env.auth(tb)).json()["push"] is True
    r = env.client.post("/v1/calls/direct", json={"to": b["id"], "language": "ta-IN"}, headers=env.auth(ta)).json()
    assert r["reachable"] is True                                         # the closed app can still be reached
    assert wait(lambda: len(push.sent) == 1)
    token, data, ttl = push.sent[0]
    assert token == TOKEN and data["type"] == "incoming_call" and data["call_id"] == r["call_id"]
    assert data["from_id"] == a["id"] and data["from_language"] == "ta-IN" and ttl == env.services.settings.ring_timeout_s
    assert all(isinstance(v, str) for v in data.values())                  # FCM data values must be strings
    env.client.post(f"/v1/calls/{r['call_id']}/cancel", headers=env.auth(ta))
    assert wait(lambda: len(push.sent) == 2)
    assert push.sent[1][1] == {"type": "call_cancelled", "call_id": r["call_id"], "reason": "cancelled"}


def test_signing_out_stops_pushes_to_that_phone(env, push) -> None:
    ta, a, tb, b = friends(env)
    env.client.post("/v1/me/push-token", json={"token": TOKEN}, headers=env.auth(tb))
    env.client.post("/v1/auth/logout", headers=env.auth(tb))
    assert env.services.db.push_tokens(b["id"]) == []


def test_invalid_tokens_are_forgotten(env, push) -> None:
    ta, a, tb, b = friends(env)
    env.client.post("/v1/me/push-token", json={"token": TOKEN}, headers=env.auth(tb))
    push.answer = "invalid"
    env.client.post("/v1/calls/direct", json={"to": b["id"], "language": "ta-IN"}, headers=env.auth(ta))
    assert wait(lambda: env.services.db.push_tokens(b["id"]) == [])


def test_push_is_off_without_a_key(env) -> None:
    (ta, a), _ = people(env)
    assert env.services.push_sender is None
    assert env.client.post("/v1/me/push-token", json={"token": TOKEN}, headers=env.auth(ta)).json()["push"] is False


def test_service_account_can_be_raw_or_base64() -> None:
    info = {"client_email": "x@y.iam.gserviceaccount.com", "private_key": "k", "project_id": "p"}
    assert load_service_account(json.dumps(info)) == info
    assert load_service_account(base64.b64encode(json.dumps(info).encode()).decode()) == info
    assert load_service_account("not json") is None and load_service_account("") is None


async def test_fcm_sender_signs_its_own_access_token_and_sends_a_high_priority_data_message() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.host == "oauth2.googleapis.com":
            assertion = dict(x.split("=", 1) for x in req.content.decode().split("&"))["assertion"]
            head, claims, sig = assertion.split(".")
            pad = lambda s: s + "=" * (-len(s) % 4)   # noqa: E731
            key.public_key().verify(base64.urlsafe_b64decode(pad(sig)), f"{head}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256())
            assert json.loads(base64.urlsafe_b64decode(pad(claims)))["iss"] == "svc@p.iam.gserviceaccount.com"
            return httpx.Response(200, json={"access_token": "ya29.test", "expires_in": 3600})
        assert req.headers["Authorization"] == "Bearer ya29.test" and "/projects/proj-1/messages:send" in req.url.path
        msg = json.loads(req.content)["message"]
        assert msg["android"] == {"priority": "HIGH", "ttl": "30s"} and msg["data"]["type"] == "incoming_call"
        return httpx.Response(200, json={"name": "projects/proj-1/messages/1"})

    sender = FcmSender({"client_email": "svc@p.iam.gserviceaccount.com", "private_key": pem, "project_id": "proj-1"},
                       client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await sender.send("tok", {"type": "incoming_call"}, 30) == "ok"
    assert await sender.send("tok", {"type": "incoming_call"}, 30) == "ok"
    assert sum(r.url.host == "oauth2.googleapis.com" for r in seen) == 1   # access token is reused
