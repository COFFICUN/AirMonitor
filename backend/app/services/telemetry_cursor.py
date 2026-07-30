"""Pure normalized-filter values and telemetry cursor v1 primitives."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, TypeAlias


CursorResource: TypeAlias = Literal["sessions", "measurements"]
SessionStatus: TypeAlias = Literal["active", "completed", "cancelled"]

_CURSOR_VERSION = 1
_MAX_ENCODED_CURSOR_CHARS = 2_048
_MAX_DECODED_CURSOR_BYTES = 1_024
_MAX_POSITION_ID = 2_147_483_647
_PAYLOAD_FIELDS = frozenset({"f", "p", "r", "v"})
_BASE64URL_ALPHABET = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789-_"
)
_FINGERPRINT_LENGTH = 43
_ERROR_MESSAGE = "Invalid telemetry cursor."


class CursorValidationError(ValueError):
    """Sanitized failure for every invalid cursor operation."""

    def __init__(self) -> None:
        super().__init__(_ERROR_MESSAGE)


@dataclass(frozen=True)
class CursorPosition:
    timestamp: datetime
    identifier: int


@dataclass(frozen=True)
class SessionReadFilters:
    device_id: int
    status: SessionStatus | None
    started_from: datetime | None
    started_to: datetime | None


@dataclass(frozen=True)
class MeasurementReadFilters:
    device_id: int
    session_id: int | None
    measured_from: datetime | None
    measured_to: datetime | None


@dataclass(frozen=True)
class SessionReadRequest:
    filters: SessionReadFilters
    limit: int
    position: CursorPosition | None


@dataclass(frozen=True)
class MeasurementReadRequest:
    filters: MeasurementReadFilters
    limit: int
    position: CursorPosition | None


def _invalid() -> CursorValidationError:
    return CursorValidationError()


def _bounded_identifier(value: object) -> int:
    if type(value) is not int or not 1 <= value <= _MAX_POSITION_ID:
        raise _invalid()
    return value


def _as_utc(value: object) -> datetime:
    if type(value) is not datetime:
        raise _invalid()
    try:
        if value.tzinfo is None or value.utcoffset() is None:
            raise _invalid()
        return value.astimezone(UTC)
    except CursorValidationError:
        raise
    except (OverflowError, TypeError, ValueError):
        raise _invalid() from None


def _optional_utc(value: object) -> datetime | None:
    if value is None:
        return None
    return _as_utc(value)


def _validate_range(
    lower: datetime | None,
    upper: datetime | None,
) -> None:
    if lower is not None and upper is not None and lower > upper:
        raise _invalid()


def normalize_session_filters(
    *,
    device_id: int,
    status: str | None,
    started_from: datetime | None,
    started_to: datetime | None,
) -> SessionReadFilters:
    """Return immutable session filters with aware times normalized to UTC."""
    normalized_device_id = _bounded_identifier(device_id)
    if status is not None and (
        type(status) is not str
        or status not in ("active", "completed", "cancelled")
    ):
        raise _invalid()
    normalized_from = _optional_utc(started_from)
    normalized_to = _optional_utc(started_to)
    _validate_range(normalized_from, normalized_to)
    return SessionReadFilters(
        normalized_device_id,
        status,
        normalized_from,
        normalized_to,
    )


def normalize_measurement_filters(
    *,
    device_id: int,
    session_id: int | None,
    measured_from: datetime | None,
    measured_to: datetime | None,
) -> MeasurementReadFilters:
    """Return immutable measurement filters with times normalized to UTC."""
    normalized_device_id = _bounded_identifier(device_id)
    normalized_session_id = (
        None if session_id is None else _bounded_identifier(session_id)
    )
    normalized_from = _optional_utc(measured_from)
    normalized_to = _optional_utc(measured_to)
    _validate_range(normalized_from, normalized_to)
    return MeasurementReadFilters(
        normalized_device_id,
        normalized_session_id,
        normalized_from,
        normalized_to,
    )


def _canonical_timestamp(value: object) -> str:
    normalized = _as_utc(value)
    return (
        f"{normalized.year:04d}-{normalized.month:02d}-"
        f"{normalized.day:02d}T{normalized.hour:02d}:"
        f"{normalized.minute:02d}:{normalized.second:02d}."
        f"{normalized.microsecond:06d}Z"
    )


def _canonical_json(document: object) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8", errors="strict")


def _session_filter_document(
    filters: SessionReadFilters,
) -> dict[str, object]:
    normalized = normalize_session_filters(
        device_id=filters.device_id,
        status=filters.status,
        started_from=filters.started_from,
        started_to=filters.started_to,
    )
    return {
        "device_id": normalized.device_id,
        "started_from": (
            None
            if normalized.started_from is None
            else _canonical_timestamp(normalized.started_from)
        ),
        "started_to": (
            None
            if normalized.started_to is None
            else _canonical_timestamp(normalized.started_to)
        ),
        "status": normalized.status,
    }


def _measurement_filter_document(
    filters: MeasurementReadFilters,
) -> dict[str, object]:
    normalized = normalize_measurement_filters(
        device_id=filters.device_id,
        session_id=filters.session_id,
        measured_from=filters.measured_from,
        measured_to=filters.measured_to,
    )
    return {
        "device_id": normalized.device_id,
        "measured_from": (
            None
            if normalized.measured_from is None
            else _canonical_timestamp(normalized.measured_from)
        ),
        "measured_to": (
            None
            if normalized.measured_to is None
            else _canonical_timestamp(normalized.measured_to)
        ),
        "session_id": normalized.session_id,
    }


def _filter_document(
    resource: CursorResource,
    filters: SessionReadFilters | MeasurementReadFilters,
) -> dict[str, object]:
    if resource == "sessions" and type(filters) is SessionReadFilters:
        return _session_filter_document(filters)
    if (
        resource == "measurements"
        and type(filters) is MeasurementReadFilters
    ):
        return _measurement_filter_document(filters)
    raise _invalid()


def _fingerprint(
    resource: CursorResource,
    filters: SessionReadFilters | MeasurementReadFilters,
) -> str:
    digest = hashlib.sha256(
        _canonical_json(_filter_document(resource, filters))
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _supported_resource(value: object) -> CursorResource:
    if type(value) is not str or value not in {"sessions", "measurements"}:
        raise _invalid()
    return value


def _validated_position(value: object) -> CursorPosition:
    if type(value) is not CursorPosition:
        raise _invalid()
    return CursorPosition(
        _as_utc(value.timestamp),
        _bounded_identifier(value.identifier),
    )


def encode_cursor(
    resource: CursorResource,
    position: CursorPosition,
    filters: SessionReadFilters | MeasurementReadFilters,
) -> str:
    """Encode one canonical, unpadded telemetry cursor."""
    try:
        normalized_resource = _supported_resource(resource)
        normalized_position = _validated_position(position)
        document = {
            "f": _fingerprint(normalized_resource, filters),
            "p": [
                _canonical_timestamp(normalized_position.timestamp),
                normalized_position.identifier,
            ],
            "r": normalized_resource,
            "v": _CURSOR_VERSION,
        }
        payload = _canonical_json(document)
        if len(payload) > _MAX_DECODED_CURSOR_BYTES:
            raise _invalid()
        cursor = (
            base64.urlsafe_b64encode(payload)
            .decode("ascii")
            .rstrip("=")
        )
        if len(cursor) > _MAX_ENCODED_CURSOR_CHARS:
            raise _invalid()
        return cursor
    except CursorValidationError:
        raise
    except (OverflowError, TypeError, UnicodeError, ValueError):
        raise _invalid() from None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise _invalid()
        document[key] = value
    return document


def _reject_constant(value: str) -> object:
    del value
    raise _invalid()


def _decode_payload(cursor: object) -> tuple[dict[str, object], bytes]:
    if type(cursor) is not str:
        raise _invalid()
    if not cursor.isascii():
        raise _invalid()
    if len(cursor) > _MAX_ENCODED_CURSOR_CHARS:
        raise _invalid()
    if "=" in cursor:
        raise _invalid()
    if (
        not cursor
        or any(character not in _BASE64URL_ALPHABET for character in cursor)
        or len(cursor) % 4 == 1
    ):
        raise _invalid()

    padding = "=" * (-len(cursor) % 4)
    try:
        payload = base64.b64decode(
            cursor + padding,
            altchars=b"-_",
            validate=True,
        )
    except ValueError:
        raise _invalid() from None
    if len(payload) > _MAX_DECODED_CURSOR_BYTES:
        raise _invalid()
    canonical_cursor = (
        base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    )
    if canonical_cursor != cursor:
        raise _invalid()

    try:
        payload_text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise _invalid() from None
    try:
        document = json.loads(
            payload_text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except CursorValidationError:
        raise
    except (json.JSONDecodeError, RecursionError):
        raise _invalid() from None

    if type(document) is not dict:
        raise _invalid()
    if frozenset(document) != _PAYLOAD_FIELDS:
        raise _invalid()
    try:
        canonical_payload = _canonical_json(document)
    except (OverflowError, RecursionError, TypeError, UnicodeError, ValueError):
        raise _invalid() from None
    if canonical_payload != payload:
        raise _invalid()
    return document, payload


def _decoded_timestamp(value: object) -> datetime:
    if type(value) is not str or len(value) != 27:
        raise _invalid()
    try:
        parsed = datetime.strptime(
            value,
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ).replace(tzinfo=UTC)
    except (TypeError, ValueError):
        raise _invalid() from None
    if _canonical_timestamp(parsed) != value:
        raise _invalid()
    return parsed


def _valid_fingerprint(value: object) -> str:
    if (
        type(value) is not str
        or len(value) != _FINGERPRINT_LENGTH
        or any(
            character not in _BASE64URL_ALPHABET
            for character in value
        )
    ):
        raise _invalid()
    return value


def _time_bounds(
    filters: SessionReadFilters | MeasurementReadFilters,
) -> tuple[datetime | None, datetime | None]:
    if type(filters) is SessionReadFilters:
        return filters.started_from, filters.started_to
    if type(filters) is MeasurementReadFilters:
        return filters.measured_from, filters.measured_to
    raise _invalid()


def _require_position_within_bounds(
    position: CursorPosition,
    filters: SessionReadFilters | MeasurementReadFilters,
) -> None:
    lower, upper = _time_bounds(filters)
    normalized_lower = _optional_utc(lower)
    normalized_upper = _optional_utc(upper)
    if normalized_lower is not None and position.timestamp < normalized_lower:
        raise _invalid()
    if normalized_upper is not None and position.timestamp >= normalized_upper:
        raise _invalid()


def decode_cursor(
    cursor: str,
    expected_resource: CursorResource,
    filters: SessionReadFilters | MeasurementReadFilters,
) -> CursorPosition:
    """Decode and validate one untrusted telemetry cursor."""
    document, _ = _decode_payload(cursor)

    version = document["v"]
    if type(version) is not int or version != _CURSOR_VERSION:
        raise _invalid()

    payload_resource = _supported_resource(document["r"])
    normalized_resource = _supported_resource(expected_resource)
    if payload_resource != normalized_resource:
        raise _invalid()

    raw_position = document["p"]
    if type(raw_position) is not list or len(raw_position) != 2:
        raise _invalid()
    position = CursorPosition(
        _decoded_timestamp(raw_position[0]),
        _bounded_identifier(raw_position[1]),
    )

    supplied_fingerprint = _valid_fingerprint(document["f"])
    expected_fingerprint = _fingerprint(
        normalized_resource,
        filters,
    )
    if supplied_fingerprint != expected_fingerprint:
        raise _invalid()

    _require_position_within_bounds(position, filters)
    return position


__all__ = [
    "CursorPosition",
    "CursorResource",
    "CursorValidationError",
    "MeasurementReadFilters",
    "MeasurementReadRequest",
    "SessionReadFilters",
    "SessionReadRequest",
    "decode_cursor",
    "encode_cursor",
    "normalize_measurement_filters",
    "normalize_session_filters",
]
