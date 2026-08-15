"""Transactional application service for device lifecycle operations."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DeviceNotFoundError,
    DuplicateDeviceUIDError,
)
from app.db.models import Device
from app.repositories.device import (
    DeviceRepository,
    DeviceRuntimeStateRepository,
)
from app.services._support import violates_constraint


DEVICE_UID_CONSTRAINT = "uq_devices_device_uid"


class DeviceService:
    """Coordinate device persistence within service-owned transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.device_repository = DeviceRepository(session)
        self.runtime_state_repository = DeviceRuntimeStateRepository(session)

    async def create_device(
        self,
        *,
        device_uid: str,
        name: str | None = None,
        is_active: bool = True,
    ) -> Device:
        try:
            async with self._session.begin():
                existing_device = (
                    await self.device_repository.get_by_device_uid(device_uid)
                )
                if existing_device is not None:
                    raise DuplicateDeviceUIDError(device_uid)

                device = await self.device_repository.create(
                    device_uid=device_uid,
                    name=name,
                    is_active=is_active,
                )
                await self.runtime_state_repository.create(
                    device_id=device.id,
                )
                return device
        except IntegrityError as error:
            if violates_constraint(error, DEVICE_UID_CONSTRAINT):
                raise DuplicateDeviceUIDError(device_uid) from error
            raise

    async def activate_device(self, device_id: int) -> Device:
        return await self._set_device_active(
            device_id=device_id,
            is_active=True,
        )

    async def deactivate_device(self, device_id: int) -> Device:
        return await self._set_device_active(
            device_id=device_id,
            is_active=False,
        )

    async def _set_device_active(
        self,
        *,
        device_id: int,
        is_active: bool,
    ) -> Device:
        async with self._session.begin():
            device = await self.device_repository.get_by_id_for_update(
                device_id
            )
            if device is None:
                raise DeviceNotFoundError(device_id)
            device.is_active = is_active
            return device
