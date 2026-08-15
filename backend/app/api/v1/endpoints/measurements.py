"""Raw-measurement ingestion endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.dependencies import (
    get_measurement_service,
    get_measurement_telemetry_query_service,
)
from app.api.query_validation import (
    resolve_measurement_read_request,
    strict_measurement_query_parameters,
)
from app.api.responses import error_responses
from app.schemas._base import POSTGRES_INTEGER_MAX
from app.schemas.measurements import (
    MeasurementCreateRequest,
    MeasurementResponse,
)
from app.schemas.telemetry import MeasurementListResponse
from app.services.measurement import MeasurementService
from app.services.telemetry import MeasurementTelemetryQueryService
from app.services.telemetry_cursor import MeasurementReadRequest


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


@router.get(
    "",
    response_model=MeasurementListResponse,
    status_code=status.HTTP_200_OK,
    responses=error_responses(404, 422),
    operation_id="list_device_measurements",
    dependencies=[Depends(strict_measurement_query_parameters)],
)
async def list_device_measurements(
    device_id: DeviceId,
    read_request: Annotated[
        MeasurementReadRequest,
        Depends(resolve_measurement_read_request),
    ],
    service: Annotated[
        MeasurementTelemetryQueryService,
        Depends(get_measurement_telemetry_query_service),
    ],
) -> MeasurementListResponse:
    page = await service.list_measurements(read_request=read_request)
    return MeasurementListResponse(
        items=list(page.items),
        next_cursor=page.next_cursor,
    )
