"""Read-only application services for API retrieval operations."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ActiveSessionNotFoundError,
    DeviceNotFoundError,
)
from app.db.models import Device, MeasurementSession
from app.repositories.device import DeviceRepository
from app.repositories.measurement_session import MeasurementSessionRepository


class DeviceQueryService:
    """Retrieve devices without opening or controlling transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.device_repository = DeviceRepository(session)

    async def get_device(self, *, device_id: int) -> Device:
        device = await self.device_repository.get_by_id(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id)
        return device


class ActiveSessionQueryService:
    """Retrieve active sessions through an unlocked repository read."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.session_repository = MeasurementSessionRepository(session)

    async def get_active_session(
        self,
        *,
        device_id: int,
    ) -> MeasurementSession:
        measurement_session = (
            await self.session_repository.get_active_for_device(device_id)
        )
        if measurement_session is None:
            raise ActiveSessionNotFoundError(device_id)
        return measurement_session


__all__ = ["ActiveSessionQueryService", "DeviceQueryService"]
