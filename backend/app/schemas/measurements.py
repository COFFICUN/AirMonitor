"""Raw-measurement request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.schemas._base import (
    AwareDatetime,
    NonNegativePostgresInteger,
    ORMResponseModel,
    PositivePostgresInteger,
    RequestModel,
)


class MeasurementCreateRequest(RequestModel):
    measured_at: AwareDatetime
    session_id: PositivePostgresInteger | None = None
    source_message_id: str | None = Field(
        default=None,
        max_length=255,
    )
    temperature: float | None = Field(default=None, ge=-40, le=85)
    humidity: float | None = Field(default=None, ge=0, le=100)
    pm1: float | None = Field(default=None, ge=0)
    pm25: float | None = Field(default=None, ge=0)
    pm10: float | None = Field(default=None, ge=0)
    pc0_3: NonNegativePostgresInteger | None = None
    pc0_5: NonNegativePostgresInteger | None = None
    pc1_0: NonNegativePostgresInteger | None = None
    pc2_5: NonNegativePostgresInteger | None = None
    pc5_0: NonNegativePostgresInteger | None = None
    pc10: NonNegativePostgresInteger | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_valid: bool = True
    validation_note: str | None = None

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> MeasurementCreateRequest:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(
                "latitude and longitude must be supplied together"
            )
        return self


class MeasurementResponse(ORMResponseModel):
    id: int
    device_id: int
    session_id: int
    source_message_id: str | None
    measured_at: datetime
    received_at: datetime
    temperature: float | None
    humidity: float | None
    pm1: float | None
    pm25: float | None
    pm10: float | None
    pc0_3: int | None
    pc0_5: int | None
    pc1_0: int | None
    pc2_5: int | None
    pc5_0: int | None
    pc10: int | None
    latitude: float | None
    longitude: float | None
    is_valid: bool
    validation_note: str | None
    created_at: datetime


__all__ = ["MeasurementCreateRequest", "MeasurementResponse"]
