"""Password hashing (scrypt), signed access tokens (HMAC-SHA256) and refresh tokens. Standard library only.

Access tokens are short-lived (15 min) and name a server-side session, so a session can be revoked at once.
Refresh tokens are random, stored only as a SHA-256 hash, and replaced on every use.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time

ACCESS_TTL_S = 15 * 60
REFRESH_TTL_S = 30 * 24 * 3600  # sliding: each refresh extends it
TOKEN_TTL_S = ACCESS_TTL_S
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_b64, digest_b64 = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), **_SCRYPT)
    return hmac.compare_digest(digest, base64.b64decode(digest_b64))


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue_token(user_id: str, key: bytes, ttl_s: int = ACCESS_TTL_S, now: float | None = None,
                sid: str | None = None) -> str:  # fmt: skip
    claims = {"uid": user_id, "exp": int((now or time.time()) + ttl_s)}
    if sid:
        claims["sid"] = sid
    payload = _b64(json.dumps(claims).encode())
    sig = _b64(hmac.new(key, payload.encode(), hashlib.sha256).digest())
    return f"v1.{payload}.{sig}"


def verify_token(token: str, key: bytes, now: float | None = None) -> str | None:
    """Returns the user id, or None if the token is malformed, forged or expired."""
    claims = token_claims(token, key, now)
    return claims["uid"] if claims else None


def token_claims(token: str, key: bytes, now: float | None = None) -> dict | None:
    """The token's claims ({uid, exp, sid?}), or None if malformed, forged or expired."""
    try:
        version, payload, sig = token.split(".")
    except ValueError:
        return None
    if version != "v1":
        return None
    expected = _b64(hmac.new(key, payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        data = json.loads(_unb64(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("exp", 0) < (now or time.time()) or not data.get("uid"):
        return None
    return {"uid": str(data["uid"]), "exp": int(data["exp"]), "sid": data.get("sid")}


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


INVITE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L


def new_invite_code(length: int = 6) -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(length))


def normalise_invite_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())
