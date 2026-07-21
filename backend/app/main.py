"""Application entry point for the AirMonitor v2 API."""

from fastapi import FastAPI

from app.api.router import api_router


def create_application() -> FastAPI:
    """Build and configure the FastAPI application."""
    application = FastAPI(title="AirMonitor API", version="2.0.0")
    application.include_router(api_router)
    return application


app = create_application()
