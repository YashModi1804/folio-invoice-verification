from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///data/folio.db"
    storage_dir: Path = Path("data/documents")
    operator_token: SecretStr = SecretStr("local-demo-only")
    operator_name: str = "Demo operator"
    provider: Literal["fixture", "gemini"] = "fixture"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    max_file_bytes: int = 20 * 1024 * 1024
    max_pages: int = 20
    retention_days: int = 7
    confidence_threshold: float = 0.85
    provider_timeout_seconds: int = 45


settings = Settings()
