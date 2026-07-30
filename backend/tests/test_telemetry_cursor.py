"""Black-box contracts for telemetry cursor v1 and normalized filters."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.schemas._base import POSTGRES_INTEGER_MAX
from app.services.telemetry_cursor import (
    CursorPosition,
    CursorResource,
    CursorValidationError,
    MeasurementReadFilters,
    SessionReadFilters,
    decode_cursor,
    encode_cursor,
    normalize_measurement_filters,
    normalize_session_filters,
)


SESSION_RESOURCE: CursorResource = "sessions"
MEASUREMENT_RESOURCE: CursorResource = "measurements"
POSITION_TIMESTAMP = datetime(
    2026,
    7,
    30,
    5,
    0,
    tzinfo=timezone(timedelta(hours=5)),
)
CANONICAL_POSITION_TIMESTAMP = "2026-07-30T00:00:00.000000Z"
URLSAFE_TEXT = re.compile(r"[A-Za-z0-9_-]+")
SAFE_FINGERPRINT = re.compile(r"[A-Za-z0-9_-]{43}")
SESSION_FINGERPRINT_VECTOR = (
    "Fyo9RltXgZFinDACG7SKuXhr-Q32CVEDDYbC8Cqwsxc"
)
MEASUREMENT_FINGERPRINT_VECTOR = (
    "ARdRoG52q4S4U3swx-AGuessvtbNE602TFCaubU_aMA"
)

INVALID_STRUCTURE_WIRES = (
    (
        "duplicate-key",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidiI6MSwidiI6MX0",
    ),
    (
        "unknown-field",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidSI6bnVsbCwidiI6MX0",
    ),
    (
        "missing-field",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIn0",
    ),
    ("top-level-array", "W10"),
)
NONSTANDARD_JSON_WIRES = (
    (
        "nan",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidiI6TmFOfQ",
    ),
    (
        "infinity",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidiI6SW5maW5pdHl9",
    ),
    (
        "negative-infinity",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidiI6LUluZmluaXR5fQ",
    ),
)
NONCANONICAL_JSON_WIRES = (
    (
        "key-order",
        "eyJ2IjoxLCJyIjoic2Vzc2lvbnMiLCJwIjpbIjIwMjYtMDctMzBUMDA6MD"
        "A6MDAuMDAwMDAwWiIsMV0sImYiOiJGeW85Umx0WGdaRmluREFDRzdTS3VY"
        "aHItUTMyQ1ZFRERZYkM4Q3F3c3hjIn0",
    ),
    (
        "whitespace",
        "eyJmIjogIkZ5bzlSbHRYZ1pGaW5EQUNHN1NLdVhoci1RMzJDVkVERFliQzhD"
        "cXdzeGMiLCJwIjpbIjIwMjYtMDctMzBUMDA6MDA6MDAuMDAwMDAwWiIsMV"
        "0sInIiOiJzZXNzaW9ucyIsInYiOjF9",
    ),
    (
        "escaped-text",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3NcdTAwNjlvbnMiLCJ2IjoxfQ",
    ),
)
INVALID_POSITION_WIRES = (
    (
        "null",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOm51bGwsInIiOiJzZXNzaW9ucyIsInYiOjF9",
    ),
    (
        "one-member",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIl0s"
        "InIiOiJzZXNzaW9ucyIsInYiOjF9",
    ),
    (
        "three-members",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "LDJdLCJyIjoic2Vzc2lvbnMiLCJ2IjoxfQ",
    ),
)
INVALID_TIMESTAMP_WIRES = (
    (
        "invalid",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsibm90LWEtdGltZXN0YW1wIiwxXSwiciI6InNlc3Np"
        "b25zIiwidiI6MX0",
    ),
    (
        "noncanonical",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMFoiLDFdLCJyIjoi"
        "c2Vzc2lvbnMiLCJ2IjoxfQ",
    ),
    (
        "naive",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDAiLDFd"
        "LCJyIjoic2Vzc2lvbnMiLCJ2IjoxfQ",
    ),
    (
        "non-utc",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwNTowMDowMC4wMDAwMDArMDU6"
        "MDAiLDFdLCJyIjoic2Vzc2lvbnMiLCJ2IjoxfQ",
    ),
    (
        "invalid-calendar",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wMi0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidiI6MX0",
    ),
)
INVALID_IDENTIFIER_WIRES = (
    (
        "boolean",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIix0"
        "cnVlXSwiciI6InNlc3Npb25zIiwidiI6MX0",
    ),
    (
        "zero",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiww"
        "XSwiciI6InNlc3Npb25zIiwidiI6MX0",
    ),
    (
        "negative",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwt"
        "MV0sInIiOiJzZXNzaW9ucyIsInYiOjF9",
    ),
    (
        "float",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "LjBdLCJyIjoic2Vzc2lvbnMiLCJ2IjoxfQ",
    ),
    (
        "string",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwi"
        "MSJdLCJyIjoic2Vzc2lvbnMiLCJ2IjoxfQ",
    ),
    (
        "above-postgres-maximum",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwy"
        "MTQ3NDgzNjQ4XSwiciI6InNlc3Npb25zIiwidiI6MX0",
    ),
)
INVALID_VERSION_WIRES = (
    (
        "integer-two",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidiI6Mn0",
    ),
    (
        "boolean",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidiI6dHJ1ZX0",
    ),
    (
        "float",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidiI6MS4wfQ",
    ),
    (
        "string",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidiI6IjEifQ",
    ),
    (
        "null",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidiI6bnVsbH0",
    ),
)
INVALID_RESOURCE_WIRES = (
    (
        "boolean",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6dHJ1ZSwidiI6MX0",
    ),
    (
        "integer",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6MSwidiI6MX0",
    ),
    (
        "null",
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6bnVsbCwidiI6MX0",
    ),
)
MALFORMED_FINGERPRINT_WIRES = (
    (
        "wrong-length",
        "eyJmIjoiQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU"
        "FBQUFBIiwicCI6WyIyMDI2LTA3LTMwVDAwOjAwOjAwLjAwMDAwMFoiLDFd"
        "LCJyIjoic2Vzc2lvbnMiLCJ2IjoxfQ",
    ),
    (
        "invalid-alphabet",
        "eyJmIjoiQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU"
        "FBQUFBKyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidiI6MX0",
    ),
)


def _session_filters(
    *,
    device_id: int = 7,
    status: str | None = None,
    started_from: datetime | None = None,
    started_to: datetime | None = None,
) -> SessionReadFilters:
    return normalize_session_filters(
        device_id=device_id,
        status=status,
        started_from=started_from,
        started_to=started_to,
    )


def _measurement_filters(
    *,
    device_id: int = 7,
    session_id: int | None = None,
    measured_from: datetime | None = None,
    measured_to: datetime | None = None,
) -> MeasurementReadFilters:
    return normalize_measurement_filters(
        device_id=device_id,
        session_id=session_id,
        measured_from=measured_from,
        measured_to=measured_to,
    )


def _position(
    timestamp: datetime = POSITION_TIMESTAMP,
    identifier: int = 1,
) -> CursorPosition:
    return CursorPosition(timestamp, identifier)


def _protocol_bytes(cursor: str) -> bytes:
    """Decode production output only for exact wire-format assertions."""
    padding = "=" * (-len(cursor) % 4)
    return base64.urlsafe_b64decode(cursor + padding)


def _protocol_document(cursor: str) -> dict[str, object]:
    return json.loads(_protocol_bytes(cursor))


def _fingerprint(
    resource: CursorResource,
    filters: SessionReadFilters | MeasurementReadFilters,
) -> str:
    document = _protocol_document(
        encode_cursor(resource, _position(), filters)
    )
    return str(document["f"])


def _require(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _assert_cursor_operation_rejected(
    operation: Callable[[], object],
) -> None:
    unexpected_type: str | None = None
    try:
        operation()
    except CursorValidationError:
        return
    except Exception as error:  # pragma: no cover - contract failure path
        unexpected_type = type(error).__name__

    if unexpected_type is not None:
        pytest.fail(
            f"cursor rejection used unexpected exception type {unexpected_type}",
            pytrace=False,
        )
    pytest.fail("invalid cursor operation was accepted", pytrace=False)


def _assert_cursor_rejected(cursor: str) -> None:
    filters = _session_filters()
    _assert_cursor_operation_rejected(
        lambda: decode_cursor(cursor, SESSION_RESOURCE, filters)
    )


def test_sessions_cursor_encode_decode_round_trip() -> None:
    filters = _session_filters(
        status="active",
        started_from=datetime(2026, 7, 29, tzinfo=UTC),
        started_to=datetime(2026, 7, 31, tzinfo=UTC),
    )

    position = _position()
    cursor = encode_cursor(SESSION_RESOURCE, position, filters)

    assert decode_cursor(cursor, SESSION_RESOURCE, filters) == position


def test_measurements_cursor_encode_decode_round_trip() -> None:
    filters = _measurement_filters(
        session_id=11,
        measured_from=datetime(2026, 7, 29, tzinfo=UTC),
        measured_to=datetime(2026, 7, 31, tzinfo=UTC),
    )

    position = _position()
    cursor = encode_cursor(MEASUREMENT_RESOURCE, position, filters)

    assert decode_cursor(cursor, MEASUREMENT_RESOURCE, filters) == position


@pytest.mark.parametrize(
    "resource",
    [SESSION_RESOURCE, MEASUREMENT_RESOURCE],
    ids=["sessions", "measurements"],
)
def test_supported_resource_kinds_are_deterministic_and_url_safe(
    resource: CursorResource,
) -> None:
    filters = (
        _session_filters()
        if resource == SESSION_RESOURCE
        else _measurement_filters()
    )
    first = encode_cursor(resource, _position(), filters)
    second = encode_cursor(resource, _position(), filters)

    _require(first == second, "cursor encoding was not deterministic")
    _require(first.isascii(), "cursor was not ASCII")
    _require("=" not in first, "cursor included Base64 padding")
    _require(
        URLSAFE_TEXT.fullmatch(first) is not None,
        "cursor used a character outside the Base64url alphabet",
    )
    _require(len(first) <= 2_048, "encoder exceeded the wire-size limit")


def test_cursor_payload_is_canonical_compact_sorted_utf8_json() -> None:
    cursor = encode_cursor(
        SESSION_RESOURCE,
        _position(),
        _session_filters(),
    )
    payload_bytes = _protocol_bytes(cursor)
    payload_text = payload_bytes.decode("utf-8")
    document = json.loads(payload_text)

    _require(
        payload_text.encode("utf-8") == payload_bytes,
        "payload did not use strict UTF-8",
    )
    _require(
        list(document) == ["f", "p", "r", "v"],
        "payload keys were not exact and lexicographically sorted",
    )
    _require(
        re.fullmatch(
            r'\{"f":"[A-Za-z0-9_-]{43}",'
            r'"p":\["2026-07-30T00:00:00\.000000Z",1\],'
            r'"r":"sessions","v":1\}',
            payload_text,
        )
        is not None,
        "payload was not exact canonical compact JSON",
    )
    _require(
        document["p"] == [CANONICAL_POSITION_TIMESTAMP, 1],
        "position timestamp was not exact canonical UTC",
    )


@pytest.mark.parametrize("identifier", [1, POSTGRES_INTEGER_MAX])
def test_cursor_identifier_accepts_postgres_integer_boundaries(
    identifier: int,
) -> None:
    position = CursorPosition(datetime(2026, 7, 30, tzinfo=UTC), identifier)
    filters = _session_filters()
    cursor = encode_cursor(SESSION_RESOURCE, position, filters)

    assert decode_cursor(cursor, SESSION_RESOURCE, filters) == position


@pytest.mark.parametrize(
    ("resource", "filters", "expected"),
    [
        (
            SESSION_RESOURCE,
            _session_filters(),
            SESSION_FINGERPRINT_VECTOR,
        ),
        (
            MEASUREMENT_RESOURCE,
            _measurement_filters(),
            MEASUREMENT_FINGERPRINT_VECTOR,
        ),
    ],
    ids=["sessions", "measurements"],
)
def test_normalized_filter_fingerprint_matches_approved_known_vector(
    resource: CursorResource,
    filters: SessionReadFilters | MeasurementReadFilters,
    expected: str,
) -> None:
    assert _fingerprint(resource, filters) == expected


@pytest.mark.parametrize("changed_field", ["device-id", "status"])
def test_session_fingerprint_changes_with_bound_filters(
    changed_field: str,
) -> None:
    if changed_field == "device-id":
        baseline = _session_filters(device_id=7)
        changed = _session_filters(device_id=8)
    else:
        baseline = _session_filters(status="active")
        changed = _session_filters(status="completed")

    assert _fingerprint(SESSION_RESOURCE, baseline) != _fingerprint(
        SESSION_RESOURCE,
        changed,
    )


def test_measurement_fingerprint_changes_with_session_id() -> None:
    first = _measurement_filters(session_id=11)
    second = _measurement_filters(session_id=12)

    assert _fingerprint(MEASUREMENT_RESOURCE, first) != _fingerprint(
        MEASUREMENT_RESOURCE,
        second,
    )


@pytest.mark.parametrize(
    ("resource", "changed_field"),
    [
        (SESSION_RESOURCE, "started-from"),
        (SESSION_RESOURCE, "started-to"),
        (MEASUREMENT_RESOURCE, "measured-from"),
        (MEASUREMENT_RESOURCE, "measured-to"),
    ],
    ids=[
        "started-from",
        "started-to",
        "measured-from",
        "measured-to",
    ],
)
def test_fingerprint_changes_with_time_filters(
    resource: CursorResource,
    changed_field: str,
) -> None:
    if changed_field == "started-from":
        baseline = _session_filters()
        changed = _session_filters(
            started_from=datetime(2026, 7, 29, tzinfo=UTC)
        )
    elif changed_field == "started-to":
        baseline = _session_filters()
        changed = _session_filters(
            started_to=datetime(2026, 7, 31, tzinfo=UTC)
        )
    elif changed_field == "measured-from":
        baseline = _measurement_filters()
        changed = _measurement_filters(
            measured_from=datetime(2026, 7, 29, tzinfo=UTC)
        )
    else:
        baseline = _measurement_filters()
        changed = _measurement_filters(
            measured_to=datetime(2026, 7, 31, tzinfo=UTC)
        )

    assert _fingerprint(resource, baseline) != _fingerprint(resource, changed)


def test_cursor_above_encoded_size_limit_is_rejected() -> None:
    _assert_cursor_rejected("A" * 2_049)


def test_cursor_at_encoded_size_limit_still_obeys_decoded_limit() -> None:
    _assert_cursor_rejected("A" * 2_048)


def test_cursor_above_decoded_size_limit_is_rejected() -> None:
    # 1,367 unpadded "A" characters decode to 1,025 zero bytes.
    _assert_cursor_rejected("A" * 1_367)


def test_cursor_at_decoded_size_limit_still_obeys_json_validation() -> None:
    # 1,366 unpadded "A" characters decode to 1,024 zero bytes.
    _assert_cursor_rejected("A" * 1_366)


@pytest.mark.parametrize(
    "wire",
    ["", "abc!", "é", "A", "_w", "ew"],
    ids=[
        "empty",
        "malformed-base64",
        "non-ascii",
        "impossible-base64-length",
        "invalid-utf8",
        "malformed-json",
    ],
)
def test_malformed_wire_values_are_rejected(wire: str) -> None:
    _assert_cursor_rejected(wire)


def test_padded_base64_is_rejected() -> None:
    valid = encode_cursor(
        SESSION_RESOURCE,
        _position(),
        _session_filters(),
    )

    _assert_cursor_rejected(valid + "=")


def test_trailing_json_is_rejected() -> None:
    wire = (
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6InNlc3Npb25zIiwidiI6MX1udWxs"
    )

    _assert_cursor_rejected(wire)


@pytest.mark.parametrize(
    "wire",
    [wire for _, wire in INVALID_STRUCTURE_WIRES],
    ids=[case for case, _ in INVALID_STRUCTURE_WIRES],
)
def test_payload_shape_requires_exact_unique_fields(wire: str) -> None:
    _assert_cursor_rejected(wire)


@pytest.mark.parametrize(
    "wire",
    [wire for _, wire in NONSTANDARD_JSON_WIRES],
    ids=[case for case, _ in NONSTANDARD_JSON_WIRES],
)
def test_nonstandard_json_constants_are_rejected(wire: str) -> None:
    _assert_cursor_rejected(wire)


@pytest.mark.parametrize(
    "wire",
    [wire for _, wire in NONCANONICAL_JSON_WIRES],
    ids=[case for case, _ in NONCANONICAL_JSON_WIRES],
)
def test_equivalent_noncanonical_json_is_rejected(wire: str) -> None:
    _assert_cursor_rejected(wire)


@pytest.mark.parametrize(
    "wire",
    [wire for _, wire in INVALID_VERSION_WIRES],
    ids=[case for case, _ in INVALID_VERSION_WIRES],
)
def test_cursor_version_must_be_exact_integer_one(wire: str) -> None:
    _assert_cursor_rejected(wire)


def test_cursor_is_rejected_for_wrong_resource_kind() -> None:
    wire = (
        "eyJmIjoiRnlvOVJsdFhnWkZpbkRBQ0c3U0t1WGhyLVEzMkNWRUREWWJDOE"
        "Nxd3N4YyIsInAiOlsiMjAyNi0wNy0zMFQwMDowMDowMC4wMDAwMDBaIiwx"
        "XSwiciI6Im1lYXN1cmVtZW50cyIsInYiOjF9"
    )

    _assert_cursor_operation_rejected(
        lambda: decode_cursor(
            wire,
            SESSION_RESOURCE,
            _session_filters(),
        )
    )


@pytest.mark.parametrize(
    "wire",
    [wire for _, wire in INVALID_RESOURCE_WIRES],
    ids=[case for case, _ in INVALID_RESOURCE_WIRES],
)
def test_cursor_resource_kind_must_be_a_string(wire: str) -> None:
    _assert_cursor_rejected(wire)


def test_unsupported_resource_kind_is_rejected() -> None:
    _assert_cursor_operation_rejected(
        lambda: encode_cursor(
            "unsupported",
            _position(),
            _session_filters(),
        )
    )


@pytest.mark.parametrize(
    "wire",
    [wire for _, wire in INVALID_POSITION_WIRES],
    ids=[case for case, _ in INVALID_POSITION_WIRES],
)
def test_cursor_position_requires_exact_two_member_array(wire: str) -> None:
    _assert_cursor_rejected(wire)


@pytest.mark.parametrize(
    "wire",
    [wire for _, wire in INVALID_TIMESTAMP_WIRES],
    ids=[case for case, _ in INVALID_TIMESTAMP_WIRES],
)
def test_cursor_timestamp_requires_exact_valid_canonical_utc(wire: str) -> None:
    _assert_cursor_rejected(wire)


@pytest.mark.parametrize(
    "wire",
    [wire for _, wire in INVALID_IDENTIFIER_WIRES],
    ids=[case for case, _ in INVALID_IDENTIFIER_WIRES],
)
def test_cursor_identifier_requires_bounded_positive_exact_integer(
    wire: str,
) -> None:
    _assert_cursor_rejected(wire)


@pytest.mark.parametrize(
    "wire",
    [wire for _, wire in MALFORMED_FINGERPRINT_WIRES],
    ids=[case for case, _ in MALFORMED_FINGERPRINT_WIRES],
)
def test_cursor_fingerprint_requires_exact_base64url_digest_shape(
    wire: str,
) -> None:
    _assert_cursor_rejected(wire)


def test_cursor_fingerprint_must_match_normalized_filters() -> None:
    cursor = encode_cursor(
        SESSION_RESOURCE,
        _position(),
        _session_filters(device_id=7),
    )

    _assert_cursor_operation_rejected(
        lambda: decode_cursor(
            cursor,
            SESSION_RESOURCE,
            _session_filters(device_id=8),
        )
    )


@pytest.mark.parametrize(
    "timestamp",
    [
        datetime(2026, 7, 29, 23, 59, 59, tzinfo=UTC),
        datetime(2026, 7, 31, tzinfo=UTC),
    ],
    ids=["before-lower-bound", "at-exclusive-upper-bound"],
)
def test_cursor_position_outside_normalized_time_bounds_is_rejected(
    timestamp: datetime,
) -> None:
    position = _position(timestamp)
    filters = _session_filters(
        started_from=datetime(2026, 7, 30, tzinfo=UTC),
        started_to=datetime(2026, 7, 31, tzinfo=UTC),
    )

    _assert_cursor_operation_rejected(
        lambda: decode_cursor(
            encode_cursor(SESSION_RESOURCE, position, filters),
            SESSION_RESOURCE,
            filters,
        )
    )


def test_cursor_for_equal_empty_time_range_is_rejected() -> None:
    boundary = datetime(2026, 7, 30, tzinfo=UTC)
    filters = _measurement_filters(
        measured_from=boundary,
        measured_to=boundary,
    )

    _assert_cursor_operation_rejected(
        lambda: decode_cursor(
            encode_cursor(MEASUREMENT_RESOURCE, _position(), filters),
            MEASUREMENT_RESOURCE,
            filters,
        )
    )


@pytest.mark.parametrize(
    "forbidden_marker",
    [
        "credential",
        "password",
        "database_url",
        "postgresql://",
        "token",
        "settings",
        "authorization",
    ],
)
def test_cursor_payload_contains_no_sensitive_or_server_state(
    forbidden_marker: str,
) -> None:
    cursor = encode_cursor(
        MEASUREMENT_RESOURCE,
        _position(),
        _measurement_filters(session_id=11),
    )
    payload = _protocol_bytes(cursor).decode("utf-8").casefold()

    _require(
        forbidden_marker not in payload,
        "cursor payload exposed a prohibited data category",
    )
    _require(
        SAFE_FINGERPRINT.fullmatch(
            str(_protocol_document(cursor)["f"])
        )
        is not None,
        "cursor fingerprint did not use the approved digest shape",
    )


def test_cursor_validation_error_does_not_echo_rejected_wire() -> None:
    marker = "cursor-payload-marker-that-must-not-be-reflected"
    error_text: str | None = None
    unexpected_type: str | None = None
    try:
        decode_cursor(marker, SESSION_RESOURCE, _session_filters())
    except CursorValidationError as error:
        error_text = str(error).casefold()
    except Exception as error:  # pragma: no cover - contract failure path
        unexpected_type = type(error).__name__

    if unexpected_type is not None:
        pytest.fail(
            f"cursor rejection used unexpected exception type {unexpected_type}",
            pytrace=False,
        )
    if error_text is None:
        pytest.fail("invalid cursor was accepted", pytrace=False)
    _require(
        marker.casefold() not in error_text,
        "cursor validation error reflected rejected wire data",
    )
