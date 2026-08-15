"""Request-scoped service providers for API routes."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

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


RequestSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_device_service(session: RequestSession) -> DeviceService:
    return DeviceService(session)


def get_measurement_service(
    session: RequestSession,
) -> MeasurementService:
    return MeasurementService(session)


def get_device_query_service(
    session: RequestSession,
) -> DeviceQueryService:
    return DeviceQueryService(session)


def get_active_session_query_service(
    session: RequestSession,
) -> ActiveSessionQueryService:
    return ActiveSessionQueryService(session)


def get_session_telemetry_query_service(
    session: RequestSession,
) -> SessionTelemetryQueryService:
    return SessionTelemetryQueryService(session)


def get_measurement_telemetry_query_service(
    session: RequestSession,
) -> MeasurementTelemetryQueryService:
    return MeasurementTelemetryQueryService(session)


__all__ = [
    "get_active_session_query_service",
    "get_device_query_service",
    "get_device_service",
    "get_measurement_service",
    "get_measurement_telemetry_query_service",
    "get_session_telemetry_query_service",
]
