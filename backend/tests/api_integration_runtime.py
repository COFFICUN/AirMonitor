"""Guarded PostgreSQL runtime fixtures for HTTP integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
import os

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tests.api_integration_guard import (
    ApiIntegrationTargetError,
    run_api_preflight_safely,
    validate_api_test_database_url,
)


_DATABASE_URL_TEXT = os.environ.get("AIRMONITOR_API_TEST_DATABASE_URL")
if _DATABASE_URL_TEXT is None:
    pytest.skip(
        "API integration tests require the dedicated disposable database URL",
        allow_module_level=True,
    )

try:
    _parsed_database_url: URL = validate_api_test_database_url(
        _DATABASE_URL_TEXT
    )
except ApiIntegrationTargetError as error:
    pytest.fail(str(error), pytrace=False)

del _DATABASE_URL_TEXT


from app.core.config import Settings
from app.db.base import Base
from app.db.dependencies import get_db_session
from app.main import create_application
from tests.integration_database_reset import reset_application_tables


EXPECTED_TABLES = {
    "alembic_version",
    "device_runtime_state",
    "devices",
    "measurement_sessions",
    "raw_measurements",
}
EXPECTED_ALEMBIC_HEAD = "a75caa2b44f5"
RESET_FAILURE_MESSAGE = "API integration database reset failed."


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


async def _preflight_disposable_database(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        async with connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            table_names = await connection.run_sync(
                lambda sync_connection: set(
                    inspect(sync_connection).get_table_names()
                )
            )
            if table_names != EXPECTED_TABLES:
                raise RuntimeError(
                    "API schema inventory is not approved"
                )

            alembic_heads = (
                await connection.execute(
                    text("SELECT version_num FROM alembic_version")
                )
            ).scalars().all()
            if alembic_heads != [EXPECTED_ALEMBIC_HEAD]:
                raise RuntimeError(
                    "API schema revision is not approved"
                )


async def _verify_application_tables_empty(
    engine: AsyncEngine,
) -> None:
    tables = tuple(Base.metadata.tables.values())
    if not tables:
        raise RuntimeError("application metadata has no tables")

    async with engine.connect() as connection:
        async with connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            row_counts = [
                await connection.scalar(
                    select(func.count()).select_from(table)
                )
                for table in tables
            ]
            if any(row_count != 0 for row_count in row_counts):
                raise RuntimeError(
                    "API application tables are not empty"
                )


@pytest.fixture(scope="session")
async def session_factory(
    anyio_backend: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    assert anyio_backend == "asyncio"
    engine = create_async_engine(
        _parsed_database_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "statement_timeout": "15000",
            }
        },
    )
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        await run_api_preflight_safely(
            lambda: _preflight_disposable_database(engine),
        )
        await reset_application_tables(
            engine,
            Base.metadata,
            RESET_FAILURE_MESSAGE,
        )
        await run_api_preflight_safely(
            lambda: _verify_application_tables_empty(engine)
        )

        # Exit the handler before cleanup so a reset failure cannot retain
        # the suite error as its exception context.
        suite_error: BaseException | None = None
        try:
            yield factory
        except BaseException as error:
            suite_error = error

        await reset_application_tables(
            engine,
            Base.metadata,
            RESET_FAILURE_MESSAGE,
        )
        if suite_error is not None:
            raise suite_error.with_traceback(
                suite_error.__traceback__
            ) from None
    finally:
        await engine.dispose()


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    application = create_application(Settings(_env_file=None))
    original_overrides = dict(application.dependency_overrides)

    async def integration_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_db_session] = integration_session
    transport = ASGITransport(
        app=application,
        raise_app_exceptions=False,
    )
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as integration_client:
            yield integration_client
    finally:
        application.dependency_overrides.clear()
        application.dependency_overrides.update(original_overrides)


__all__ = [
    "_preflight_disposable_database",
    "_verify_application_tables_empty",
    "anyio_backend",
    "client",
    "reset_application_tables",
    "session_factory",
]
