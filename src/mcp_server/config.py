"""
Configuration management using pydantic-settings.
Loads environment variables from .env and environment.
"""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration and database connection settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    max_request_bytes: int = Field(default=1048576, alias="MAX_REQUEST_BYTES")

    # Database URLs
    database_url: str = Field(
        ...,
        alias="DATABASE_URL",
        description="Standard tenant database connection using app_user (strictly subject to RLS)",
    )
    migration_database_url: str = Field(
        ...,
        alias="MIGRATION_DATABASE_URL",
        description="Owner/superuser connection using postgres for DDL operations and migrations",
    )
    admin_database_url: str | None = Field(
        default=None,
        alias="ADMIN_DATABASE_URL",
        description="Dedicated admin pool for system inspection",
    )

    # Redis settings
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
        description="Redis connection URL for rate limiting and sessions",
    )

    # Hardcoded test user ID for Phase 2
    test_user_id: str = Field(
        default="00000000-0000-0000-0000-000000000001",
        alias="TEST_USER_ID",
        description="Default hardcoded tenant UUID for Phase 2 development",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()


# Singleton settings instance
settings = get_settings()
