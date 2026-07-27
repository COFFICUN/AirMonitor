"""Tests for the health-check endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_application


EXPECTED_RESPONSE = {
    "status": "ok",
    "service": "airmonitor-api",
    "version": "2.0.0",
}


def test_health_returns_expected_response_with_conflicting_ambient_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The health endpoint returns the public service status contract."""
    conflicting_settings = {
        "AIRMONITOR_APP_NAME": "Ambient Sentinel Application",
        "AIRMONITOR_APP_VERSION": "99.99.99-ambient",
        "AIRMONITOR_SERVICE_NAME": "ambient-sentinel-service",
        "AIRMONITOR_ENVIRONMENT": "test",
        "AIRMONITOR_DEBUG": "true",
        "AIRMONITOR_API_PREFIX": "/ambient-sentinel",
        "AIRMONITOR_DATABASE_URL": (
            "postgresql+asyncpg://ambient_sentinel@localhost/"
            "airmonitor_health_test_ambient"
        ),
        "AIRMONITOR_DATABASE_ECHO": "false",
        "AIRMONITOR_DATABASE_POOL_PRE_PING": "false",
    }
    for name, value in conflicting_settings.items():
        monkeypatch.setenv(name, value)

    settings = Settings(
        app_name="AirMonitor API",
        app_version=EXPECTED_RESPONSE["version"],
        service_name=EXPECTED_RESPONSE["service"],
        environment="test",
        debug=False,
        api_prefix="/api/v1",
        database_url=(
            "postgresql+asyncpg://health_test@localhost/"
            "airmonitor_health_test_isolated"
        ),
        database_echo=False,
        database_pool_pre_ping=True,
        _env_file=None,
    )
    client = TestClient(create_application(settings))
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == EXPECTED_RESPONSE
    assert response.headers["content-type"] == "application/json"
