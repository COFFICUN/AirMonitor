"""Centralized application configuration."""

from functools import lru_cache
from ipaddress import IPv6Address, ip_address
from pathlib import Path
from typing import Literal, Self
from urllib.parse import unquote

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


BACKEND_DIRECTORY: Path = Path(__file__).resolve().parents[2]
_DATABASE_DRIVER = "postgresql+asyncpg"
_POSTGRESQL_DEFAULT_PORT = 5432
_ASCII_WHITESPACE = " \t\n\r\v\f"
_HEXADECIMAL_DIGITS = frozenset("0123456789abcdef")
_TARGET_IDENTITY_QUERY_KEYS = frozenset(
    {
        "host",
        "port",
        "database",
        "dbname",
        "user",
        "username",
        "password",
        "passfile",
        "service",
        "servicefile",
    }
)


def _parse_database_url(value: str) -> URL:
    try:
        return make_url(value)
    except (ArgumentError, ValueError):
        raise ValueError("database_url is invalid") from None


def _normalized_host_identity(
    host: str | None,
) -> tuple[bool, str | None]:
    if host is None:
        return False, None

    normalized_host = unquote(host).casefold().rstrip(".")
    if normalized_host == "localhost":
        return True, None

    try:
        address = ip_address(normalized_host)
    except ValueError:
        return False, normalized_host

    mapped_address = (
        address.ipv4_mapped if isinstance(address, IPv6Address) else None
    )
    if address.is_loopback or (
        mapped_address is not None and mapped_address.is_loopback
    ):
        return True, None
    return False, normalized_host


def _database_target_identity(
    database_url: URL,
) -> tuple[
    str,
    str | None,
    str | None,
    tuple[bool, str | None],
    int,
    str | None,
]:
    try:
        port = database_url.port
    except ValueError:
        raise ValueError("database_url is invalid") from None

    database_name = (
        unquote(database_url.database)
        if database_url.database is not None
        else None
    )
    return (
        database_url.drivername.casefold(),
        database_url.username,
        database_url.password,
        _normalized_host_identity(database_url.host),
        port if port is not None else _POSTGRESQL_DEFAULT_PORT,
        database_name,
    )


def _has_target_identity_query_key(database_url: URL) -> bool:
    return any(
        unquote(query_key).casefold() in _TARGET_IDENTITY_QUERY_KEYS
        for query_key in database_url.query
    )


def _is_ambiguous_production_host(host: str) -> bool:
    decoded_host = unquote(host)
    if not decoded_host.isascii() or any(
        character in _ASCII_WHITESPACE
        for character in decoded_host
    ):
        return True

    normalized_host = decoded_host.casefold().rstrip(".")
    try:
        address = ip_address(normalized_host)
    except ValueError:
        components = normalized_host.split(".")
        if not 1 <= len(components) <= 4:
            return False
        return all(
            component.isascii()
            and (
                component.isdecimal()
                or (
                    component.startswith("0x")
                    and len(component) > 2
                    and all(
                        digit in _HEXADECIMAL_DIGITS
                        for digit in component[2:]
                    )
                )
            )
            for component in components
        )
    mapped_address = (
        address.ipv4_mapped if isinstance(address, IPv6Address) else None
    )
    return address.is_unspecified or (
        mapped_address is not None and mapped_address.is_unspecified
    )


def _validate_explicit_production_target(database_url: URL) -> None:
    try:
        port = database_url.port
    except ValueError:
        raise ValueError("database_url is invalid") from None

    host = database_url.host
    if (
        not database_url.username
        or not database_url.password
        or not host
        or port is None
        or not database_url.database
        or "," in unquote(host)
        or _is_ambiguous_production_host(host)
    ):
        raise ValueError(
            "database_url must explicitly identify a single production target"
        )


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and backend/.env."""

    app_name: str = "AirMonitor API"
    app_version: str = "2.0.0"
    service_name: str = "airmonitor-api"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    database_url: str = (
        "postgresql+asyncpg://airmonitor:airmonitor@localhost:5432/airmonitor"
    )
    database_echo: bool = False
    database_pool_pre_ping: bool = True

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Restrict database access to the configured asynchronous driver."""
        database_url = _parse_database_url(value)
        if database_url.drivername != _DATABASE_DRIVER:
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
        candidate_database_url = _parse_database_url(self.database_url)
        if _has_target_identity_query_key(candidate_database_url):
            raise ValueError("database_url has ambiguous target options")
        candidate_host = candidate_database_url.host
        if candidate_host is not None and _is_ambiguous_production_host(
            candidate_host
        ):
            raise ValueError(
                "database_url must explicitly identify a single production target"
            )
        default_database_url = type(self).model_fields[
            "database_url"
        ].default
        if not isinstance(default_database_url, str):
            raise ValueError("database_url is invalid")
        default_target = _parse_database_url(default_database_url)
        if _database_target_identity(
            candidate_database_url
        ) == _database_target_identity(default_target):
            raise ValueError(
                "database_url must be explicitly configured in production"
            )
        _validate_explicit_production_target(candidate_database_url)
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
