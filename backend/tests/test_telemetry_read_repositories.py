"""RED contracts for bounded, read-only telemetry list repositories."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select, operators
from sqlalchemy.sql.elements import BooleanClauseList, ClauseElement

from app.db.models import MeasurementSession, RawMeasurement
from app.repositories.measurement import RawMeasurementRepository
from app.repositories.measurement_session import MeasurementSessionRepository
from app.services.telemetry_cursor import CursorPosition


# Resolve the approved future methods during collection. The Phase C1 RED
# boundary is their absence, never a test-local substitute implementation.
SESSION_LIST_METHOD = MeasurementSessionRepository.list_for_device
MEASUREMENT_LIST_METHOD = RawMeasurementRepository.list_for_device


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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


def _repository_session(
    rows: list[MeasurementSession] | list[RawMeasurement],
) -> tuple[AsyncMock, MagicMock, MagicMock]:
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    scalar_result = MagicMock()
    scalar_result.all.return_value = rows
    result.scalars.return_value = scalar_result
    session.execute.return_value = result
    return session, result, scalar_result


def _executed_statement(session: AsyncMock) -> Select[Any]:
    execute_call = session.execute.await_args
    assert execute_call is not None
    statement = execute_call.args[0]
    assert isinstance(statement, Select)
    return statement


def _where_terms(statement: Select[Any]) -> tuple[ClauseElement, ...]:
    whereclause = statement.whereclause
    assert whereclause is not None
    if (
        isinstance(whereclause, BooleanClauseList)
        and whereclause.operator is operators.and_
    ):
        return tuple(whereclause.clauses)
    return (whereclause,)


def _assert_has_predicate(
    statement: Select[Any],
    expected: ClauseElement,
) -> None:
    assert any(
        candidate.compare(expected)
        for candidate in _where_terms(statement)
    )


def _assert_ordering(
    statement: Select[Any],
    *expected: ClauseElement,
) -> None:
    actual = tuple(statement._order_by_clauses)
    assert len(actual) == len(expected)
    assert all(
        actual_clause.compare(expected_clause)
        for actual_clause, expected_clause in zip(
            actual,
            expected,
            strict=True,
        )
    )


def _assert_limit_plus_one(
    statement: Select[Any],
    public_limit: int,
) -> None:
    limit_clause = statement._limit_clause
    assert limit_clause is not None
    assert getattr(limit_clause, "value", None) == public_limit + 1
    assert statement._offset_clause is None


def _mapped_state(entity: MeasurementSession | RawMeasurement) -> tuple[
    tuple[str, object],
    ...,
]:
    return tuple(
        (attribute.key, getattr(entity, attribute.key))
        for attribute in type(entity).__mapper__.column_attrs
    )


def _assert_read_only(session: AsyncMock) -> None:
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


async def _list_sessions(
    *,
    rows: list[MeasurementSession] | None = None,
    device_id: int = 7,
    status: str | None = None,
    started_from: datetime | None = None,
    started_to: datetime | None = None,
    position: CursorPosition | None = None,
    limit: int = 100,
) -> tuple[
    list[MeasurementSession],
    AsyncMock,
    MagicMock,
    MagicMock,
    Select[Any],
]:
    returned_rows = [] if rows is None else rows
    session, result, scalar_result = _repository_session(returned_rows)
    repository = MeasurementSessionRepository(session)

    actual = await SESSION_LIST_METHOD(
        repository,
        device_id=device_id,
        status=status,
        started_from=started_from,
        started_to=started_to,
        position=position,
        limit=limit,
    )

    return (
        actual,
        session,
        result,
        scalar_result,
        _executed_statement(session),
    )


async def _list_measurements(
    *,
    rows: list[RawMeasurement] | None = None,
    device_id: int = 7,
    session_id: int | None = None,
    measured_from: datetime | None = None,
    measured_to: datetime | None = None,
    position: CursorPosition | None = None,
    limit: int = 100,
) -> tuple[
    list[RawMeasurement],
    AsyncMock,
    MagicMock,
    MagicMock,
    Select[Any],
]:
    returned_rows = [] if rows is None else rows
    session, result, scalar_result = _repository_session(returned_rows)
    repository = RawMeasurementRepository(session)

    actual = await MEASUREMENT_LIST_METHOD(
        repository,
        device_id=device_id,
        session_id=session_id,
        measured_from=measured_from,
        measured_to=measured_to,
        position=position,
        limit=limit,
    )

    return (
        actual,
        session,
        result,
        scalar_result,
        _executed_statement(session),
    )


@pytest.mark.anyio
async def test_session_list_always_scopes_to_device() -> None:
    *_, statement = await _list_sessions(device_id=7)

    assert len(_where_terms(statement)) == 1
    _assert_has_predicate(
        statement,
        MeasurementSession.device_id == 7,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status",
    ["active", "completed", "cancelled"],
)
async def test_session_status_filter_is_optional_and_exact(
    status: str,
) -> None:
    *_, statement = await _list_sessions(status=status)

    assert len(_where_terms(statement)) == 2
    _assert_has_predicate(
        statement,
        MeasurementSession.device_id == 7,
    )
    _assert_has_predicate(
        statement,
        MeasurementSession.status == status,
    )


@pytest.mark.anyio
async def test_session_started_from_is_inclusive() -> None:
    started_from = datetime(2026, 7, 30, tzinfo=UTC)

    *_, statement = await _list_sessions(started_from=started_from)

    _assert_has_predicate(
        statement,
        MeasurementSession.device_id == 7,
    )
    _assert_has_predicate(
        statement,
        MeasurementSession.started_at >= started_from,
    )


@pytest.mark.anyio
async def test_session_started_to_is_exclusive() -> None:
    started_to = datetime(2026, 7, 31, tzinfo=UTC)

    *_, statement = await _list_sessions(started_to=started_to)

    _assert_has_predicate(
        statement,
        MeasurementSession.device_id == 7,
    )
    _assert_has_predicate(
        statement,
        MeasurementSession.started_at < started_to,
    )


@pytest.mark.anyio
async def test_session_time_range_predicates_compose() -> None:
    started_from = datetime(2026, 7, 30, tzinfo=UTC)
    started_to = datetime(2026, 7, 31, tzinfo=UTC)

    *_, statement = await _list_sessions(
        started_from=started_from,
        started_to=started_to,
    )

    assert len(_where_terms(statement)) == 3
    _assert_has_predicate(
        statement,
        MeasurementSession.device_id == 7,
    )
    _assert_has_predicate(
        statement,
        MeasurementSession.started_at >= started_from,
    )
    _assert_has_predicate(
        statement,
        MeasurementSession.started_at < started_to,
    )


@pytest.mark.anyio
async def test_session_cursor_is_exclusive_with_identifier_tie_break() -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    position = CursorPosition(timestamp, 41)

    *_, statement = await _list_sessions(position=position)

    _assert_has_predicate(
        statement,
        MeasurementSession.device_id == 7,
    )
    _assert_has_predicate(
        statement,
        or_(
            MeasurementSession.started_at < timestamp,
            and_(
                MeasurementSession.started_at == timestamp,
                MeasurementSession.id < 41,
            ),
        ),
    )


@pytest.mark.anyio
async def test_session_list_uses_stable_descending_order() -> None:
    *_, statement = await _list_sessions()

    _assert_ordering(
        statement,
        MeasurementSession.started_at.desc(),
        MeasurementSession.id.desc(),
    )


@pytest.mark.anyio
@pytest.mark.parametrize("public_limit", [1, 100, 500])
async def test_session_list_applies_limit_plus_one_without_offset(
    public_limit: int,
) -> None:
    *_, statement = await _list_sessions(limit=public_limit)

    _assert_limit_plus_one(statement, public_limit)


@pytest.mark.anyio
async def test_session_rows_preserve_repository_result_order() -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    rows = [
        _session_row(7, timestamp),
        _session_row(9, timestamp - timedelta(seconds=1)),
        _session_row(8, timestamp + timedelta(seconds=1)),
    ]

    actual, session, result, scalar_result, _ = await _list_sessions(
        rows=rows
    )

    assert actual == rows
    assert all(
        actual[index] is rows[index]
        for index in range(len(rows))
    )
    session.execute.assert_awaited_once()
    result.scalars.assert_called_once_with()
    scalar_result.all.assert_called_once_with()


@pytest.mark.anyio
async def test_session_list_is_read_only_and_does_not_mutate_rows() -> None:
    row = _session_row(9, datetime(2026, 7, 30, tzinfo=UTC))
    before = _mapped_state(row)

    _, session, _, _, statement = await _list_sessions(rows=[row])

    assert _mapped_state(row) == before
    assert statement._for_update_arg is None
    _assert_read_only(session)


@pytest.mark.anyio
async def test_measurement_list_always_scopes_to_device() -> None:
    *_, statement = await _list_measurements(device_id=7)

    assert len(_where_terms(statement)) == 1
    _assert_has_predicate(
        statement,
        RawMeasurement.device_id == 7,
    )


@pytest.mark.anyio
async def test_measurement_session_filter_retains_device_scope() -> None:
    *_, statement = await _list_measurements(
        device_id=7,
        session_id=11,
    )

    assert len(_where_terms(statement)) == 2
    _assert_has_predicate(
        statement,
        RawMeasurement.device_id == 7,
    )
    _assert_has_predicate(
        statement,
        RawMeasurement.session_id == 11,
    )


@pytest.mark.anyio
async def test_measurement_measured_from_is_inclusive() -> None:
    measured_from = datetime(2026, 7, 30, tzinfo=UTC)

    *_, statement = await _list_measurements(
        measured_from=measured_from
    )

    _assert_has_predicate(
        statement,
        RawMeasurement.device_id == 7,
    )
    _assert_has_predicate(
        statement,
        RawMeasurement.measured_at >= measured_from,
    )


@pytest.mark.anyio
async def test_measurement_measured_to_is_exclusive() -> None:
    measured_to = datetime(2026, 7, 31, tzinfo=UTC)

    *_, statement = await _list_measurements(measured_to=measured_to)

    _assert_has_predicate(
        statement,
        RawMeasurement.device_id == 7,
    )
    _assert_has_predicate(
        statement,
        RawMeasurement.measured_at < measured_to,
    )


@pytest.mark.anyio
async def test_measurement_time_range_predicates_compose() -> None:
    measured_from = datetime(2026, 7, 30, tzinfo=UTC)
    measured_to = datetime(2026, 7, 31, tzinfo=UTC)

    *_, statement = await _list_measurements(
        measured_from=measured_from,
        measured_to=measured_to,
    )

    assert len(_where_terms(statement)) == 3
    _assert_has_predicate(
        statement,
        RawMeasurement.device_id == 7,
    )
    _assert_has_predicate(
        statement,
        RawMeasurement.measured_at >= measured_from,
    )
    _assert_has_predicate(
        statement,
        RawMeasurement.measured_at < measured_to,
    )


@pytest.mark.anyio
async def test_measurement_cursor_is_exclusive_with_identifier_tie_break(
) -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    position = CursorPosition(timestamp, 41)

    *_, statement = await _list_measurements(position=position)

    _assert_has_predicate(
        statement,
        RawMeasurement.device_id == 7,
    )
    _assert_has_predicate(
        statement,
        or_(
            RawMeasurement.measured_at < timestamp,
            and_(
                RawMeasurement.measured_at == timestamp,
                RawMeasurement.id < 41,
            ),
        ),
    )


@pytest.mark.anyio
async def test_measurement_list_uses_stable_descending_order() -> None:
    *_, statement = await _list_measurements()

    _assert_ordering(
        statement,
        RawMeasurement.measured_at.desc(),
        RawMeasurement.id.desc(),
    )


@pytest.mark.anyio
@pytest.mark.parametrize("public_limit", [1, 100, 500])
async def test_measurement_list_applies_limit_plus_one_without_offset(
    public_limit: int,
) -> None:
    *_, statement = await _list_measurements(limit=public_limit)

    _assert_limit_plus_one(statement, public_limit)


@pytest.mark.anyio
async def test_measurement_rows_preserve_repository_result_order() -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    rows = [
        _measurement_row(7, timestamp),
        _measurement_row(9, timestamp - timedelta(seconds=1)),
        _measurement_row(8, timestamp + timedelta(seconds=1)),
    ]

    actual, session, result, scalar_result, _ = await _list_measurements(
        rows=rows
    )

    assert actual == rows
    assert all(
        actual[index] is rows[index]
        for index in range(len(rows))
    )
    session.execute.assert_awaited_once()
    result.scalars.assert_called_once_with()
    scalar_result.all.assert_called_once_with()


@pytest.mark.anyio
async def test_measurement_list_is_read_only_and_does_not_mutate_rows(
) -> None:
    row = _measurement_row(9, datetime(2026, 7, 30, tzinfo=UTC))
    before = _mapped_state(row)

    _, session, _, _, statement = await _list_measurements(rows=[row])

    assert _mapped_state(row) == before
    assert statement._for_update_arg is None
    _assert_read_only(session)
