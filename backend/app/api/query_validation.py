"""Strict raw-query guards and pure telemetry request resolvers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Path, Query, Request
from fastapi.exceptions import RequestValidationError

from app.schemas._base import POSTGRES_INTEGER_MAX
from app.schemas.telemetry import MeasurementListQuery, SessionListQuery
from app.services.telemetry_cursor import (
    CursorValidationError,
    MeasurementReadRequest,
    SessionReadRequest,
    decode_cursor,
    normalize_measurement_filters,
    normalize_session_filters,
)


_SESSION_QUERY_KEYS = frozenset(
    {"status", "started_from", "started_to", "limit", "cursor"}
)
_MEASUREMENT_QUERY_KEYS = frozenset(
    {"session_id", "measured_from", "measured_to", "limit", "cursor"}
)
_DeviceId = Annotated[
    int,
    Path(gt=0, le=POSTGRES_INTEGER_MAX),
]
_SessionQuery = Annotated[SessionListQuery, Query()]
_MeasurementQuery = Annotated[MeasurementListQuery, Query()]


def _validation_error() -> RequestValidationError:
    return RequestValidationError([])


def _strict_query_parameters(
    request: Request,
    allowed_keys: frozenset[str],
) -> None:
    seen: set[str] = set()
    for key, _ in request.query_params.multi_items():
        if key not in allowed_keys or key in seen:
            raise _validation_error()
        seen.add(key)


def strict_session_query_parameters(request: Request) -> None:
    """Reject unknown or repeated session-list scalar query parameters."""
    _strict_query_parameters(request, _SESSION_QUERY_KEYS)


def strict_measurement_query_parameters(request: Request) -> None:
    """Reject unknown or repeated measurement-list scalar parameters."""
    _strict_query_parameters(request, _MEASUREMENT_QUERY_KEYS)


def resolve_session_read_request(
    device_id: _DeviceId,
    query: _SessionQuery,
) -> SessionReadRequest:
    try:
        filters = normalize_session_filters(
            device_id=device_id,
            status=query.status,
            started_from=query.started_from,
            started_to=query.started_to,
        )
        position = (
            None
            if query.cursor is None
            else decode_cursor(query.cursor, "sessions", filters)
        )
    except CursorValidationError:
        raise _validation_error() from None
    return SessionReadRequest(filters, query.limit, position)


def resolve_measurement_read_request(
    device_id: _DeviceId,
    query: _MeasurementQuery,
) -> MeasurementReadRequest:
    try:
        filters = normalize_measurement_filters(
            device_id=device_id,
            session_id=query.session_id,
            measured_from=query.measured_from,
            measured_to=query.measured_to,
        )
        position = (
            None
            if query.cursor is None
            else decode_cursor(query.cursor, "measurements", filters)
        )
    except CursorValidationError:
        raise _validation_error() from None
    return MeasurementReadRequest(filters, query.limit, position)


__all__ = [
    "resolve_measurement_read_request",
    "resolve_session_read_request",
    "strict_measurement_query_parameters",
    "strict_session_query_parameters",
]
