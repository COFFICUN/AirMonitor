"""FastAPI dependencies for database sessions."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def get_session_factory(
    request: Request,
) -> async_sessionmaker[AsyncSession]:
    """Resolve the session factory owned by the request application."""
    return request.app.state.session_factory


async def get_db_session(
    session_factory: Annotated[
        async_sessionmaker[AsyncSession],
        Depends(get_session_factory),
    ],
) -> AsyncIterator[AsyncSession]:
    """Yield one session and close it after the request finishes."""
    async with session_factory() as session:
        yield session
