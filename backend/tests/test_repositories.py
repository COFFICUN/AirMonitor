"""Unit contracts for asynchronous persistence repositories."""

from __future__ import annotations

import ast
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Device,
    DeviceRuntimeState,
    MeasurementSession,
    RawMeasurement,
)
from app.repositories.device import (
    DeviceRepository,
    DeviceRuntimeStateRepository,
)
from app.repositories.measurement import RawMeasurementRepository
from app.repositories.measurement_session import MeasurementSessionRepository


REPOSITORY_DIRECTORY = Path(__file__).resolve().parents[1] / "app" / "repositories"
FORBIDDEN_TRANSACTION_CALLS = {"begin", "begin_nested", "commit", "rollback"}
FORBIDDEN_LAYER_IMPORTS = ("fastapi", "app.api")
BROAD_EXCEPTION_NAMES = {"BaseException", "Exception"}
POSTGRESQL_DIALECT = postgresql.dialect()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _session_returning(value: Any) -> tuple[AsyncMock, MagicMock]:
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    session.execute.return_value = result
    return session, result


def _executed_statement(session: AsyncMock) -> Any:
    execute_call = session.execute.await_args
    assert execute_call is not None
    return execute_call.args[0]


def _compiled_sql(statement: Any) -> str:
    sql = statement.compile(
        dialect=POSTGRESQL_DIALECT,
        compile_kwargs={"literal_binds": True},
    )
    return re.sub(r"\s+", " ", str(sql)).strip()


def _assert_populate_existing(session: AsyncMock, statement: Any) -> None:
    execute_call = session.execute.await_args
    assert execute_call is not None
    statement_options = statement.get_execution_options()
    execute_options = execute_call.kwargs.get("execution_options", {})
    assert (
        statement_options.get("populate_existing") is True
        or execute_options.get("populate_existing") is True
    )


def _assert_no_transaction_calls(session: AsyncMock) -> None:
    for method_name in FORBIDDEN_TRANSACTION_CALLS:
        getattr(session, method_name).assert_not_called()


def _catches_broad_exception(expression: ast.expr | None) -> bool:
    if expression is None:
        return True
    if isinstance(expression, ast.Name):
        return expression.id in BROAD_EXCEPTION_NAMES
    if isinstance(expression, ast.Attribute):
        return expression.attr in BROAD_EXCEPTION_NAMES
    if isinstance(expression, ast.Tuple):
        return any(
            _catches_broad_exception(element)
            for element in expression.elts
        )
    return False


@pytest.mark.anyio
async def test_device_repository_getters_use_expected_predicates() -> None:
    expected = Device(id=17, device_uid="monitor-17")
    session, result = _session_returning(expected)
    repository = DeviceRepository(session)

    by_id = await repository.get_by_id(17)
    id_sql = _compiled_sql(_executed_statement(session))

    assert by_id is expected
    assert "FROM devices" in id_sql
    assert "WHERE devices.id = 17" in id_sql
    assert "FOR UPDATE" not in id_sql
    result.scalar_one_or_none.assert_called_once_with()

    session.execute.reset_mock()
    result.scalar_one_or_none.reset_mock()

    by_uid = await repository.get_by_device_uid("monitor-17")
    uid_sql = _compiled_sql(_executed_statement(session))

    assert by_uid is expected
    assert "FROM devices" in uid_sql
    assert "WHERE devices.device_uid = 'monitor-17'" in uid_sql
    assert "FOR UPDATE" not in uid_sql
    result.scalar_one_or_none.assert_called_once_with()
    _assert_no_transaction_calls(session)


@pytest.mark.anyio
async def test_device_repository_locked_getter_refreshes_identity_map() -> None:
    expected = Device(id=18, device_uid="monitor-18")
    session, result = _session_returning(expected)
    repository = DeviceRepository(session)

    actual = await repository.get_by_id_for_update(18)
    statement = _executed_statement(session)
    sql = _compiled_sql(statement)

    assert actual is expected
    assert "WHERE devices.id = 18" in sql
    assert "FOR UPDATE" in sql
    _assert_populate_existing(session, statement)
    result.scalar_one_or_none.assert_called_once_with()
    _assert_no_transaction_calls(session)


