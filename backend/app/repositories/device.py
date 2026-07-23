"""Persistence operations for devices and their mutable runtime state."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, DeviceRuntimeState


class DeviceRepository:
    """Persist and retrieve device identity records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, device_id: int) -> Device | None:
        statement = select(Device).where(Device.id == device_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, device_id: int) -> Device | None:
        statement = (
            select(Device)
            .where(Device.id == device_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_device_uid(self, device_uid: str) -> Device | None:
        statement = select(Device).where(Device.device_uid == device_uid)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def create(
        self,
        device_uid: str,
        name: str | None = None,
        is_active: bool = True,
    ) -> Device:
        device = Device(
            device_uid=device_uid,
            name=name,
            is_active=is_active,
        )
        self._session.add(device)
        await self._session.flush()
        return device


class DeviceRuntimeStateRepository:
    """Persist and lock the single mutable state row for a device."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, device_id: int) -> DeviceRuntimeState:
        runtime_state = DeviceRuntimeState(device_id=device_id)
        self._session.add(runtime_state)
        await self._session.flush()
        return runtime_state

    async def get_for_update(
        self,
        device_id: int,
    ) -> DeviceRuntimeState | None:
        statement = (
            select(DeviceRuntimeState)
            .where(DeviceRuntimeState.device_id == device_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()
