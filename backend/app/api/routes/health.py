"""Health-check endpoint."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Stable service-health payload."""

    status: Literal["ok"]
    service: Literal["airmonitor-api"]
    version: Literal["2.0.0"]


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return the API health status."""
    return HealthResponse(
        status="ok",
        service="airmonitor-api",
        version="2.0.0",
    )
