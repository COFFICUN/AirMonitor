"""Read-only telemetry page orchestration."""

from dataclasses import dataclass
from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DeviceNotFoundError
from app.db.models import MeasurementSession, RawMeasurement
from app.repositories.device import DeviceRepository
from app.repositories.measurement import RawMeasurementRepository
from app.repositories.measurement_session import (
    MeasurementSessionRepository,
)
from app.services.telemetry_cursor import (
    CursorPosition,
    MeasurementReadRequest,
    SessionReadRequest,
    encode_cursor,
)


PageItem = TypeVar("PageItem")


@dataclass(frozen=True)
class TelemetryPage(Generic[PageItem]):
    items: tuple[PageItem, ...]
    next_cursor: str | None


class SessionTelemetryQueryService:
    """List measurement sessions without controlling transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.device_repository = DeviceRepository(session)
        self.session_repository = MeasurementSessionRepository(session)

    async def list_sessions(
        self,
        *,
        read_request: SessionReadRequest,
    ) -> TelemetryPage[MeasurementSession]:
        filters = read_request.filters
        device = await self.device_repository.get_by_id(
            filters.device_id
        )
        if device is None:
            raise DeviceNotFoundError(filters.device_id)

        if (
            filters.started_from is not None
            and filters.started_from == filters.started_to
        ):
            return TelemetryPage(items=(), next_cursor=None)

        rows = await self.session_repository.list_for_device(
            device_id=filters.device_id,
            status=filters.status,
            started_from=filters.started_from,
            started_to=filters.started_to,
            position=read_request.position,
            limit=read_request.limit,
        )
        if len(rows) <= read_request.limit:
            return TelemetryPage(items=tuple(rows), next_cursor=None)

        items = tuple(rows[: read_request.limit])
        final_item = items[-1]
        next_cursor = encode_cursor(
            "sessions",
            CursorPosition(final_item.started_at, final_item.id),
            filters,
        )
        return TelemetryPage(items=items, next_cursor=next_cursor)


class MeasurementTelemetryQueryService:
    """List raw measurements without controlling transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.device_repository = DeviceRepository(session)
        self.measurement_repository = RawMeasurementRepository(session)

    async def list_measurements(
        self,
        *,
        read_request: MeasurementReadRequest,
    ) -> TelemetryPage[RawMeasurement]:
        filters = read_request.filters
        device = await self.device_repository.get_by_id(
            filters.device_id
        )
        if device is None:
            raise DeviceNotFoundError(filters.device_id)

        if (
            filters.measured_from is not None
            and filters.measured_from == filters.measured_to
        ):
            return TelemetryPage(items=(), next_cursor=None)

        rows = await self.measurement_repository.list_for_device(
            device_id=filters.device_id,
            session_id=filters.session_id,
            measured_from=filters.measured_from,
            measured_to=filters.measured_to,
            position=read_request.position,
            limit=read_request.limit,
        )
        if len(rows) <= read_request.limit:
            return TelemetryPage(items=tuple(rows), next_cursor=None)

        items = tuple(rows[: read_request.limit])
        final_item = items[-1]
        next_cursor = encode_cursor(
            "measurements",
            CursorPosition(final_item.measured_at, final_item.id),
            filters,
        )
        return TelemetryPage(items=items, next_cursor=next_cursor)


__all__ = [
    "MeasurementTelemetryQueryService",
    "SessionTelemetryQueryService",
    "TelemetryPage",
]
