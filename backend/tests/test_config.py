"""Tests for centralized application configuration."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pytest import MonkeyPatch

from app.core.config import Settings
from app.main import create_application


ENVIRONMENT_VARIABLES = (
    "AIRMONITOR_APP_NAME",
    "AIRMONITOR_APP_VERSION",
    "AIRMONITOR_SERVICE_NAME",
    "AIRMONITOR_ENVIRONMENT",
    "AIRMONITOR_DEBUG",
    "AIRMONITOR_API_PREFIX",
    "AIRMONITOR_DATABASE_URL",
    "AIRMONITOR_DATABASE_ECHO",
    "AIRMONITOR_DATABASE_POOL_PRE_PING",
)


def clear_settings_environment(monkeypatch: MonkeyPatch) -> None:
    """Remove supported overrides so defaults can be tested in isolation."""
    for variable_name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable_name, raising=False)


def default_database_url() -> str:
    value = Settings.model_fields["database_url"].default
    assert isinstance(value, str)
    return value


def non_default_database_url() -> str:
    return f"{default_database_url()}_production"


def sensitive_database_url(
    username: str,
    password: str,
    sentinel: str,
) -> str:
    driver = default_database_url().split("://", maxsplit=1)[0]
    return f"{driver}://{username}:{password}@invalid/{sentinel}"


def test_settings_defaults(monkeypatch: MonkeyPatch) -> None:
    clear_settings_environment(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.app_name == "AirMonitor API"
    assert settings.app_version == "2.0.0"
    assert settings.service_name == "airmonitor-api"
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.api_prefix == "/api/v1"
    assert settings.database_url == (
        "postgresql+asyncpg://airmonitor:airmonitor@localhost:5432/airmonitor"
    )
    assert settings.database_echo is False
    assert settings.database_pool_pre_ping is True


def test_settings_environment_variable_overrides(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("AIRMONITOR_APP_NAME", "AirMonitor Test API")
    monkeypatch.setenv("AIRMONITOR_APP_VERSION", "2.1.0")
    monkeypatch.setenv("AIRMONITOR_SERVICE_NAME", "airmonitor-test-api")
    monkeypatch.setenv("AIRMONITOR_ENVIRONMENT", "test")
    monkeypatch.setenv("AIRMONITOR_DEBUG", "true")
    monkeypatch.setenv("AIRMONITOR_API_PREFIX", "/test/api")

    settings = Settings(_env_file=None)

    assert settings.app_name == "AirMonitor Test API"
    assert settings.app_version == "2.1.0"
    assert settings.service_name == "airmonitor-test-api"
    assert settings.environment == "test"
    assert settings.debug is True
    assert settings.api_prefix == "/test/api"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [("true", True), ("false", False)],
)
def test_settings_parses_debug_boolean(
    monkeypatch: MonkeyPatch,
    raw_value: str,
    expected: bool,
) -> None:
    monkeypatch.setenv("AIRMONITOR_DEBUG", raw_value)

    settings = Settings(_env_file=None)

    assert settings.debug is expected


def test_settings_rejects_invalid_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("AIRMONITOR_ENVIRONMENT", "staging")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_production_rejects_debug() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            debug=True,
            database_url=non_default_database_url(),
            _env_file=None,
        )


def test_production_rejects_database_echo() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            database_echo=True,
            database_url=non_default_database_url(),
            _env_file=None,
        )


def test_production_rejects_unchanged_default_database_url() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            database_url=default_database_url(),
            _env_file=None,
        )


def test_safe_explicit_production_configuration_is_accepted() -> None:
    settings = Settings(
        environment="production",
        debug=False,
        database_echo=False,
        database_url=non_default_database_url(),
        _env_file=None,
    )

    assert settings.environment == "production"
    assert settings.debug is False
    assert settings.database_echo is False
    assert settings.database_url != default_database_url()


@pytest.mark.parametrize("environment", ["development", "test"])
def test_non_production_settings_retain_diagnostic_defaults(
    environment: str,
) -> None:
    settings = Settings(
        environment=environment,
        debug=True,
        database_echo=True,
        database_url=default_database_url(),
        _env_file=None,
    )

    assert settings.environment == environment
    assert settings.debug is True
    assert settings.database_echo is True
    assert settings.database_url == default_database_url()


def test_production_validation_hides_sensitive_inputs_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    username = "PHASE_C2B_USERNAME_SENTINEL"
    password = "PHASE_C2B_PASSWORD_SENTINEL"
    sentinel = "PHASE_C2B_DATABASE_SENTINEL"
    database_url = sensitive_database_url(username, password, sentinel)

    with pytest.raises(ValidationError) as error_info:
        Settings(
            environment="production",
            debug=True,
            database_url=database_url,
            _env_file=None,
        )

    error_text = str(error_info.value).casefold()
    captured_logs = caplog.text.casefold()
    for marker in (username, password, sentinel):
        assert marker.casefold() not in error_text
        assert marker.casefold() not in captured_logs


def test_application_metadata_uses_supplied_settings() -> None:
    settings = Settings(
        app_name="Configured AirMonitor API",
        app_version="3.0.0",
        debug=True,
        _env_file=None,
    )

    application = create_application(settings)

    assert application.title == "Configured AirMonitor API"
    assert application.version == "3.0.0"
    assert application.debug is True
    assert application.state.settings is settings


def test_health_uses_supplied_settings() -> None:
    settings = Settings(
        app_version="3.0.0",
        service_name="configured-airmonitor-api",
        _env_file=None,
    )
    client = TestClient(create_application(settings))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "configured-airmonitor-api",
        "version": "3.0.0",
    }