@pytest.mark.anyio
async def test_device_repository_create_adds_and_flushes() -> None:
    session = AsyncMock(spec=AsyncSession)
    repository = DeviceRepository(session)

    device = await repository.create(
        device_uid="monitor-create",
        name="Workshop",
        is_active=False,
    )

    assert isinstance(device, Device)
    assert device.device_uid == "monitor-create"
    assert device.name == "Workshop"
    assert device.is_active is False
    session.add.assert_called_once_with(device)
    session.flush.assert_awaited_once()
    _assert_no_transaction_calls(session)


@pytest.mark.anyio
async def test_runtime_state_repository_create_adds_and_flushes() -> None:
    session = AsyncMock(spec=AsyncSession)
    repository = DeviceRuntimeStateRepository(session)

    runtime_state = await repository.create(device_id=21)

    assert isinstance(runtime_state, DeviceRuntimeState)
    assert runtime_state.device_id == 21
    assert runtime_state.active_session_id is None
    session.add.assert_called_once_with(runtime_state)
    session.flush.assert_awaited_once()
    _assert_no_transaction_calls(session)


@pytest.mark.anyio
async def test_runtime_state_get_for_update_locks_and_refreshes_row() -> None:
    expected = DeviceRuntimeState(device_id=22)
    session, result = _session_returning(expected)
    repository = DeviceRuntimeStateRepository(session)

    actual = await repository.get_for_update(22)
    statement = _executed_statement(session)
    sql = _compiled_sql(statement)

    assert actual is expected
    assert "FROM device_runtime_state" in sql
    assert "WHERE device_runtime_state.device_id = 22" in sql
    assert "FOR UPDATE" in sql
    _assert_populate_existing(session, statement)
    result.scalar_one_or_none.assert_called_once_with()
    _assert_no_transaction_calls(session)


@pytest.mark.anyio
async def test_measurement_session_repository_getters_lock_only_when_requested() -> None:
    expected = MeasurementSession(id=31, device_id=22)
    session, result = _session_returning(expected)
    repository = MeasurementSessionRepository(session)

    unlocked = await repository.get_by_id(31)
    unlocked_sql = _compiled_sql(_executed_statement(session))

    assert unlocked is expected
    assert "WHERE measurement_sessions.id = 31" in unlocked_sql
    assert "FOR UPDATE" not in unlocked_sql

    session.execute.reset_mock()
    result.scalar_one_or_none.reset_mock()

    locked = await repository.get_by_id_for_update(31)
    locked_statement = _executed_statement(session)
    locked_sql = _compiled_sql(locked_statement)

    assert locked is expected
    assert "WHERE measurement_sessions.id = 31" in locked_sql
    assert "FOR UPDATE" in locked_sql
    _assert_populate_existing(session, locked_statement)
    result.scalar_one_or_none.assert_called_once_with()
    _assert_no_transaction_calls(session)


@pytest.mark.anyio
async def test_get_active_session_filters_by_device_and_active_status() -> None:
    expected = MeasurementSession(id=32, device_id=23, status="active")
    session, result = _session_returning(expected)
    repository = MeasurementSessionRepository(session)

    actual = await repository.get_active_for_device(23)
    sql = _compiled_sql(_executed_statement(session))

    assert actual is expected
    assert "measurement_sessions.device_id = 23" in sql
    assert "measurement_sessions.status = 'active'" in sql
    assert "FOR UPDATE" not in sql
    result.scalar_one_or_none.assert_called_once_with()
    _assert_no_transaction_calls(session)


@pytest.mark.anyio
async def test_measurement_session_create_adds_active_session_and_flushes() -> None:
    session = AsyncMock(spec=AsyncSession)
    repository = MeasurementSessionRepository(session)
    started_at = datetime(2026, 7, 23, 9, 30, tzinfo=timezone.utc)

    measurement_session = await repository.create(
        device_id=24,
        latitude=51.1694,
        longitude=71.4491,
        started_at=started_at,
    )

    assert isinstance(measurement_session, MeasurementSession)
    assert measurement_session.device_id == 24
    assert measurement_session.status == "active"
    assert measurement_session.started_at is started_at
    assert measurement_session.ended_at is None
    assert measurement_session.latitude == 51.1694
    assert measurement_session.longitude == 71.4491
    assert measurement_session.sample_count == 0
    session.add.assert_called_once_with(measurement_session)
    session.flush.assert_awaited_once()
    _assert_no_transaction_calls(session)


