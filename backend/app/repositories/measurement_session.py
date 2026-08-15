"""Persistence operations for measurement sessions."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MeasurementSession

if TYPE_CHECKING:
    from app.services.telemetry_cursor import CursorPosition


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

    async def list_for_device(
        self,
        *,
        device_id: int,
        status: str | None,
        started_from: datetime | None,
        started_to: datetime | None,
        position: CursorPosition | None,
        limit: int,
    ) -> list[MeasurementSession]:
        statement = select(MeasurementSession).where(
            MeasurementSession.device_id == device_id
        )
        if status is not None:
            statement = statement.where(
                MeasurementSession.status == status
            )
        if started_from is not None:
            statement = statement.where(
                MeasurementSession.started_at >= started_from
            )
        if started_to is not None:
            statement = statement.where(
                MeasurementSession.started_at < started_to
            )
        if position is not None:
            statement = statement.where(
                or_(
                    MeasurementSession.started_at < position.timestamp,
                    and_(
                        MeasurementSession.started_at
                        == position.timestamp,
                        MeasurementSession.id < position.identifier,
                    ),
                )
            )
        statement = statement.order_by(
            MeasurementSession.started_at.desc(),
            MeasurementSession.id.desc(),
        ).limit(limit + 1)
        result = await self._session.execute(statement)
        return result.scalars().all()

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
