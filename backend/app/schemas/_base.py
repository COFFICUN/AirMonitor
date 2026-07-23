"""Shared Pydantic configuration and validators."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


def require_timezone(value: datetime) -> datetime:
    """Reject timestamps whose UTC offset cannot be determined."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("a timezone-aware datetime is required")
    return value


AwareDatetime = Annotated[datetime, AfterValidator(require_timezone)]


class RequestModel(BaseModel):
    """Base for request bodies with a closed field contract."""

    model_config = ConfigDict(extra="forbid")


class ORMResponseModel(BaseModel):
    """Base for responses built from declared scalar ORM attributes."""

    model_config = ConfigDict(from_attributes=True)


__all__ = ["AwareDatetime", "ORMResponseModel", "RequestModel"]
