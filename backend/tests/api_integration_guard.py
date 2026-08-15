"""Pure validation for the guarded Sprint 7 HTTP integration target."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


APPROVED_DRIVER = "postgresql+asyncpg"
APPROVED_HOSTS = frozenset({"localhost", "127.0.0.1"})
DATABASE_PREFIX = "airmonitor_api_test_"
PROTECTED_DATABASE = "airmonitor"
TARGET_AFFECTING_QUERY_KEYS = frozenset(
    {
        "database",
        "dbname",
        "dsn",
        "host",
        "port",
        "service",
    }
)


class ApiIntegrationTargetError(ValueError):
    """Raised when an API integration target is not provably disposable."""


async def run_api_preflight_safely(
    preflight: Callable[[], Awaitable[None]],
) -> None:
    """Fail without retaining secret-bearing connection exceptions."""
    try:
        await preflight()
    except Exception:
        pass
    else:
        return

    failure = pytest.fail.Exception(
        "API integration database preflight failed.",
        pytrace=False,
    )
    raise failure from None


def validate_api_test_database_url(value: str) -> URL:
    """Return a validated local disposable target without exposing its text."""
    try:
        parsed = make_url(value)
    except (ArgumentError, TypeError):
        raise ApiIntegrationTargetError(
            "API integration database URL is invalid."
        ) from None

    query_keys = {key.casefold() for key in parsed.query}
    if query_keys.intersection(TARGET_AFFECTING_QUERY_KEYS):
        raise ApiIntegrationTargetError(
            "API integration database URL contains a forbidden "
            "target override."
        )
    if parsed.drivername != APPROVED_DRIVER:
        raise ApiIntegrationTargetError(
            "API integration database driver is not approved."
        )
    if parsed.host not in APPROVED_HOSTS:
        raise ApiIntegrationTargetError(
            "API integration database host is not approved."
        )
    if (
        parsed.database is None
        or parsed.database == PROTECTED_DATABASE
        or not parsed.database.startswith(DATABASE_PREFIX)
    ):
        raise ApiIntegrationTargetError(
            "API integration database name is not approved."
        )

    return parsed


__all__ = [
    "ApiIntegrationTargetError",
    "run_api_preflight_safely",
    "validate_api_test_database_url",
]
