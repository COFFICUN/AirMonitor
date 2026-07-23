"""Persistence operations for measurement sessions."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MeasurementSession


class MeasurementSessionRepository:
    """Persist, retrieve, and atomically update measurement sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        session_id: int,
    ) -> MeasurementSession | None:
        statement = select(MeasurementSession).where(
            MeasurementSession.id == session_id
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id_for_update(
        self,
        session_id: int,
    ) -> MeasurementSession | None:
        statement = (
            select(MeasurementSession)
            .where(MeasurementSession.id == session_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_active_for_device(
        self,
        device_id: int,
    ) -> MeasurementSession | None:
        statement = select(MeasurementSession).where(
            MeasurementSession.device_id == device_id,
            MeasurementSession.status == "active",
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def create(
        self,
        device_id: int,
        latitude: float,
        longitude: float,
        started_at: datetime,
    ) -> MeasurementSession:
        measurement_session = MeasurementSession(
            device_id=device_id,
            status="active",
            started_at=started_at,
            ended_at=None,
            latitude=latitude,
            longitude=longitude,
            sample_count=0,
        )
        self._session.add(measurement_session)
        await self._session.flush()
        return measurement_session

    async def increment_sample_count(self, session_id: int) -> None:
        statement = (
            update(MeasurementSession)
            .where(MeasurementSession.id == session_id)
            .values(
                sample_count=MeasurementSession.sample_count + 1,
            )
        )
        await self._session.execute(statement)
