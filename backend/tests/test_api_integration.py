"""Guarded PostgreSQL HTTP lifecycle tests for Sprint 7."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
import os
from uuid import uuid4

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tests.api_integration_guard import (
    ApiIntegrationTargetError,
    run_api_preflight_safely,
    validate_api_test_database_url,
)


_DATABASE_URL_TEXT = os.environ.get("AIRMONITOR_API_TEST_DATABASE_URL")
if _DATABASE_URL_TEXT is None:
    pytest.skip(
        "API integration tests require the dedicated disposable database URL",
        allow_module_level=True,
    )

try:
    _parsed_database_url: URL = validate_api_test_database_url(
        _DATABASE_URL_TEXT
    )
except ApiIntegrationTargetError as error:
    pytest.fail(str(error), pytrace=False)

del _DATABASE_URL_TEXT


from app.core.config import Settings
from app.core.exceptions import (
    ActiveSessionNotFoundError,
    InvalidTimestampError,
)
from app.db.base import Base
from app.db.dependencies import get_db_session
from app.db.models import (
    Device,
    DeviceRuntimeState,
    MeasurementSession,
    RawMeasurement,
)
from app.main import create_application
from app.services.measurement import MeasurementService
from tests.integration_database_reset import reset_application_tables


pytestmark = pytest.mark.anyio

EXPECTED_TABLES = {
    "alembic_version",
    "device_runtime_state",
    "devices",
    "measurement_sessions",
    "raw_measurements",
}
EXPECTED_ALEMBIC_HEAD = "a4f9c2e7d1b6"
RESET_FAILURE_MESSAGE = "API integration database reset failed."


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
                raise RuntimeError(
                    "API schema inventory is not approved"
                )

            alembic_heads = (
                await connection.execute(
                    text("SELECT version_num FROM alembic_version")
                )
            ).scalars().all()
            if alembic_heads != [EXPECTED_ALEMBIC_HEAD]:
                raise RuntimeError(
                    "API schema revision is not approved"
                )



async def _verify_application_tables_empty(
    engine: AsyncEngine,
) -> None:
    tables = tuple(Base.metadata.tables.values())
    if not tables:
        raise RuntimeError("application metadata has no tables")

    async with engine.connect() as connection:
        async with connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            row_counts = [
                await connection.scalar(
                    select(func.count()).select_from(table)
                )
                for table in tables
            ]
            if any(row_count != 0 for row_count in row_counts):
                raise RuntimeError(
                    "API application tables are not empty"
                )


@pytest.fixture(scope="session")
async def session_factory(
    anyio_backend: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
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
        await run_api_preflight_safely(
            lambda: _preflight_disposable_database(engine),
        )
        await reset_application_tables(
            engine,
            Base.metadata,
            RESET_FAILURE_MESSAGE,
        )
        await run_api_preflight_safely(
            lambda: _verify_application_tables_empty(engine)
        )

        # Exit the handler before cleanup so a reset failure cannot retain
        # the suite error as its exception context.
        suite_error: BaseException | None = None
        try:
            yield factory
        except BaseException as error:
            suite_error = error

        await reset_application_tables(
            engine,
            Base.metadata,
            RESET_FAILURE_MESSAGE,
        )
        if suite_error is not None:
            raise suite_error.with_traceback(
                suite_error.__traceback__
            ) from None
    finally:
        await engine.dispose()


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    application = create_application(Settings(_env_file=None))
    original_overrides = dict(application.dependency_overrides)

    async def integration_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_db_session] = integration_session
    transport = ASGITransport(
        app=application,
        raise_app_exceptions=False,
    )
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as integration_client:
            yield integration_client
    finally:
        application.dependency_overrides.clear()
        application.dependency_overrides.update(original_overrides)


async def test_complete_http_lifecycle_and_rollback_behavior(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device_uid = f"api-lifecycle-{uuid4().hex}"

    create_response = await client.post(
        "/api/v1/devices",
        json={"device_uid": device_uid, "name": "API integration"},
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["id"]

    duplicate_device = await client.post(
        "/api/v1/devices",
        json={"device_uid": device_uid},
    )
    assert duplicate_device.status_code == 409
    assert duplicate_device.json()["error"]["code"] == "duplicate_device_uid"

    get_response = await client.get(f"/api/v1/devices/{device_id}")
    assert get_response.status_code == 200
    assert get_response.json()["device_uid"] == device_uid

    deactivate_response = await client.patch(
        f"/api/v1/devices/{device_id}/status",
        json={"is_active": False},
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    inactive_session = await client.post(
        f"/api/v1/devices/{device_id}/sessions",
        json={"latitude": 51.1694, "longitude": 71.4491},
    )
    assert inactive_session.status_code == 409
    assert inactive_session.json()["error"]["code"] == "device_inactive"

    activate_response = await client.patch(
        f"/api/v1/devices/{device_id}/status",
        json={"is_active": True},
    )
    assert activate_response.status_code == 200

    invalid_coordinates = await client.post(
        f"/api/v1/devices/{device_id}/sessions",
        json={"latitude": 91.0, "longitude": 71.4491},
    )
    assert invalid_coordinates.status_code == 422

    session_response = await client.post(
        f"/api/v1/devices/{device_id}/sessions",
        json={"latitude": 51.1694, "longitude": 71.4491},
    )
    assert session_response.status_code == 201
    session_payload = session_response.json()
    session_id = session_payload["id"]
    measured_at = session_payload["started_at"]

    second_session = await client.post(
        f"/api/v1/devices/{device_id}/sessions",
        json={"latitude": 43.2389, "longitude": 76.8897},
    )
    assert second_session.status_code == 409
    assert (
        second_session.json()["error"]["code"]
        == "active_session_already_exists"
    )

    active_response = await client.get(
        f"/api/v1/devices/{device_id}/sessions/active"
    )
    assert active_response.status_code == 200
    assert active_response.json()["id"] == session_id

    source_message_id = f"message-{uuid4().hex}"
    measurement_response = await client.post(
        f"/api/v1/devices/{device_id}/measurements",
        json={
            "source_message_id": source_message_id,
            "measured_at": measured_at,
            "pm25": 7.5,
            "pc0_3": 100,
        },
    )
    assert measurement_response.status_code == 201
    measurement_id = measurement_response.json()["id"]

    duplicate_measurement = await client.post(
        f"/api/v1/devices/{device_id}/measurements",
        json={
            "source_message_id": source_message_id,
            "measured_at": datetime.now(UTC).isoformat(),
            "pm25": 8.5,
        },
    )
    assert duplicate_measurement.status_code == 409
    assert (
        duplicate_measurement.json()["error"]["code"]
        == "duplicate_source_message"
    )

    complete_response = await client.post(
        f"/api/v1/devices/{device_id}/sessions/active/complete",
        json={"ended_at": datetime.now(UTC).isoformat()},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"

    post_completion_measurement = await client.post(
        f"/api/v1/devices/{device_id}/measurements",
        json={"measured_at": datetime.now(UTC).isoformat(), "pm25": 9.5},
    )
    assert post_completion_measurement.status_code == 404
    assert (
        post_completion_measurement.json()["error"]["code"]
        == "active_session_not_found"
    )

    async with session_factory() as session:
        persisted_device = await session.get(Device, device_id)
        runtime_state = await session.get(DeviceRuntimeState, device_id)
        persisted_session = await session.get(
            MeasurementSession,
            session_id,
        )
        persisted_measurement = await session.get(
            RawMeasurement,
            measurement_id,
        )
        matching_device_count = await session.scalar(
            select(func.count())
            .select_from(Device)
            .where(Device.device_uid == device_uid)
        )
        matching_measurement_count = await session.scalar(
            select(func.count())
            .select_from(RawMeasurement)
            .where(
                RawMeasurement.device_id == device_id,
                RawMeasurement.source_message_id == source_message_id,
            )
        )

    assert persisted_device is not None
    assert persisted_device.is_active is True
    assert runtime_state is not None
    assert runtime_state.measurement_enabled is False
    assert runtime_state.active_session_id is None
    assert persisted_session is not None
    assert persisted_session.status == "completed"
    assert persisted_session.sample_count == 1
    assert persisted_measurement is not None
    assert persisted_measurement.pm25 == 7.5
    assert matching_device_count == 1
    assert matching_measurement_count == 1


async def test_cancel_session_clears_runtime_state(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device_uid = f"api-cancel-{uuid4().hex}"
    created = await client.post(
        "/api/v1/devices",
        json={"device_uid": device_uid},
    )
    assert created.status_code == 201
    device_id = created.json()["id"]

    started = await client.post(
        f"/api/v1/devices/{device_id}/sessions",
        json={"latitude": 51.1694, "longitude": 71.4491},
    )
    assert started.status_code == 201
    session_id = started.json()["id"]

    cancelled = await client.post(
        f"/api/v1/devices/{device_id}/sessions/active/cancel",
        json={"ended_at": datetime.now(UTC).isoformat()},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    missing_active = await client.get(
        f"/api/v1/devices/{device_id}/sessions/active"
    )
    assert missing_active.status_code == 404

    async with session_factory() as session:
        runtime_state = await session.get(DeviceRuntimeState, device_id)
        persisted_session = await session.get(
            MeasurementSession,
            session_id,
        )

    assert runtime_state is not None
    assert runtime_state.measurement_enabled is False
    assert runtime_state.active_session_id is None
    assert persisted_session is not None
    assert persisted_session.status == "cancelled"

# Live PostgreSQL concurrency verification


async def _create_active_session_for_concurrency(
    client: AsyncClient,
    *,
    scenario: str,
) -> tuple[int, int, datetime]:
    created = await client.post(
        "/api/v1/devices",
        json={
            "device_uid": (
                f"api-concurrency-{scenario}-{uuid4().hex}"
            ),
        },
    )
    assert created.status_code == 201
    device_id = created.json()["id"]

    started = await client.post(
        f"/api/v1/devices/{device_id}/sessions",
        json={
            "latitude": 51.1694,
            "longitude": 71.4491,
        },
    )
    assert started.status_code == 201

    session_payload = started.json()
    started_at = datetime.fromisoformat(
        session_payload["started_at"].replace("Z", "+00:00")
    )

    return (
        device_id,
        session_payload["id"],
        started_at,
    )


async def _run_with_first_device_lock(
    *,
    first_service: MeasurementService,
    first_operation,
    second_service: MeasurementService,
    second_operation,
) -> tuple[object, object]:
    first_has_device_lock = asyncio.Event()
    release_first_operation = asyncio.Event()
    second_attempted_device_lock = asyncio.Event()

    original_first_lock = (
        first_service.device_repository.get_by_id_for_update
    )
    original_second_lock = (
        second_service.device_repository.get_by_id_for_update
    )

    async def first_lock(device_id: int):
        device = await original_first_lock(device_id)
        first_has_device_lock.set()
        await release_first_operation.wait()
        return device

    async def second_lock(device_id: int):
        second_attempted_device_lock.set()
        return await original_second_lock(device_id)

    first_service.device_repository.get_by_id_for_update = (
        first_lock
    )
    second_service.device_repository.get_by_id_for_update = (
        second_lock
    )

    first_task = asyncio.create_task(first_operation())
    second_task = None

    try:
        await asyncio.wait_for(
            first_has_device_lock.wait(),
            timeout=5,
        )

        second_task = asyncio.create_task(second_operation())

        await asyncio.wait_for(
            second_attempted_device_lock.wait(),
            timeout=5,
        )

        # The second transaction has reached the common first row lock.
        # It must remain blocked while the first transaction owns it.
        await asyncio.sleep(0.1)
        assert second_task.done() is False

        release_first_operation.set()

        return tuple(
            await asyncio.wait_for(
                asyncio.gather(
                    first_task,
                    second_task,
                    return_exceptions=True,
                ),
                timeout=10,
            )
        )
    finally:
        release_first_operation.set()

        tasks = [first_task]
        if second_task is not None:
            tasks.append(second_task)

        for task in tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )


@pytest.mark.parametrize(
    ("terminal_method", "terminal_status"),
    [
        ("complete_session", "completed"),
        ("cancel_session", "cancelled"),
    ],
)
async def test_terminal_transition_serializes_before_waiting_record(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    terminal_method: str,
    terminal_status: str,
) -> None:
    device_id, session_id, started_at = (
        await _create_active_session_for_concurrency(
            client,
            scenario=f"{terminal_status}-first",
        )
    )

    ended_at = started_at + timedelta(seconds=2)
    measured_at = started_at + timedelta(seconds=1)

    async with (
        session_factory() as terminal_db_session,
        session_factory() as record_db_session,
    ):
        terminal_service = MeasurementService(
            terminal_db_session
        )
        record_service = MeasurementService(record_db_session)

        terminal_result, record_result = (
            await _run_with_first_device_lock(
                first_service=terminal_service,
                first_operation=lambda: getattr(
                    terminal_service,
                    terminal_method,
                )(
                    device_id=device_id,
                    ended_at=ended_at,
                ),
                second_service=record_service,
                second_operation=lambda: (
                    record_service.record_measurement(
                        device_id=device_id,
                        measured_at=measured_at,
                        source_message_id=(
                            f"terminal-first-{uuid4().hex}"
                        ),
                        pm25=12.5,
                    )
                ),
            )
        )

    assert isinstance(terminal_result, MeasurementSession)
    assert terminal_result.status == terminal_status
    assert isinstance(
        record_result,
        ActiveSessionNotFoundError,
    )

    async with session_factory() as verification_session:
        runtime_state = await verification_session.get(
            DeviceRuntimeState,
            device_id,
        )
        persisted_session = await verification_session.get(
            MeasurementSession,
            session_id,
        )
        measurement_count = await verification_session.scalar(
            select(func.count())
            .select_from(RawMeasurement)
            .where(RawMeasurement.session_id == session_id)
        )

    assert runtime_state is not None
    assert runtime_state.measurement_enabled is False
    assert runtime_state.active_session_id is None

    assert persisted_session is not None
    assert persisted_session.status == terminal_status
    assert persisted_session.sample_count == 0
    assert measurement_count == 0


@pytest.mark.parametrize(
    ("terminal_method", "terminal_status"),
    [
        ("complete_session", "completed"),
        ("cancel_session", "cancelled"),
    ],
)
async def test_record_serializes_before_waiting_terminal_transition(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    terminal_method: str,
    terminal_status: str,
) -> None:
    device_id, session_id, started_at = (
        await _create_active_session_for_concurrency(
            client,
            scenario=f"record-before-{terminal_status}",
        )
    )

    measured_at = started_at + timedelta(seconds=2)
    contradictory_end = started_at + timedelta(seconds=1)

    async with (
        session_factory() as record_db_session,
        session_factory() as terminal_db_session,
    ):
        record_service = MeasurementService(record_db_session)
        terminal_service = MeasurementService(
            terminal_db_session
        )

        record_result, terminal_result = (
            await _run_with_first_device_lock(
                first_service=record_service,
                first_operation=lambda: (
                    record_service.record_measurement(
                        device_id=device_id,
                        measured_at=measured_at,
                        source_message_id=(
                            f"record-first-{uuid4().hex}"
                        ),
                        pm25=15.0,
                    )
                ),
                second_service=terminal_service,
                second_operation=lambda: getattr(
                    terminal_service,
                    terminal_method,
                )(
                    device_id=device_id,
                    ended_at=contradictory_end,
                ),
            )
        )

    assert isinstance(record_result, RawMeasurement)
    assert isinstance(terminal_result, InvalidTimestampError)

    async with session_factory() as verification_session:
        runtime_state = await verification_session.get(
            DeviceRuntimeState,
            device_id,
        )
        persisted_session = await verification_session.get(
            MeasurementSession,
            session_id,
        )
        measurement_count = await verification_session.scalar(
            select(func.count())
            .select_from(RawMeasurement)
            .where(RawMeasurement.session_id == session_id)
        )

    assert runtime_state is not None
    assert runtime_state.measurement_enabled is True
    assert runtime_state.active_session_id == session_id

    assert persisted_session is not None
    assert persisted_session.status == "active"
    assert persisted_session.ended_at is None
    assert persisted_session.sample_count == 1
    assert measurement_count == 1
