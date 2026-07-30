"""Persistence operations for immutable raw measurements."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RawMeasurement

if TYPE_CHECKING:
    from app.services.telemetry_cursor import CursorPosition


class RawMeasurementRepository:
    """Persist raw measurements and resolve source-message idempotency."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_source_message_id(
        self,
        device_id: int,
        source_message_id: str,
    ) -> RawMeasurement | None:
        statement = select(RawMeasurement).where(
            RawMeasurement.device_id == device_id,
            RawMeasurement.source_message_id == source_message_id,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_latest_measured_at(
        self,
        *,
        session_id: int,
    ) -> datetime | None:
        statement = select(func.max(RawMeasurement.measured_at)).where(
            RawMeasurement.session_id == session_id
        )
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def list_for_device(
        self,
        *,
        device_id: int,
        session_id: int | None,
        measured_from: datetime | None,
        measured_to: datetime | None,
        position: CursorPosition | None,
        limit: int,
    ) -> list[RawMeasurement]:
        statement = select(RawMeasurement).where(
            RawMeasurement.device_id == device_id
        )
        if session_id is not None:
            statement = statement.where(
                RawMeasurement.session_id == session_id
            )
        if measured_from is not None:
            statement = statement.where(
                RawMeasurement.measured_at >= measured_from
            )
        if measured_to is not None:
            statement = statement.where(
                RawMeasurement.measured_at < measured_to
            )
        if position is not None:
            statement = statement.where(
                or_(
                    RawMeasurement.measured_at < position.timestamp,
                    and_(
                        RawMeasurement.measured_at == position.timestamp,
                        RawMeasurement.id < position.identifier,
                    ),
                )
            )
        statement = statement.order_by(
            RawMeasurement.measured_at.desc(),
            RawMeasurement.id.desc(),
        ).limit(limit + 1)
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def create(
        self,
        *,
        device_id: int,
        session_id: int,
        measured_at: datetime,
        source_message_id: str | None = None,
        temperature: float | None = None,
        humidity: float | None = None,
        pm1: float | None = None,
        pm25: float | None = None,
        pm10: float | None = None,
        pc0_3: int | None = None,
        pc0_5: int | None = None,
        pc1_0: int | None = None,
        pc2_5: int | None = None,
        pc5_0: int | None = None,
        pc10: int | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        is_valid: bool = True,
        validation_note: str | None = None,
    ) -> RawMeasurement:
        measurement = RawMeasurement(
            device_id=device_id,
            session_id=session_id,
            source_message_id=source_message_id,
            measured_at=measured_at,
            temperature=temperature,
            humidity=humidity,
            pm1=pm1,
            pm25=pm25,
            pm10=pm10,
            pc0_3=pc0_3,
            pc0_5=pc0_5,
            pc1_0=pc1_0,
            pc2_5=pc2_5,
            pc5_0=pc5_0,
            pc10=pc10,
            latitude=latitude,
            longitude=longitude,
            is_valid=is_valid,
            validation_note=validation_note,
        )
        self._session.add(measurement)
        await self._session.flush()
        return measurement
