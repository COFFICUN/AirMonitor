"""Device request and response schemas."""

from datetime import datetime

from pydantic import Field

from app.schemas._base import ORMResponseModel, RequestModel


class DeviceCreateRequest(RequestModel):
    device_uid: str = Field(max_length=255)
    name: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class DeviceStatusRequest(RequestModel):
    is_active: bool


class DeviceResponse(ORMResponseModel):
    id: int
    device_uid: str
    name: str | None
    is_active: bool
    created_at: datetime


__all__ = [
    "DeviceCreateRequest",
    "DeviceResponse",
    "DeviceStatusRequest",
]
