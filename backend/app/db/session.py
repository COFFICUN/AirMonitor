"""Asynchronous database engine and session construction."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def create_database_engine(settings: Settings) -> AsyncEngine:
    """Create an engine without opening a database connection."""
    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=settings.database_pool_pre_ping,
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create the application's configured asynchronous session factory."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


def get_database_engine(settings: Settings) -> AsyncEngine:
    """Create the engine owned by one application instance."""
    return create_database_engine(settings)


def get_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create the session factory owned by one application instance."""
    return create_session_factory(engine)
