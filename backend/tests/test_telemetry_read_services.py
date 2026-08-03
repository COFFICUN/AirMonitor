"""RED contracts for immutable, read-only telemetry query pages."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DeviceNotFoundError
from app.db.models import Device, MeasurementSession, RawMeasurement
from app.services.telemetry import (
    MeasurementTelemetryQueryService,
    SessionTelemetryQueryService,
    TelemetryPage,
)
from app.services.telemetry_cursor import (
    CursorPosition,
    CursorValidationError,
    MeasurementReadRequest,
    SessionReadRequest,
    decode_cursor,
    encode_cursor,
    normalize_measurement_filters,
    normalize_session_filters,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class RepositoryFailure(RuntimeError):
    """Sentinel repository exception that services must not swallow."""


def _device(identifier: int = 7) -> Device:
    return Device(
        id=identifier,
        device_uid=f"monitor-{identifier}",
        is_active=True,
        created_at=datetime(2026, 7, 30, tzinfo=UTC),
    )


def _session_row(
    identifier: int,
    started_at: datetime,
) -> MeasurementSession:
    return MeasurementSession(
        id=identifier,
        device_id=7,
        status="completed",
        started_at=started_at,
        ended_at=started_at + timedelta(minutes=5),
        latitude=51.1694,
        longitude=71.4491,
        sample_count=0,
        created_at=started_at,
    )


def _measurement_row(
    identifier: int,
    measured_at: datetime,
) -> RawMeasurement:
    return RawMeasurement(
        id=identifier,
        device_id=7,
        session_id=11,
        source_message_id=None,
        measured_at=measured_at,
        received_at=measured_at + timedelta(seconds=1),
        is_valid=True,
        validation_note=None,
        created_at=measured_at + timedelta(seconds=1),
    )


def _session_request(
    *,
    status: str | None = None,
    started_from: datetime | None = None,
    started_to: datetime | None = None,
    limit: int = 2,
    position: CursorPosition | None = None,
) -> SessionReadRequest:
    filters = normalize_session_filters(
        device_id=7,
        status=status,
        started_from=started_from,
        started_to=started_to,
    )
    return SessionReadRequest(filters, limit, position)


def _measurement_request(
    *,
    session_id: int | None = None,
    measured_from: datetime | None = None,
    measured_to: datetime | None = None,
    limit: int = 2,
    position: CursorPosition | None = None,
) -> MeasurementReadRequest:
    filters = normalize_measurement_filters(
        device_id=7,
        session_id=session_id,
        measured_from=measured_from,
        measured_to=measured_to,
    )
    return MeasurementReadRequest(filters, limit, position)


def _session_service(
    *,
    device: Device | None = None,
    rows: list[MeasurementSession] | None = None,
) -> tuple[
    SessionTelemetryQueryService,
    Mock,
    AsyncMock,
    AsyncMock,
]:
    session = Mock(spec=AsyncSession)
    service = SessionTelemetryQueryService(session)
    device_lookup = AsyncMock(return_value=device)
    list_for_device = AsyncMock(
        return_value=[] if rows is None else rows
    )
    service.device_repository = SimpleNamespace(get_by_id=device_lookup)
    service.session_repository = SimpleNamespace(
        list_for_device=list_for_device
    )
    return service, session, device_lookup, list_for_device


def _measurement_service(
    *,
    device: Device | None = None,
    rows: list[RawMeasurement] | None = None,
) -> tuple[
    MeasurementTelemetryQueryService,
    Mock,
    AsyncMock,
    AsyncMock,
]:
    session = Mock(spec=AsyncSession)
    service = MeasurementTelemetryQueryService(session)
    device_lookup = AsyncMock(return_value=device)
    list_for_device = AsyncMock(
        return_value=[] if rows is None else rows
    )
    service.device_repository = SimpleNamespace(get_by_id=device_lookup)
    service.measurement_repository = SimpleNamespace(
        list_for_device=list_for_device
    )
    return service, session, device_lookup, list_for_device


def _mapped_state(
    entity: Device | MeasurementSession | RawMeasurement,
) -> tuple[
    tuple[str, object],
    ...,
]:
    return tuple(
        (attribute.key, getattr(entity, attribute.key))
        for attribute in type(entity).__mapper__.column_attrs
    )


def _assert_read_only(session: Mock) -> None:
    for method_name in (
        "add",
        "add_all",
        "begin",
        "begin_nested",
        "commit",
        "delete",
        "flush",
        "rollback",
    ):
        getattr(session, method_name).assert_not_called()


def test_telemetry_page_is_frozen_and_tuple_backed() -> None:
    marker = object()
    page: TelemetryPage[object] = TelemetryPage(
        items=(marker,),
        next_cursor=None,
    )

    assert type(page.items) is tuple
    assert page.items == (marker,)
    with pytest.raises(FrozenInstanceError):
        setattr(page, "next_cursor", "replacement")


@pytest.mark.anyio
async def test_session_service_unknown_device_uses_domain_exception() -> None:
    service, session, device_lookup, list_for_device = _session_service()

    with pytest.raises(DeviceNotFoundError):
        await service.list_sessions(read_request=_session_request())

    device_lookup.assert_awaited_once_with(7)
    list_for_device.assert_not_awaited()
    _assert_read_only(session)


@pytest.mark.anyio
async def test_session_service_existing_device_with_no_rows_is_empty() -> None:
    service, session, device_lookup, list_for_device = _session_service(
        device=_device()
    )
    read_request = _session_request()

    page = await service.list_sessions(read_request=read_request)

    assert page == TelemetryPage(items=(), next_cursor=None)
    assert type(page.items) is tuple
    device_lookup.assert_awaited_once_with(7)
    list_for_device.assert_awaited_once()
    _assert_read_only(session)


@pytest.mark.anyio
async def test_session_equal_range_checks_device_then_skips_list() -> None:
    boundary = datetime(2026, 7, 30, tzinfo=UTC)
    service, session, device_lookup, list_for_device = _session_service(
        device=_device()
    )

    page = await service.list_sessions(
        read_request=_session_request(
            started_from=boundary,
            started_to=boundary,
        )
    )

    assert page == TelemetryPage(items=(), next_cursor=None)
    device_lookup.assert_awaited_once_with(7)
    list_for_device.assert_not_awaited()
    _assert_read_only(session)


@pytest.mark.anyio
async def test_session_equal_range_unknown_device_is_not_empty_success(
) -> None:
    boundary = datetime(2026, 7, 30, tzinfo=UTC)
    service, session, device_lookup, list_for_device = _session_service()

    with pytest.raises(DeviceNotFoundError):
        await service.list_sessions(
            read_request=_session_request(
                started_from=boundary,
                started_to=boundary,
            )
        )

    device_lookup.assert_awaited_once_with(7)
    list_for_device.assert_not_awaited()
    _assert_read_only(session)


@pytest.mark.anyio
async def test_session_service_forwards_normalized_request_and_public_limit(
) -> None:
    offset = timezone(timedelta(hours=5))
    position = CursorPosition(
        datetime(2026, 7, 30, 6, 0, tzinfo=UTC),
        31,
    )
    read_request = _session_request(
        status="active",
        started_from=datetime(2026, 7, 30, 10, 0, tzinfo=offset),
        started_to=datetime(2026, 7, 31, 10, 0, tzinfo=offset),
        limit=37,
        position=position,
    )
    service, session, _, list_for_device = _session_service(
        device=_device()
    )

    await service.list_sessions(read_request=read_request)

    list_for_device.assert_awaited_once_with(
        device_id=read_request.filters.device_id,
        status=read_request.filters.status,
        started_from=read_request.filters.started_from,
        started_to=read_request.filters.started_to,
        position=position,
        limit=37,
    )
    assert read_request.filters.started_from == datetime(
        2026,
        7,
        30,
        5,
        0,
        tzinfo=UTC,
    )
    _assert_read_only(session)


@pytest.mark.anyio
async def test_session_service_checks_device_before_nonempty_list() -> None:
    events: list[str] = []
    service, session, device_lookup, list_for_device = _session_service(
        device=_device()
    )

    async def find_device(device_id: int) -> Device:
        assert device_id == 7
        events.append("device")
        return _device()

    async def list_rows(**_: object) -> list[MeasurementSession]:
        events.append("list")
        return []

    device_lookup.side_effect = find_device
    list_for_device.side_effect = list_rows

    await service.list_sessions(read_request=_session_request())

    assert events == ["device", "list"]
    _assert_read_only(session)


@pytest.mark.anyio
async def test_session_under_limit_returns_all_rows_without_cursor() -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    device = _device()
    rows = [
        _session_row(4, timestamp - timedelta(seconds=1)),
        _session_row(9, timestamp),
    ]
    device_before = _mapped_state(device)
    rows_before = tuple(_mapped_state(row) for row in rows)
    service, session, _, list_for_device = _session_service(
        device=device,
        rows=rows,
    )

    page = await service.list_sessions(
        read_request=_session_request(limit=3)
    )

    assert type(page.items) is tuple
    assert page.items == (rows[0], rows[1])
    assert page.items[0] is rows[0]
    assert page.items[1] is rows[1]
    assert page.next_cursor is None
    assert _mapped_state(device) == device_before
    assert tuple(_mapped_state(row) for row in rows) == rows_before
    list_for_device.assert_awaited_once()
    _assert_read_only(session)


@pytest.mark.anyio
async def test_session_exact_limit_has_null_cursor_and_tuple_items() -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    rows = [
        _session_row(9, timestamp),
        _session_row(8, timestamp),
    ]
    service, session, _, _ = _session_service(
        device=_device(),
        rows=rows,
    )

    page = await service.list_sessions(
        read_request=_session_request(limit=2)
    )

    assert page.items == tuple(rows)
    assert type(page.items) is tuple
    assert page.next_cursor is None
    _assert_read_only(session)


@pytest.mark.anyio
async def test_session_extra_row_is_trimmed_and_never_cursor_position(
) -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    returned_rows = [
        _session_row(9, timestamp),
        _session_row(8, timestamp),
        _session_row(7, timestamp - timedelta(seconds=1)),
    ]
    read_request = _session_request(status="completed", limit=2)
    service, session, _, _ = _session_service(
        device=_device(),
        rows=returned_rows,
    )

    page = await service.list_sessions(read_request=read_request)

    expected_position = CursorPosition(
        returned_rows[1].started_at,
        returned_rows[1].id,
    )
    extra_position = CursorPosition(
        returned_rows[2].started_at,
        returned_rows[2].id,
    )
    expected_cursor = encode_cursor(
        "sessions",
        expected_position,
        read_request.filters,
    )
    assert page.items == tuple(returned_rows[:2])
    assert returned_rows[2] not in page.items
    assert page.next_cursor == expected_cursor
    assert decode_cursor(
        page.next_cursor,
        "sessions",
        read_request.filters,
    ) == expected_position
    assert expected_position != extra_position
    changed_filters = normalize_session_filters(
        device_id=7,
        status="active",
        started_from=None,
        started_to=None,
    )
    with pytest.raises(CursorValidationError):
        decode_cursor(page.next_cursor, "sessions", changed_filters)
    _assert_read_only(session)


@pytest.mark.anyio
async def test_session_repository_exception_is_not_swallowed() -> None:
    failure = RepositoryFailure("session repository marker")
    service, session, _, list_for_device = _session_service(
        device=_device()
    )
    list_for_device.side_effect = failure

    with pytest.raises(RepositoryFailure) as captured:
        await service.list_sessions(read_request=_session_request())

    assert captured.value is failure
    _assert_read_only(session)


@pytest.mark.anyio
async def test_session_cursor_encoder_failure_is_not_fake_success() -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    invalid_final_item = _session_row(0, timestamp)
    extra_item = _session_row(1, timestamp - timedelta(seconds=1))
    service, session, _, _ = _session_service(
        device=_device(),
        rows=[invalid_final_item, extra_item],
    )

    with pytest.raises(CursorValidationError):
        await service.list_sessions(
            read_request=_session_request(limit=1)
        )

    _assert_read_only(session)


@pytest.mark.anyio
async def test_session_service_does_not_mutate_returned_rows() -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    device = _device()
    rows = [
        _session_row(9, timestamp),
        _session_row(8, timestamp - timedelta(seconds=1)),
    ]
    device_before = _mapped_state(device)
    before = tuple(_mapped_state(row) for row in rows)
    service, session, _, _ = _session_service(
        device=device,
        rows=rows,
    )

    page = await service.list_sessions(
        read_request=_session_request(limit=2)
    )

    assert page.items == tuple(rows)
    assert _mapped_state(device) == device_before
    assert tuple(_mapped_state(row) for row in rows) == before
    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_service_unknown_device_uses_domain_exception(
) -> None:
    service, session, device_lookup, list_for_device = (
        _measurement_service()
    )

    with pytest.raises(DeviceNotFoundError):
        await service.list_measurements(
            read_request=_measurement_request()
        )

    device_lookup.assert_awaited_once_with(7)
    list_for_device.assert_not_awaited()
    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_service_existing_device_with_no_rows_is_empty(
) -> None:
    service, session, device_lookup, list_for_device = (
        _measurement_service(device=_device())
    )
    read_request = _measurement_request()

    page = await service.list_measurements(read_request=read_request)

    assert page == TelemetryPage(items=(), next_cursor=None)
    assert type(page.items) is tuple
    device_lookup.assert_awaited_once_with(7)
    list_for_device.assert_awaited_once()
    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_equal_range_checks_device_then_skips_list(
) -> None:
    boundary = datetime(2026, 7, 30, tzinfo=UTC)
    service, session, device_lookup, list_for_device = (
        _measurement_service(device=_device())
    )

    page = await service.list_measurements(
        read_request=_measurement_request(
            measured_from=boundary,
            measured_to=boundary,
        )
    )

    assert page == TelemetryPage(items=(), next_cursor=None)
    device_lookup.assert_awaited_once_with(7)
    list_for_device.assert_not_awaited()
    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_equal_range_unknown_device_is_not_empty_success(
) -> None:
    boundary = datetime(2026, 7, 30, tzinfo=UTC)
    service, session, device_lookup, list_for_device = (
        _measurement_service()
    )

    with pytest.raises(DeviceNotFoundError):
        await service.list_measurements(
            read_request=_measurement_request(
                measured_from=boundary,
                measured_to=boundary,
            )
        )

    device_lookup.assert_awaited_once_with(7)
    list_for_device.assert_not_awaited()
    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_service_forwards_normalized_request_and_limit(
) -> None:
    offset = timezone(timedelta(hours=5))
    position = CursorPosition(
        datetime(2026, 7, 30, 6, 0, tzinfo=UTC),
        31,
    )
    read_request = _measurement_request(
        session_id=11,
        measured_from=datetime(2026, 7, 30, 10, 0, tzinfo=offset),
        measured_to=datetime(2026, 7, 31, 10, 0, tzinfo=offset),
        limit=37,
        position=position,
    )
    service, session, _, list_for_device = _measurement_service(
        device=_device()
    )

    await service.list_measurements(read_request=read_request)

    list_for_device.assert_awaited_once_with(
        device_id=read_request.filters.device_id,
        session_id=read_request.filters.session_id,
        measured_from=read_request.filters.measured_from,
        measured_to=read_request.filters.measured_to,
        position=position,
        limit=37,
    )
    assert read_request.filters.measured_from == datetime(
        2026,
        7,
        30,
        5,
        0,
        tzinfo=UTC,
    )
    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_service_checks_device_before_nonempty_list(
) -> None:
    events: list[str] = []
    service, session, device_lookup, list_for_device = (
        _measurement_service(device=_device())
    )

    async def find_device(device_id: int) -> Device:
        assert device_id == 7
        events.append("device")
        return _device()

    async def list_rows(**_: object) -> list[RawMeasurement]:
        events.append("list")
        return []

    device_lookup.side_effect = find_device
    list_for_device.side_effect = list_rows

    await service.list_measurements(
        read_request=_measurement_request()
    )

    assert events == ["device", "list"]
    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_under_limit_returns_all_rows_without_cursor(
) -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    device = _device()
    rows = [
        _measurement_row(4, timestamp - timedelta(seconds=1)),
        _measurement_row(9, timestamp),
    ]
    device_before = _mapped_state(device)
    rows_before = tuple(_mapped_state(row) for row in rows)
    service, session, _, list_for_device = _measurement_service(
        device=device,
        rows=rows,
    )

    page = await service.list_measurements(
        read_request=_measurement_request(limit=3)
    )

    assert type(page.items) is tuple
    assert page.items == (rows[0], rows[1])
    assert page.items[0] is rows[0]
    assert page.items[1] is rows[1]
    assert page.next_cursor is None
    assert _mapped_state(device) == device_before
    assert tuple(_mapped_state(row) for row in rows) == rows_before
    list_for_device.assert_awaited_once()
    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_exact_limit_has_null_cursor_and_tuple_items(
) -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    rows = [
        _measurement_row(9, timestamp),
        _measurement_row(8, timestamp),
    ]
    service, session, _, _ = _measurement_service(
        device=_device(),
        rows=rows,
    )

    page = await service.list_measurements(
        read_request=_measurement_request(limit=2)
    )

    assert page.items == tuple(rows)
    assert type(page.items) is tuple
    assert page.next_cursor is None
    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_extra_row_is_trimmed_and_never_cursor_position(
) -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    returned_rows = [
        _measurement_row(9, timestamp),
        _measurement_row(8, timestamp),
        _measurement_row(7, timestamp - timedelta(seconds=1)),
    ]
    read_request = _measurement_request(session_id=11, limit=2)
    service, session, _, _ = _measurement_service(
        device=_device(),
        rows=returned_rows,
    )

    page = await service.list_measurements(read_request=read_request)

    expected_position = CursorPosition(
        returned_rows[1].measured_at,
        returned_rows[1].id,
    )
    extra_position = CursorPosition(
        returned_rows[2].measured_at,
        returned_rows[2].id,
    )
    expected_cursor = encode_cursor(
        "measurements",
        expected_position,
        read_request.filters,
    )
    assert page.items == tuple(returned_rows[:2])
    assert returned_rows[2] not in page.items
    assert page.next_cursor == expected_cursor
    assert decode_cursor(
        page.next_cursor,
        "measurements",
        read_request.filters,
    ) == expected_position
    assert expected_position != extra_position
    changed_filters = normalize_measurement_filters(
        device_id=7,
        session_id=12,
        measured_from=None,
        measured_to=None,
    )
    with pytest.raises(CursorValidationError):
        decode_cursor(
            page.next_cursor,
            "measurements",
            changed_filters,
        )
    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_repository_exception_is_not_swallowed() -> None:
    failure = RepositoryFailure("measurement repository marker")
    service, session, _, list_for_device = _measurement_service(
        device=_device()
    )
    list_for_device.side_effect = failure

    with pytest.raises(RepositoryFailure) as captured:
        await service.list_measurements(
            read_request=_measurement_request()
        )

    assert captured.value is failure
    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_cursor_encoder_failure_is_not_fake_success(
) -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    invalid_final_item = _measurement_row(0, timestamp)
    extra_item = _measurement_row(1, timestamp - timedelta(seconds=1))
    service, session, _, _ = _measurement_service(
        device=_device(),
        rows=[invalid_final_item, extra_item],
    )

    with pytest.raises(CursorValidationError):
        await service.list_measurements(
            read_request=_measurement_request(limit=1)
        )

    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_service_does_not_mutate_returned_rows() -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    device = _device()
    rows = [
        _measurement_row(9, timestamp),
        _measurement_row(8, timestamp - timedelta(seconds=1)),
    ]
    device_before = _mapped_state(device)
    before = tuple(_mapped_state(row) for row in rows)
    service, session, _, _ = _measurement_service(
        device=device,
        rows=rows,
    )

    page = await service.list_measurements(
        read_request=_measurement_request(limit=2)
    )

    assert page.items == tuple(rows)
    assert _mapped_state(device) == device_before
    assert tuple(_mapped_state(row) for row in rows) == before
    _assert_read_only(session)
