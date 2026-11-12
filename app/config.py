"""Configuration settings for FireChronicle Backend."""

from functools import lru_cache
import json
from pathlib import Path
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings with environment variable override."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # CORS settings
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://firechronicle.vercel.app",
        "*",
    ]

    # Paths
    DATA_DIR: Path = BACKEND_ROOT / "data"
    DUCKDB_PATH: str = ":memory:"

    # ML Model remote connection settings
    ML_MODEL_API_URL: Union[str, None] = None
    ML_MODEL_API_KEY: Union[str, None] = "firechronicle_ml_secret_key_2026"
    ML_MODEL_TIMEOUT_SECONDS: float = 5.0

    # ML Model Webhook / Sync API Key
    WEBHOOK_API_KEY: str = "firechronicle_webhook_sync_key_2026"

    # Region Guardrail Constant
    ANALYSIS_REGION_ID: str = "BR-PA"
    ANALYSIS_REGION_NAME: str = "Pará, Brazil"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @field_validator("DATA_DIR", mode="before")
    @classmethod
    def resolve_data_dir(cls, v: Union[str, Path]) -> Path:
        p = Path(v)
        if not p.is_absolute():
            return (BACKEND_ROOT / p).resolve()
        return p.resolve()


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
