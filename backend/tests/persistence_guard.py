"""Pure validation for disposable PostgreSQL integration targets."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


APPROVED_DRIVER = "postgresql+asyncpg"
APPROVED_HOSTS = frozenset({"localhost", "127.0.0.1"})
DATABASE_PREFIX = "airmonitor_persistence_test_"
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


class PersistenceTargetError(ValueError):
    """Raised when an integration target is not provably disposable."""


async def run_persistence_preflight_safely(
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
        "Persistence integration database preflight failed.",
        pytrace=False,
    )
    raise failure from None


def validate_persistence_database_url(value: str) -> URL:
    """Return a validated local disposable target without exposing its text."""
    try:
        parsed = make_url(value)
    except (ArgumentError, TypeError):
        raise PersistenceTargetError(
            "Persistence integration database URL is invalid."
        ) from None

    query_keys = {key.casefold() for key in parsed.query}
    if query_keys.intersection(TARGET_AFFECTING_QUERY_KEYS):
        raise PersistenceTargetError(
            "Persistence integration database URL contains a forbidden "
            "target override."
        )
    if parsed.drivername != APPROVED_DRIVER:
        raise PersistenceTargetError(
            "Persistence integration database driver is not approved."
        )
    if parsed.host not in APPROVED_HOSTS:
        raise PersistenceTargetError(
            "Persistence integration database host is not approved."
        )
    if (
        parsed.database is None
        or not parsed.database.startswith(DATABASE_PREFIX)
    ):
        raise PersistenceTargetError(
            "Persistence integration database name is not approved."
        )

    return parsed


__all__ = [
    "PersistenceTargetError",
    "run_persistence_preflight_safely",
    "validate_persistence_database_url",
]
