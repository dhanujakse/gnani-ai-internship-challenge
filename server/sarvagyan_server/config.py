"""Server settings from environment variables (or the repo-root .env). Secrets never leave the server."""

import base64
import hashlib
import hmac
import secrets
import time
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", ".env"), extra="ignore")

    gnani_api_key: SecretStr = SecretStr("")
    gnani_stt_url: str = "wss://api.vachana.ai/stt/v3/stream"
    gnani_tts_url: str = "wss://api.vachana.ai/api/v1/tts"
    stt_model: str = "prisma-v3.0"  # measured faster than v2.5 on streaming, supports indic-auto
    tts_model: str = "timbre-v2.5"
    mymemory_email: str = ""
    auth_secret: SecretStr = SecretStr("")
    demo_mode: bool = True
    stun_urls: str = "stun:stun.l.google.com:19302"
    turn_urls: str = ""
    turn_username: str = ""
    turn_credential: SecretStr = SecretStr("")
    turn_secret: SecretStr = SecretStr("")  # coturn `static-auth-secret`: per-user credentials valid 24 h
    ring_timeout_s: int = 30  # an unanswered direct call becomes a missed call after this
    data_dir: str = "server/data"
    daily_utterance_cap: int = 600  # per user, protects shared API credits
    daily_voicemail_cap: int = 30  # voicemails sent per user per day
    chat_retention_days: int = 30  # chat messages and voice clips are deleted after this
    trust_proxy_headers: bool = False  # true only behind Cloudflare: use CF-Connecting-IP for rate limits
    log_level: str = "INFO"

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        return p if p.is_absolute() else REPO_ROOT / p

    @property
    def signing_key(self) -> bytes:
        value = self.auth_secret.get_secret_value()
        return value.encode() if value else _ephemeral_key()

    def ice_servers(self, user_id: str = "anonymous") -> list[dict]:
        servers: list[dict] = []
        stun = [u.strip() for u in self.stun_urls.split(",") if u.strip()]
        if stun:
            servers.append({"urls": stun})
        turn = [u.strip() for u in self.turn_urls.split(",") if u.strip()]
        if turn and self.turn_secret.get_secret_value():
            # TURN REST credentials (coturn use-auth-secret): expire after 24 h, so a leaked one is short-lived
            username = f"{int(time.time()) + 24 * 3600}:{user_id}"
            digest = hmac.new(self.turn_secret.get_secret_value().encode(), username.encode(), hashlib.sha1).digest()
            servers.append({"urls": turn, "username": username, "credential": base64.b64encode(digest).decode()})
        elif turn:
            servers.append({"urls": turn, "username": self.turn_username,
                            "credential": self.turn_credential.get_secret_value()})  # fmt: skip
        return servers


@lru_cache(maxsize=1)
def _ephemeral_key() -> bytes:
    # Without AUTH_SECRET, tokens are valid until the server restarts (fine for local dev only).
    return secrets.token_bytes(32)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
