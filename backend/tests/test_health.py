"""Tests for the health-check endpoint."""

from fastapi.testclient import TestClient

from app.main import create_application


EXPECTED_RESPONSE = {
    "status": "ok",
    "service": "airmonitor-api",
    "version": "2.0.0",
}


def test_health_returns_expected_response() -> None:
    """The health endpoint returns the public service status contract."""
    client = TestClient(create_application())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == EXPECTED_RESPONSE
    assert response.headers["content-type"] == "application/json"
