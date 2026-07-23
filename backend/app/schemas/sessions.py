"""Measurement-session request and response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas._base import (
    AwareDatetime,
    ORMResponseModel,
    RequestModel,
)


class SessionCreateRequest(RequestModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    started_at: AwareDatetime | None = None


class SessionTransitionRequest(RequestModel):
    ended_at: AwareDatetime | None = None


class SessionResponse(ORMResponseModel):
    id: int
    device_id: int
    status: Literal["active", "completed", "cancelled"]
    started_at: datetime
    ended_at: datetime | None
    latitude: float
    longitude: float
    sample_count: int
    created_at: datetime


__all__ = [
    "SessionCreateRequest",
    "SessionResponse",
    "SessionTransitionRequest",
]
