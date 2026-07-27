"""Offline HTTP contract tests using dependency-overridden services."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient

from app.api.dependencies import (
    get_active_session_query_service,
    get_device_query_service,
    get_device_service,
    get_measurement_service,
)
from app.core.config import Settings
from app.core.exceptions import (
    ActiveSessionAlreadyExistsError,
    ActiveSessionNotFoundError,
    DeviceInactiveError,
    DeviceNotFoundError,
    DuplicateDeviceUIDError,
    DuplicateSourceMessageError,
    InvalidTimestampError,
)
from app.main import create_application


NOW = datetime(2026, 7, 23, 8, 30, tzinfo=UTC)
POSTGRES_INTEGER_MAX = 2_147_483_647
PARTICLE_COUNTER_FIELDS = (
    "pc0_3",
    "pc0_5",
    "pc1_0",
    "pc2_5",
    "pc5_0",
    "pc10",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def application() -> FastAPI:
    application = create_application(Settings(_env_file=None))
    original_overrides = dict(application.dependency_overrides)
    try:
        yield application
    finally:
        application.dependency_overrides.clear()
        application.dependency_overrides.update(original_overrides)


def _device(*, is_active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        device_uid="monitor-7",
        name="Workshop",
        is_active=is_active,
        created_at=NOW,
        updated_at=NOW,
    )


def _session(
    *,
    status: str = "active",
    ended_at: datetime | None = None,
    sample_count: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=11,
        device_id=7,
        status=status,
        started_at=NOW,
        ended_at=ended_at,
        latitude=51.1694,
        longitude=71.4491,
        sample_count=sample_count,
        created_at=NOW,
        updated_at=NOW,
    )


def _measurement() -> SimpleNamespace:
    return SimpleNamespace(
        id=13,
        device_id=7,
        session_id=11,
        source_message_id="message-13",
        measured_at=NOW,
        received_at=NOW,
        temperature=21.5,
        humidity=44.0,
        pm1=3.0,
        pm25=7.5,
        pm10=12.0,
        pc0_3=100,
        pc0_5=90,
        pc1_0=80,
        pc2_5=70,
        pc5_0=60,
        pc10=50,
        latitude=51.1694,
        longitude=71.4491,
        is_valid=True,
        validation_note=None,
        created_at=NOW,
    )


async def _request(
    application: FastAPI,
    method: str,
    path: str,
    *,
    json: dict[str, object] | None = None,
    content: str | bytes | None = None,
    headers: dict[str, str] | None = None,
):
    transport = ASGITransport(app=application)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(
            method,
            path,
            json=json,
            content=content,
            headers=headers,
        )


PATH_DEVICE_ID_CASES = (
    (
        "get-device",
        "GET",
        "/api/v1/devices/{device_id}",
        None,
        get_device_query_service,
        "get_device",
    ),
    (
        "set-device-status",
        "PATCH",
        "/api/v1/devices/{device_id}/status",
        {"is_active": True},
        get_device_service,
        "activate_device",
    ),
    (
        "start-session",
        "POST",
        "/api/v1/devices/{device_id}/sessions",
        {"latitude": 51.1694, "longitude": 71.4491},
        get_measurement_service,
        "start_session",
    ),
    (
        "get-active-session",
        "GET",
        "/api/v1/devices/{device_id}/sessions/active",
        None,
        get_active_session_query_service,
        "get_active_session",
    ),
    (
        "complete-session",
        "POST",
        "/api/v1/devices/{device_id}/sessions/active/complete",
        {"ended_at": "2026-07-23T08:30:00Z"},
        get_measurement_service,
        "complete_session",
    ),
    (
        "cancel-session",
        "POST",
        "/api/v1/devices/{device_id}/sessions/active/cancel",
        {"ended_at": "2026-07-23T08:30:00Z"},
        get_measurement_service,
        "cancel_session",
    ),
    (
        "record-measurement",
        "POST",
        "/api/v1/devices/{device_id}/measurements",
        {"measured_at": "2026-07-23T08:30:00Z"},
        get_measurement_service,
        "record_measurement",
    ),
)


def _path_case_return_value(service_method: str) -> SimpleNamespace:
    if service_method in {"get_device", "activate_device"}:
        return _device()
    if service_method == "complete_session":
        return _session(status="completed", ended_at=NOW)
    if service_method == "cancel_session":
        return _session(status="cancelled", ended_at=NOW)
    if service_method == "record_measurement":
        return _measurement()
    return _session()


@pytest.mark.anyio
@pytest.mark.parametrize(
    (
        "_case_name",
        "method",
        "path_template",
        "payload",
        "dependency",
        "service_method",
    ),
    PATH_DEVICE_ID_CASES,
    ids=[case[0] for case in PATH_DEVICE_ID_CASES],
)
async def test_path_device_id_accepts_postgres_integer_max(
    application: FastAPI,
    _case_name: str,
    method: str,
    path_template: str,
    payload: dict[str, object] | None,
    dependency: object,
    service_method: str,
) -> None:
    operation = AsyncMock(
        return_value=_path_case_return_value(service_method)
    )
    service = SimpleNamespace(**{service_method: operation})
    application.dependency_overrides[dependency] = lambda: service

    response = await _request(
        application,
        method,
        path_template.format(device_id=POSTGRES_INTEGER_MAX),
        json=payload,
    )

    assert response.status_code in {200, 201}
    operation.assert_awaited_once()
    assert operation.await_args is not None
    assert (
        operation.await_args.kwargs["device_id"]
        == POSTGRES_INTEGER_MAX
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    (
        "_case_name",
        "method",
        "path_template",
        "payload",
        "dependency",
        "service_method",
    ),
    PATH_DEVICE_ID_CASES,
    ids=[case[0] for case in PATH_DEVICE_ID_CASES],
)
async def test_path_device_id_above_postgres_integer_max_uses_safe_422_before_service(
    application: FastAPI,
    _case_name: str,
    method: str,
    path_template: str,
    payload: dict[str, object] | None,
    dependency: object,
    service_method: str,
) -> None:
    operation = AsyncMock(
        return_value=_path_case_return_value(service_method)
    )
    service = SimpleNamespace(**{service_method: operation})
    application.dependency_overrides[dependency] = lambda: service

    response = await _request(
        application,
        method,
        path_template.format(device_id=POSTGRES_INTEGER_MAX + 1),
        json=payload,
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "request_validation_error",
            "message": "Request validation failed.",
            "details": None,
        }
    }
    operation.assert_not_awaited()


@pytest.mark.anyio
async def test_create_device_calls_write_service_and_returns_201(
    application: FastAPI,
) -> None:
    service = SimpleNamespace(
        create_device=AsyncMock(return_value=_device())
    )
    application.dependency_overrides[get_device_service] = lambda: service

    with patch("asyncpg.connect") as connect:
        response = await _request(
            application,
            "POST",
            "/api/v1/devices",
            json={
                "device_uid": "monitor-7",
                "name": "Workshop",
                "is_active": True,
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": 7,
        "device_uid": "monitor-7",
        "name": "Workshop",
        "is_active": True,
        "created_at": "2026-07-23T08:30:00Z",
    }
    service.create_device.assert_awaited_once_with(
        device_uid="monitor-7",
        name="Workshop",
        is_active=True,
    )
    connect.assert_not_called()


@pytest.mark.anyio
async def test_create_device_maps_duplicate_uid(
    application: FastAPI,
) -> None:
    service = SimpleNamespace(
        create_device=AsyncMock(
            side_effect=DuplicateDeviceUIDError("monitor-7")
        )
    )
    application.dependency_overrides[get_device_service] = lambda: service

    response = await _request(
        application,
        "POST",
        "/api/v1/devices",
        json={"device_uid": "monitor-7"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_device_uid"


@pytest.mark.anyio
async def test_get_device_uses_query_service(
    application: FastAPI,
) -> None:
    service = SimpleNamespace(
        get_device=AsyncMock(return_value=_device())
    )
    application.dependency_overrides[get_device_query_service] = (
        lambda: service
    )

    response = await _request(
        application,
        "GET",
        "/api/v1/devices/7",
    )

    assert response.status_code == 200
    assert response.json()["device_uid"] == "monitor-7"
    service.get_device.assert_awaited_once_with(device_id=7)


@pytest.mark.anyio
async def test_get_device_maps_missing_device(
    application: FastAPI,
) -> None:
    service = SimpleNamespace(
        get_device=AsyncMock(side_effect=DeviceNotFoundError(7))
    )
    application.dependency_overrides[get_device_query_service] = (
        lambda: service
    )

    response = await _request(
        application,
        "GET",
        "/api/v1/devices/7",
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "device_not_found"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("requested_state", "called_method"),
    [(True, "activate_device"), (False, "deactivate_device")],
)
async def test_patch_device_status_uses_exact_transition_service(
    application: FastAPI,
    requested_state: bool,
    called_method: str,
) -> None:
    service = SimpleNamespace(
        activate_device=AsyncMock(return_value=_device(is_active=True)),
        deactivate_device=AsyncMock(return_value=_device(is_active=False)),
    )
    application.dependency_overrides[get_device_service] = lambda: service

    response = await _request(
        application,
        "PATCH",
        "/api/v1/devices/7/status",
        json={"is_active": requested_state},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is requested_state
    getattr(service, called_method).assert_awaited_once_with(device_id=7)
    other_method = (
        "deactivate_device"
        if called_method == "activate_device"
        else "activate_device"
    )
    getattr(service, other_method).assert_not_awaited()


@pytest.mark.anyio
async def test_start_session_calls_measurement_service_and_returns_201(
    application: FastAPI,
) -> None:
    service = SimpleNamespace(
        start_session=AsyncMock(return_value=_session())
    )
    application.dependency_overrides[get_measurement_service] = (
        lambda: service
    )

    response = await _request(
        application,
        "POST",
        "/api/v1/devices/7/sessions",
        json={
            "latitude": 51.1694,
            "longitude": 71.4491,
            "started_at": "2026-07-23T08:30:00Z",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "active"
    service.start_session.assert_awaited_once_with(
        device_id=7,
        latitude=51.1694,
        longitude=71.4491,
        started_at=NOW,
    )


@pytest.mark.anyio
async def test_start_session_maps_existing_active_session(
    application: FastAPI,
) -> None:
    service = SimpleNamespace(
        start_session=AsyncMock(
            side_effect=ActiveSessionAlreadyExistsError(7)
        )
    )
    application.dependency_overrides[get_measurement_service] = (
        lambda: service
    )

    response = await _request(
        application,
        "POST",
        "/api/v1/devices/7/sessions",
        json={"latitude": 51.1694, "longitude": 71.4491},
    )

    assert response.status_code == 409
    assert (
        response.json()["error"]["code"]
        == "active_session_already_exists"
    )


@pytest.mark.anyio
async def test_get_active_session_uses_read_only_query_service(
    application: FastAPI,
) -> None:
    service = SimpleNamespace(
        get_active_session=AsyncMock(return_value=_session())
    )
    application.dependency_overrides[get_active_session_query_service] = (
        lambda: service
    )

    response = await _request(
        application,
        "GET",
        "/api/v1/devices/7/sessions/active",
    )

    assert response.status_code == 200
    assert response.json()["id"] == 11
    service.get_active_session.assert_awaited_once_with(device_id=7)


@pytest.mark.anyio
async def test_get_active_session_maps_missing_active_session(
    application: FastAPI,
) -> None:
    service = SimpleNamespace(
        get_active_session=AsyncMock(
            side_effect=ActiveSessionNotFoundError(7)
        )
    )
    application.dependency_overrides[get_active_session_query_service] = (
        lambda: service
    )

    response = await _request(
        application,
        "GET",
        "/api/v1/devices/7/sessions/active",
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "active_session_not_found"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path_suffix", "service_method", "status"),
    [
        ("complete", "complete_session", "completed"),
        ("cancel", "cancel_session", "cancelled"),
    ],
)
async def test_terminal_session_routes_call_exact_service_operation(
    application: FastAPI,
    path_suffix: str,
    service_method: str,
    status: str,
) -> None:
    ended_at = datetime(2026, 7, 23, 9, 0, tzinfo=UTC)
    service = SimpleNamespace(
        complete_session=AsyncMock(
            return_value=_session(status="completed", ended_at=ended_at)
        ),
        cancel_session=AsyncMock(
            return_value=_session(status="cancelled", ended_at=ended_at)
        ),
    )
    application.dependency_overrides[get_measurement_service] = (
        lambda: service
    )

    response = await _request(
        application,
        "POST",
        f"/api/v1/devices/7/sessions/active/{path_suffix}",
        json={"ended_at": "2026-07-23T09:00:00Z"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == status
    getattr(service, service_method).assert_awaited_once_with(
        device_id=7,
        ended_at=ended_at,
    )


@pytest.mark.anyio
async def test_complete_session_allows_omitted_optional_body(
    application: FastAPI,
) -> None:
    service = SimpleNamespace(
        complete_session=AsyncMock(
            return_value=_session(status="completed", ended_at=NOW)
        )
    )
    application.dependency_overrides[get_measurement_service] = (
        lambda: service
    )

    response = await _request(
        application,
        "POST",
        "/api/v1/devices/7/sessions/active/complete",
    )

    assert response.status_code == 200
    service.complete_session.assert_awaited_once_with(
        device_id=7,
        ended_at=None,
    )


@pytest.mark.anyio
async def test_record_measurement_calls_service_with_validated_payload(
    application: FastAPI,
) -> None:
    service = SimpleNamespace(
        record_measurement=AsyncMock(return_value=_measurement())
    )
    application.dependency_overrides[get_measurement_service] = (
        lambda: service
    )
    payload = {
        "source_message_id": "message-13",
        "measured_at": "2026-07-23T08:30:00Z",
        "temperature": 21.5,
        "humidity": 44.0,
        "pm1": 3.0,
        "pm25": 7.5,
        "pm10": 12.0,
        "pc0_3": 100,
        "pc0_5": 90,
        "pc1_0": 80,
        "pc2_5": 70,
        "pc5_0": 60,
        "pc10": 50,
        "latitude": 51.1694,
        "longitude": 71.4491,
        "is_valid": True,
        "validation_note": None,
    }

    response = await _request(
        application,
        "POST",
        "/api/v1/devices/7/measurements",
        json=payload,
    )

    assert response.status_code == 201
    assert response.json()["id"] == 13
    service.record_measurement.assert_awaited_once_with(
        device_id=7,
        source_message_id="message-13",
        measured_at=NOW,
        temperature=21.5,
        humidity=44.0,
        pm1=3.0,
        pm25=7.5,
        pm10=12.0,
        pc0_3=100,
        pc0_5=90,
        pc1_0=80,
        pc2_5=70,
        pc5_0=60,
        pc10=50,
        latitude=51.1694,
        longitude=71.4491,
        is_valid=True,
        validation_note=None,
    )


@pytest.mark.anyio
async def test_particle_counters_accept_postgres_integer_max(
    application: FastAPI,
) -> None:
    operation = AsyncMock(return_value=_measurement())
    service = SimpleNamespace(record_measurement=operation)
    application.dependency_overrides[get_measurement_service] = (
        lambda: service
    )
    payload = {
        "measured_at": "2026-07-23T08:30:00Z",
        **{
            field_name: POSTGRES_INTEGER_MAX
            for field_name in PARTICLE_COUNTER_FIELDS
        },
    }

    response = await _request(
        application,
        "POST",
        "/api/v1/devices/7/measurements",
        json=payload,
    )

    assert response.status_code == 201
    operation.assert_awaited_once()
    assert operation.await_args is not None
    for field_name in PARTICLE_COUNTER_FIELDS:
        assert (
            operation.await_args.kwargs[field_name]
            == POSTGRES_INTEGER_MAX
        )


@pytest.mark.anyio
@pytest.mark.parametrize("field_name", PARTICLE_COUNTER_FIELDS)
async def test_particle_counter_above_postgres_integer_max_uses_safe_422_before_service(
    application: FastAPI,
    field_name: str,
) -> None:
    operation = AsyncMock(return_value=_measurement())
    service = SimpleNamespace(record_measurement=operation)
    application.dependency_overrides[get_measurement_service] = (
        lambda: service
    )

    response = await _request(
        application,
        "POST",
        "/api/v1/devices/7/measurements",
        json={
            "measured_at": "2026-07-23T08:30:00Z",
            field_name: POSTGRES_INTEGER_MAX + 1,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "request_validation_error",
            "message": "Request validation failed.",
            "details": None,
        }
    }
    operation.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "service_method", "payload"),
    [
        (
            "/api/v1/devices/7/measurements",
            "record_measurement",
            {"measured_at": "2026-07-23T08:30:00Z"},
        ),
        (
            "/api/v1/devices/7/sessions/active/complete",
            "complete_session",
            {"ended_at": "2026-07-23T08:30:00Z"},
        ),
        (
            "/api/v1/devices/7/sessions/active/cancel",
            "cancel_session",
            {"ended_at": "2026-07-23T08:30:00Z"},
        ),
    ],
)
async def test_chronology_conflicts_use_safe_409(
    application: FastAPI,
    path: str,
    service_method: str,
    payload: dict[str, object],
) -> None:
    operation = AsyncMock(
        side_effect=InvalidTimestampError(
            "timestamp",
            "SECRET chronology detail",
        )
    )
    service = SimpleNamespace(**{service_method: operation})
    application.dependency_overrides[get_measurement_service] = (
        lambda: service
    )

    response = await _request(
        application,
        "POST",
        path,
        json=payload,
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "invalid_timestamp",
            "message": (
                "The supplied timestamp conflicts with session state."
            ),
            "details": None,
        }
    }
    assert "SECRET" not in response.text


@pytest.mark.anyio
@pytest.mark.parametrize(
    "raw_value",
    ["1e999", "-1e999", "NaN", "Infinity", "-Infinity"],
)
async def test_non_finite_measurement_json_uses_safe_422_before_service(
    application: FastAPI,
    raw_value: str,
) -> None:
    service = SimpleNamespace(
        record_measurement=AsyncMock(return_value=_measurement())
    )
    application.dependency_overrides[get_measurement_service] = (
        lambda: service
    )
    payload = (
        '{"measured_at":"2026-07-23T08:30:00Z",'
        f'"pm25":{raw_value}}}'
    )

    response = await _request(
        application,
        "POST",
        "/api/v1/devices/7/measurements",
        content=payload,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "request_validation_error",
            "message": "Request validation failed.",
            "details": None,
        }
    }
    service.record_measurement.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "code"),
    [
        (
            DuplicateSourceMessageError(7, "message-13"),
            "duplicate_source_message",
        ),
        (DeviceInactiveError(7), "device_inactive"),
    ],
)
async def test_record_measurement_maps_conflicts(
    application: FastAPI,
    error: Exception,
    code: str,
) -> None:
    service = SimpleNamespace(
        record_measurement=AsyncMock(side_effect=error)
    )
    application.dependency_overrides[get_measurement_service] = (
        lambda: service
    )

    response = await _request(
        application,
        "POST",
        "/api/v1/devices/7/measurements",
        json={"measured_at": "2026-07-23T08:30:00Z"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == code


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/devices/0", None),
        (
            "POST",
            "/api/v1/devices",
            {"device_uid": "monitor-7", "unknown": True},
        ),
        (
            "POST",
            "/api/v1/devices/7/sessions",
            {"latitude": 91, "longitude": 0},
        ),
        (
            "POST",
            "/api/v1/devices/7/measurements",
            {
                "measured_at": "2026-07-23T08:30:00",
                "pc0_3": -1,
            },
        ),
        (
            "POST",
            "/api/v1/devices/7/measurements",
            {
                "measured_at": "2026-07-23T08:30:00Z",
                "latitude": 51.1694,
            },
        ),
    ],
)
async def test_invalid_requests_use_the_stable_422_envelope(
    application: FastAPI,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    response = await _request(
        application,
        method,
        path,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "request_validation_error",
            "message": "Request validation failed.",
            "details": None,
        }
    }


@pytest.mark.anyio
async def test_health_endpoint_is_preserved(application: FastAPI) -> None:
    response = await _request(application, "GET", "/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_application_fixture_restores_dependency_overrides_after_failure() -> None:
    application = create_application(Settings(_env_file=None))
    original = dict(application.dependency_overrides)
    application.dependency_overrides[get_device_service] = lambda: object()

    application.dependency_overrides.clear()
    application.dependency_overrides.update(original)

    assert application.dependency_overrides == original