@pytest.mark.anyio
async def test_increment_sample_count_uses_atomic_sql_expression() -> None:
    session = AsyncMock(spec=AsyncSession)
    repository = MeasurementSessionRepository(session)

    await repository.increment_sample_count(41)
    sql = _compiled_sql(_executed_statement(session))

    assert sql.startswith("UPDATE measurement_sessions SET")
    assert re.search(
        r"sample_count=\(measurement_sessions\.sample_count \+ 1\)",
        sql,
    )
    assert "WHERE measurement_sessions.id = 41" in sql
    _assert_no_transaction_calls(session)


@pytest.mark.anyio
async def test_source_message_lookup_scopes_idempotency_to_device() -> None:
    expected = RawMeasurement(
        id=51,
        device_id=25,
        session_id=41,
        source_message_id="message-51",
    )
    session, result = _session_returning(expected)
    repository = RawMeasurementRepository(session)

    actual = await repository.get_by_source_message_id(25, "message-51")
    sql = _compiled_sql(_executed_statement(session))

    assert actual is expected
    assert "raw_measurements.device_id = 25" in sql
    assert "raw_measurements.source_message_id = 'message-51'" in sql
    assert "FOR UPDATE" not in sql
    result.scalar_one_or_none.assert_called_once_with()
    _assert_no_transaction_calls(session)


@pytest.mark.anyio
async def test_latest_measurement_timestamp_uses_one_bounded_aggregate() -> None:
    latest_measured_at = datetime(
        2026,
        7,
        23,
        9,
        45,
        tzinfo=timezone.utc,
    )
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one.return_value = latest_measured_at
    session.execute.return_value = result
    repository = RawMeasurementRepository(session)

    actual = await repository.get_latest_measured_at(session_id=41)
    sql = _compiled_sql(_executed_statement(session))

    assert actual is latest_measured_at
    assert sql.startswith("SELECT max(raw_measurements.measured_at)")
    assert "WHERE raw_measurements.session_id = 41" in sql
    assert "FROM raw_measurements" in sql
    assert "FOR UPDATE" not in sql
    result.scalar_one.assert_called_once_with()
    result.scalars.assert_not_called()
    _assert_no_transaction_calls(session)


@pytest.mark.anyio
async def test_raw_measurement_create_adds_all_inputs_and_flushes() -> None:
    session = AsyncMock(spec=AsyncSession)
    repository = RawMeasurementRepository(session)
    measured_at = datetime(2026, 7, 23, 9, 31, tzinfo=timezone.utc)
    values = {
        "device_id": 26,
        "session_id": 42,
        "source_message_id": "message-create",
        "measured_at": measured_at,
        "temperature": 22.5,
        "humidity": 48.0,
        "pm1": 4.0,
        "pm25": 7.5,
        "pm10": 11.0,
        "pc0_3": 100,
        "pc0_5": 90,
        "pc1_0": 70,
        "pc2_5": 40,
        "pc5_0": 20,
        "pc10": 5,
        "latitude": 51.1694,
        "longitude": 71.4491,
        "is_valid": False,
        "validation_note": "sensor warming up",
    }

    measurement = await repository.create(**values)

    assert isinstance(measurement, RawMeasurement)
    for field_name, expected in values.items():
        assert getattr(measurement, field_name) == expected
    session.add.assert_called_once_with(measurement)
    session.flush.assert_awaited_once()
    _assert_no_transaction_calls(session)


def test_repository_source_obeys_layer_and_transaction_policy() -> None:
    repository_files = sorted(REPOSITORY_DIRECTORY.rglob("*.py"))
    assert repository_files, "repository package must contain Python modules"

    violations: list[str] = []
    for repository_file in repository_files:
        tree = ast.parse(
            repository_file.read_text(encoding="utf-8"),
            filename=str(repository_file),
        )
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in FORBIDDEN_TRANSACTION_CALLS
            ):
                violations.append(
                    f"{repository_file.relative_to(REPOSITORY_DIRECTORY)}:"
                    f"{node.lineno}:{node.func.attr}"
                )

            if isinstance(node, ast.Import):
                imported_modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_modules = [node.module]
            else:
                imported_modules = []

            for imported_module in imported_modules:
                if any(
                    imported_module == prefix
                    or imported_module.startswith(f"{prefix}.")
                    for prefix in FORBIDDEN_LAYER_IMPORTS
                ):
                    violations.append(
                        f"{repository_file.name}:{node.lineno}:"
                        f"import {imported_module}"
                    )

            if (
                isinstance(node, ast.ExceptHandler)
                and _catches_broad_exception(node.type)
            ):
                violations.append(
                    f"{repository_file.name}:{node.lineno}:"
                    "broad exception handler"
                )

    assert violations == []
