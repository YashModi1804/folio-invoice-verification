from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///data/folio.db"
    storage_dir: Path = Path("data/documents")
    source_storage: Literal["file", "database"] = "file"
    embedded_worker: bool = False
    public_demo: bool = False
    guest_enabled: bool = False
    guest_upload_retention_minutes: int = 120
    guest_uploads_per_guest_day: int = 2
    guest_uploads_per_day: int = 20
    guest_queue_limit: int = 10
    guest_max_file_bytes: int = 5 * 1024 * 1024
    guest_max_pages: int = 3
    operator_token: SecretStr = SecretStr("local-demo-only")
    operator_name: str = "Demo operator"
    provider: Literal["fixture", "gemini", "groq", "ollama"] = "fixture"
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "qwen/qwen3.8-27b"
    groq_tokens_per_minute: int = 8_000
    groq_image_tokens: int = 2_048
    groq_request_overhead_tokens: int = 1_200
    groq_output_reserve_tokens: int = 1_400
    ollama_model: str = "qwen3-vl:4b-instruct"
    ollama_timeout_seconds: int = 240
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    gemini_thinking_level: Literal["", "minimal", "low", "medium", "high"] = ""
    local_fallback_enabled: bool = False
    max_file_bytes: int = 20 * 1024 * 1024
    max_pages: int = 20
    retention_days: int = 7
    confidence_threshold: float = 0.85
    provider_timeout_seconds: int = 90

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


settings = Settings()
