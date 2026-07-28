"""Guarded PostgreSQL HTTP lifecycle tests for Sprint 7."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
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
from app.db.base import Base
from app.db.dependencies import get_db_session
from app.db.models import (
    Device,
    DeviceRuntimeState,
    MeasurementSession,
    RawMeasurement,
)
from app.main import create_application
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
    measured_at = datetime.now(UTC).isoformat()

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
    session_id = session_response.json()["id"]

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
