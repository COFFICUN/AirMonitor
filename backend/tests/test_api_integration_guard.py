"""Offline tests for the Sprint 7 API integration URL guard."""

import asyncio
from pathlib import Path

import pytest
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError

from tests.api_integration_guard import (
    ApiIntegrationTargetError,
    run_api_preflight_safely,
    validate_api_test_database_url,
)


SAFE_URL = (
    "postgresql+asyncpg://integration_user"
    "@localhost:5432/airmonitor_api_test_guard"
)


def test_validator_accepts_only_local_asyncpg_disposable_target() -> None:
    parsed = validate_api_test_database_url(SAFE_URL)

    assert isinstance(parsed, URL)
    assert parsed.drivername == "postgresql+asyncpg"
    assert parsed.host == "localhost"
    assert parsed.database == "airmonitor_api_test_guard"


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://localhost/airmonitor_api_test_guard",
        "sqlite+aiosqlite:///airmonitor_api_test_guard",
        (
            "postgresql+asyncpg://remote.example.test/"
            "airmonitor_api_test_guard"
        ),
        "postgresql+asyncpg:///airmonitor_api_test_guard",
        "postgresql+asyncpg://localhost/airmonitor",
        "postgresql+asyncpg://localhost/api_test_guard",
        "postgresql+asyncpg://localhost",
        (
            "postgresql+asyncpg://localhost/"
            "airmonitor_api_test_guard?host=remote.example.test"
        ),
    ],
)
def test_validator_rejects_every_unapproved_target(
    database_url: str,
) -> None:
    with pytest.raises(ApiIntegrationTargetError):
        validate_api_test_database_url(database_url)


def test_validation_errors_never_expose_target_details() -> None:
    database_url = (
        "postgresql+asyncpg://SECRET_USER:SECRET_PASSWORD"
        "@remote.example.test/airmonitor_api_test_guard"
    )

    with pytest.raises(ApiIntegrationTargetError) as raised:
        validate_api_test_database_url(database_url)

    message = str(raised.value)
    assert database_url not in message
    assert "SECRET" not in message
    assert raised.value.__cause__ is None


def test_live_suite_never_reads_protected_application_url_variable() -> None:
    integration_sources = [
        Path(__file__).with_name("test_api_integration.py"),
        Path(__file__).with_name("api_integration_runtime.py"),
    ]
    integration_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in integration_sources
    )
    protected_variable = "AIRMONITOR_" + "DATABASE_URL"

    assert protected_variable not in integration_source
    assert "AIRMONITOR_API_TEST_DATABASE_URL" in integration_source
    assert "run_api_preflight_safely" in integration_source
    assert "raise_app_exceptions=False" in integration_source


def test_unavailable_database_failure_never_exposes_connection_secrets() -> None:
    database_name = "airmonitor_api_test_security_regression"
    username = "LEAKED_DATABASE_USERNAME"
    password = "LEAKED_DATABASE_PASSWORD"
    database_url = (
        f"postgresql+asyncpg://{username}:{password}"
        f"@localhost:5432/{database_name}"
    )
    connection_parameters = (
        "ConnectionParameters("
        f"user={username!r}, password={password!r}, "
        f"database={database_name!r})"
    )

    async def failing_preflight() -> None:
        origin = RuntimeError(
            f"{connection_parameters}; target={database_url}"
        )
        raise OperationalError("CONNECT", {}, origin)

    with pytest.raises(pytest.fail.Exception) as raised:
        asyncio.run(
            run_api_preflight_safely(
                failing_preflight,
            )
        )

    failure = raised.value
    failure_message = str(failure)
    assert not isinstance(failure, pytest.skip.Exception)
    assert failure.pytrace is False
    assert failure.__cause__ is None
    assert failure.__context__ is None
    assert failure.__suppress_context__ is True
    assert len(failure_message) < 180
    assert failure_message == "API integration database preflight failed."
    for secret in (
        database_url,
        username,
        password,
        database_name,
        connection_parameters,
        "OperationalError",
        "RuntimeError",
        "CONNECT",
    ):
        assert secret not in failure_message
