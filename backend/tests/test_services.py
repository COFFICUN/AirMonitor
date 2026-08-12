"""Unit tests for transactional persistence services."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ActiveSessionAlreadyExistsError,
    ActiveSessionMismatchError,
    ActiveSessionNotFoundError,
    DeviceInactiveError,
    DeviceNotFoundError,
    DeviceRuntimeStateNotFoundError,
    DuplicateDeviceUIDError,
    DuplicateSourceMessageError,
    InvalidSessionTransitionError,
    InvalidTimestampError,
    SessionDoesNotBelongToDeviceError,
    SessionNotFoundError,
)
from app.db.models import (
    Device,
    DeviceRuntimeState,
    MeasurementSession,
    RawMeasurement,
)
from app.services.device import DeviceService
from app.services.measurement import MeasurementService
from app.services._support import violates_constraint


DEVICE_ID = 17
OTHER_DEVICE_ID = 29
SESSION_ID = 41
DEVICE_UID = "airmonitor-unit-17"
STARTED_AT = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
ENDED_AT = STARTED_AT + timedelta(hours=1)
MEASURED_AT = STARTED_AT + timedelta(minutes=5)
UTC_PLUS_FIVE = timezone(timedelta(hours=5))
APP_DIRECTORY = Path(__file__).resolve().parents[1] / "app"
SERVICE_POLICY_FILES = (
    *sorted((APP_DIRECTORY / "services").glob("*.py"), key=str),
    APP_DIRECTORY / "core" / "exceptions.py",
)
FORBIDDEN_LAYER_IMPORTS = ("fastapi", "app.api")
BROAD_EXCEPTION_NAMES = {"BaseException", "Exception"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class RecordingTransaction:
    """Minimal async transaction context that exposes boundary behavior."""

    def __init__(self) -> None:
        self.active = False
        self.enter_count = 0
        self.exit_count = 0
        self.exit_exception_types: list[type[BaseException] | None] = []
        self.on_exit: Callable[[], None] | None = None

    async def __aenter__(self) -> RecordingTransaction:
        self.enter_count += 1
        self.active = True
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: Any,
    ) -> bool:
        del exception, traceback
        self.exit_count += 1
        self.exit_exception_types.append(exception_type)
        if self.on_exit is not None:
            self.on_exit()
        self.active = False
        return False


@dataclass
class DeviceServiceHarness:
    service: DeviceService
    session: Mock
    transaction: RecordingTransaction
    device_repository: SimpleNamespace
    runtime_state_repository: SimpleNamespace


@dataclass
class MeasurementServiceHarness:
    service: MeasurementService
    session: Mock
    transaction: RecordingTransaction
    device_repository: SimpleNamespace
    runtime_state_repository: SimpleNamespace
    session_repository: SimpleNamespace
    measurement_repository: SimpleNamespace


class ConstraintViolation(Exception):
    """Integrity-error origin carrying a PostgreSQL-style constraint name."""

    def __init__(self, constraint_name: str) -> None:
        super().__init__(
            f'duplicate key value violates unique constraint "{constraint_name}"'
        )
        self.constraint_name = constraint_name
        self.diag = SimpleNamespace(constraint_name=constraint_name)


def _integrity_error(constraint_name: str) -> IntegrityError:
    return IntegrityError(
        "INSERT",
        {},
        ConstraintViolation(constraint_name),
    )


def test_constraint_matching_uses_structured_fields_and_handles_cycles() -> None:
    text_only_constraint = "uq_text_only_decoy"
    structured_constraint = "uq_structured_target"
    origin = Exception(
        f'violates unique constraint "{text_only_constraint}"'
    )
    nested = Exception("structured database diagnostics")
    origin.orig = nested
    nested.orig = origin
    nested.constraint_name = structured_constraint
    error = IntegrityError("INSERT", {}, origin)

    assert violates_constraint(error, structured_constraint) is True
    assert violates_constraint(error, text_only_constraint) is False
    assert violates_constraint(error, "uq_missing") is False


def _device_service_harness() -> DeviceServiceHarness:
    transaction = RecordingTransaction()
    session = Mock(spec=AsyncSession)
    session.begin.return_value = transaction
    service = DeviceService(session)
    device_repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        get_by_id_for_update=AsyncMock(return_value=None),
        get_by_device_uid=AsyncMock(return_value=None),
        create=AsyncMock(return_value=None),
    )
    runtime_state_repository = SimpleNamespace(
        create=AsyncMock(return_value=None),
        get_for_update=AsyncMock(return_value=None),
    )
    service.device_repository = device_repository
    service.runtime_state_repository = runtime_state_repository
    return DeviceServiceHarness(
        service=service,
        session=session,
        transaction=transaction,
        device_repository=device_repository,
        runtime_state_repository=runtime_state_repository,
    )


def _measurement_service_harness() -> MeasurementServiceHarness:
    transaction = RecordingTransaction()
    session = Mock(spec=AsyncSession)
    session.begin.return_value = transaction
    service = MeasurementService(session)
    device_repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        get_by_id_for_update=AsyncMock(return_value=None),
        get_by_device_uid=AsyncMock(return_value=None),
        create=AsyncMock(return_value=None),
    )
    runtime_state_repository = SimpleNamespace(
        create=AsyncMock(return_value=None),
        get_for_update=AsyncMock(return_value=None),
    )
    session_repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        get_by_id_for_update=AsyncMock(return_value=None),
        get_active_for_device=AsyncMock(return_value=None),
        create=AsyncMock(return_value=None),
        increment_sample_count=AsyncMock(return_value=None),
    )
    measurement_repository = SimpleNamespace(
        get_by_source_message_id=AsyncMock(return_value=None),
        get_latest_measured_at=AsyncMock(return_value=None),
        create=AsyncMock(return_value=None),
    )
    service.device_repository = device_repository
    service.runtime_state_repository = runtime_state_repository
    service.session_repository = session_repository
    service.measurement_repository = measurement_repository
    return MeasurementServiceHarness(
        service=service,
        session=session,
        transaction=transaction,
        device_repository=device_repository,
        runtime_state_repository=runtime_state_repository,
        session_repository=session_repository,
        measurement_repository=measurement_repository,
    )


def _device(*, is_active: bool = True, device_id: int = DEVICE_ID) -> Device:
    return Device(
        id=device_id,
        device_uid=DEVICE_UID,
        name="Unit-test monitor",
        is_active=is_active,
    )


def _runtime_state(
    *,
    device_id: int = DEVICE_ID,
    measurement_enabled: bool = False,
    active_session_id: int | None = None,
) -> DeviceRuntimeState:
    return DeviceRuntimeState(
        device_id=device_id,
        measurement_enabled=measurement_enabled,
        active_session_id=active_session_id,
        fixed_latitude=51.1694,
        fixed_longitude=71.4491,
        measurement_started_at=(
            STARTED_AT if active_session_id is not None else None
        ),
        last_seen_at=None,
    )


def _measurement_session(
    *,
    device_id: int = DEVICE_ID,
    status: str = "active",
    started_at: datetime = STARTED_AT,
) -> MeasurementSession:
    return MeasurementSession(
        id=SESSION_ID,
        device_id=device_id,
        status=status,
        started_at=started_at,
        ended_at=None if status == "active" else ENDED_AT,
        latitude=51.1694,
        longitude=71.4491,
        sample_count=0,
    )


def _raw_measurement(
    *,
    source_message_id: str | None = "source-message-1",
    received_at: datetime | None = None,
) -> RawMeasurement:
    return RawMeasurement(
        id=73,
        device_id=DEVICE_ID,
        session_id=SESSION_ID,
        source_message_id=source_message_id,
        measured_at=MEASURED_AT,
        received_at=received_at or datetime.now(UTC),
        is_valid=True,
    )


def _assert_one_transaction(
    harness: DeviceServiceHarness | MeasurementServiceHarness,
    exception_type: type[BaseException] | None = None,
) -> None:
    harness.session.begin.assert_called_once_with()
    assert harness.transaction.enter_count == 1
    assert harness.transaction.exit_count == 1
    assert harness.transaction.exit_exception_types == [exception_type]
    assert harness.transaction.active is False
    harness.session.commit.assert_not_called()
    harness.session.rollback.assert_not_called()
    harness.session.begin_nested.assert_not_called()
    if isinstance(harness, MeasurementServiceHarness):
        harness.device_repository.get_by_id.assert_not_awaited()


def _awaited_argument(
    method: AsyncMock,
    name: str,
    *,
    position: int = 0,
) -> Any:
    method.assert_awaited_once()
    assert method.await_args is not None
    if name in method.await_args.kwargs:
        return method.await_args.kwargs[name]
    return method.await_args.args[position]


def _assert_utc(value: datetime) -> None:
    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)


def _prepare_active_measurement_session(
    harness: MeasurementServiceHarness,
    *,
    device_active: bool = True,
    measurement_enabled: bool = True,
    active_session_id: int | None = SESSION_ID,
    session_device_id: int = DEVICE_ID,
    session_status: str = "active",
) -> tuple[Device, DeviceRuntimeState, MeasurementSession]:
    device = _device(is_active=device_active)
    runtime_state = _runtime_state(
        measurement_enabled=measurement_enabled,
        active_session_id=active_session_id,
    )
    measurement_session = _measurement_session(
        device_id=session_device_id,
        status=session_status,
    )
    harness.device_repository.get_by_id_for_update.return_value = device
    harness.runtime_state_repository.get_for_update.return_value = runtime_state
    harness.session_repository.get_by_id_for_update.return_value = (
        measurement_session
    )
    return device, runtime_state, measurement_session


@pytest.mark.anyio
async def test_create_device_and_runtime_state_share_one_transaction() -> None:
    harness = _device_service_harness()
    device = _device()
    runtime_state = _runtime_state()
    events: list[str] = []

    async def get_by_device_uid(device_uid: str) -> None:
        assert harness.transaction.active is True
        assert device_uid == DEVICE_UID
        events.append("duplicate-check")
        return None

    async def create_device(**values: Any) -> Device:
        assert harness.transaction.active is True
        assert values == {
            "device_uid": DEVICE_UID,
            "name": "Roof monitor",
            "is_active": True,
        }
        events.append("device")
        return device

    async def create_runtime_state(**values: Any) -> DeviceRuntimeState:
        assert harness.transaction.active is True
        assert values == {"device_id": DEVICE_ID}
        events.append("runtime-state")
        return runtime_state

    harness.device_repository.get_by_device_uid.side_effect = get_by_device_uid
    harness.device_repository.create.side_effect = create_device
    harness.runtime_state_repository.create.side_effect = create_runtime_state

    result = await harness.service.create_device(
        device_uid=DEVICE_UID,
        name="Roof monitor",
    )

    assert result is device
    assert events == ["duplicate-check", "device", "runtime-state"]
    _assert_one_transaction(harness)


@pytest.mark.anyio
async def test_create_device_rejects_an_existing_device_uid() -> None:
    harness = _device_service_harness()
    harness.device_repository.get_by_device_uid.return_value = _device()

    with pytest.raises(DuplicateDeviceUIDError):
        await harness.service.create_device(device_uid=DEVICE_UID)

    harness.device_repository.create.assert_not_awaited()
    harness.runtime_state_repository.create.assert_not_awaited()
    _assert_one_transaction(harness, DuplicateDeviceUIDError)


@pytest.mark.anyio
async def test_create_device_maps_known_integrity_error_after_transaction_exit() -> None:
    harness = _device_service_harness()
    error = _integrity_error("uq_devices_device_uid")
    harness.device_repository.create.side_effect = error

    with pytest.raises(DuplicateDeviceUIDError):
        await harness.service.create_device(device_uid=DEVICE_UID)

    assert harness.transaction.exit_exception_types == [IntegrityError]
    harness.runtime_state_repository.create.assert_not_awaited()
    _assert_one_transaction(harness, IntegrityError)


@pytest.mark.anyio
async def test_create_device_reraises_unknown_integrity_error() -> None:
    harness = _device_service_harness()
    error = _integrity_error("uq_unrelated_table_value")
    harness.device_repository.create.side_effect = error

    with pytest.raises(IntegrityError) as raised:
        await harness.service.create_device(device_uid=DEVICE_UID)

    assert raised.value is error
    _assert_one_transaction(harness, IntegrityError)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method_name", "initial_state", "expected_state"),
    [
        ("activate_device", False, True),
        ("deactivate_device", True, False),
    ],
)
async def test_device_activation_changes_locked_device_atomically(
    method_name: str,
    initial_state: bool,
    expected_state: bool,
) -> None:
    harness = _device_service_harness()
    device = _device(is_active=initial_state)
    harness.device_repository.get_by_id_for_update.return_value = device
    observed_at_exit: list[bool] = []
    harness.transaction.on_exit = lambda: observed_at_exit.append(
        device.is_active
    )

    result = await getattr(harness.service, method_name)(DEVICE_ID)

    assert result is device
    assert device.is_active is expected_state
    assert observed_at_exit == [expected_state]
    assert (
        _awaited_argument(
            harness.device_repository.get_by_id_for_update,
            "device_id",
        )
        == DEVICE_ID
    )
    _assert_one_transaction(harness)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "method_name",
    ["activate_device", "deactivate_device"],
)
async def test_device_activation_requires_an_existing_device(
    method_name: str,
) -> None:
    harness = _device_service_harness()

    with pytest.raises(DeviceNotFoundError):
        await getattr(harness.service, method_name)(DEVICE_ID)

    _assert_one_transaction(harness, DeviceNotFoundError)


@pytest.mark.anyio
async def test_start_session_updates_runtime_state_atomically() -> None:
    harness = _measurement_service_harness()
    device = _device()
    runtime_state = _runtime_state()
    harness.device_repository.get_by_id_for_update.return_value = device
    harness.runtime_state_repository.get_for_update.return_value = runtime_state
    supplied_time = datetime(
        2026,
        7,
        23,
        13,
        0,
        tzinfo=UTC_PLUS_FIVE,
    )
    expected_time = supplied_time.astimezone(UTC)
    created_session = _measurement_session(started_at=expected_time)

    async def create_session(**values: Any) -> MeasurementSession:
        assert harness.transaction.active is True
        assert values == {
            "device_id": DEVICE_ID,
            "latitude": 51.1694,
            "longitude": 71.4491,
            "started_at": expected_time,
        }
        return created_session

    harness.session_repository.create.side_effect = create_session
    fixed_coordinates = (
        runtime_state.fixed_latitude,
        runtime_state.fixed_longitude,
    )
    observed_at_exit: list[tuple[bool, int | None, datetime | None]] = []
    harness.transaction.on_exit = lambda: observed_at_exit.append(
        (
            runtime_state.measurement_enabled,
            runtime_state.active_session_id,
            runtime_state.measurement_started_at,
        )
    )

    result = await harness.service.start_session(
        device_id=DEVICE_ID,
        latitude=51.1694,
        longitude=71.4491,
        started_at=supplied_time,
    )

    assert result is created_session
    assert runtime_state.measurement_enabled is True
    assert runtime_state.active_session_id == SESSION_ID
    assert runtime_state.measurement_started_at == expected_time
    assert (
        runtime_state.fixed_latitude,
        runtime_state.fixed_longitude,
    ) == fixed_coordinates
    assert observed_at_exit == [(True, SESSION_ID, expected_time)]
    assert (
        _awaited_argument(
            harness.runtime_state_repository.get_for_update,
            "device_id",
        )
        == DEVICE_ID
    )
    _assert_one_transaction(harness)


@pytest.mark.anyio
async def test_start_session_supplies_a_timezone_aware_utc_default() -> None:
    harness = _measurement_service_harness()
    harness.device_repository.get_by_id_for_update.return_value = _device()
    harness.runtime_state_repository.get_for_update.return_value = (
        _runtime_state()
    )

    async def create_session(**values: Any) -> MeasurementSession:
        return _measurement_session(started_at=values["started_at"])

    harness.session_repository.create.side_effect = create_session
    before = datetime.now(UTC)

    result = await harness.service.start_session(
        device_id=DEVICE_ID,
        latitude=51.1694,
        longitude=71.4491,
    )
    after = datetime.now(UTC)

    _assert_utc(result.started_at)
    assert before <= result.started_at <= after
    _assert_one_transaction(harness)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("device", "exception_type"),
    [
        (None, DeviceNotFoundError),
        (_device(is_active=False), DeviceInactiveError),
    ],
)
async def test_start_session_requires_an_active_device(
    device: Device | None,
    exception_type: type[Exception],
) -> None:
    harness = _measurement_service_harness()
    harness.device_repository.get_by_id_for_update.return_value = device

    with pytest.raises(exception_type):
        await harness.service.start_session(
            device_id=DEVICE_ID,
            latitude=51.1694,
            longitude=71.4491,
        )

    harness.runtime_state_repository.get_for_update.assert_not_awaited()
    harness.session_repository.create.assert_not_awaited()
    _assert_one_transaction(harness, exception_type)


@pytest.mark.anyio
async def test_start_session_requires_runtime_state() -> None:
    harness = _measurement_service_harness()
    harness.device_repository.get_by_id_for_update.return_value = _device()

    with pytest.raises(DeviceRuntimeStateNotFoundError):
        await harness.service.start_session(
            device_id=DEVICE_ID,
            latitude=51.1694,
            longitude=71.4491,
        )

    harness.session_repository.create.assert_not_awaited()
    _assert_one_transaction(harness, DeviceRuntimeStateNotFoundError)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("measurement_enabled", "active_session_id"),
    [
        (False, SESSION_ID),
        (True, None),
        (True, SESSION_ID),
    ],
)
async def test_start_session_rejects_existing_active_runtime_state(
    measurement_enabled: bool,
    active_session_id: int | None,
) -> None:
    harness = _measurement_service_harness()
    harness.device_repository.get_by_id_for_update.return_value = _device()
    harness.runtime_state_repository.get_for_update.return_value = (
        _runtime_state(
            measurement_enabled=measurement_enabled,
            active_session_id=active_session_id,
        )
    )

    with pytest.raises(ActiveSessionAlreadyExistsError):
        await harness.service.start_session(
            device_id=DEVICE_ID,
            latitude=51.1694,
            longitude=71.4491,
        )

    harness.session_repository.create.assert_not_awaited()
    _assert_one_transaction(harness, ActiveSessionAlreadyExistsError)


@pytest.mark.anyio
async def test_start_session_rejects_a_naive_timestamp() -> None:
    harness = _measurement_service_harness()
    harness.device_repository.get_by_id_for_update.return_value = _device()
    harness.runtime_state_repository.get_for_update.return_value = (
        _runtime_state()
    )

    with pytest.raises(InvalidTimestampError):
        await harness.service.start_session(
            device_id=DEVICE_ID,
            latitude=51.1694,
            longitude=71.4491,
            started_at=datetime(2026, 7, 23, 8, 0),
        )

    harness.session_repository.create.assert_not_awaited()
    _assert_one_transaction(harness, InvalidTimestampError)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method_name", "target_status"),
    [
        ("complete_session", "completed"),
        ("cancel_session", "cancelled"),
    ],
)
async def test_terminal_session_transition_is_atomic(
    method_name: str,
    target_status: str,
) -> None:
    harness = _measurement_service_harness()
    _, runtime_state, measurement_session = (
        _prepare_active_measurement_session(harness)
    )
    supplied_end = datetime(
        2026,
        7,
        23,
        14,
        0,
        tzinfo=UTC_PLUS_FIVE,
    )
    expected_end = supplied_end.astimezone(UTC)
    observed_at_exit: list[
        tuple[str, datetime | None, bool, int | None, datetime | None]
    ] = []
    harness.transaction.on_exit = lambda: observed_at_exit.append(
        (
            measurement_session.status,
            measurement_session.ended_at,
            runtime_state.measurement_enabled,
            runtime_state.active_session_id,
            runtime_state.measurement_started_at,
        )
    )

    result = await getattr(harness.service, method_name)(
        device_id=DEVICE_ID,
        ended_at=supplied_end,
    )

    assert result is measurement_session
    assert measurement_session.status == target_status
    assert measurement_session.ended_at == expected_end
    assert runtime_state.measurement_enabled is False
    assert runtime_state.active_session_id is None
    assert runtime_state.measurement_started_at is None
    assert observed_at_exit == [
        (target_status, expected_end, False, None, None)
    ]
    assert (
        _awaited_argument(
            harness.session_repository.get_by_id_for_update,
            "session_id",
        )
        == SESSION_ID
    )
    _assert_one_transaction(harness)


@pytest.mark.anyio
async def test_complete_session_supplies_a_timezone_aware_utc_default() -> None:
    harness = _measurement_service_harness()
    _, _, measurement_session = _prepare_active_measurement_session(harness)
    before = datetime.now(UTC)

    result = await harness.service.complete_session(device_id=DEVICE_ID)
    after = datetime.now(UTC)

    assert result is measurement_session
    assert measurement_session.ended_at is not None
    _assert_utc(measurement_session.ended_at)
    assert before <= measurement_session.ended_at <= after
    _assert_one_transaction(harness)


@pytest.mark.anyio
async def test_terminal_transition_requires_an_existing_device() -> None:
    harness = _measurement_service_harness()

    with pytest.raises(DeviceNotFoundError):
        await harness.service.complete_session(device_id=DEVICE_ID)

    harness.runtime_state_repository.get_for_update.assert_not_awaited()
    _assert_one_transaction(harness, DeviceNotFoundError)


@pytest.mark.anyio
async def test_terminal_transition_requires_runtime_state() -> None:
    harness = _measurement_service_harness()
    harness.device_repository.get_by_id_for_update.return_value = _device()

    with pytest.raises(DeviceRuntimeStateNotFoundError):
        await harness.service.complete_session(device_id=DEVICE_ID)

    _assert_one_transaction(harness, DeviceRuntimeStateNotFoundError)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method_name", "measurement_enabled", "active_session_id"),
    [
        ("complete_session", False, None),
        ("complete_session", True, None),
        ("cancel_session", False, SESSION_ID),
    ],
)
async def test_terminal_transition_requires_enabled_active_session(
    method_name: str,
    measurement_enabled: bool,
    active_session_id: int | None,
) -> None:
    harness = _measurement_service_harness()
    harness.device_repository.get_by_id_for_update.return_value = _device()
    harness.runtime_state_repository.get_for_update.return_value = (
        _runtime_state(
            measurement_enabled=measurement_enabled,
            active_session_id=active_session_id,
        )
    )

    with pytest.raises(ActiveSessionNotFoundError):
        await getattr(harness.service, method_name)(device_id=DEVICE_ID)

    harness.session_repository.get_by_id_for_update.assert_not_awaited()
    _assert_one_transaction(harness, ActiveSessionNotFoundError)


@pytest.mark.anyio
async def test_terminal_transition_reports_missing_active_session() -> None:
    harness = _measurement_service_harness()
    harness.device_repository.get_by_id_for_update.return_value = _device()
    harness.runtime_state_repository.get_for_update.return_value = (
        _runtime_state(
            measurement_enabled=True,
            active_session_id=SESSION_ID,
        )
    )

    with pytest.raises(SessionNotFoundError):
        await harness.service.complete_session(device_id=DEVICE_ID)

    _assert_one_transaction(harness, SessionNotFoundError)


@pytest.mark.anyio
async def test_terminal_transition_rejects_session_from_another_device() -> None:
    harness = _measurement_service_harness()
    _, runtime_state, measurement_session = (
        _prepare_active_measurement_session(
            harness,
            session_device_id=OTHER_DEVICE_ID,
        )
    )

    with pytest.raises(SessionDoesNotBelongToDeviceError):
        await harness.service.complete_session(device_id=DEVICE_ID)

    assert measurement_session.status == "active"
    assert runtime_state.active_session_id == SESSION_ID
    assert runtime_state.measurement_enabled is True
    _assert_one_transaction(harness, SessionDoesNotBelongToDeviceError)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "method_name",
    ["complete_session", "cancel_session"],
)
async def test_terminal_transition_rejects_non_active_status(
    method_name: str,
) -> None:
    harness = _measurement_service_harness()
    _, runtime_state, measurement_session = (
        _prepare_active_measurement_session(
            harness,
            session_status="completed",
        )
    )

    with pytest.raises(InvalidSessionTransitionError):
        await getattr(harness.service, method_name)(device_id=DEVICE_ID)

    assert measurement_session.status == "completed"
    assert runtime_state.active_session_id == SESSION_ID
    _assert_one_transaction(harness, InvalidSessionTransitionError)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "ended_at",
    [
        STARTED_AT - timedelta(microseconds=1),
        datetime(2026, 7, 23, 9, 0),
    ],
)
async def test_terminal_transition_rejects_invalid_end_timestamp(
    ended_at: datetime,
) -> None:
    harness = _measurement_service_harness()
    _, runtime_state, measurement_session = (
        _prepare_active_measurement_session(harness)
    )

    with pytest.raises(InvalidTimestampError):
        await harness.service.complete_session(
            device_id=DEVICE_ID,
            ended_at=ended_at,
        )

    assert measurement_session.status == "active"
    assert measurement_session.ended_at is None
    assert runtime_state.measurement_enabled is True
    assert runtime_state.active_session_id == SESSION_ID
    _assert_one_transaction(harness, InvalidTimestampError)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "method_name",
    ["complete_session", "cancel_session"],
)
async def test_terminal_transition_rejects_end_before_latest_measurement_without_state_changes(
    method_name: str,
) -> None:
    harness = _measurement_service_harness()
    _, runtime_state, measurement_session = (
        _prepare_active_measurement_session(harness)
    )
    measurement_session.sample_count = 1
    latest_measurement = _raw_measurement()
    harness.measurement_repository.get_latest_measured_at.return_value = (
        latest_measurement.measured_at
    )
    session_snapshot = (
        measurement_session.status,
        measurement_session.ended_at,
        measurement_session.sample_count,
    )
    runtime_snapshot = (
        runtime_state.measurement_enabled,
        runtime_state.active_session_id,
        runtime_state.measurement_started_at,
        runtime_state.last_seen_at,
    )
    with pytest.raises(InvalidTimestampError):
        await getattr(harness.service, method_name)(
            device_id=DEVICE_ID,
            ended_at=MEASURED_AT - timedelta(microseconds=1),
        )

    assert (
        measurement_session.status,
        measurement_session.ended_at,
        measurement_session.sample_count,
    ) == session_snapshot
    assert (
        runtime_state.measurement_enabled,
        runtime_state.active_session_id,
        runtime_state.measurement_started_at,
        runtime_state.last_seen_at,
    ) == runtime_snapshot
    harness.measurement_repository.get_latest_measured_at.assert_awaited_once_with(
        session_id=SESSION_ID
    )
    harness.measurement_repository.create.assert_not_awaited()
    harness.session_repository.increment_sample_count.assert_not_awaited()
    _assert_one_transaction(harness, InvalidTimestampError)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method_name", "target_status"),
    [
        ("complete_session", "completed"),
        ("cancel_session", "cancelled"),
    ],
)
async def test_terminal_transition_accepts_end_equal_to_latest_measurement(
    method_name: str,
    target_status: str,
) -> None:
    harness = _measurement_service_harness()
    _, runtime_state, measurement_session = (
        _prepare_active_measurement_session(harness)
    )
    harness.measurement_repository.get_latest_measured_at.return_value = (
        MEASURED_AT
    )

    result = await getattr(harness.service, method_name)(
        device_id=DEVICE_ID,
        ended_at=MEASURED_AT,
    )

    assert result is measurement_session
    assert measurement_session.status == target_status
    assert measurement_session.ended_at == MEASURED_AT
    assert runtime_state.measurement_enabled is False
    assert runtime_state.active_session_id is None
    assert runtime_state.measurement_started_at is None
    harness.measurement_repository.get_latest_measured_at.assert_awaited_once_with(
        session_id=SESSION_ID
    )
    _assert_one_transaction(harness)


@pytest.mark.anyio
async def test_record_measurement_updates_counter_and_last_seen_atomically() -> None:
    harness = _measurement_service_harness()
    _, runtime_state, _ = _prepare_active_measurement_session(harness)
    supplied_measured_at = datetime(
        2026,
        7,
        23,
        13,
        5,
        tzinfo=UTC_PLUS_FIVE,
    )
    expected_measured_at = supplied_measured_at.astimezone(UTC)
    received_at = datetime.now(UTC)
    created_measurement = _raw_measurement(received_at=received_at)

    async def create_measurement(**values: Any) -> RawMeasurement:
        assert harness.transaction.active is True
        assert values == {
            "device_id": DEVICE_ID,
            "session_id": SESSION_ID,
            "source_message_id": "source-message-1",
            "measured_at": expected_measured_at,
            "temperature": 21.5,
            "humidity": 48.0,
            "pm1": 4.0,
            "pm25": 7.5,
            "pm10": 12.0,
            "pc0_3": 120,
            "pc0_5": 100,
            "pc1_0": 80,
            "pc2_5": 40,
            "pc5_0": 20,
            "pc10": 10,
            "latitude": 51.1694,
            "longitude": 71.4491,
            "is_valid": False,
            "validation_note": "unit-test note",
        }
        return created_measurement

    async def increment_sample_count(*args: Any, **kwargs: Any) -> None:
        assert harness.transaction.active is True
        assert kwargs.get("session_id", args[0] if args else None) == SESSION_ID

    harness.measurement_repository.create.side_effect = create_measurement
    harness.session_repository.increment_sample_count.side_effect = (
        increment_sample_count
    )
    observed_at_exit: list[datetime | None] = []
    harness.transaction.on_exit = lambda: observed_at_exit.append(
        runtime_state.last_seen_at
    )

    result = await harness.service.record_measurement(
        device_id=DEVICE_ID,
        source_message_id="source-message-1",
        measured_at=supplied_measured_at,
        temperature=21.5,
        humidity=48.0,
        pm1=4.0,
        pm25=7.5,
        pm10=12.0,
        pc0_3=120,
        pc0_5=100,
        pc1_0=80,
        pc2_5=40,
        pc5_0=20,
        pc10=10,
        latitude=51.1694,
        longitude=71.4491,
        is_valid=False,
        validation_note="unit-test note",
    )

    assert result is created_measurement
    assert (
        _awaited_argument(
            harness.measurement_repository.get_by_source_message_id,
            "device_id",
        )
        == DEVICE_ID
    )
    assert (
        _awaited_argument(
            harness.measurement_repository.get_by_source_message_id,
            "source_message_id",
            position=1,
        )
        == "source-message-1"
    )
    assert (
        _awaited_argument(
            harness.session_repository.increment_sample_count,
            "session_id",
        )
        == SESSION_ID
    )
    assert runtime_state.last_seen_at is not None
    _assert_utc(runtime_state.last_seen_at)
    assert runtime_state.last_seen_at >= received_at
    assert observed_at_exit == [runtime_state.last_seen_at]
    _assert_one_transaction(harness)


@pytest.mark.anyio
async def test_record_measurement_rejects_timestamp_before_session_start_without_state_changes() -> None:
    harness = _measurement_service_harness()
    _, runtime_state, measurement_session = (
        _prepare_active_measurement_session(harness)
    )
    measurement_session.sample_count = 3
    runtime_state.last_seen_at = STARTED_AT - timedelta(minutes=10)
    session_snapshot = (
        measurement_session.status,
        measurement_session.ended_at,
        measurement_session.sample_count,
    )
    runtime_snapshot = (
        runtime_state.measurement_enabled,
        runtime_state.active_session_id,
        runtime_state.measurement_started_at,
        runtime_state.last_seen_at,
    )

    with pytest.raises(InvalidTimestampError):
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            source_message_id="too-early",
            measured_at=STARTED_AT - timedelta(microseconds=1),
        )

    assert (
        measurement_session.status,
        measurement_session.ended_at,
        measurement_session.sample_count,
    ) == session_snapshot
    assert (
        runtime_state.measurement_enabled,
        runtime_state.active_session_id,
        runtime_state.measurement_started_at,
        runtime_state.last_seen_at,
    ) == runtime_snapshot
    harness.measurement_repository.get_by_source_message_id.assert_not_awaited()
    harness.measurement_repository.create.assert_not_awaited()
    harness.session_repository.increment_sample_count.assert_not_awaited()
    _assert_one_transaction(harness, InvalidTimestampError)


@pytest.mark.anyio
async def test_record_measurement_accepts_timestamp_equal_to_session_start() -> None:
    harness = _measurement_service_harness()
    _prepare_active_measurement_session(harness)
    created_measurement = _raw_measurement()
    created_measurement.measured_at = STARTED_AT
    harness.measurement_repository.create.return_value = created_measurement

    result = await harness.service.record_measurement(
        device_id=DEVICE_ID,
        measured_at=STARTED_AT,
    )

    assert result is created_measurement
    assert harness.measurement_repository.create.await_args is not None
    assert (
        harness.measurement_repository.create.await_args.kwargs["measured_at"]
        == STARTED_AT
    )
    harness.session_repository.increment_sample_count.assert_awaited_once_with(
        session_id=SESSION_ID
    )
    _assert_one_transaction(harness)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "operation",
    ["record_measurement", "complete_session", "cancel_session"],
)
async def test_record_and_terminal_transitions_preserve_lock_order(
    operation: str,
) -> None:
    harness = _measurement_service_harness()
    device, runtime_state, measurement_session = (
        _prepare_active_measurement_session(harness)
    )
    events: list[str] = []

    def observe(name: str, value: object):
        def side_effect(*args: Any, **kwargs: Any) -> object:
            del args, kwargs
            assert harness.transaction.active is True
            events.append(name)
            return value

        return side_effect

    harness.device_repository.get_by_id_for_update.side_effect = observe(
        "device",
        device,
    )
    harness.runtime_state_repository.get_for_update.side_effect = observe(
        "runtime",
        runtime_state,
    )
    harness.session_repository.get_by_id_for_update.side_effect = observe(
        "session",
        measurement_session,
    )
    harness.measurement_repository.get_latest_measured_at.side_effect = (
        observe("latest-measurement", MEASURED_AT)
    )
    harness.measurement_repository.create.return_value = _raw_measurement()

    if operation == "record_measurement":
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            measured_at=MEASURED_AT,
        )
        assert events == ["device", "runtime", "session"]
        harness.measurement_repository.get_latest_measured_at.assert_not_awaited()
    else:
        await getattr(harness.service, operation)(
            device_id=DEVICE_ID,
            ended_at=MEASURED_AT,
        )
        assert events == [
            "device",
            "runtime",
            "session",
            "latest-measurement",
        ]

    _assert_one_transaction(harness)


@pytest.mark.anyio
@pytest.mark.parametrize("field_name", ["pm1", "pm25", "pm10"])
@pytest.mark.parametrize(
    "value",
    [float("inf"), float("-inf"), float("nan")],
    ids=["positive-infinity", "negative-infinity", "nan"],
)
async def test_record_measurement_rejects_non_finite_pm_before_transaction(
    field_name: str,
    value: float,
) -> None:
    harness = _measurement_service_harness()

    with pytest.raises(ValueError, match=rf"{field_name} must be finite"):
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            measured_at=MEASURED_AT,
            **{field_name: value},
        )

    harness.session.begin.assert_not_called()
    harness.device_repository.get_by_id_for_update.assert_not_awaited()
    harness.runtime_state_repository.get_for_update.assert_not_awaited()
    harness.session_repository.get_by_id_for_update.assert_not_awaited()
    harness.measurement_repository.get_by_source_message_id.assert_not_awaited()
    harness.measurement_repository.create.assert_not_awaited()
    harness.session_repository.increment_sample_count.assert_not_awaited()


@pytest.mark.anyio
async def test_record_measurement_allows_null_source_message_id() -> None:
    harness = _measurement_service_harness()
    _prepare_active_measurement_session(harness)
    created_measurement = _raw_measurement(source_message_id=None)
    harness.measurement_repository.create.return_value = created_measurement

    result = await harness.service.record_measurement(
        device_id=DEVICE_ID,
        source_message_id=None,
        measured_at=MEASURED_AT,
    )

    assert result is created_measurement
    harness.measurement_repository.get_by_source_message_id.assert_not_awaited()
    harness.measurement_repository.create.assert_awaited_once()
    assert (
        harness.measurement_repository.create.await_args.kwargs[
            "source_message_id"
        ]
        is None
    )
    harness.session_repository.increment_sample_count.assert_awaited_once()
    _assert_one_transaction(harness)


@pytest.mark.anyio
async def test_record_measurement_rejects_stale_expected_session() -> None:
    harness = _measurement_service_harness()
    _, runtime_state, _ = _prepare_active_measurement_session(harness)

    with pytest.raises(ActiveSessionMismatchError):
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            session_id=SESSION_ID + 1,
            measured_at=MEASURED_AT,
        )

    assert runtime_state.active_session_id == SESSION_ID
    harness.session_repository.get_by_id_for_update.assert_not_awaited()
    harness.measurement_repository.create.assert_not_awaited()
    harness.session_repository.increment_sample_count.assert_not_awaited()
    _assert_one_transaction(harness, ActiveSessionMismatchError)


@pytest.mark.anyio
async def test_record_measurement_rejects_duplicate_source_message() -> None:
    harness = _measurement_service_harness()
    _, runtime_state, _ = _prepare_active_measurement_session(harness)
    harness.measurement_repository.get_by_source_message_id.return_value = (
        _raw_measurement()
    )

    with pytest.raises(DuplicateSourceMessageError):
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            source_message_id="source-message-1",
            measured_at=MEASURED_AT,
        )

    harness.measurement_repository.create.assert_not_awaited()
    harness.session_repository.increment_sample_count.assert_not_awaited()
    assert runtime_state.last_seen_at is None
    _assert_one_transaction(harness, DuplicateSourceMessageError)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("device", "exception_type"),
    [
        (None, DeviceNotFoundError),
        (_device(is_active=False), DeviceInactiveError),
    ],
)
async def test_record_measurement_requires_an_active_device(
    device: Device | None,
    exception_type: type[Exception],
) -> None:
    harness = _measurement_service_harness()
    harness.device_repository.get_by_id_for_update.return_value = device

    with pytest.raises(exception_type):
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            measured_at=MEASURED_AT,
        )

    harness.runtime_state_repository.get_for_update.assert_not_awaited()
    harness.measurement_repository.create.assert_not_awaited()
    _assert_one_transaction(harness, exception_type)


@pytest.mark.anyio
async def test_record_measurement_requires_runtime_state() -> None:
    harness = _measurement_service_harness()
    harness.device_repository.get_by_id_for_update.return_value = _device()

    with pytest.raises(DeviceRuntimeStateNotFoundError):
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            measured_at=MEASURED_AT,
        )

    _assert_one_transaction(harness, DeviceRuntimeStateNotFoundError)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("measurement_enabled", "active_session_id"),
    [
        (False, None),
        (False, SESSION_ID),
        (True, None),
    ],
)
async def test_record_measurement_requires_enabled_active_session(
    measurement_enabled: bool,
    active_session_id: int | None,
) -> None:
    harness = _measurement_service_harness()
    harness.device_repository.get_by_id_for_update.return_value = _device()
    harness.runtime_state_repository.get_for_update.return_value = (
        _runtime_state(
            measurement_enabled=measurement_enabled,
            active_session_id=active_session_id,
        )
    )

    with pytest.raises(ActiveSessionNotFoundError):
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            measured_at=MEASURED_AT,
        )

    harness.session_repository.get_by_id_for_update.assert_not_awaited()
    harness.measurement_repository.create.assert_not_awaited()
    _assert_one_transaction(harness, ActiveSessionNotFoundError)


@pytest.mark.anyio
async def test_record_measurement_reports_missing_active_session() -> None:
    harness = _measurement_service_harness()
    harness.device_repository.get_by_id_for_update.return_value = _device()
    harness.runtime_state_repository.get_for_update.return_value = (
        _runtime_state(
            measurement_enabled=True,
            active_session_id=SESSION_ID,
        )
    )

    with pytest.raises(SessionNotFoundError):
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            measured_at=MEASURED_AT,
        )

    _assert_one_transaction(harness, SessionNotFoundError)


@pytest.mark.anyio
async def test_record_measurement_rejects_session_from_another_device() -> None:
    harness = _measurement_service_harness()
    _, runtime_state, _ = _prepare_active_measurement_session(
        harness,
        session_device_id=OTHER_DEVICE_ID,
    )

    with pytest.raises(SessionDoesNotBelongToDeviceError):
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            measured_at=MEASURED_AT,
        )

    harness.measurement_repository.create.assert_not_awaited()
    harness.session_repository.increment_sample_count.assert_not_awaited()
    assert runtime_state.last_seen_at is None
    _assert_one_transaction(harness, SessionDoesNotBelongToDeviceError)


@pytest.mark.anyio
async def test_record_measurement_rejects_non_active_session() -> None:
    harness = _measurement_service_harness()
    _, runtime_state, _ = _prepare_active_measurement_session(
        harness,
        session_status="completed",
    )

    with pytest.raises(InvalidSessionTransitionError):
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            measured_at=MEASURED_AT,
        )

    harness.measurement_repository.create.assert_not_awaited()
    harness.session_repository.increment_sample_count.assert_not_awaited()
    assert runtime_state.last_seen_at is None
    _assert_one_transaction(harness, InvalidSessionTransitionError)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "measured_at",
    [None, datetime(2026, 7, 23, 8, 5)],
)
async def test_record_measurement_rejects_invalid_measured_at(
    measured_at: datetime | None,
) -> None:
    harness = _measurement_service_harness()
    _, runtime_state, _ = _prepare_active_measurement_session(harness)

    with pytest.raises(InvalidTimestampError):
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            measured_at=measured_at,
        )

    harness.measurement_repository.create.assert_not_awaited()
    harness.session_repository.increment_sample_count.assert_not_awaited()
    assert runtime_state.last_seen_at is None
    _assert_one_transaction(harness, InvalidTimestampError)


@pytest.mark.anyio
async def test_record_measurement_maps_known_integrity_error_after_exit() -> None:
    harness = _measurement_service_harness()
    _, runtime_state, _ = _prepare_active_measurement_session(harness)
    error = _integrity_error(
        "uq_raw_measurements_device_id_source_message_id"
    )
    harness.measurement_repository.create.side_effect = error

    with pytest.raises(DuplicateSourceMessageError):
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            source_message_id="source-message-1",
            measured_at=MEASURED_AT,
        )

    assert harness.transaction.exit_exception_types == [IntegrityError]
    harness.session_repository.increment_sample_count.assert_not_awaited()
    assert runtime_state.last_seen_at is None
    _assert_one_transaction(harness, IntegrityError)


@pytest.mark.anyio
async def test_record_measurement_reraises_unknown_integrity_error() -> None:
    harness = _measurement_service_harness()
    _prepare_active_measurement_session(harness)
    error = _integrity_error("uq_unrelated_table_value")
    harness.measurement_repository.create.side_effect = error

    with pytest.raises(IntegrityError) as raised:
        await harness.service.record_measurement(
            device_id=DEVICE_ID,
            source_message_id="source-message-1",
            measured_at=MEASURED_AT,
        )

    assert raised.value is error
    _assert_one_transaction(harness, IntegrityError)


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


@pytest.mark.parametrize(
    "module_path",
    SERVICE_POLICY_FILES,
    ids=lambda path: str(path.relative_to(APP_DIRECTORY)),
)
def test_service_and_domain_sources_obey_layer_policy(
    module_path: Path,
) -> None:
    tree = ast.parse(
        module_path.read_text(encoding="utf-8"),
        filename=str(module_path),
    )
    violations: list[str] = []

    for node in ast.walk(tree):
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
                    f"{module_path.name}:{node.lineno}:"
                    f"import {imported_module}"
                )

        if (
            isinstance(node, ast.ExceptHandler)
            and _catches_broad_exception(node.type)
        ):
            violations.append(
                f"{module_path.name}:{node.lineno}:broad exception handler"
            )

    assert violations == []
