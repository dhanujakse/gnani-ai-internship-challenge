"""Firebase Cloud Messaging (HTTP v1): wakes a phone for an incoming call when the app is closed.

Configured by FCM_SERVICE_ACCOUNT: the Firebase service-account key (the JSON file from Firebase console → Project
settings → Service accounts → Generate new private key), pasted as-is or base64-encoded. Without it, pushes are off
and calls still ring through the app's live connection while the app is open.

Messages are data-only and carry no conversation content: the call id, who is calling, and when ringing stops.
Never logs tokens or keys.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Protocol

import httpx

log = logging.getLogger("sarvagyan.push")

TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class PushSender(Protocol):
    async def send(self, token: str, data: dict[str, str], ttl_s: int) -> str:
        """Returns "ok", "invalid" (token no longer valid: forget it) or "error"."""
        ...


def load_service_account(raw: str) -> dict | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        text = raw if raw.startswith("{") else base64.b64decode(raw).decode()
        info = json.loads(text)
        return info if {"client_email", "private_key", "project_id"} <= set(info) else None
    except (ValueError, UnicodeDecodeError):
        return None


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


class FcmSender:
    def __init__(self, service_account: dict, client: httpx.AsyncClient | None = None) -> None:
        from cryptography.hazmat.primitives import serialization

        self._email = service_account["client_email"]
        self._project = service_account["project_id"]
        self._key = serialization.load_pem_private_key(service_account["private_key"].encode(), password=None)
        self._client = client or httpx.AsyncClient(timeout=10)
        self._access: tuple[str, float] | None = None  # (token, expires_at)

    async def _access_token(self) -> str:
        if self._access and self._access[1] - 60 > time.time():
            return self._access[0]
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        now = int(time.time())
        header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        claims = _b64url(json.dumps({"iss": self._email, "scope": SCOPE, "aud": TOKEN_URL, "iat": now, "exp": now + 3600}).encode())
        signature = self._key.sign(f"{header}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256())
        r = await self._client.post(TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                                     "assertion": f"{header}.{claims}.{_b64url(signature)}"})
        r.raise_for_status()
        body = r.json()
        self._access = (body["access_token"], time.time() + int(body.get("expires_in", 3600)))
        return self._access[0]

    async def send(self, token: str, data: dict[str, str], ttl_s: int) -> str:
        try:
            access = await self._access_token()
            r = await self._client.post(
                f"https://fcm.googleapis.com/v1/projects/{self._project}/messages:send",
                headers={"Authorization": f"Bearer {access}"},
                json={"message": {"token": token, "data": data,
                                  "android": {"priority": "HIGH", "ttl": f"{max(1, ttl_s)}s"}}},
            )
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            log.warning("push failed: %s", type(exc).__name__)
            return "error"
        if r.status_code == 200:
            return "ok"
        if r.status_code in (400, 404) and ("UNREGISTERED" in r.text or "INVALID_ARGUMENT" in r.text):
            return "invalid"
        log.warning("push rejected status=%s", r.status_code)
        return "error"
