"""Guarded PostgreSQL integration tests for transactional persistence."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
import os
from uuid import uuid4

import pytest
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tests.persistence_guard import (
    PersistenceTargetError,
    validate_persistence_database_url,
)


if os.environ.get("AIRMONITOR_RUN_PERSISTENCE_INTEGRATION") != "1":
    pytest.skip(
        "persistence integration tests require explicit opt-in",
        allow_module_level=True,
    )

_DATABASE_URL_TEXT = os.environ.get("AIRMONITOR_DATABASE_URL")
if _DATABASE_URL_TEXT is None:
    pytest.fail(
        "persistence integration tests require an explicit database URL",
        pytrace=False,
    )

try:
    _parsed_database_url: URL = validate_persistence_database_url(
        _DATABASE_URL_TEXT
    )
except PersistenceTargetError as error:
    pytest.fail(str(error), pytrace=False)

del _DATABASE_URL_TEXT


from app.core.exceptions import (
    ActiveSessionAlreadyExistsError,
    ActiveSessionNotFoundError,
    DeviceInactiveError,
    DuplicateDeviceUIDError,
    DuplicateSourceMessageError,
)
from app.db.models.device import Device, DeviceRuntimeState
from app.db.models.measurement import RawMeasurement
from app.db.models.measurement_session import MeasurementSession
from app.services.device import DeviceService
from app.services.measurement import MeasurementService


pytestmark = pytest.mark.anyio

EXPECTED_TABLES = {
    "alembic_version",
    "device_runtime_state",
    "devices",
    "measurement_sessions",
    "raw_measurements",
}
EXPECTED_ALEMBIC_HEAD = "a4f9c2e7d1b6"
DOMAIN_MODELS = (
    Device,
    DeviceRuntimeState,
    MeasurementSession,
    RawMeasurement,
)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


async def _preflight_disposable_database(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        async with connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            table_names = await connection.run_sync(
                lambda sync_connection: set(
                    inspect(sync_connection).get_table_names()
                )
            )
            if table_names != EXPECTED_TABLES:
                pytest.fail(
                    "persistence integration database schema is not approved",
                    pytrace=False,
                )

            alembic_heads = (
                await connection.execute(
                    text("SELECT version_num FROM alembic_version")
                )
            ).scalars().all()
            if alembic_heads != [EXPECTED_ALEMBIC_HEAD]:
                pytest.fail(
                    "persistence integration database revision is not approved",
                    pytrace=False,
                )

            row_counts = [
                await connection.scalar(
                    select(func.count()).select_from(model)
                )
                for model in DOMAIN_MODELS
            ]
            if any(row_count != 0 for row_count in row_counts):
                pytest.fail(
                    "persistence integration database is not empty",
                    pytrace=False,
                )


@pytest.fixture(scope="session")
async def session_factory(
    anyio_backend: str,
) -> AsyncIterator[
    async_sessionmaker[AsyncSession]
]:
    assert anyio_backend == "asyncio"
    engine = create_async_engine(
        _parsed_database_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "statement_timeout": "15000",
            }
        },
    )
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        await _preflight_disposable_database(engine)
        yield factory
    finally:
        await engine.dispose()


def _unique_device_uid(label: str) -> str:
    return f"integration-{label}-{uuid4().hex}"


async def _create_device(
    session_factory: async_sessionmaker[AsyncSession],
    label: str,
) -> Device:
    async with session_factory() as session:
        return await DeviceService(session).create_device(
            device_uid=_unique_device_uid(label),
            name=f"Integration {label}",
        )


async def _start_session(
    session_factory: async_sessionmaker[AsyncSession],
    device_id: int,
) -> MeasurementSession:
    async with session_factory() as session:
        return await MeasurementService(session).start_session(
            device_id=device_id,
            latitude=51.1694,
            longitude=71.4491,
        )


async def test_create_device_creates_runtime_state_atomically(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device_uid = _unique_device_uid("create")

    async with session_factory() as session:
        created = await DeviceService(session).create_device(
            device_uid=device_uid,
            name="Integration create",
        )

    async with session_factory() as session:
        persisted = await session.scalar(
            select(Device).where(Device.device_uid == device_uid)
        )
        runtime_state = await session.get(
            DeviceRuntimeState,
            created.id,
        )

    assert persisted is not None
    assert persisted.id == created.id
    assert persisted.is_active is True
    assert runtime_state is not None
    assert runtime_state.device_id == created.id
    assert runtime_state.measurement_enabled is False
    assert runtime_state.active_session_id is None


async def test_duplicate_device_uid_rolls_back_without_partial_state(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    duplicate_uid = _unique_device_uid("duplicate-device")
    recovery_uid = _unique_device_uid("duplicate-recovery")

    async with session_factory() as session:
        service = DeviceService(session)
        original = await service.create_device(device_uid=duplicate_uid)
        original_id = original.id

        with pytest.raises(DuplicateDeviceUIDError):
            await service.create_device(device_uid=duplicate_uid)

        recovered = await service.create_device(device_uid=recovery_uid)
        recovered_id = recovered.id

    async with session_factory() as session:
        matching_devices = (
            await session.scalars(
                select(Device).where(
                    Device.device_uid.in_((duplicate_uid, recovery_uid))
                )
            )
        ).all()
        matching_runtime_count = await session.scalar(
            select(func.count())
            .select_from(DeviceRuntimeState)
            .join(Device)
            .where(Device.device_uid.in_((duplicate_uid, recovery_uid)))
        )

    assert original_id != recovered_id
    assert {device.device_uid for device in matching_devices} == {
        duplicate_uid,
        recovery_uid,
    }
    assert matching_runtime_count == 2


async def test_runtime_creation_failure_rolls_back_flushed_device(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failed_uid = _unique_device_uid("runtime-failure")
    recovery_uid = _unique_device_uid("runtime-recovery")

    async with session_factory() as session:
        service = DeviceService(session)
        create_runtime_state = service.runtime_state_repository.create

        async def fail_runtime_creation(device_id: int) -> None:
            del device_id
            raise RuntimeError("injected runtime-state creation failure")

        monkeypatch.setattr(
            service.runtime_state_repository,
            "create",
            fail_runtime_creation,
        )
        try:
            with pytest.raises(
                RuntimeError,
                match="injected runtime-state creation failure",
            ):
                await service.create_device(device_uid=failed_uid)
        finally:
            monkeypatch.setattr(
                service.runtime_state_repository,
                "create",
                create_runtime_state,
            )

        recovered = await service.create_device(device_uid=recovery_uid)
        recovered_id = recovered.id

    async with session_factory() as session:
        failed_device_id = await session.scalar(
            select(Device.id).where(Device.device_uid == failed_uid)
        )
        failed_runtime_count = await session.scalar(
            select(func.count())
            .select_from(DeviceRuntimeState)
            .join(Device)
            .where(Device.device_uid == failed_uid)
        )
        recovered_runtime_state = await session.get(
            DeviceRuntimeState,
            recovered_id,
        )

    assert failed_device_id is None
    assert failed_runtime_count == 0
    assert recovered_runtime_state is not None


async def test_start_session_rejects_a_second_active_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device = await _create_device(session_factory, "second-session")
    device_id = device.id

    async with session_factory() as session:
        service = MeasurementService(session)
        started = await service.start_session(
            device_id=device_id,
            latitude=51.1694,
            longitude=71.4491,
        )
        started_id = started.id

        with pytest.raises(ActiveSessionAlreadyExistsError):
            await service.start_session(
                device_id=device_id,
                latitude=43.2389,
                longitude=76.8897,
            )

    async with session_factory() as session:
        active_sessions = (
            await session.scalars(
                select(MeasurementSession).where(
                    MeasurementSession.device_id == device_id,
                    MeasurementSession.status == "active",
                )
            )
        ).all()
        runtime_state = await session.get(DeviceRuntimeState, device_id)

    assert [item.id for item in active_sessions] == [started_id]
    assert runtime_state is not None
    assert runtime_state.measurement_enabled is True
    assert runtime_state.active_session_id == started_id
    assert runtime_state.measurement_started_at == active_sessions[0].started_at


async def test_record_measurement_updates_count_and_last_seen_atomically(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device = await _create_device(session_factory, "record")
    started = await _start_session(session_factory, device.id)
    measured_at = datetime.now(UTC)

    async with session_factory() as session:
        recorded = await MeasurementService(session).record_measurement(
            device_id=device.id,
            source_message_id=f"message-{uuid4().hex}",
            measured_at=measured_at,
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

    async with session_factory() as session:
        persisted = await session.get(RawMeasurement, recorded.id)
        persisted_session = await session.get(
            MeasurementSession,
            started.id,
        )
        runtime_state = await session.get(DeviceRuntimeState, device.id)

    assert persisted is not None
    assert persisted.device_id == device.id
    assert persisted.session_id == started.id
    assert persisted.measured_at == measured_at
    assert persisted_session is not None
    assert persisted_session.sample_count == 1
    assert runtime_state is not None
    assert runtime_state.last_seen_at is not None
    assert runtime_state.last_seen_at.utcoffset() is not None


async def test_duplicate_non_null_source_message_is_rejected_without_updates(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device = await _create_device(session_factory, "duplicate-message")
    device_id = device.id
    started = await _start_session(session_factory, device_id)
    started_id = started.id
    source_message_id = f"duplicate-{uuid4().hex}"

    async with session_factory() as session:
        await MeasurementService(session).record_measurement(
            device_id=device_id,
            source_message_id=source_message_id,
            measured_at=datetime.now(UTC),
            pm25=8.0,
        )

    async with session_factory() as session:
        before_duplicate_state = await session.get(
            DeviceRuntimeState,
            device_id,
        )
        assert before_duplicate_state is not None
        previous_last_seen_at = before_duplicate_state.last_seen_at

    async with session_factory() as session:
        with pytest.raises(DuplicateSourceMessageError):
            await MeasurementService(session).record_measurement(
                device_id=device_id,
                source_message_id=source_message_id,
                measured_at=datetime.now(UTC),
                pm25=9.0,
            )

    async with session_factory() as session:
        measurement_count = await session.scalar(
            select(func.count())
            .select_from(RawMeasurement)
            .where(
                RawMeasurement.device_id == device_id,
                RawMeasurement.source_message_id == source_message_id,
            )
        )
        persisted_session = await session.get(
            MeasurementSession,
            started_id,
        )
        runtime_state = await session.get(DeviceRuntimeState, device_id)

    assert measurement_count == 1
    assert persisted_session is not None
    assert persisted_session.sample_count == 1
    assert runtime_state is not None
    assert runtime_state.last_seen_at == previous_last_seen_at


async def test_multiple_null_source_message_ids_are_allowed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device = await _create_device(session_factory, "null-message")
    started = await _start_session(session_factory, device.id)

    async with session_factory() as session:
        service = MeasurementService(session)
        first = await service.record_measurement(
            device_id=device.id,
            source_message_id=None,
            measured_at=datetime.now(UTC),
            pm25=4.0,
        )
        second = await service.record_measurement(
            device_id=device.id,
            source_message_id=None,
            measured_at=datetime.now(UTC),
            pm25=5.0,
        )

    async with session_factory() as session:
        measurement_count = await session.scalar(
            select(func.count())
            .select_from(RawMeasurement)
            .where(
                RawMeasurement.device_id == device.id,
                RawMeasurement.source_message_id.is_(None),
            )
        )
        persisted_session = await session.get(
            MeasurementSession,
            started.id,
        )

    assert first.id != second.id
    assert measurement_count == 2
    assert persisted_session is not None
    assert persisted_session.sample_count == 2


async def test_complete_session_clears_runtime_and_rejects_measurements(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device = await _create_device(session_factory, "complete")
    device_id = device.id
    started = await _start_session(session_factory, device_id)
    started_id = started.id

    async with session_factory() as session:
        service = MeasurementService(session)
        completed = await service.complete_session(device_id=device_id)
        completed_id = completed.id

        with pytest.raises(ActiveSessionNotFoundError):
            await service.record_measurement(
                device_id=device_id,
                source_message_id=f"after-complete-{uuid4().hex}",
                measured_at=datetime.now(UTC),
                pm25=5.0,
            )

    async with session_factory() as session:
        persisted_session = await session.get(
            MeasurementSession,
            started_id,
        )
        runtime_state = await session.get(DeviceRuntimeState, device_id)
        measurement_count = await session.scalar(
            select(func.count())
            .select_from(RawMeasurement)
            .where(RawMeasurement.device_id == device_id)
        )

    assert completed_id == started_id
    assert persisted_session is not None
    assert persisted_session.status == "completed"
    assert persisted_session.ended_at is not None
    assert runtime_state is not None
    assert runtime_state.measurement_enabled is False
    assert runtime_state.active_session_id is None
    assert measurement_count == 0


async def test_cancel_session_performs_consistent_terminal_transition(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device = await _create_device(session_factory, "cancel")
    started = await _start_session(session_factory, device.id)

    async with session_factory() as session:
        cancelled = await MeasurementService(session).cancel_session(
            device_id=device.id
        )

    async with session_factory() as session:
        persisted_session = await session.get(
            MeasurementSession,
            started.id,
        )
        runtime_state = await session.get(DeviceRuntimeState, device.id)

    assert cancelled.id == started.id
    assert persisted_session is not None
    assert persisted_session.status == "cancelled"
    assert persisted_session.ended_at is not None
    assert runtime_state is not None
    assert runtime_state.measurement_enabled is False
    assert runtime_state.active_session_id is None


async def test_inactive_device_rejects_start_and_recording(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device = await _create_device(session_factory, "inactive")
    device_id = device.id

    async with session_factory() as session:
        device_service = DeviceService(session)
        measurement_service = MeasurementService(session)

        await device_service.deactivate_device(device_id=device_id)

        with pytest.raises(DeviceInactiveError):
            await measurement_service.start_session(
                device_id=device_id,
                latitude=51.1694,
                longitude=71.4491,
            )

        await device_service.activate_device(device_id=device_id)
        started = await measurement_service.start_session(
            device_id=device_id,
            latitude=51.1694,
            longitude=71.4491,
        )
        started_id = started.id
        await device_service.deactivate_device(device_id=device_id)

        with pytest.raises(DeviceInactiveError):
            await measurement_service.record_measurement(
                device_id=device_id,
                source_message_id=f"inactive-{uuid4().hex}",
                measured_at=datetime.now(UTC),
                pm25=6.0,
            )

    async with session_factory() as session:
        persisted_session = await session.get(
            MeasurementSession,
            started_id,
        )
        measurement_count = await session.scalar(
            select(func.count())
            .select_from(RawMeasurement)
            .where(RawMeasurement.device_id == device_id)
        )

    assert persisted_session is not None
    assert persisted_session.status == "active"
    assert measurement_count == 0


async def test_invalid_measurement_insert_rolls_back_and_session_recovers(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device = await _create_device(session_factory, "rollback")
    device_id = device.id
    started = await _start_session(session_factory, device_id)
    started_id = started.id

    async with session_factory() as session:
        service = MeasurementService(session)

        with pytest.raises(IntegrityError):
            await service.record_measurement(
                device_id=device_id,
                source_message_id=f"invalid-{uuid4().hex}",
                measured_at=datetime.now(UTC),
                pm25=-1.0,
            )

        async with session_factory() as verification_session:
            failed_measurement_count = await verification_session.scalar(
                select(func.count())
                .select_from(RawMeasurement)
                .where(RawMeasurement.device_id == device_id)
            )
            unchanged_session = await verification_session.get(
                MeasurementSession,
                started_id,
            )
            unchanged_runtime = await verification_session.get(
                DeviceRuntimeState,
                device_id,
            )

        assert failed_measurement_count == 0
        assert unchanged_session is not None
        assert unchanged_session.sample_count == 0
        assert unchanged_runtime is not None
        assert unchanged_runtime.last_seen_at is None

        recovered = await service.record_measurement(
            device_id=device_id,
            source_message_id=f"recovered-{uuid4().hex}",
            measured_at=datetime.now(UTC),
            pm25=6.0,
        )

    async with session_factory() as session:
        measurements = (
            await session.scalars(
                select(RawMeasurement).where(
                    RawMeasurement.device_id == device_id
                )
            )
        ).all()
        persisted_session = await session.get(
            MeasurementSession,
            started_id,
        )
        runtime_state = await session.get(DeviceRuntimeState, device_id)

    assert [measurement.id for measurement in measurements] == [recovered.id]
    assert persisted_session is not None
    assert persisted_session.status == "active"
    assert persisted_session.sample_count == 1
    assert runtime_state is not None
    assert runtime_state.last_seen_at is not None


async def test_late_measurement_failure_rolls_back_every_side_effect(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device = await _create_device(session_factory, "late-rollback")
    device_id = device.id
    started = await _start_session(session_factory, device_id)
    started_id = started.id
    failed_source_message_id = f"late-failure-{uuid4().hex}"
    recovery_source_message_id = f"late-recovery-{uuid4().hex}"

    async with session_factory() as session:
        service = MeasurementService(session)
        create_measurement = service.measurement_repository.create
        increment_sample_count = (
            service.session_repository.increment_sample_count
        )
        get_runtime_for_update = (
            service.runtime_state_repository.get_for_update
        )
        raw_measurement_flushed = False
        counter_updated = False
        locked_runtime_state: DeviceRuntimeState | None = None
        failure_injected = False

        async def tracked_create_measurement(**values: object) -> RawMeasurement:
            nonlocal raw_measurement_flushed
            measurement = await create_measurement(**values)
            raw_measurement_flushed = True
            return measurement

        async def tracked_increment_sample_count(session_id: int) -> None:
            nonlocal counter_updated
            await increment_sample_count(session_id)
            counter_updated = True

        async def tracked_get_runtime_for_update(
            locked_device_id: int,
        ) -> DeviceRuntimeState | None:
            nonlocal locked_runtime_state
            locked_runtime_state = await get_runtime_for_update(
                locked_device_id
            )
            return locked_runtime_state

        def fail_before_commit(sync_session: object) -> None:
            del sync_session
            nonlocal failure_injected
            if failure_injected:
                return
            failure_injected = True
            assert raw_measurement_flushed is True
            assert counter_updated is True
            assert locked_runtime_state is not None
            assert locked_runtime_state.last_seen_at is not None
            raise RuntimeError("injected late measurement failure")

        monkeypatch.setattr(
            service.measurement_repository,
            "create",
            tracked_create_measurement,
        )
        monkeypatch.setattr(
            service.session_repository,
            "increment_sample_count",
            tracked_increment_sample_count,
        )
        monkeypatch.setattr(
            service.runtime_state_repository,
            "get_for_update",
            tracked_get_runtime_for_update,
        )
        event.listen(
            session.sync_session,
            "before_commit",
            fail_before_commit,
        )
        try:
            with pytest.raises(
                RuntimeError,
                match="injected late measurement failure",
            ):
                await service.record_measurement(
                    device_id=device_id,
                    source_message_id=failed_source_message_id,
                    measured_at=datetime.now(UTC),
                    pm25=5.0,
                )
        finally:
            event.remove(
                session.sync_session,
                "before_commit",
                fail_before_commit,
            )
            monkeypatch.setattr(
                service.measurement_repository,
                "create",
                create_measurement,
            )
            monkeypatch.setattr(
                service.session_repository,
                "increment_sample_count",
                increment_sample_count,
            )
            monkeypatch.setattr(
                service.runtime_state_repository,
                "get_for_update",
                get_runtime_for_update,
            )

        assert failure_injected is True

        async with session_factory() as verification_session:
            failed_measurement_count = await verification_session.scalar(
                select(func.count())
                .select_from(RawMeasurement)
                .where(
                    RawMeasurement.device_id == device_id,
                    RawMeasurement.source_message_id
                    == failed_source_message_id,
                )
            )
            unchanged_session = await verification_session.get(
                MeasurementSession,
                started_id,
            )
            unchanged_runtime = await verification_session.get(
                DeviceRuntimeState,
                device_id,
            )

        assert failed_measurement_count == 0
        assert unchanged_session is not None
        assert unchanged_session.sample_count == 0
        assert unchanged_runtime is not None
        assert unchanged_runtime.last_seen_at is None

        recovered = await service.record_measurement(
            device_id=device_id,
            source_message_id=recovery_source_message_id,
            measured_at=datetime.now(UTC),
            pm25=6.0,
        )
        recovered_id = recovered.id

    async with session_factory() as session:
        persisted_recovery = await session.get(RawMeasurement, recovered_id)
        persisted_session = await session.get(
            MeasurementSession,
            started_id,
        )
        runtime_state = await session.get(DeviceRuntimeState, device_id)

    assert persisted_recovery is not None
    assert persisted_recovery.source_message_id == recovery_source_message_id
    assert persisted_session is not None
    assert persisted_session.sample_count == 1
    assert runtime_state is not None
    assert runtime_state.last_seen_at is not None


async def test_concurrent_start_session_creates_exactly_one_active_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device = await _create_device(session_factory, "concurrent-start")
    device_id = device.id
    device_lock_barrier = asyncio.Barrier(2)

    async def attempt_start(
        latitude: float,
        longitude: float,
    ) -> MeasurementSession:
        async with session_factory() as session:
            service = MeasurementService(session)
            get_device_for_update = (
                service.device_repository.get_by_id_for_update
            )

            async def synchronized_get_device_for_update(
                locked_device_id: int,
            ) -> Device | None:
                await device_lock_barrier.wait()
                return await get_device_for_update(locked_device_id)

            service.device_repository.get_by_id_for_update = (
                synchronized_get_device_for_update
            )
            return await service.start_session(
                device_id=device_id,
                latitude=latitude,
                longitude=longitude,
            )

    results = await asyncio.wait_for(
        asyncio.gather(
            attempt_start(51.1694, 71.4491),
            attempt_start(43.2389, 76.8897),
            return_exceptions=True,
        ),
        timeout=20,
    )
    successes = [
        result for result in results if isinstance(result, MeasurementSession)
    ]
    expected_failures = [
        result
        for result in results
        if isinstance(result, ActiveSessionAlreadyExistsError)
    ]
    unexpected_failures = [
        result
        for result in results
        if isinstance(result, BaseException)
        and not isinstance(result, ActiveSessionAlreadyExistsError)
    ]

    async with session_factory() as session:
        sessions = (
            await session.scalars(
                select(MeasurementSession).where(
                    MeasurementSession.device_id == device_id
                )
            )
        ).all()
        runtime_state = await session.get(DeviceRuntimeState, device_id)

    assert unexpected_failures == []
    assert len(successes) == 1
    assert len(expected_failures) == 1
    assert len(sessions) == 1
    assert sessions[0].status == "active"
    assert sessions[0].id == successes[0].id
    assert runtime_state is not None
    assert runtime_state.measurement_enabled is True
    assert runtime_state.active_session_id == successes[0].id
