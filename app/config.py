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


settings = Settings()
