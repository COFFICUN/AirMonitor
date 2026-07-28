"""Offline tests for the disposable-database URL guard."""

from __future__ import annotations

import asyncio
from pathlib import Path
import runpy
from typing import Any

import pytest
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError

from tests.persistence_guard import (
    PersistenceTargetError,
    validate_persistence_database_url,
)


SAFE_URL = (
    "postgresql+asyncpg://integration_user"
    "@localhost:5432/airmonitor_persistence_test_guard"
)
PERSISTENCE_INTEGRATION_MODULE = Path(__file__).with_name(
    "test_persistence_integration.py"
)
MISSING_DEDICATED_URL_MESSAGE = (
    "Persistence integration tests require the dedicated database URL."
)


def _run_persistence_integration_module(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dedicated_url: str | None,
    application_url: str | None,
) -> dict[str, Any]:
    monkeypatch.setenv("AIRMONITOR_RUN_PERSISTENCE_INTEGRATION", "1")
    if dedicated_url is None:
        monkeypatch.delenv("AIRMONITOR_TEST_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("AIRMONITOR_TEST_DATABASE_URL", dedicated_url)
    if application_url is None:
        monkeypatch.delenv("AIRMONITOR_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("AIRMONITOR_DATABASE_URL", application_url)

    return runpy.run_path(str(PERSISTENCE_INTEGRATION_MODULE))


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


def test_persistence_suite_uses_dedicated_database_url_when_opted_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = _run_persistence_integration_module(
        monkeypatch,
        dedicated_url=SAFE_URL,
        application_url=None,
    )

    parsed = namespace["_parsed_database_url"]
    assert isinstance(parsed, URL)
    assert parsed.database == "airmonitor_persistence_test_guard"


def test_application_database_url_alone_cannot_configure_persistence_suite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(pytest.fail.Exception) as raised:
        _run_persistence_integration_module(
            monkeypatch,
            dedicated_url=None,
            application_url=SAFE_URL,
        )

    failure = raised.value
    assert str(failure) == MISSING_DEDICATED_URL_MESSAGE
    assert failure.pytrace is False
    assert SAFE_URL not in str(failure)


def test_persistence_suite_ignores_application_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application_sentinel_url = (
        "postgresql+asyncpg://APPLICATION_SENTINEL"
        "@remote.example.test/airmonitor_persistence_test_application"
    )

    namespace = _run_persistence_integration_module(
        monkeypatch,
        dedicated_url=SAFE_URL,
        application_url=application_sentinel_url,
    )

    parsed = namespace["_parsed_database_url"]
    assert isinstance(parsed, URL)
    assert parsed.database == "airmonitor_persistence_test_guard"


def test_dedicated_database_url_uses_existing_target_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dedicated_sentinel_url = (
        "postgresql+asyncpg://DEDICATED_SENTINEL"
        "@remote.example.test/airmonitor_persistence_test_guard"
    )

    with pytest.raises(pytest.fail.Exception) as raised:
        _run_persistence_integration_module(
            monkeypatch,
            dedicated_url=dedicated_sentinel_url,
            application_url=SAFE_URL,
        )

    failure_message = str(raised.value)
    assert failure_message == (
        "Persistence integration database host is not approved."
    )
    assert dedicated_sentinel_url not in failure_message
    assert "DEDICATED_SENTINEL" not in failure_message


def test_persistence_preflight_failure_is_sanitized_without_exception_chaining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = _run_persistence_integration_module(
        monkeypatch,
        dedicated_url=SAFE_URL,
        application_url=SAFE_URL,
    )

    class FakeEngine:
        disposed = False

        async def dispose(self) -> None:
            self.disposed = True

    engine = FakeEngine()
    username = "SENTINEL_USERNAME"
    password = "SENTINEL_PASSWORD"
    database_name = "airmonitor_persistence_test_SENTINEL_DATABASE"
    query_parameter = "ssl=SENTINEL_QUERY"
    database_url = (
        f"postgresql+asyncpg://{username}:{password}"
        f"@localhost:5432/{database_name}?{query_parameter}"
    )
    driver_text = "SENTINEL_ASYNCPG_DRIVER_TEXT"
    sql_text = "SELECT SENTINEL_SQL_TEXT"
    filesystem_path = "C:/SENTINEL/filesystem/path"
    arbitrary_text = "SENTINEL_ARBITRARY_TEXT"

    async def failing_preflight(unused_engine: object) -> None:
        assert unused_engine is engine
        origin = RuntimeError(
            "; ".join(
                (
                    database_url,
                    username,
                    password,
                    database_name,
                    query_parameter,
                    driver_text,
                    sql_text,
                    filesystem_path,
                    arbitrary_text,
                )
            )
        )
        raise OperationalError(sql_text, {}, origin)

    fixture_function = namespace["session_factory"].__wrapped__
    fixture_globals = fixture_function.__globals__

    def fail_if_asyncpg_connects(*args: object, **kwargs: object) -> None:
        raise AssertionError("A PostgreSQL connection was attempted")

    monkeypatch.setattr("asyncpg.connect", fail_if_asyncpg_connects)
    monkeypatch.setitem(
        fixture_globals,
        "create_async_engine",
        lambda *args, **kwargs: engine,
    )
    monkeypatch.setitem(
        fixture_globals,
        "async_sessionmaker",
        lambda **kwargs: object(),
    )
    monkeypatch.setitem(
        fixture_globals,
        "_preflight_disposable_database",
        failing_preflight,
    )
    fixture_generator = fixture_function("asyncio")

    with pytest.raises(pytest.fail.Exception) as raised:
        asyncio.run(anext(fixture_generator))

    failure = raised.value
    failure_message = str(failure)
    assert engine.disposed is True
    assert failure.pytrace is False
    assert failure.__cause__ is None
    assert failure.__context__ is None
    assert failure.__suppress_context__ is True
    assert failure_message == (
        "Persistence integration database preflight failed."
    )
    for secret in (
        database_url,
        username,
        password,
        database_name,
        query_parameter,
        driver_text,
        sql_text,
        filesystem_path,
        arbitrary_text,
        "OperationalError",
        "RuntimeError",
    ):
        assert secret not in failure_message
