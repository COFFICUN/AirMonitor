"""Black-box contracts for strict telemetry query validation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx2 import ASGITransport, AsyncClient, Response
from pydantic import ValidationError
from starlette.responses import Response as StarletteResponse

from app.api.errors import install_exception_handlers
from app.api.query_validation import (
    resolve_measurement_read_request,
    resolve_session_read_request,
    strict_measurement_query_parameters,
    strict_session_query_parameters,
)
from app.schemas._base import POSTGRES_INTEGER_MAX
from app.schemas.telemetry import MeasurementListQuery, SessionListQuery
from app.services.telemetry_cursor import (
    CursorPosition,
    MeasurementReadRequest,
    SessionReadRequest,
    encode_cursor,
    normalize_measurement_filters,
    normalize_session_filters,
)


SESSION_QUERY_KEYS = (
    "status",
    "started_from",
    "started_to",
    "limit",
    "cursor",
)
MEASUREMENT_QUERY_KEYS = (
    "session_id",
    "measured_from",
    "measured_to",
    "limit",
    "cursor",
)
SESSION_ALLOWED_VALUES = (
    ("status", "active"),
    ("started_from", "2026-07-30T00%3A00%3A00Z"),
    ("started_to", "2026-07-31T00%3A00%3A00Z"),
    ("limit", "1"),
    ("cursor", "opaque"),
)
MEASUREMENT_ALLOWED_VALUES = (
    ("session_id", "1"),
    ("measured_from", "2026-07-30T00%3A00%3A00Z"),
    ("measured_to", "2026-07-31T00%3A00%3A00Z"),
    ("limit", "1"),
    ("cursor", "opaque"),
)
SAFE_VALIDATION_ERROR = {
    "error": {
        "code": "request_validation_error",
        "message": "Request validation failed.",
        "details": None,
    }
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _strict_application(
    dependency: Callable[..., object],
) -> FastAPI:
    application = FastAPI()
    install_exception_handlers(application)

    @application.get("/validate", dependencies=[Depends(dependency)])
    async def validate() -> dict[str, bool]:
        return {"accepted": True}

    return application


def _session_resolution_application(
    captured: list[SessionReadRequest],
) -> FastAPI:
    application = FastAPI()
    install_exception_handlers(application)

    @application.get(
        "/devices/{device_id}/sessions",
        dependencies=[Depends(strict_session_query_parameters)],
    )
    async def resolve(
        read_request: Annotated[
            SessionReadRequest,
            Depends(resolve_session_read_request),
        ],
    ) -> StarletteResponse:
        captured.append(read_request)
        return StarletteResponse(status_code=204)

    return application


def _measurement_resolution_application(
    captured: list[MeasurementReadRequest],
) -> FastAPI:
    application = FastAPI()
    install_exception_handlers(application)

    @application.get(
        "/devices/{device_id}/measurements",
        dependencies=[Depends(strict_measurement_query_parameters)],
    )
    async def resolve(
        read_request: Annotated[
            MeasurementReadRequest,
            Depends(resolve_measurement_read_request),
        ],
    ) -> StarletteResponse:
        captured.append(read_request)
        return StarletteResponse(status_code=204)

    return application


async def _get(
    application: FastAPI,
    path: str,
    *,
    params: dict[str, object] | None = None,
) -> Response:
    transport = ASGITransport(
        app=application,
        raise_app_exceptions=False,
    )
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(path, params=params)


def _assert_safe_422(response: Response) -> None:
    if response.status_code != 422:
        pytest.fail(
            "invalid query did not return HTTP 422",
            pytrace=False,
        )
    try:
        payload = response.json()
    except Exception:
        pytest.fail(
            "validation response was not JSON",
            pytrace=False,
        )
    if payload != SAFE_VALIDATION_ERROR:
        pytest.fail(
            "validation response did not use the exact safe envelope",
            pytrace=False,
        )


def _assert_model_rejected(operation: Callable[[], object]) -> None:
    unexpected_type: str | None = None
    try:
        operation()
    except ValidationError:
        return
    except Exception as error:  # pragma: no cover - contract failure path
        unexpected_type = type(error).__name__

    if unexpected_type is not None:
        pytest.fail(
            f"model rejection used unexpected exception type {unexpected_type}",
            pytrace=False,
        )
    pytest.fail("invalid query model input was accepted", pytrace=False)


def test_session_query_model_has_exact_allowlist_and_forbids_extras() -> None:
    assert frozenset(SessionListQuery.model_fields) == frozenset(
        SESSION_QUERY_KEYS
    )
    assert SessionListQuery.model_config.get("extra") == "forbid"


def test_measurement_query_model_has_exact_allowlist_and_forbids_extras() -> None:
    assert frozenset(MeasurementListQuery.model_fields) == frozenset(
        MEASUREMENT_QUERY_KEYS
    )
    assert MeasurementListQuery.model_config.get("extra") == "forbid"


@pytest.mark.parametrize(
    "model",
    [SessionListQuery, MeasurementListQuery],
    ids=["sessions", "measurements"],
)
def test_query_models_reject_unknown_fields(
    model: type[SessionListQuery] | type[MeasurementListQuery],
) -> None:
    _assert_model_rejected(
        lambda: model.model_validate({"unknown": "raw-value-marker"})
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("parameter", "value"),
    SESSION_ALLOWED_VALUES,
    ids=[name for name, _ in SESSION_ALLOWED_VALUES],
)
async def test_strict_session_boundary_accepts_every_allowlisted_key(
    parameter: str,
    value: str,
) -> None:
    application = _strict_application(strict_session_query_parameters)

    response = await _get(application, f"/validate?{parameter}={value}")

    assert response.status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("parameter", "value"),
    MEASUREMENT_ALLOWED_VALUES,
    ids=[name for name, _ in MEASUREMENT_ALLOWED_VALUES],
)
async def test_strict_measurement_boundary_accepts_every_allowlisted_key(
    parameter: str,
    value: str,
) -> None:
    application = _strict_application(strict_measurement_query_parameters)

    response = await _get(application, f"/validate?{parameter}={value}")

    assert response.status_code == 200


@pytest.mark.anyio
async def test_unknown_session_parameter_returns_safe_422() -> None:
    application = _strict_application(strict_session_query_parameters)

    response = await _get(
        application,
        "/validate?unknown=raw-session-value-marker",
    )

    _assert_safe_422(response)


@pytest.mark.anyio
async def test_unknown_measurement_parameter_returns_safe_422() -> None:
    application = _strict_application(strict_measurement_query_parameters)

    response = await _get(
        application,
        "/validate?unknown=raw-measurement-value-marker",
    )

    _assert_safe_422(response)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "parameter",
    ["session_id", "measured_from", "measured_to"],
)
async def test_session_boundary_rejects_measurement_only_keys(
    parameter: str,
) -> None:
    application = _strict_application(strict_session_query_parameters)

    response = await _get(
        application,
        f"/validate?{parameter}=cross-endpoint-marker",
    )

    _assert_safe_422(response)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "parameter",
    ["status", "started_from", "started_to"],
)
async def test_measurement_boundary_rejects_session_only_keys(
    parameter: str,
) -> None:
    application = _strict_application(strict_measurement_query_parameters)

    response = await _get(
        application,
        f"/validate?{parameter}=cross-endpoint-marker",
    )

    _assert_safe_422(response)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("dependency", "parameter"),
    [
        *(
            (strict_session_query_parameters, parameter)
            for parameter in SESSION_QUERY_KEYS
        ),
        *(
            (strict_measurement_query_parameters, parameter)
            for parameter in MEASUREMENT_QUERY_KEYS
        ),
    ],
    ids=[
        *(f"sessions-{parameter}" for parameter in SESSION_QUERY_KEYS),
        *(
            f"measurements-{parameter}"
            for parameter in MEASUREMENT_QUERY_KEYS
        ),
    ],
)
async def test_every_repeated_supported_scalar_returns_safe_422(
    dependency: Callable[..., object],
    parameter: str,
) -> None:
    application = _strict_application(dependency)

    response = await _get(
        application,
        f"/validate?{parameter}=first&{parameter}=second",
    )

    _assert_safe_422(response)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("dependency", "parameter"),
    [
        *(
            (strict_session_query_parameters, parameter)
            for parameter in SESSION_QUERY_KEYS
        ),
        *(
            (strict_measurement_query_parameters, parameter)
            for parameter in MEASUREMENT_QUERY_KEYS
        ),
    ],
    ids=[
        *(f"sessions-{parameter}" for parameter in SESSION_QUERY_KEYS),
        *(
            f"measurements-{parameter}"
            for parameter in MEASUREMENT_QUERY_KEYS
        ),
    ],
)
async def test_repeated_identical_supported_scalar_returns_safe_422(
    dependency: Callable[..., object],
    parameter: str,
) -> None:
    application = _strict_application(dependency)

    response = await _get(
        application,
        f"/validate?{parameter}=same&{parameter}=same",
    )

    _assert_safe_422(response)


@pytest.mark.parametrize(
    "model",
    [SessionListQuery, MeasurementListQuery],
    ids=["sessions", "measurements"],
)
def test_query_limit_defaults_to_100(
    model: type[SessionListQuery] | type[MeasurementListQuery],
) -> None:
    assert model().limit == 100


@pytest.mark.parametrize(
    "model",
    [SessionListQuery, MeasurementListQuery],
    ids=["sessions", "measurements"],
)
@pytest.mark.parametrize("limit", [1, 500])
def test_query_limit_accepts_inclusive_boundaries(
    model: type[SessionListQuery] | type[MeasurementListQuery],
    limit: int,
) -> None:
    assert model(limit=limit).limit == limit


@pytest.mark.parametrize(
    "model",
    [SessionListQuery, MeasurementListQuery],
    ids=["sessions", "measurements"],
)
@pytest.mark.parametrize("limit", [0, 501])
def test_query_limit_rejects_values_outside_boundaries(
    model: type[SessionListQuery] | type[MeasurementListQuery],
    limit: int,
) -> None:
    _assert_model_rejected(lambda: model(limit=limit))


@pytest.mark.parametrize(
    "model",
    [SessionListQuery, MeasurementListQuery],
    ids=["sessions", "measurements"],
)
def test_query_cursor_accepts_exact_encoded_length_limit(
    model: type[SessionListQuery] | type[MeasurementListQuery],
) -> None:
    query = model(cursor="A" * 2_048)

    assert query.cursor is not None
    assert len(query.cursor) == 2_048


@pytest.mark.parametrize(
    "model",
    [SessionListQuery, MeasurementListQuery],
    ids=["sessions", "measurements"],
)
def test_query_cursor_rejects_above_encoded_length_limit(
    model: type[SessionListQuery] | type[MeasurementListQuery],
) -> None:
    _assert_model_rejected(lambda: model(cursor="A" * 2_049))


@pytest.mark.parametrize("session_id", [1, POSTGRES_INTEGER_MAX])
def test_session_id_accepts_positive_postgres_integer_boundaries(
    session_id: int,
) -> None:
    assert MeasurementListQuery(session_id=session_id).session_id == session_id


@pytest.mark.parametrize("session_id", [-1, 0, POSTGRES_INTEGER_MAX + 1])
def test_session_id_rejects_values_outside_postgres_integer_boundaries(
    session_id: int,
) -> None:
    _assert_model_rejected(
        lambda: MeasurementListQuery(session_id=session_id)
    )


@pytest.mark.parametrize("status", ["active", "completed", "cancelled"])
def test_session_status_accepts_exact_approved_values(status: str) -> None:
    assert SessionListQuery(status=status).status == status


@pytest.mark.parametrize(
    "status",
    ["pending", "ACTIVE", "Completed", "CANCELLED"],
)
def test_session_status_rejects_invalid_and_case_changed_values(
    status: str,
) -> None:
    _assert_model_rejected(lambda: SessionListQuery(status=status))


@pytest.mark.parametrize(
    ("model", "field_name"),
    [
        (SessionListQuery, "started_from"),
        (SessionListQuery, "started_to"),
        (MeasurementListQuery, "measured_from"),
        (MeasurementListQuery, "measured_to"),
    ],
)
def test_query_timestamps_accept_aware_values(
    model: type[SessionListQuery] | type[MeasurementListQuery],
    field_name: str,
) -> None:
    aware = datetime(2026, 7, 30, tzinfo=UTC)

    query = model.model_validate({field_name: aware})

    assert getattr(query, field_name).utcoffset() is not None


@pytest.mark.parametrize(
    ("model", "field_name"),
    [
        (SessionListQuery, "started_from"),
        (SessionListQuery, "started_to"),
        (MeasurementListQuery, "measured_from"),
        (MeasurementListQuery, "measured_to"),
    ],
)
def test_query_timestamps_reject_naive_values(
    model: type[SessionListQuery] | type[MeasurementListQuery],
    field_name: str,
) -> None:
    naive = datetime(2026, 7, 30)

    _assert_model_rejected(
        lambda: model.model_validate({field_name: naive})
    )


@pytest.mark.parametrize(
    ("model", "from_field", "to_field"),
    [
        (SessionListQuery, "started_from", "started_to"),
        (MeasurementListQuery, "measured_from", "measured_to"),
    ],
    ids=["sessions", "measurements"],
)
def test_query_range_accepts_lower_bound_before_upper_bound(
    model: type[SessionListQuery] | type[MeasurementListQuery],
    from_field: str,
    to_field: str,
) -> None:
    query = model.model_validate(
        {
            from_field: datetime(2026, 7, 30, tzinfo=UTC),
            to_field: datetime(2026, 7, 31, tzinfo=UTC),
        }
    )

    assert getattr(query, from_field) < getattr(query, to_field)


@pytest.mark.parametrize(
    ("model", "from_field", "to_field"),
    [
        (SessionListQuery, "started_from", "started_to"),
        (MeasurementListQuery, "measured_from", "measured_to"),
    ],
    ids=["sessions", "measurements"],
)
def test_query_range_accepts_equal_bounds(
    model: type[SessionListQuery] | type[MeasurementListQuery],
    from_field: str,
    to_field: str,
) -> None:
    boundary = datetime(2026, 7, 30, tzinfo=UTC)

    query = model.model_validate(
        {from_field: boundary, to_field: boundary}
    )

    assert getattr(query, from_field) == getattr(query, to_field)


@pytest.mark.parametrize(
    ("model", "from_field", "to_field"),
    [
        (SessionListQuery, "started_from", "started_to"),
        (MeasurementListQuery, "measured_from", "measured_to"),
    ],
    ids=["sessions", "measurements"],
)
def test_query_range_rejects_lower_bound_after_upper_bound(
    model: type[SessionListQuery] | type[MeasurementListQuery],
    from_field: str,
    to_field: str,
) -> None:
    _assert_model_rejected(
        lambda: model.model_validate(
            {
                from_field: datetime(2026, 7, 31, tzinfo=UTC),
                to_field: datetime(2026, 7, 30, tzinfo=UTC),
            }
        )
    )


@pytest.mark.anyio
async def test_equivalent_session_timezone_offsets_normalize_consistently() -> None:
    captured: list[SessionReadRequest] = []
    application = _session_resolution_application(captured)

    first = await _get(
        application,
        "/devices/7/sessions",
        params={"started_from": "2026-07-30T05:30:00+05:30"},
    )
    second = await _get(
        application,
        "/devices/7/sessions",
        params={"started_from": "2026-07-30T00:00:00Z"},
    )

    assert first.status_code == 204
    assert second.status_code == 204
    assert captured[0].filters == captured[1].filters


@pytest.mark.anyio
async def test_equivalent_measurement_timezone_offsets_normalize_consistently(
) -> None:
    captured: list[MeasurementReadRequest] = []
    application = _measurement_resolution_application(captured)

    first = await _get(
        application,
        "/devices/7/measurements",
        params={"measured_from": "2026-07-30T05:30:00+05:30"},
    )
    second = await _get(
        application,
        "/devices/7/measurements",
        params={"measured_from": "2026-07-30T00:00:00Z"},
    )

    assert first.status_code == 204
    assert second.status_code == 204
    assert captured[0].filters == captured[1].filters


@pytest.mark.anyio
async def test_session_cursor_filter_mismatch_returns_safe_422() -> None:
    filters = normalize_session_filters(
        device_id=7,
        status="active",
        started_from=None,
        started_to=None,
    )
    cursor = encode_cursor(
        "sessions",
        CursorPosition(datetime(2026, 7, 30, tzinfo=UTC), 1),
        filters,
    )
    application = _session_resolution_application([])

    response = await _get(
        application,
        "/devices/7/sessions",
        params={"status": "completed", "cursor": cursor},
    )

    _assert_safe_422(response)


@pytest.mark.anyio
async def test_measurement_cursor_filter_mismatch_returns_safe_422() -> None:
    filters = normalize_measurement_filters(
        device_id=7,
        session_id=11,
        measured_from=None,
        measured_to=None,
    )
    cursor = encode_cursor(
        "measurements",
        CursorPosition(datetime(2026, 7, 30, tzinfo=UTC), 1),
        filters,
    )
    application = _measurement_resolution_application([])

    response = await _get(
        application,
        "/devices/7/measurements",
        params={"session_id": 12, "cursor": cursor},
    )

    _assert_safe_422(response)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "resource",
    ["sessions", "measurements"],
)
async def test_cursor_accepts_changed_valid_page_limit(
    resource: str,
) -> None:
    position = CursorPosition(datetime(2026, 7, 30, tzinfo=UTC), 1)

    if resource == "sessions":
        filters = normalize_session_filters(
            device_id=7,
            status="active",
            started_from=None,
            started_to=None,
        )
        cursor = encode_cursor("sessions", position, filters)
        captured: list[SessionReadRequest] = []
        application = _session_resolution_application(captured)
        path = "/devices/7/sessions"
        params = {"status": "active", "limit": 500, "cursor": cursor}
        expected = SessionReadRequest(filters, 500, position)
    else:
        filters = normalize_measurement_filters(
            device_id=7,
            session_id=11,
            measured_from=None,
            measured_to=None,
        )
        cursor = encode_cursor("measurements", position, filters)
        captured = []
        application = _measurement_resolution_application(captured)
        path = "/devices/7/measurements"
        params = {"session_id": 11, "limit": 500, "cursor": cursor}
        expected = MeasurementReadRequest(filters, 500, position)

    response = await _get(application, path, params=params)

    assert response.status_code == 204
    assert captured == [expected]
    assert captured[0].limit == 500
    assert captured[0].filters == filters


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("application_factory", "path"),
    [
        (_session_resolution_application, "/devices/7/sessions"),
        (
            _measurement_resolution_application,
            "/devices/7/measurements",
        ),
    ],
    ids=["sessions", "measurements"],
)
async def test_oversized_query_cursor_uses_safe_422_flow(
    application_factory: Callable[[list[object]], FastAPI],
    path: str,
) -> None:
    application = application_factory([])

    response = await _get(
        application,
        path,
        params={"cursor": "A" * 2_049},
    )

    _assert_safe_422(response)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("application_factory", "path", "params"),
    [
        (
            _session_resolution_application,
            "/devices/7/sessions",
            {"status": "invalid-status-marker"},
        ),
        (
            _session_resolution_application,
            "/devices/7/sessions",
            {"started_from": "2026-07-30T00:00:00"},
        ),
        (
            _session_resolution_application,
            "/devices/7/sessions",
            {
                "started_from": "2026-07-31T00:00:00Z",
                "started_to": "2026-07-30T00:00:00Z",
            },
        ),
        (
            _measurement_resolution_application,
            "/devices/7/measurements",
            {"session_id": 0},
        ),
        (
            _measurement_resolution_application,
            "/devices/7/measurements",
            {"measured_from": "2026-07-30T00:00:00"},
        ),
        (
            _measurement_resolution_application,
            "/devices/7/measurements",
            {
                "measured_from": "2026-07-31T00:00:00Z",
                "measured_to": "2026-07-30T00:00:00Z",
            },
        ),
    ],
    ids=[
        "invalid-status",
        "naive-session-time",
        "reversed-session-range",
        "zero-session-id",
        "naive-measurement-time",
        "reversed-measurement-range",
    ],
)
async def test_typed_query_failures_use_safe_422_flow(
    application_factory: Callable[[list[object]], FastAPI],
    path: str,
    params: dict[str, object],
) -> None:
    application = application_factory([])

    response = await _get(application, path, params=params)

    _assert_safe_422(response)


@pytest.mark.anyio
async def test_invalid_cursor_payload_is_not_exposed_by_safe_422() -> None:
    application = _session_resolution_application([])

    response = await _get(
        application,
        "/devices/7/sessions",
        params={"cursor": "cursor-payload-value-marker"},
    )

    _assert_safe_422(response)


@pytest.mark.anyio
async def test_resolvers_complete_without_injected_data_layer_dependencies() -> None:
    captured_sessions: list[SessionReadRequest] = []
    captured_measurements: list[MeasurementReadRequest] = []
    session_application = _session_resolution_application(
        captured_sessions
    )
    measurement_application = _measurement_resolution_application(
        captured_measurements
    )

    session_response = await _get(
        session_application,
        "/devices/7/sessions",
        params={"status": "active"},
    )
    measurement_response = await _get(
        measurement_application,
        "/devices/7/measurements",
        params={"session_id": 11},
    )

    assert session_response.status_code == 204
    assert measurement_response.status_code == 204
    assert type(captured_sessions[0]) is SessionReadRequest
    assert type(captured_measurements[0]) is MeasurementReadRequest
