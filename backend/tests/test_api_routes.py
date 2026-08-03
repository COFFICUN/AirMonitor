"""Offline HTTP contract tests using dependency-overridden services."""

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient

from app.api import dependencies as api_dependencies
from app.api.dependencies import (
    get_active_session_query_service,
    get_device_query_service,
    get_device_service,
    get_measurement_service,
)
from app.api.query_validation import (
    resolve_measurement_read_request,
    resolve_session_read_request,
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
from app.services.telemetry import TelemetryPage
from app.services.telemetry_cursor import (
    CursorPosition,
    MeasurementReadRequest,
    SessionReadRequest,
    encode_cursor,
    normalize_measurement_filters,
    normalize_session_filters,
)


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
SAFE_VALIDATION_ERROR = {
    "error": {
        "code": "request_validation_error",
        "message": "Request validation failed.",
        "details": None,
    }
}
SAFE_INTERNAL_ERROR = {
    "error": {
        "code": "internal_server_error",
        "message": "An internal server error occurred.",
        "details": None,
    }
}
TELEMETRY_FORBIDDEN_SERVICE_METHODS = (
    "add",
    "begin",
    "begin_nested",
    "commit",
    "delete",
    "flush",
    "rollback",
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
    identifier: int = 11,
    status: str = "active",
    started_at: datetime = NOW,
    ended_at: datetime | None = None,
    sample_count: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier,
        device_id=7,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        latitude=51.1694,
        longitude=71.4491,
        sample_count=sample_count,
        created_at=started_at,
        updated_at=started_at,
    )


def _measurement(
    *,
    identifier: int = 13,
    measured_at: datetime = NOW,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier,
        device_id=7,
        session_id=11,
        source_message_id=f"message-{identifier}",
        measured_at=measured_at,
        received_at=measured_at,
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
        created_at=measured_at,
    )


async def _request(
    application: FastAPI,
    method: str,
    path: str,
    *,
    json: dict[str, object] | None = None,
    content: str | bytes | None = None,
    headers: dict[str, str] | None = None,
    params: (
        dict[str, object]
        | list[tuple[str, str]]
        | None
    ) = None,
    raise_app_exceptions: bool = True,
):
    transport = ASGITransport(
        app=application,
        raise_app_exceptions=raise_app_exceptions,
    )
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
            params=params,
        )


def _telemetry_provider(resource: str) -> object:
    if resource == "sessions":
        return api_dependencies.get_session_telemetry_query_service
    return api_dependencies.get_measurement_telemetry_query_service


def _telemetry_service(
    operation_name: str,
    operation: AsyncMock,
) -> SimpleNamespace:
    service = SimpleNamespace(**{operation_name: operation})
    for method_name in TELEMETRY_FORBIDDEN_SERVICE_METHODS:
        setattr(service, method_name, Mock())
    return service


def _override_telemetry_service(
    application: FastAPI,
    *,
    resource: str,
    operation_name: str,
    operation: AsyncMock,
) -> SimpleNamespace:
    service = _telemetry_service(operation_name, operation)
    application.dependency_overrides[_telemetry_provider(resource)] = (
        lambda: service
    )
    return service


def _assert_telemetry_service_read_only(
    service: SimpleNamespace,
) -> None:
    for method_name in TELEMETRY_FORBIDDEN_SERVICE_METHODS:
        getattr(service, method_name).assert_not_called()


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


def _application_fixture_context() -> object:
    return contextmanager(application.__wrapped__)()


def test_application_fixture_restores_exact_overrides_after_normal_use() -> None:
    with _application_fixture_context() as test_application:
        original = dict(test_application.dependency_overrides)
        assert original
        test_application.dependency_overrides[get_device_service] = (
            lambda: object()
        )

    assert test_application.dependency_overrides == original


def test_application_fixture_restores_exact_overrides_after_exception() -> None:
    class IntentionalFixtureFailure(RuntimeError):
        pass

    with pytest.raises(IntentionalFixtureFailure):
        with _application_fixture_context() as test_application:
            original = dict(test_application.dependency_overrides)
            assert original
            test_application.dependency_overrides[get_device_service] = (
                lambda: object()
            )
            raise IntentionalFixtureFailure

    assert test_application.dependency_overrides == original


