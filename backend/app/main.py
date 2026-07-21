"""Application entry point for the AirMonitor v2 API."""

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings, get_settings


def create_application(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    application_settings = settings if settings is not None else get_settings()
    application = FastAPI(
        title=application_settings.app_name,
        version=application_settings.app_version,
        debug=application_settings.debug,
    )
    application.state.settings = application_settings

    def resolve_application_settings() -> Settings:
        return application_settings

    application.dependency_overrides[get_settings] = resolve_application_settings
    application.include_router(api_router)
    return application


app = create_application()
