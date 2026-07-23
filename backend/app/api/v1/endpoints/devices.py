"""Device identity and activation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.dependencies import (
    get_device_query_service,
    get_device_service,
)
from app.api.responses import error_responses
from app.schemas.devices import (
    DeviceCreateRequest,
    DeviceResponse,
    DeviceStatusRequest,
)
from app.services.device import DeviceService
from app.services.queries import DeviceQueryService


router = APIRouter(prefix="/devices", tags=["devices"])
DeviceId = Annotated[int, Path(gt=0, description="Positive device ID")]


@router.post(
    "",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409, 422),
    operation_id="create_device",
)
async def create_device(
    request: DeviceCreateRequest,
    service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceResponse:
    device = await service.create_device(**request.model_dump())
    return DeviceResponse.model_validate(device)


@router.get(
    "/{device_id}",
    response_model=DeviceResponse,
    status_code=status.HTTP_200_OK,
    responses=error_responses(404, 422),
    operation_id="get_device",
)
async def get_device(
    device_id: DeviceId,
    query_service: Annotated[
        DeviceQueryService,
        Depends(get_device_query_service),
    ],
) -> DeviceResponse:
    device = await query_service.get_device(device_id=device_id)
    return DeviceResponse.model_validate(device)


@router.patch(
    "/{device_id}/status",
    response_model=DeviceResponse,
    status_code=status.HTTP_200_OK,
    responses=error_responses(404, 422),
    operation_id="set_device_status",
)
async def set_device_status(
    device_id: DeviceId,
    request: DeviceStatusRequest,
    service: Annotated[DeviceService, Depends(get_device_service)],
) -> DeviceResponse:
    if request.is_active:
        device = await service.activate_device(device_id=device_id)
    else:
        device = await service.deactivate_device(device_id=device_id)
    return DeviceResponse.model_validate(device)