@pytest.mark.anyio
async def test_telemetry_read_session_route_returns_exact_ordered_envelope(
    application: FastAPI,
) -> None:
    rows = (
        _session(
            identifier=12,
            status="active",
            started_at=NOW,
            sample_count=17,
        ),
        _session(
            identifier=11,
            status="completed",
            started_at=datetime(2026, 7, 23, 8, 0, tzinfo=UTC),
            ended_at=NOW,
            sample_count=9,
        ),
    )
    operation = AsyncMock(
        return_value=TelemetryPage(
            items=rows,
            next_cursor="opaque-session-next",
        )
    )
    service = _override_telemetry_service(
        application,
        resource="sessions",
        operation_name="list_sessions",
        operation=operation,
    )

    response = await _request(
        application,
        "GET",
        "/api/v1/devices/7/sessions",
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": 12,
                "device_id": 7,
                "status": "active",
                "started_at": "2026-07-23T08:30:00Z",
                "ended_at": None,
                "latitude": 51.1694,
                "longitude": 71.4491,
                "sample_count": 17,
                "created_at": "2026-07-23T08:30:00Z",
            },
            {
                "id": 11,
                "device_id": 7,
                "status": "completed",
                "started_at": "2026-07-23T08:00:00Z",
                "ended_at": "2026-07-23T08:30:00Z",
                "latitude": 51.1694,
                "longitude": 71.4491,
                "sample_count": 9,
                "created_at": "2026-07-23T08:00:00Z",
            },
        ],
        "next_cursor": "opaque-session-next",
    }
    operation.assert_awaited_once()
    _assert_telemetry_service_read_only(service)


@pytest.mark.anyio
async def test_telemetry_read_measurement_route_returns_exact_ordered_envelope(
    application: FastAPI,
) -> None:
    rows = (
        _measurement(identifier=14, measured_at=NOW),
        _measurement(
            identifier=13,
            measured_at=datetime(2026, 7, 23, 8, 0, tzinfo=UTC),
        ),
    )
    operation = AsyncMock(
        return_value=TelemetryPage(
            items=rows,
            next_cursor="opaque-measurement-next",
        )
    )
    service = _override_telemetry_service(
        application,
        resource="measurements",
        operation_name="list_measurements",
        operation=operation,
    )

    response = await _request(
        application,
        "GET",
        "/api/v1/devices/7/measurements",
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "next_cursor"}
    assert [item["id"] for item in payload["items"]] == [14, 13]
    assert set(payload["items"][0]) == {
        "id",
        "device_id",
        "session_id",
        "source_message_id",
        "measured_at",
        "received_at",
        "temperature",
        "humidity",
        "pm1",
        "pm25",
        "pm10",
        "pc0_3",
        "pc0_5",
        "pc1_0",
        "pc2_5",
        "pc5_0",
        "pc10",
        "latitude",
        "longitude",
        "is_valid",
        "validation_note",
        "created_at",
    }
    assert payload["items"][0]["measured_at"] == (
        "2026-07-23T08:30:00Z"
    )
    assert payload["items"][0]["pm25"] == 7.5
    assert isinstance(payload["items"][0]["pm25"], float)
    assert payload["items"][0]["pc0_3"] == 100
    assert isinstance(payload["items"][0]["pc0_3"], int)
    assert payload["next_cursor"] == "opaque-measurement-next"
    operation.assert_awaited_once()
    _assert_telemetry_service_read_only(service)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("resource", "path", "operation_name"),
    [
        (
            "sessions",
            "/api/v1/devices/7/sessions",
            "list_sessions",
        ),
        (
            "measurements",
            "/api/v1/devices/7/measurements",
            "list_measurements",
        ),
    ],
)
async def test_telemetry_read_default_limit_and_empty_page(
    application: FastAPI,
    resource: str,
    path: str,
    operation_name: str,
) -> None:
    operation = AsyncMock(
        return_value=TelemetryPage(items=(), next_cursor=None)
    )
    _override_telemetry_service(
        application,
        resource=resource,
        operation_name=operation_name,
        operation=operation,
    )

    response = await _request(application, "GET", path)

    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}
    operation.assert_awaited_once()
    assert operation.await_args is not None
    assert operation.await_args.kwargs["read_request"].limit == 100


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("resource", "path", "operation_name"),
    [
        (
            "sessions",
            f"/api/v1/devices/{POSTGRES_INTEGER_MAX}/sessions",
            "list_sessions",
        ),
        (
            "measurements",
            f"/api/v1/devices/{POSTGRES_INTEGER_MAX}/measurements",
            "list_measurements",
        ),
    ],
)
async def test_telemetry_read_path_accepts_postgres_integer_max(
    application: FastAPI,
    resource: str,
    path: str,
    operation_name: str,
) -> None:
    operation = AsyncMock(
        return_value=TelemetryPage(items=(), next_cursor=None)
    )
    _override_telemetry_service(
        application,
        resource=resource,
        operation_name=operation_name,
        operation=operation,
    )

    response = await _request(application, "GET", path)

    assert response.status_code == 200
    operation.assert_awaited_once()
    assert operation.await_args is not None
    assert (
        operation.await_args.kwargs["read_request"].filters.device_id
        == POSTGRES_INTEGER_MAX
    )


