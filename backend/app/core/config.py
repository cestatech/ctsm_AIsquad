from __future__ import annotations

from functools import lru_cache
from typing import Literal

import json

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_NAME: str = "TrialGenesis Clinical Trial Platform"
    APP_VERSION: str = "0.1.0"
    APP_SECRET_KEY: str
    APP_ALLOWED_ORIGINS: str = "http://localhost:3000"
    APP_DEBUG: bool = False

    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Auth rate limiting
    AUTH_MAX_FAILED_ATTEMPTS: int = 5
    AUTH_LOCKOUT_MINUTES: int = 15
    AUTH_IP_MAX_FAILED_ATTEMPTS: int = 5
    AUTH_IP_WINDOW_MINUTES: int = 15

    # Storage
    STORAGE_BACKEND: Literal["filesystem", "azure"] = "filesystem"
    STORAGE_LOCAL_PATH: str = "/tmp/celerius-storage"
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_ACCOUNT_NAME: str = ""
    AZURE_STORAGE_SAS_TOKEN: str = ""
    AZURE_CONTAINER_NAME: str = ""

    # Email
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM: str = "noreply@trialgenesis.dev"
    SMTP_TLS: bool = False
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""

    # AI generation
    ANTHROPIC_API_KEY: str = ""
    AI_MAX_CONCURRENT_JOBS: int = 5
    AI_JOB_TIMEOUT_SECONDS: int = 300

    # Pinnacle 21 CDISC conformance (license purchased separately)
    PINNACLE21_ENABLED: bool = False
    PINNACLE21_API_BASE_URL: str = "https://api.pinnacle21.com"
    PINNACLE21_API_KEY: str = ""
    PINNACLE21_PROJECT_ID: str = ""
    PINNACLE21_RULE_SET_VERSION: str = "CE 3.1"
    SDTM_IG_VERSION: str = "3.3"
    ADAM_IG_VERSION: str = "1.3"

    # Pagination
    DEFAULT_PAGE_SIZE: int = 25
    MAX_PAGE_SIZE: int = 100

    @staticmethod
    def parse_origins(v: str | list) -> list[str]:
        """Parse CORS origins from env string (comma-separated or JSON array)."""
        origins: list[str]
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    origins = [str(item) for item in parsed]
                except json.JSONDecodeError:
                    origins = [
                        part.strip() for part in stripped.split(",") if part.strip()
                    ]
            else:
                origins = [part.strip() for part in stripped.split(",") if part.strip()]
        else:
            origins = [str(item) for item in v]
        return [origin.rstrip("/") for origin in origins if origin]

    @property
    def allowed_origins(self) -> list[str]:
        """Normalized CORS allowlist without trailing slashes."""
        return self.parse_origins(self.APP_ALLOWED_ORIGINS)

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def pinnacle21_configured(self) -> bool:
        """True when Pinnacle 21 credentials are set and integration is enabled."""
        return self.PINNACLE21_ENABLED and bool(self.PINNACLE21_API_KEY.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
