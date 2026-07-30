"""Strict typed query contracts for future telemetry read routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas._base import (
    AwareDatetime,
    PositivePostgresInteger,
    RequestModel,
)


class SessionListQuery(RequestModel):
    status: Literal["active", "completed", "cancelled"] | None = None
    started_from: AwareDatetime | None = None
    started_to: AwareDatetime | None = None
    limit: int = Field(default=100, ge=1, le=500)
    cursor: str | None = Field(default=None, max_length=2_048)

    @model_validator(mode="after")
    def normalize_and_validate_range(self) -> SessionListQuery:
        self.started_from = _as_optional_utc(self.started_from)
        self.started_to = _as_optional_utc(self.started_to)
        _require_ordered_range(self.started_from, self.started_to)
        return self


class MeasurementListQuery(RequestModel):
    session_id: PositivePostgresInteger | None = None
    measured_from: AwareDatetime | None = None
    measured_to: AwareDatetime | None = None
    limit: int = Field(default=100, ge=1, le=500)
    cursor: str | None = Field(default=None, max_length=2_048)

    @model_validator(mode="after")
    def normalize_and_validate_range(self) -> MeasurementListQuery:
        self.measured_from = _as_optional_utc(self.measured_from)
        self.measured_to = _as_optional_utc(self.measured_to)
        _require_ordered_range(self.measured_from, self.measured_to)
        return self


def _as_optional_utc(value: datetime | None) -> datetime | None:
    return None if value is None else value.astimezone(UTC)


def _require_ordered_range(
    lower: datetime | None,
    upper: datetime | None,
) -> None:
    if lower is not None and upper is not None and lower > upper:
        raise ValueError("the lower time bound must not exceed the upper")


__all__ = ["MeasurementListQuery", "SessionListQuery"]
