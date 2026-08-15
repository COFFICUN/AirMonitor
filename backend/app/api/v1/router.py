"""Router composition for version 1 endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints.devices import router as devices_router
from app.api.v1.endpoints.measurements import router as measurements_router
from app.api.v1.endpoints.sessions import router as sessions_router


router = APIRouter()
router.include_router(devices_router)
router.include_router(sessions_router)
router.include_router(measurements_router)
