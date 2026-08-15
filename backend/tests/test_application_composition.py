"""Connection-free application composition and lifespan regressions."""

from contextlib import ExitStack
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.dependencies import get_db_session, get_session_factory
from app.db.session import create_database_engine, create_session_factory
from app.main import app as module_app
from app.main import create_application


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_create_application_uses_exact_settings_for_engine_and_session_factory() -> (
    None
):
    settings = Settings(
        database_url=(
            "postgresql+asyncpg://phase_c1@localhost/phase_c1_exact"
        ),
        database_echo=True,
        database_pool_pre_ping=False,
        _env_file=None,
    )

    with (
        patch(
            "app.db.session.create_database_engine",
            wraps=create_database_engine,
        ) as engine_creator,
        patch(
            "app.db.session.create_session_factory",
            wraps=create_session_factory,
        ) as session_factory_creator,
    ):
        application = create_application(settings)

    assert application.state.settings is settings
    engine_creator.assert_called_once_with(settings)
    session_factory_creator.assert_called_once_with(
        application.state.database_engine
    )
    assert (
        application.state.session_factory.kw["bind"]
        is application.state.database_engine
    )

    async with application.router.lifespan_context(application):
        pass


@pytest.mark.anyio
async def test_applications_with_distinct_database_urls_do_not_share_database_state() -> (
    None
):
    first_settings = Settings(
        database_url=(
            "postgresql+asyncpg://phase_c1@localhost/phase_c1_first"
        ),
        _env_file=None,
    )
    second_settings = Settings(
        database_url=(
            "postgresql+asyncpg://phase_c1@localhost/phase_c1_second"
        ),
        _env_file=None,
    )

    first_application = create_application(first_settings)
    second_application = create_application(second_settings)

    assert first_application.state.settings is first_settings
    assert second_application.state.settings is second_settings
    assert (
        first_application.state.database_engine
        is not second_application.state.database_engine
    )
    assert (
        first_application.state.database_engine.pool
        is not second_application.state.database_engine.pool
    )
    assert (
        first_application.state.session_factory
        is not second_application.state.session_factory
    )
    assert (
        first_application.state.session_factory.kw["bind"]
        is first_application.state.database_engine
    )
    assert (
        second_application.state.session_factory.kw["bind"]
        is second_application.state.database_engine
    )
    assert first_application.state.database_engine.url.database == (
        "phase_c1_first"
    )
    assert second_application.state.database_engine.url.database == (
        "phase_c1_second"
    )

    async with first_application.router.lifespan_context(first_application):
        async with second_application.router.lifespan_context(
            second_application
        ):
            pass


@pytest.mark.anyio
async def test_request_session_factory_comes_from_request_application_without_global_settings() -> (
    None
):
    application = create_application(
        Settings(
            database_url=(
                "postgresql+asyncpg://phase_c1@localhost/phase_c1_request"
            ),
            _env_file=None,
        )
    )

    @application.get("/session-factory-probe")
    async def session_factory_probe(
        session_factory: Annotated[
            async_sessionmaker[AsyncSession],
            Depends(get_session_factory),
        ],
    ) -> dict[str, bool]:
        return {
            "uses_application_factory": (
                session_factory is application.state.session_factory
            )
        }

    transport = ASGITransport(app=application)
    with (
        patch(
            "app.core.config.get_settings",
            side_effect=AssertionError("global settings were consulted"),
        ),
        patch(
            "app.db.session.get_settings",
            side_effect=AssertionError("global settings were consulted"),
            create=True,
        ),
    ):
        async with application.router.lifespan_context(application):
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                response = await client.get("/session-factory-probe")

    assert response.status_code == 200
    assert response.json() == {"uses_application_factory": True}


@pytest.mark.anyio
async def test_request_reuses_one_session_from_application_factory() -> None:
    application = create_application(
        Settings(
            database_url=(
                "postgresql+asyncpg://phase_c1@localhost/phase_c1_session"
            ),
            _env_file=None,
        )
    )

    @application.get("/request-session-probe")
    async def request_session_probe(
        first_session: Annotated[AsyncSession, Depends(get_db_session)],
        second_session: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> dict[str, bool]:
        return {
            "same_session": first_session is second_session,
            "uses_application_engine": (
                first_session.bind is application.state.database_engine
            ),
        }

    transport = ASGITransport(app=application)
    with patch("asyncpg.connect") as connect:
        async with application.router.lifespan_context(application):
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                response = await client.get("/request-session-probe")

    assert response.status_code == 200
    assert response.json() == {
        "same_session": True,
        "uses_application_engine": True,
    }
    connect.assert_not_called()


@pytest.mark.anyio
async def test_factory_openapi_and_lifespan_do_not_connect() -> None:
    connection_targets = (
        "asyncpg.connect",
        "sqlalchemy.engine.Engine.connect",
        "sqlalchemy.ext.asyncio.AsyncEngine.connect",
    )

    with ExitStack() as stack:
        connection_mocks = [
            stack.enter_context(patch(target))
            for target in connection_targets
        ]
        application = create_application(
            Settings(
                database_url=(
                    "postgresql+asyncpg://phase_c1@localhost/"
                    "phase_c1_no_connect"
                ),
                _env_file=None,
            )
        )
        application.openapi()
        async with application.router.lifespan_context(application):
            pass

    assert all(not mock.called for mock in connection_mocks)


@pytest.mark.anyio
async def test_application_lifespan_disposes_engine_exactly_once() -> None:
    engine = SimpleNamespace(dispose=AsyncMock(), pool=object())
    session_factory = object()

    with (
        patch(
            "app.db.session.create_database_engine",
            return_value=engine,
        ),
        patch(
            "app.db.session.create_session_factory",
            return_value=session_factory,
        ),
    ):
        application = create_application(Settings(_env_file=None))

    async with application.router.lifespan_context(application):
        pass

    engine.dispose.assert_awaited_once_with()


@pytest.mark.anyio
async def test_independent_application_lifespans_use_and_dispose_distinct_engines() -> (
    None
):
    first_engine = SimpleNamespace(dispose=AsyncMock(), pool=object())
    second_engine = SimpleNamespace(dispose=AsyncMock(), pool=object())
    first_session_factory = object()
    second_session_factory = object()

    with (
        patch(
            "app.db.session.create_database_engine",
            side_effect=[first_engine, second_engine],
        ),
        patch(
            "app.db.session.create_session_factory",
            side_effect=[first_session_factory, second_session_factory],
        ),
    ):
        first_application = create_application(Settings(_env_file=None))
        second_application = create_application(Settings(_env_file=None))

    assert first_application.state.database_engine is first_engine
    assert second_application.state.database_engine is second_engine
    assert first_application.state.session_factory is first_session_factory
    assert second_application.state.session_factory is second_session_factory
    assert first_engine.pool is not second_engine.pool

    async with first_application.router.lifespan_context(first_application):
        pass
    async with second_application.router.lifespan_context(second_application):
        pass

    first_engine.dispose.assert_awaited_once_with()
    second_engine.dispose.assert_awaited_once_with()


def test_module_level_app_remains_a_fastapi_application() -> None:
    assert isinstance(module_app, FastAPI)
