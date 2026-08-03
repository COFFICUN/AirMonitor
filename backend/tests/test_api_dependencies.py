"""Dependency-provider contracts for request-scoped services."""

from collections.abc import AsyncIterator
from unittest.mock import Mock

import pytest
from fastapi import Depends, FastAPI
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import dependencies as api_dependencies
from app.api.dependencies import (
    get_active_session_query_service,
    get_device_query_service,
    get_device_service,
    get_measurement_service,
)
from app.db.dependencies import get_db_session
from app.services.device import DeviceService
from app.services.measurement import MeasurementService
from app.services.queries import (
    ActiveSessionQueryService,
    DeviceQueryService,
)
from app.services.telemetry import (
    MeasurementTelemetryQueryService,
    SessionTelemetryQueryService,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_service_dependencies_share_the_supplied_request_session() -> None:
    session = Mock(spec=AsyncSession)

    device_service = get_device_service(session)
    measurement_service = get_measurement_service(session)
    device_query = get_device_query_service(session)
    active_session_query = get_active_session_query_service(session)

    assert isinstance(device_service, DeviceService)
    assert isinstance(measurement_service, MeasurementService)
    assert isinstance(device_query, DeviceQueryService)
    assert isinstance(active_session_query, ActiveSessionQueryService)
    assert device_service._session is session
    assert measurement_service._session is session
    assert device_query._session is session
    assert active_session_query._session is session
    session.begin.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.anyio
async def test_fastapi_reuses_one_session_for_all_request_services() -> None:
    application = FastAPI()
    session = Mock(spec=AsyncSession)
    dependency_entries = 0

    async def request_session() -> AsyncIterator[AsyncSession]:
        nonlocal dependency_entries
        dependency_entries += 1
        yield session

    @application.get("/dependency-probe")
    async def dependency_probe(
        device_service: DeviceService = Depends(get_device_service),
        measurement_service: MeasurementService = Depends(
            get_measurement_service
        ),
        device_query: DeviceQueryService = Depends(
            get_device_query_service
        ),
        active_query: ActiveSessionQueryService = Depends(
            get_active_session_query_service
        ),
    ) -> dict[str, bool]:
        return {
            "same_session": all(
                service._session is session
                for service in (
                    device_service,
                    measurement_service,
                    device_query,
                    active_query,
                )
            )
        }

    application.dependency_overrides[get_db_session] = request_session
    transport = ASGITransport(app=application)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get("/dependency-probe")
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"same_session": True}
    assert dependency_entries == 1


def test_telemetry_read_service_dependencies_share_supplied_session() -> None:
    session_provider = (
        api_dependencies.get_session_telemetry_query_service
    )
    measurement_provider = (
        api_dependencies.get_measurement_telemetry_query_service
    )
    session = Mock(spec=AsyncSession)

    session_query = session_provider(session)
    measurement_query = measurement_provider(session)

    assert isinstance(session_query, SessionTelemetryQueryService)
    assert isinstance(measurement_query, MeasurementTelemetryQueryService)
    assert session_query._session is session
    assert measurement_query._session is session
    for method_name in (
        "begin",
        "begin_nested",
        "commit",
        "execute",
        "flush",
        "rollback",
    ):
        getattr(session, method_name).assert_not_called()


@pytest.mark.anyio
async def test_telemetry_read_fastapi_reuses_one_request_session() -> None:
    session_provider = (
        api_dependencies.get_session_telemetry_query_service
    )
    measurement_provider = (
        api_dependencies.get_measurement_telemetry_query_service
    )
    application = FastAPI()
    session = Mock(spec=AsyncSession)
    dependency_entries = 0

    async def request_session() -> AsyncIterator[AsyncSession]:
        nonlocal dependency_entries
        dependency_entries += 1
        yield session

    @application.get("/telemetry-dependency-probe")
    async def dependency_probe(
        session_query: SessionTelemetryQueryService = Depends(
            session_provider
        ),
        measurement_query: MeasurementTelemetryQueryService = Depends(
            measurement_provider
        ),
    ) -> dict[str, bool]:
        return {
            "same_session": (
                session_query._session is session
                and measurement_query._session is session
            )
        }

    application.dependency_overrides[get_db_session] = request_session
    transport = ASGITransport(app=application)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get("/telemetry-dependency-probe")
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"same_session": True}
    assert dependency_entries == 1
