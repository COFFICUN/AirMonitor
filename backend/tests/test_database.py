"""Tests for asynchronous database infrastructure."""

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.dependencies import get_db_session
from app.db.session import create_database_engine, create_session_factory


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://airmonitor:airmonitor@localhost:5432/airmonitor"
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class TrackingAsyncSession(AsyncSession):
    """Async session that records dependency-managed closure."""

    was_closed: bool = False

    async def close(self) -> None:
        self.was_closed = True
        await super().close()


def test_default_database_settings(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("AIRMONITOR_DATABASE_URL", raising=False)
    monkeypatch.delenv("AIRMONITOR_DATABASE_ECHO", raising=False)
    monkeypatch.delenv("AIRMONITOR_DATABASE_POOL_PRE_PING", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.database_echo is False
    assert settings.database_pool_pre_ping is True


def test_database_url_environment_override(monkeypatch: MonkeyPatch) -> None:
    database_url = (
        "postgresql+asyncpg://test_user:test_password@db.example.test/test_db"
    )
    monkeypatch.setenv("AIRMONITOR_DATABASE_URL", database_url)

    settings = Settings(_env_file=None)

    assert settings.database_url == database_url


@pytest.mark.parametrize(
    ("variable_name", "settings_attribute", "raw_value", "expected"),
    [
        ("AIRMONITOR_DATABASE_ECHO", "database_echo", "true", True),
        ("AIRMONITOR_DATABASE_ECHO", "database_echo", "false", False),
        (
            "AIRMONITOR_DATABASE_POOL_PRE_PING",
            "database_pool_pre_ping",
            "true",
            True,
        ),
        (
            "AIRMONITOR_DATABASE_POOL_PRE_PING",
            "database_pool_pre_ping",
            "false",
            False,
        ),
    ],
)
def test_database_boolean_parsing(
    monkeypatch: MonkeyPatch,
    variable_name: str,
    settings_attribute: str,
    raw_value: str,
    expected: bool,
) -> None:
    monkeypatch.setenv(variable_name, raw_value)

    settings = Settings(_env_file=None)

    assert getattr(settings, settings_attribute) is expected


def test_rejects_unsupported_database_driver() -> None:
    with pytest.raises(
        ValidationError,
        match="database_url must use the postgresql\\+asyncpg driver",
    ):
        Settings(database_url="sqlite+aiosqlite:///airmonitor.db", _env_file=None)


@pytest.mark.anyio
async def test_database_engine_uses_asyncpg_without_connecting() -> None:
    settings = Settings(_env_file=None)

    with patch("asyncpg.connect") as connect:
        engine = create_database_engine(settings)

    try:
        assert isinstance(engine, AsyncEngine)
        assert engine.url.drivername == "postgresql+asyncpg"
        connect.assert_not_called()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_session_factory_configuration() -> None:
    engine = create_database_engine(Settings(_env_file=None))
    session_factory = create_session_factory(engine)
    session = session_factory()

    try:
        assert isinstance(session_factory, async_sessionmaker)
        assert isinstance(session, AsyncSession)
        assert session.sync_session.expire_on_commit is False
        assert session.autoflush is False
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.anyio
async def test_database_dependency_closes_session() -> None:
    engine = create_database_engine(Settings(_env_file=None))
    session_factory = async_sessionmaker(
        bind=engine,
        class_=TrackingAsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    dependency: AsyncIterator[AsyncSession] = get_db_session(session_factory)

    try:
        session = await anext(dependency)
        assert isinstance(session, AsyncSession)
        assert isinstance(session, TrackingAsyncSession)
        assert session.was_closed is False

        await dependency.aclose()

        assert session.was_closed is True
    finally:
        await dependency.aclose()
        await engine.dispose()


def test_declarative_base_has_empty_metadata() -> None:
    assert Base.metadata is not None
    assert not Base.metadata.tables


def test_alembic_configuration_files_exist() -> None:
    assert (BACKEND_DIRECTORY / "alembic.ini").is_file()
    assert (BACKEND_DIRECTORY / "alembic" / "env.py").is_file()
    assert (BACKEND_DIRECTORY / "alembic" / "script.py.mako").is_file()
    assert (BACKEND_DIRECTORY / "alembic" / "README").is_file()
    assert (BACKEND_DIRECTORY / "alembic" / "versions").is_dir()


def test_alembic_uses_application_settings_and_base_metadata() -> None:
    environment_source = (
        BACKEND_DIRECTORY / "alembic" / "env.py"
    ).read_text(encoding="utf-8")

    assert "get_settings()" in environment_source
    assert "target_metadata = Base.metadata" in environment_source
    assert '.replace("%", "%%")' in environment_source
