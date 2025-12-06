"""Application configuration management."""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "AIOps Agent Executor"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # Database
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/aiops_agent_executor"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Security
    secret_key: str = "change-me-in-production-with-a-secure-random-key"
    encryption_key: str = "dev-encryption-key-32-bytes!!!!!"  # Exactly 32 bytes
    access_token_expire_minutes: int = 30

    # CORS
    cors_origins: list[str] = ["*"]

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """Ensure encryption key is exactly 32 bytes for AES-256."""
        if len(v.encode()) != 32:
            raise ValueError("Encryption key must be exactly 32 bytes")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
