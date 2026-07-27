"""Raw-measurement ingestion endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.dependencies import get_measurement_service
from app.api.responses import error_responses
from app.schemas._base import POSTGRES_INTEGER_MAX
from app.schemas.measurements import (
    MeasurementCreateRequest,
    MeasurementResponse,
)
from app.services.measurement import MeasurementService


router = APIRouter(
    prefix="/devices/{device_id}/measurements",
    tags=["measurements"],
)
DeviceId = Annotated[
    int,
    Path(
        gt=0,
        le=POSTGRES_INTEGER_MAX,
        description="Positive device ID",
    ),
]


@router.post(
    "",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404, 409, 422, 500),
    operation_id="record_raw_measurement",
)
async def record_raw_measurement(
    device_id: DeviceId,
    request: MeasurementCreateRequest,
    service: Annotated[
        MeasurementService,
        Depends(get_measurement_service),
    ],
) -> MeasurementResponse:
    measurement = await service.record_measurement(
        device_id=device_id,
        **request.model_dump(),
    )
    return MeasurementResponse.model_validate(measurement)
