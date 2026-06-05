from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, PostgresDsn, field_validator
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
    APP_ALLOWED_ORIGINS: list[AnyHttpUrl] = []
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

    # Storage
    STORAGE_BACKEND: Literal["filesystem", "s3", "azure"] = "filesystem"
    STORAGE_LOCAL_PATH: str = "/tmp/celerius-storage"
    AWS_S3_BUCKET: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AZURE_STORAGE_CONNECTION_STRING: str = ""
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

    # Pagination
    DEFAULT_PAGE_SIZE: int = 25
    MAX_PAGE_SIZE: int = 100

    @field_validator("APP_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list) -> list:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
