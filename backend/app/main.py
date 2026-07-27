"""Application entry point for the AirMonitor v2 API."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import install_exception_handlers
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.db import session as database_session


def create_application(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    application_settings = settings if settings is not None else get_settings()
    database_engine = database_session.get_database_engine(
        application_settings
    )
    session_factory = database_session.get_session_factory(database_engine)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await application.state.database_engine.dispose()

    application = FastAPI(
        title=application_settings.app_name,
        version=application_settings.app_version,
        debug=application_settings.debug,
        lifespan=lifespan,
    )
    application.state.settings = application_settings
    application.state.database_engine = database_engine
    application.state.session_factory = session_factory
    install_exception_handlers(application)

    def resolve_application_settings() -> Settings:
        return application_settings

    application.dependency_overrides[get_settings] = resolve_application_settings
    application.include_router(api_router)
    return application


app = create_application()