@pytest.mark.anyio
async def test_telemetry_read_session_filters_and_cursor_are_forwarded(
    application: FastAPI,
) -> None:
    filters = normalize_session_filters(
        device_id=7,
        status="active",
        started_from=datetime(2026, 7, 23, 8, 0, tzinfo=UTC),
        started_to=datetime(2026, 7, 24, tzinfo=UTC),
    )
    position = CursorPosition(NOW, 11)
    cursor = encode_cursor("sessions", position, filters)
    expected = SessionReadRequest(filters, 37, position)
    operation = AsyncMock(
        return_value=TelemetryPage(items=(), next_cursor=None)
    )
    _override_telemetry_service(
        application,
        resource="sessions",
        operation_name="list_sessions",
        operation=operation,
    )

    response = await _request(
        application,
        "GET",
        "/api/v1/devices/7/sessions",
        params={
            "status": "active",
            "started_from": "2026-07-23T08:00:00Z",
            "started_to": "2026-07-24T00:00:00Z",
            "limit": 37,
            "cursor": cursor,
        },
    )

    assert response.status_code == 200
    operation.assert_awaited_once_with(read_request=expected)


@pytest.mark.anyio
async def test_telemetry_read_measurement_filters_and_cursor_are_forwarded(
    application: FastAPI,
) -> None:
    filters = normalize_measurement_filters(
        device_id=7,
        session_id=11,
        measured_from=datetime(2026, 7, 23, 8, 0, tzinfo=UTC),
        measured_to=datetime(2026, 7, 24, tzinfo=UTC),
    )
    position = CursorPosition(NOW, 13)
    cursor = encode_cursor("measurements", position, filters)
    expected = MeasurementReadRequest(filters, 41, position)
    operation = AsyncMock(
        return_value=TelemetryPage(items=(), next_cursor=None)
    )
    _override_telemetry_service(
        application,
        resource="measurements",
        operation_name="list_measurements",
        operation=operation,
    )

    response = await _request(
        application,
        "GET",
        "/api/v1/devices/7/measurements",
        params={
            "session_id": 11,
            "measured_from": "2026-07-23T08:00:00Z",
            "measured_to": "2026-07-24T00:00:00Z",
            "limit": 41,
            "cursor": cursor,
        },
    )

    assert response.status_code == 200
    operation.assert_awaited_once_with(read_request=expected)


