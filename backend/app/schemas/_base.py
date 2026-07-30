"""Shared Pydantic configuration and validators."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def require_timezone(value: datetime) -> datetime:
    """Reject timestamps whose UTC offset cannot be determined."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("a timezone-aware datetime is required")
    return value


AwareDatetime = Annotated[datetime, AfterValidator(require_timezone)]
POSTGRES_INTEGER_MAX = 2_147_483_647
PositivePostgresInteger = Annotated[
    int,
    Field(gt=0, le=POSTGRES_INTEGER_MAX),
]
NonNegativePostgresInteger = Annotated[
    int,
    Field(ge=0, le=POSTGRES_INTEGER_MAX),
]


class RequestModel(BaseModel):
    """Base for request bodies with a closed field contract."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ORMResponseModel(BaseModel):
    """Base for responses built from declared scalar ORM attributes."""

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "AwareDatetime",
    "NonNegativePostgresInteger",
    "ORMResponseModel",
    "POSTGRES_INTEGER_MAX",
    "PositivePostgresInteger",
    "RequestModel",
]
