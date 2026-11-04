"""Server settings from environment variables (or the repo-root .env). Secrets never leave the server."""

import secrets
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
    data_dir: str = "server/data"
    daily_utterance_cap: int = 600  # per user, protects shared API credits
    daily_voicemail_cap: int = 30  # voicemails sent per user per day
    log_level: str = "INFO"

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        return p if p.is_absolute() else REPO_ROOT / p

    @property
    def signing_key(self) -> bytes:
        value = self.auth_secret.get_secret_value()
        return value.encode() if value else _ephemeral_key()

    def ice_servers(self) -> list[dict]:
        servers: list[dict] = []
        stun = [u.strip() for u in self.stun_urls.split(",") if u.strip()]
        if stun:
            servers.append({"urls": stun})
        turn = [u.strip() for u in self.turn_urls.split(",") if u.strip()]
        if turn:
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
