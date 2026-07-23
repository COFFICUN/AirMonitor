"""Offline tests for the disposable-database URL guard."""

from __future__ import annotations

import pytest
from sqlalchemy.engine import URL

from tests.persistence_guard import (
    PersistenceTargetError,
    validate_persistence_database_url,
)


SAFE_URL = (
    "postgresql+asyncpg://integration_user"
    "@localhost:5432/airmonitor_persistence_test_guard"
)


def test_validator_returns_sqlalchemy_url_for_approved_target() -> None:
    parsed = validate_persistence_database_url(SAFE_URL)

    assert isinstance(parsed, URL)
    assert parsed.drivername == "postgresql+asyncpg"
    assert parsed.host == "localhost"
    assert parsed.database == "airmonitor_persistence_test_guard"


def test_validator_allows_non_target_connection_options() -> None:
    parsed = validate_persistence_database_url(
        f"{SAFE_URL}?ssl=disable&application_name=airmonitor-tests"
    )

    assert parsed.query["ssl"] == "disable"
    assert parsed.query["application_name"] == "airmonitor-tests"


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://localhost/airmonitor_persistence_test_guard",
        "sqlite+aiosqlite:///airmonitor_persistence_test_guard",
    ],
)
def test_validator_rejects_wrong_driver(database_url: str) -> None:
    with pytest.raises(PersistenceTargetError):
        validate_persistence_database_url(database_url)


@pytest.mark.parametrize(
    "database_url",
    [
        (
            "postgresql+asyncpg://remote.example.test/"
            "airmonitor_persistence_test_guard"
        ),
        "postgresql+asyncpg:///airmonitor_persistence_test_guard",
        (
            "postgresql+asyncpg://[::1]/"
            "airmonitor_persistence_test_guard"
        ),
    ],
)
def test_validator_rejects_wrong_or_missing_host(database_url: str) -> None:
    with pytest.raises(PersistenceTargetError):
        validate_persistence_database_url(database_url)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://localhost/airmonitor",
        "postgresql+asyncpg://localhost/persistence_test_guard",
        "postgresql+asyncpg://localhost",
    ],
)
def test_validator_rejects_wrong_or_missing_database_name(
    database_url: str,
) -> None:
    with pytest.raises(PersistenceTargetError):
        validate_persistence_database_url(database_url)


@pytest.mark.parametrize(
    "query_key",
    [
        "host",
        "PORT",
        "DataBase",
        "DBNAME",
        "dSn",
        "SeRvIcE",
    ],
)
def test_validator_rejects_case_insensitive_target_query_overrides(
    query_key: str,
) -> None:
    with pytest.raises(PersistenceTargetError):
        validate_persistence_database_url(
            f"{SAFE_URL}?{query_key}=remote.example.test"
        )


@pytest.mark.parametrize(
    "database_url",
    [
        "not-a-database-url-with-URL_SENTINEL",
        (
            "postgresql+asyncpg://URL_SENTINEL@remote.example.test/"
            "airmonitor_persistence_test_guard"
        ),
        (
            "postgresql+asyncpg://URL_SENTINEL@localhost/"
            "airmonitor?host=remote.example.test"
        ),
    ],
)
def test_validation_errors_never_include_database_url_or_target_details(
    database_url: str,
) -> None:
    with pytest.raises(PersistenceTargetError) as raised:
        validate_persistence_database_url(database_url)

    message = str(raised.value)
    assert database_url not in message
    assert "URL_SENTINEL" not in message
    assert raised.value.__cause__ is None
