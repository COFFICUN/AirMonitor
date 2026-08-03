"""Measurement-session lifecycle endpoints."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status

from app.api.dependencies import (
    get_active_session_query_service,
    get_measurement_service,
    get_session_telemetry_query_service,
)
from app.api.query_validation import (
    resolve_session_read_request,
    strict_session_query_parameters,
)
from app.api.responses import error_responses
from app.schemas._base import POSTGRES_INTEGER_MAX
from app.schemas.sessions import (
    SessionCreateRequest,
    SessionResponse,
    SessionTransitionRequest,
)
from app.schemas.telemetry import SessionListResponse
from app.services.measurement import MeasurementService
from app.services.queries import ActiveSessionQueryService
from app.services.telemetry import SessionTelemetryQueryService
from app.services.telemetry_cursor import SessionReadRequest


router = APIRouter(
    prefix="/devices/{device_id}/sessions",
    tags=["measurement sessions"],
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
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404, 409, 422, 500),
    operation_id="start_measurement_session",
)
async def start_measurement_session(
    device_id: DeviceId,
    request: SessionCreateRequest,
    service: Annotated[
        MeasurementService,
        Depends(get_measurement_service),
    ],
) -> SessionResponse:
    measurement_session = await service.start_session(
        device_id=device_id,
        **request.model_dump(),
    )
    return SessionResponse.model_validate(measurement_session)


@router.get(
    "",
    response_model=SessionListResponse,
    status_code=status.HTTP_200_OK,
    responses=error_responses(404, 422),
    operation_id="list_device_sessions",
    dependencies=[Depends(strict_session_query_parameters)],
)
async def list_device_sessions(
    device_id: DeviceId,
    read_request: Annotated[
        SessionReadRequest,
        Depends(resolve_session_read_request),
    ],
    service: Annotated[
        SessionTelemetryQueryService,
        Depends(get_session_telemetry_query_service),
    ],
) -> SessionListResponse:
    page = await service.list_sessions(read_request=read_request)
    return SessionListResponse(
        items=list(page.items),
        next_cursor=page.next_cursor,
    )


@router.get(
    "/active",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    responses=error_responses(404, 422),
    operation_id="get_active_measurement_session",
)
async def get_active_measurement_session(
    device_id: DeviceId,
    query_service: Annotated[
        ActiveSessionQueryService,
        Depends(get_active_session_query_service),
    ],
) -> SessionResponse:
    measurement_session = await query_service.get_active_session(
        device_id=device_id
    )
    return SessionResponse.model_validate(measurement_session)


@router.post(
    "/active/complete",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    responses=error_responses(404, 409, 422, 500),
    operation_id="complete_active_measurement_session",
)
async def complete_active_measurement_session(
    device_id: DeviceId,
    service: Annotated[
        MeasurementService,
        Depends(get_measurement_service),
    ],
    request: SessionTransitionRequest = Body(
        default_factory=SessionTransitionRequest
    ),
) -> SessionResponse:
    measurement_session = await service.complete_session(
        device_id=device_id,
        **request.model_dump(),
    )
    return SessionResponse.model_validate(measurement_session)


@router.post(
    "/active/cancel",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    responses=error_responses(404, 409, 422, 500),
    operation_id="cancel_active_measurement_session",
)
async def cancel_active_measurement_session(
    device_id: DeviceId,
    service: Annotated[
        MeasurementService,
        Depends(get_measurement_service),
    ],
    request: SessionTransitionRequest = Body(
        default_factory=SessionTransitionRequest
    ),
) -> SessionResponse:
    measurement_session = await service.cancel_session(
        device_id=device_id,
        **request.model_dump(),
    )
    return SessionResponse.model_validate(measurement_session)
