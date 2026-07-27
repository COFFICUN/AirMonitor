"""Centralized application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIRECTORY: Path = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and backend/.env."""

    app_name: str = "AirMonitor API"
    app_version: str = "2.0.0"
    service_name: str = "airmonitor-api"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+asyncpg://airmonitor:airmonitor@localhost:5432/airmonitor"
    )
    database_echo: bool = False
    database_pool_pre_ping: bool = True

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Restrict database access to the configured asynchronous driver."""
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "database_url must use the postgresql+asyncpg driver"
            )
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> Self:
        """Reject diagnostic and development defaults in production."""
        if self.environment != "production":
            return self
        if self.debug:
            raise ValueError("debug must be disabled in production")
        if self.database_echo:
            raise ValueError("database_echo must be disabled in production")
        default_database_url = type(self).model_fields[
            "database_url"
        ].default
        if self.database_url == default_database_url:
            raise ValueError(
                "database_url must be explicitly configured in production"
            )
        return self

    model_config = SettingsConfigDict(
        env_prefix="AIRMONITOR_",
        env_file=BACKEND_DIRECTORY / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Return the shared application settings instance."""
    return Settings()
