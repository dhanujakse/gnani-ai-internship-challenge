"""Settings from environment variables (or .env for local runs)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gnani_api_key: SecretStr = SecretStr("")
    gnani_base_url: str = "https://api.vachana.ai"
    tts_model: Literal["timbre-v2.5", "timbre-v3.0"] = "timbre-v2.5"
    cache_path: str = "cache/kuralcheck.sqlite"
    language_code: str = "ta-IN"


@lru_cache
def get_settings() -> Settings:
    return Settings()
