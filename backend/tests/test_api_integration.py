"""Guarded PostgreSQL HTTP lifecycle tests for Sprint 7."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx2 import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from app.core.exceptions import (
    ActiveSessionNotFoundError,
    InvalidTimestampError,
)
from app.db.models import (
    Device,
    DeviceRuntimeState,
    MeasurementSession,
    RawMeasurement,
)
from app.services.measurement import MeasurementService
from tests.api_integration_runtime import (
    _preflight_disposable_database,
    _verify_application_tables_empty,
    anyio_backend,
    client,
    reset_application_tables,
    session_factory,
)


pytestmark = pytest.mark.anyio


async def _seed_device(
    session: AsyncSession,
    *,
    scenario: str,
) -> Device:
    device = Device(
        device_uid=f"api-read-{scenario}-{uuid4().hex}",
        is_active=True,
    )
    session.add(device)
    await session.flush()
    return device


async def _seed_measurement_session(
    session: AsyncSession,
    *,
    device_id: int,
    status_value: str,
    started_at: datetime,
) -> MeasurementSession:
    measurement_session = MeasurementSession(
        device_id=device_id,
        status=status_value,
        started_at=started_at,
        ended_at=(
            None
            if status_value == "active"
            else started_at + timedelta(minutes=30)
        ),
        latitude=51.1694,
        longitude=71.4491,
        sample_count=0,
    )
    session.add(measurement_session)
    await session.flush()
    return measurement_session


async def _seed_measurement(
    session: AsyncSession,
    *,
    device_id: int,
    session_id: int,
    measured_at: datetime,
) -> RawMeasurement:
    measurement = RawMeasurement(
        device_id=device_id,
        session_id=session_id,
        source_message_id=f"api-read-message-{uuid4().hex}",
        measured_at=measured_at,
        pm25=7.5,
    )
    session.add(measurement)
    await session.flush()
    return measurement


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


async def test_session_collection_postgresql_contract(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    base_time = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    async with session_factory() as database_session:
        async with database_session.begin():
            device = await _seed_device(
                database_session,
                scenario="sessions",
            )
            empty_device = await _seed_device(
                database_session,
                scenario="sessions-empty",
            )
            other_device = await _seed_device(
                database_session,
                scenario="sessions-other",
            )
            oldest = await _seed_measurement_session(
                database_session,
                device_id=device.id,
                status_value="completed",
                started_at=base_time,
            )
            middle = await _seed_measurement_session(
                database_session,
                device_id=device.id,
                status_value="completed",
                started_at=base_time + timedelta(hours=1),
            )
            tied_lower_id = await _seed_measurement_session(
                database_session,
                device_id=device.id,
                status_value="active",
                started_at=base_time + timedelta(hours=2),
            )
            tied_higher_id = await _seed_measurement_session(
                database_session,
                device_id=device.id,
                status_value="cancelled",
                started_at=base_time + timedelta(hours=2),
            )
            other_session = await _seed_measurement_session(
                database_session,
                device_id=other_device.id,
                status_value="completed",
                started_at=base_time + timedelta(hours=3),
            )

    unknown = await client.get(
        "/api/v1/devices/2147483647/sessions"
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "device_not_found"

    empty = await client.get(
        f"/api/v1/devices/{empty_device.id}/sessions"
    )
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "next_cursor": None}

    complete = await client.get(
        f"/api/v1/devices/{device.id}/sessions"
    )
    assert complete.status_code == 200
    complete_payload = complete.json()
    expected_ids = [
        tied_higher_id.id,
        tied_lower_id.id,
        middle.id,
        oldest.id,
    ]
    assert [item["id"] for item in complete_payload["items"]] == (
        expected_ids
    )
    assert complete_payload["next_cursor"] is None
    assert other_session.id not in expected_ids

    completed_only = await client.get(
        f"/api/v1/devices/{device.id}/sessions",
        params={"status": "completed"},
    )
    assert completed_only.status_code == 200
    assert [
        item["id"] for item in completed_only.json()["items"]
    ] == [middle.id, oldest.id]

    half_open = await client.get(
        f"/api/v1/devices/{device.id}/sessions",
        params={
            "started_from": (base_time + timedelta(hours=1)).isoformat(),
            "started_to": (base_time + timedelta(hours=2)).isoformat(),
        },
    )
    assert half_open.status_code == 200
    assert [item["id"] for item in half_open.json()["items"]] == [
        middle.id
    ]

    first_page = await client.get(
        f"/api/v1/devices/{device.id}/sessions",
        params={"limit": 2},
    )
    assert first_page.status_code == 200
    first_payload = first_page.json()
    first_ids = [item["id"] for item in first_payload["items"]]
    assert first_ids == expected_ids[:2]
    assert len(first_ids) <= 2
    assert isinstance(first_payload["next_cursor"], str)

    second_page = await client.get(
        f"/api/v1/devices/{device.id}/sessions",
        params={
            "limit": 2,
            "cursor": first_payload["next_cursor"],
        },
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    second_ids = [item["id"] for item in second_payload["items"]]
    assert second_ids == expected_ids[2:]
    assert second_payload["next_cursor"] is None
    assert set(first_ids).isdisjoint(second_ids)
    assert first_ids + second_ids == expected_ids

    rebound_cursor = await client.get(
        f"/api/v1/devices/{device.id}/sessions",
        params={
            "status": "completed",
            "cursor": first_payload["next_cursor"],
        },
    )
    assert rebound_cursor.status_code == 422
    assert (
        rebound_cursor.json()["error"]["code"]
        == "request_validation_error"
    )

    equal_bound = (base_time + timedelta(hours=1)).isoformat()
    equal_existing = await client.get(
        f"/api/v1/devices/{device.id}/sessions",
        params={"started_from": equal_bound, "started_to": equal_bound},
    )
    assert equal_existing.status_code == 200
    assert equal_existing.json() == {"items": [], "next_cursor": None}

    equal_unknown = await client.get(
        "/api/v1/devices/2147483647/sessions",
        params={"started_from": equal_bound, "started_to": equal_bound},
    )
    assert equal_unknown.status_code == 404

    active = await client.get(
        f"/api/v1/devices/{device.id}/sessions/active"
    )
    assert active.status_code == 200
    assert active.json()["id"] == tied_lower_id.id


async def test_measurement_collection_postgresql_contract(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    base_time = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)
    async with session_factory() as database_session:
        async with database_session.begin():
            device = await _seed_device(
                database_session,
                scenario="measurements",
            )
            empty_device = await _seed_device(
                database_session,
                scenario="measurements-empty",
            )
            other_device = await _seed_device(
                database_session,
                scenario="measurements-other",
            )
            first_session = await _seed_measurement_session(
                database_session,
                device_id=device.id,
                status_value="completed",
                started_at=base_time - timedelta(hours=1),
            )
            second_session = await _seed_measurement_session(
                database_session,
                device_id=device.id,
                status_value="completed",
                started_at=base_time - timedelta(hours=1),
            )
            other_session = await _seed_measurement_session(
                database_session,
                device_id=other_device.id,
                status_value="completed",
                started_at=base_time - timedelta(hours=1),
            )
            oldest = await _seed_measurement(
                database_session,
                device_id=device.id,
                session_id=first_session.id,
                measured_at=base_time,
            )
            middle = await _seed_measurement(
                database_session,
                device_id=device.id,
                session_id=first_session.id,
                measured_at=base_time + timedelta(hours=1),
            )
            tied_lower_id = await _seed_measurement(
                database_session,
                device_id=device.id,
                session_id=first_session.id,
                measured_at=base_time + timedelta(hours=2),
            )
            tied_higher_id = await _seed_measurement(
                database_session,
                device_id=device.id,
                session_id=second_session.id,
                measured_at=base_time + timedelta(hours=2),
            )
            other_measurement = await _seed_measurement(
                database_session,
                device_id=other_device.id,
                session_id=other_session.id,
                measured_at=base_time + timedelta(hours=3),
            )

    unknown = await client.get(
        "/api/v1/devices/2147483647/measurements"
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "device_not_found"

    empty = await client.get(
        f"/api/v1/devices/{empty_device.id}/measurements"
    )
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "next_cursor": None}

    complete = await client.get(
        f"/api/v1/devices/{device.id}/measurements"
    )
    assert complete.status_code == 200
    complete_payload = complete.json()
    expected_ids = [
        tied_higher_id.id,
        tied_lower_id.id,
        middle.id,
        oldest.id,
    ]
    assert [item["id"] for item in complete_payload["items"]] == (
        expected_ids
    )
    assert complete_payload["next_cursor"] is None
    assert other_measurement.id not in expected_ids

    session_filtered = await client.get(
        f"/api/v1/devices/{device.id}/measurements",
        params={"session_id": first_session.id},
    )
    assert session_filtered.status_code == 200
    assert [
        item["id"] for item in session_filtered.json()["items"]
    ] == [tied_lower_id.id, middle.id, oldest.id]

    half_open = await client.get(
        f"/api/v1/devices/{device.id}/measurements",
        params={
            "measured_from": (base_time + timedelta(hours=1)).isoformat(),
            "measured_to": (base_time + timedelta(hours=2)).isoformat(),
        },
    )
    assert half_open.status_code == 200
    assert [item["id"] for item in half_open.json()["items"]] == [
        middle.id
    ]

    first_page = await client.get(
        f"/api/v1/devices/{device.id}/measurements",
        params={"limit": 2},
    )
    assert first_page.status_code == 200
    first_payload = first_page.json()
    first_ids = [item["id"] for item in first_payload["items"]]
    assert first_ids == expected_ids[:2]
    assert len(first_ids) <= 2
    assert isinstance(first_payload["next_cursor"], str)

    second_page = await client.get(
        f"/api/v1/devices/{device.id}/measurements",
        params={
            "limit": 2,
            "cursor": first_payload["next_cursor"],
        },
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    second_ids = [item["id"] for item in second_payload["items"]]
    assert second_ids == expected_ids[2:]
    assert second_payload["next_cursor"] is None
    assert set(first_ids).isdisjoint(second_ids)
    assert first_ids + second_ids == expected_ids

    rebound_cursor = await client.get(
        f"/api/v1/devices/{device.id}/measurements",
        params={
            "session_id": first_session.id,
            "cursor": first_payload["next_cursor"],
        },
    )
    assert rebound_cursor.status_code == 422
    assert (
        rebound_cursor.json()["error"]["code"]
        == "request_validation_error"
    )

    other_device_filter = await client.get(
        f"/api/v1/devices/{device.id}/measurements",
        params={"session_id": other_session.id},
    )
    nonexistent_filter = await client.get(
        f"/api/v1/devices/{device.id}/measurements",
        params={"session_id": 2_147_483_647},
    )
    assert other_device_filter.status_code == 200
    assert nonexistent_filter.status_code == 200
    assert other_device_filter.json() == nonexistent_filter.json() == {
        "items": [],
        "next_cursor": None,
    }

    equal_bound = (base_time + timedelta(hours=1)).isoformat()
    equal_existing = await client.get(
        f"/api/v1/devices/{device.id}/measurements",
        params={"measured_from": equal_bound, "measured_to": equal_bound},
    )
    assert equal_existing.status_code == 200
    assert equal_existing.json() == {"items": [], "next_cursor": None}

    equal_unknown = await client.get(
        "/api/v1/devices/2147483647/measurements",
        params={"measured_from": equal_bound, "measured_to": equal_bound},
    )
    assert equal_unknown.status_code == 404


async def test_read_collections_preserve_write_and_active_routes(
    client: AsyncClient,
) -> None:
    created = await client.post(
        "/api/v1/devices",
        json={"device_uid": f"api-read-compat-{uuid4().hex}"},
    )
    assert created.status_code == 201
    device_id = created.json()["id"]

    started = await client.post(
        f"/api/v1/devices/{device_id}/sessions",
        json={"latitude": 51.1694, "longitude": 71.4491},
    )
    assert started.status_code == 201
    session_id = started.json()["id"]

    active = await client.get(
        f"/api/v1/devices/{device_id}/sessions/active"
    )
    assert active.status_code == 200
    assert active.json()["id"] == session_id

    recorded = await client.post(
        f"/api/v1/devices/{device_id}/measurements",
        json={
            "measured_at": started.json()["started_at"],
            "source_message_id": f"api-read-compat-{uuid4().hex}",
            "pm25": 9.5,
        },
    )
    assert recorded.status_code == 201

    listed_sessions = await client.get(
        f"/api/v1/devices/{device_id}/sessions"
    )
    listed_measurements = await client.get(
        f"/api/v1/devices/{device_id}/measurements"
    )
    assert listed_sessions.status_code == 200
    assert [
        item["id"] for item in listed_sessions.json()["items"]
    ] == [session_id]
    assert listed_measurements.status_code == 200
    assert [
        item["id"] for item in listed_measurements.json()["items"]
    ] == [recorded.json()["id"]]

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