@pytest.mark.anyio
@pytest.mark.parametrize("resource", ["sessions", "measurements"])
async def test_telemetry_read_resolved_request_identity_is_preserved(
    application: FastAPI,
    resource: str,
) -> None:
    if resource == "sessions":
        sentinel: SessionReadRequest | MeasurementReadRequest = (
            SessionReadRequest(
                normalize_session_filters(
                    device_id=7,
                    status=None,
                    started_from=None,
                    started_to=None,
                ),
                100,
                None,
            )
        )
        resolver = resolve_session_read_request
        path = "/api/v1/devices/7/sessions"
        operation_name = "list_sessions"
    else:
        sentinel = MeasurementReadRequest(
            normalize_measurement_filters(
                device_id=7,
                session_id=None,
                measured_from=None,
                measured_to=None,
            ),
            100,
            None,
        )
        resolver = resolve_measurement_read_request
        path = "/api/v1/devices/7/measurements"
        operation_name = "list_measurements"
    operation = AsyncMock(
        return_value=TelemetryPage(items=(), next_cursor=None)
    )
    _override_telemetry_service(
        application,
        resource=resource,
        operation_name=operation_name,
        operation=operation,
    )
    application.dependency_overrides[resolver] = lambda: sentinel

    response = await _request(application, "GET", path)

    assert response.status_code == 200
    operation.assert_awaited_once()
    assert operation.await_args is not None
    assert operation.await_args.kwargs["read_request"] is sentinel


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("resource", "path", "operation_name"),
    [
        (
            "sessions",
            "/api/v1/devices/7/sessions",
            "list_sessions",
        ),
        (
            "measurements",
            "/api/v1/devices/7/measurements",
            "list_measurements",
        ),
    ],
)
async def test_telemetry_read_unknown_device_uses_safe_404(
    application: FastAPI,
    resource: str,
    path: str,
    operation_name: str,
) -> None:
    operation = AsyncMock(side_effect=DeviceNotFoundError(7))
    _override_telemetry_service(
        application,
        resource=resource,
        operation_name=operation_name,
        operation=operation,
    )

    response = await _request(application, "GET", path)

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "device_not_found",
            "message": "Device was not found.",
            "details": None,
        }
    }
    operation.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("resource", "path", "operation_name"),
    [
        (
            "sessions",
            "/api/v1/devices/7/sessions",
            "list_sessions",
        ),
        (
            "measurements",
            "/api/v1/devices/7/measurements",
            "list_measurements",
        ),
    ],
)
async def test_telemetry_read_generic_failure_uses_safe_500(
    application: FastAPI,
    resource: str,
    path: str,
    operation_name: str,
) -> None:
    marker = "SECRET telemetry repository and database detail"
    operation = AsyncMock(side_effect=RuntimeError(marker))
    _override_telemetry_service(
        application,
        resource=resource,
        operation_name=operation_name,
        operation=operation,
    )

    response = await _request(
        application,
        "GET",
        path,
        raise_app_exceptions=False,
    )

    assert response.status_code == 500
    assert response.json() == SAFE_INTERNAL_ERROR
    assert marker not in response.text
    operation.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("resource", "path", "operation_name"),
    [
        (
            "sessions",
            "/api/v1/devices/0/sessions",
            "list_sessions",
        ),
        (
            "sessions",
            "/api/v1/devices/2147483648/sessions",
            "list_sessions",
        ),
        (
            "sessions",
            "/api/v1/devices/7/sessions?status=pending",
            "list_sessions",
        ),
        (
            "sessions",
            (
                "/api/v1/devices/7/sessions"
                "?started_from=2026-07-23T08%3A30%3A00"
            ),
            "list_sessions",
        ),
        (
            "sessions",
            "/api/v1/devices/7/sessions?cursor=malformed",
            "list_sessions",
        ),
        (
            "measurements",
            "/api/v1/devices/0/measurements",
            "list_measurements",
        ),
        (
            "measurements",
            "/api/v1/devices/2147483648/measurements",
            "list_measurements",
        ),
        (
            "measurements",
            "/api/v1/devices/7/measurements?session_id=0",
            "list_measurements",
        ),
        (
            "measurements",
            (
                "/api/v1/devices/7/measurements"
                "?measured_from=2026-07-23T08%3A30%3A00"
            ),
            "list_measurements",
        ),
        (
            "measurements",
            "/api/v1/devices/7/measurements?cursor=malformed",
            "list_measurements",
        ),
    ],
)
async def test_telemetry_read_malformed_input_is_safe_422_before_service(
    application: FastAPI,
    resource: str,
    path: str,
    operation_name: str,
) -> None:
    operation = AsyncMock(
        return_value=TelemetryPage(items=(), next_cursor=None)
    )
    _override_telemetry_service(
        application,
        resource=resource,
        operation_name=operation_name,
        operation=operation,
    )

    response = await _request(application, "GET", path)

    assert response.status_code == 422
    assert response.json() == SAFE_VALIDATION_ERROR
    operation.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("resource", "path", "operation_name"),
    [
        (
            "sessions",
            "/api/v1/devices/7/sessions?unknown=value",
            "list_sessions",
        ),
        (
            "sessions",
            "/api/v1/devices/7/sessions?limit=1&limit=2",
            "list_sessions",
        ),
        (
            "sessions",
            "/api/v1/devices/7/sessions?limit=1&limit=1",
            "list_sessions",
        ),
        (
            "measurements",
            "/api/v1/devices/7/measurements?unknown=value",
            "list_measurements",
        ),
        (
            "measurements",
            "/api/v1/devices/7/measurements?limit=1&limit=2",
            "list_measurements",
        ),
        (
            "measurements",
            "/api/v1/devices/7/measurements?limit=1&limit=1",
            "list_measurements",
        ),
    ],
)
async def test_telemetry_read_unknown_or_repeated_query_never_calls_service(
    application: FastAPI,
    resource: str,
    path: str,
    operation_name: str,
) -> None:
    operation = AsyncMock(
        return_value=TelemetryPage(items=(), next_cursor=None)
    )
    _override_telemetry_service(
        application,
        resource=resource,
        operation_name=operation_name,
        operation=operation,
    )

    response = await _request(application, "GET", path)

    assert response.status_code == 422
    assert response.json() == SAFE_VALIDATION_ERROR
    operation.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("resource", "path", "operation_name"),
    [
        (
            "sessions",
            (
                "/api/v1/devices/7/sessions"
                "?started_from=2026-07-23T08%3A30%3A00Z"
                "&started_to=2026-07-23T08%3A30%3A00Z"
            ),
            "list_sessions",
        ),
        (
            "measurements",
            (
                "/api/v1/devices/7/measurements"
                "?measured_from=2026-07-23T08%3A30%3A00Z"
                "&measured_to=2026-07-23T08%3A30%3A00Z"
            ),
            "list_measurements",
        ),
    ],
)
async def test_telemetry_read_equal_range_reaches_service(
    application: FastAPI,
    resource: str,
    path: str,
    operation_name: str,
) -> None:
    operation = AsyncMock(
        return_value=TelemetryPage(items=(), next_cursor=None)
    )
    _override_telemetry_service(
        application,
        resource=resource,
        operation_name=operation_name,
        operation=operation,
    )

    response = await _request(application, "GET", path)

    assert response.status_code == 200
    operation.assert_awaited_once()
    assert operation.await_args is not None
    read_request = operation.await_args.kwargs["read_request"]
    if resource == "sessions":
        assert (
            read_request.filters.started_from
            == read_request.filters.started_to
        )
    else:
        assert (
            read_request.filters.measured_from
            == read_request.filters.measured_to
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "session_id",
    [999_999, 12],
    ids=["nonexistent", "belongs-to-another-device"],
)
async def test_telemetry_read_measurement_session_filter_is_non_disclosing(
    application: FastAPI,
    session_id: int,
) -> None:
    operation = AsyncMock(
        return_value=TelemetryPage(items=(), next_cursor=None)
    )
    _override_telemetry_service(
        application,
        resource="measurements",
        operation_name="list_measurements",
        operation=operation,
    )

    response = await _request(
        application,
        "GET",
        "/api/v1/devices/7/measurements",
        params={"session_id": session_id},
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}
    operation.assert_awaited_once()
    assert operation.await_args is not None
    assert (
        operation.await_args.kwargs["read_request"].filters.session_id
        == session_id
    )


@pytest.mark.anyio
async def test_telemetry_read_session_collection_preserves_active_route(
    application: FastAPI,
) -> None:
    active_operation = AsyncMock(return_value=_session())
    active_service = SimpleNamespace(
        get_active_session=active_operation
    )
    application.dependency_overrides[
        get_active_session_query_service
    ] = lambda: active_service
    list_operation = AsyncMock(
        return_value=TelemetryPage(items=(), next_cursor=None)
    )
    _override_telemetry_service(
        application,
        resource="sessions",
        operation_name="list_sessions",
        operation=list_operation,
    )

    active_response = await _request(
        application,
        "GET",
        "/api/v1/devices/7/sessions/active",
    )
    list_response = await _request(
        application,
        "GET",
        "/api/v1/devices/7/sessions",
    )

    assert active_response.status_code == 200
    assert active_response.json()["id"] == 11
    assert list_response.status_code == 200
    assert list_response.json() == {"items": [], "next_cursor": None}
    active_operation.assert_awaited_once_with(device_id=7)
    list_operation.assert_awaited_once()
