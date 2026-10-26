"""Settings loaded from environment variables (and .env for local dev)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Looks for .env in backend/ first, then the repo root.
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # Gnani (Prisma STT + Timbre TTS)
    gnani_api_key: SecretStr = SecretStr("")
    gnani_base_url: str = "https://api.vachana.ai"
    tts_model: Literal["timbre-v2.5", "timbre-v3.0"] = "timbre-v2.5"

    # Evon translation (self-hosted vLLM, OpenAI-compatible)
    evon_base_url: str = "https://evon.example.com/v1"
    evon_api_key: SecretStr = SecretStr("")
    evon_model: str = "model"
    translation_provider: Literal["evon", "fallback"] = "evon"

    # WhatsApp Cloud API
    wa_access_token: SecretStr = SecretStr("")
    wa_phone_number_id: str = ""
    wa_app_secret: SecretStr = SecretStr("")
    wa_verify_token: SecretStr = SecretStr("")
    wa_graph_version: str = "v23.0"

    # Web app channel
    web_client_token_secret: SecretStr = SecretStr("")
    allowed_origins: str = "https://bhashabridge.example.app"  # comma-separated

    # Storage / privacy
    hash_salt: SecretStr = SecretStr("")
    database_path: str = "data/bhashabridge.db"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def wa_graph_base_url(self) -> str:
        return f"https://graph.facebook.com/{self.wa_graph_version}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
