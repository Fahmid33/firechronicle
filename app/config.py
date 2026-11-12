"""Configuration settings for FireChronicle Backend."""

from functools import lru_cache
import json
import os
from pathlib import Path
from typing import List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings with environment variable override."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # CORS settings: restricted to explicit FRONTEND_URL origin(s), never wildcard "*"
    FRONTEND_URL: str = Field(default_factory=lambda: os.getenv("FRONTEND_URL", "http://localhost:3000"))
    CORS_ORIGINS: Union[List[str], str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv("FRONTEND_URL", "http://localhost:3000").split(",")
            if origin.strip() and origin.strip() != "*"
        ]
    )

    # Paths
    DATA_DIR: Path = BACKEND_ROOT / "data"
    REAL_DATA_DIR: Optional[Path] = Field(
        default_factory=lambda: (
            Path(os.getenv("REAL_DATA_DIR"))
            if os.getenv("REAL_DATA_DIR")
            else (BACKEND_ROOT / "data" / "real")
        )
    )
    DUCKDB_PATH: str = ":memory:"

    # ML Model remote connection settings (strictly loaded from environment, no hardcoded secrets)
    ML_MODEL_API_URL: Optional[str] = Field(default_factory=lambda: os.getenv("ML_MODEL_API_URL"))
    ML_MODEL_API_KEY: Optional[str] = Field(default_factory=lambda: os.getenv("ML_MODEL_API_KEY"))
    ML_MODEL_TIMEOUT_SECONDS: float = 5.0

    # ML Model Webhook / Sync API Key (strictly loaded from environment, no hardcoded secrets)
    WEBHOOK_API_KEY: Optional[str] = Field(default_factory=lambda: os.getenv("WEBHOOK_API_KEY"))

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
                    parsed = json.loads(v)
                    return [str(x).strip() for x in parsed if str(x).strip() and str(x).strip() != "*"]
                except Exception:
                    pass
            return [x.strip() for x in v.split(",") if x.strip() and x.strip() != "*"]
        return [str(x).strip() for x in v if str(x).strip() and str(x).strip() != "*"]

    @field_validator("FRONTEND_URL", mode="before")
    @classmethod
    def sanitize_frontend_url(cls, v: Union[str, None]) -> str:
        cleaned = (v or "http://localhost:3000").strip()
        if cleaned == "*" or not cleaned:
            raise ValueError("FRONTEND_URL cannot be wildcard '*' or empty.")
        return cleaned

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in ("production", "prod")

    @field_validator("DATA_DIR", mode="before")
    @classmethod
    def resolve_data_dir(cls, v: Union[str, Path]) -> Path:
        p = Path(v)
        if not p.is_absolute():
            return (BACKEND_ROOT / p).resolve()
        return p.resolve()

    @field_validator("REAL_DATA_DIR", mode="before")
    @classmethod
    def resolve_real_data_dir(cls, v: Union[str, Path, None]) -> Optional[Path]:
        if v is None or v == "":
            return None
        p = Path(v)
        if not p.is_absolute():
            return (BACKEND_ROOT / p).resolve()
        return p.resolve()


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
