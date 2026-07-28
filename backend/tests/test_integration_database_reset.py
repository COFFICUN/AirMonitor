"""Offline regressions for repeatable live-integration database isolation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import importlib
from pathlib import Path
import runpy
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import Column, Integer, MetaData, Table
from sqlalchemy.dialects import postgresql

from app.db.base import Base
import app.db.models  # noqa: F401  # Register every ORM table.
import tests.api_integration_guard as api_guard
import tests.persistence_guard as persistence_guard


RESET_MODULE_NAME = "tests.integration_database_reset"
PERSISTENCE_RESET_FAILURE = (
    "Persistence integration database reset failed."
)
API_RESET_FAILURE = "API integration database reset failed."
PERSISTENCE_PREFLIGHT_FAILURE = (
    "Persistence integration database preflight failed."
)
API_PREFLIGHT_FAILURE = "API integration database preflight failed."
APPLICATION_TABLE_NAMES = {
    "devices",
    "device_runtime_state",
    "measurement_sessions",
    "raw_measurements",
}


@dataclass(frozen=True)
class SuiteSpec:
    name: str
    module_path: Path
    guard_module: ModuleType
    validator_name: str
    dedicated_url_variable: str
    reset_failure_message: str
    preflight_failure_message: str
    opt_in_variable: str | None = None


SUITES = (
    SuiteSpec(
        name="persistence",
        module_path=Path(__file__).with_name(
            "test_persistence_integration.py"
        ),
        guard_module=persistence_guard,
        validator_name="validate_persistence_database_url",
        dedicated_url_variable="AIRMONITOR_TEST_DATABASE_URL",
        reset_failure_message=PERSISTENCE_RESET_FAILURE,
        preflight_failure_message=PERSISTENCE_PREFLIGHT_FAILURE,
        opt_in_variable="AIRMONITOR_RUN_PERSISTENCE_INTEGRATION",
    ),
    SuiteSpec(
        name="api",
        module_path=Path(__file__).with_name("test_api_integration.py"),
        guard_module=api_guard,
        validator_name="validate_api_test_database_url",
        dedicated_url_variable="AIRMONITOR_API_TEST_DATABASE_URL",
        reset_failure_message=API_RESET_FAILURE,
        preflight_failure_message=API_PREFLIGHT_FAILURE,
    ),
)


class SuiteBodyFailure(RuntimeError):
    """Sentinel raised through a simulated integration-suite body."""


class FakeLifecycleEngine:
    """Connection-free engine double for fixture lifecycle tests."""

    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def dispose(self) -> None:
        self.events.append("dispose")


class FakeResetConnection:
    """Records a reset statement without executing database I/O."""

    def __init__(
        self,
        events: list[str],
        statements: list[object],
        *,
        execute_failure: Exception | None = None,
    ) -> None:
        self.events = events
        self.statements = statements
        self.execute_failure = execute_failure

    async def execute(self, statement: object) -> None:
        self.events.append("execute")
        self.statements.append(statement)
        if self.execute_failure is not None:
            raise self.execute_failure


class FakeResetTransaction:
    """Async transaction context used by the reset helper unit tests."""

    def __init__(
        self,
        engine: FakeResetEngine,
    ) -> None:
        self.engine = engine

    async def __aenter__(self) -> FakeResetConnection:
        self.engine.events.append("transaction_enter")
        return self.engine.connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool:
        self.engine.events.append("transaction_exit")
        return False


class FakeResetEngine:
    """Minimal AsyncEngine-shaped object with a PostgreSQL dialect."""

    def __init__(
        self,
        *,
        execute_failure: Exception | None = None,
    ) -> None:
        self.dialect = postgresql.dialect()
        self.events: list[str] = []
        self.statements: list[object] = []
        self.begin_calls = 0
        self.connection = FakeResetConnection(
            self.events,
            self.statements,
            execute_failure=execute_failure,
        )

    def begin(self) -> FakeResetTransaction:
        self.begin_calls += 1
        self.events.append("begin")
        return FakeResetTransaction(self)


class FakeScalarResult:
    """Result double for the Alembic revision preflight."""

    def scalars(self) -> FakeScalarResult:
        return self

    def all(self) -> list[str]:
        return ["a4f9c2e7d1b6"]


class FakeInspector:
    """Schema inspector returning the approved disposable inventory."""

    def get_table_names(self) -> list[str]:
        return [
            "alembic_version",
            *sorted(APPLICATION_TABLE_NAMES),
        ]


class FakePreflightConnection:
    """Read-only connection double exposing stale application rows."""

    def __init__(self) -> None:
        self.scalar_calls = 0

    def begin(self) -> FakeAsyncContext:
        return FakeAsyncContext(self)

    async def execute(self, statement: object) -> FakeScalarResult:
        return FakeScalarResult()

    async def run_sync(
        self,
        operation: Callable[[object], object],
    ) -> object:
        return operation(object())

    async def scalar(self, statement: object) -> int:
        self.scalar_calls += 1
        return 1


class FakeAsyncContext:
    """Reusable asynchronous context manager for connection doubles."""

    def __init__(self, value: object) -> None:
        self.value = value

    async def __aenter__(self) -> object:
        return self.value

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool:
        return False


class FakePreflightEngine:
    """Engine double for direct schema/revision preflight tests."""

    def __init__(self) -> None:
        self.connection_value = FakePreflightConnection()

    def connect(self) -> FakeAsyncContext:
        return FakeAsyncContext(self.connection_value)


def _load_reset_function() -> Callable[..., Awaitable[None]]:
    reset_module = importlib.import_module(RESET_MODULE_NAME)
    reset_function = getattr(reset_module, "reset_application_tables")
    assert callable(reset_function)
    return reset_function


def _load_suite_namespace(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
    events: list[str],
) -> dict[str, Any]:
    for variable_name in (
        "AIRMONITOR_DATABASE_URL",
        "AIRMONITOR_RUN_PERSISTENCE_INTEGRATION",
        "AIRMONITOR_TEST_DATABASE_URL",
        "AIRMONITOR_API_TEST_DATABASE_URL",
        "AIRMONITOR_READ_API_TEST_DATABASE_URL",
    ):
        monkeypatch.delenv(variable_name, raising=False)

    monkeypatch.setenv(
        spec.dedicated_url_variable,
        "OFFLINE_DATABASE_TARGET_SENTINEL",
    )
    if spec.opt_in_variable is not None:
        monkeypatch.setenv(spec.opt_in_variable, "1")

    def validate_target(value: str) -> SimpleNamespace:
        assert value == "OFFLINE_DATABASE_TARGET_SENTINEL"
        events.append("target_validation")
        return SimpleNamespace(database="offline_database_target")

    monkeypatch.setattr(
        spec.guard_module,
        spec.validator_name,
        validate_target,
    )
    return runpy.run_path(str(spec.module_path))


def _prepare_fixture(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
    *,
    preflight_failure: Exception | None = None,
    reset_fail_on_call: int | None = None,
    state: dict[str, int] | None = None,
) -> tuple[
    Any,
    list[str],
    FakeLifecycleEngine,
]:
    events: list[str] = []
    namespace = _load_suite_namespace(monkeypatch, spec, events)
    fixture_function = namespace["session_factory"].__wrapped__
    fixture_globals = fixture_function.__globals__
    engine = FakeLifecycleEngine(events)
    reset_calls = 0

    def create_engine(*args: object, **kwargs: object) -> object:
        events.append("engine_construction")
        return engine

    def create_factory(**kwargs: object) -> object:
        events.append("factory_construction")
        return object()

    async def preflight(unused_engine: object) -> None:
        assert unused_engine is engine
        events.append("schema_preflight")
        if preflight_failure is not None:
            raise preflight_failure

    async def reset(
        unused_engine: object,
        metadata: MetaData,
        failure_message: str,
    ) -> None:
        nonlocal reset_calls
        assert unused_engine is engine
        assert metadata is Base.metadata
        assert failure_message == spec.reset_failure_message
        reset_calls += 1
        events.append("reset")
        if reset_calls == reset_fail_on_call:
            failure = pytest.fail.Exception(
                spec.reset_failure_message,
                pytrace=False,
            )
            raise failure from None
        if state is not None:
            state["rows"] = 0

    async def verify_empty(unused_engine: object) -> None:
        assert unused_engine is engine
        events.append("empty_verification")
        if state is not None and state["rows"] != 0:
            raise RuntimeError("OFFLINE_STALE_STATE_SENTINEL")

    monkeypatch.setitem(
        fixture_globals,
        "create_async_engine",
        create_engine,
    )
    monkeypatch.setitem(
        fixture_globals,
        "async_sessionmaker",
        create_factory,
    )
    monkeypatch.setitem(
        fixture_globals,
        "_preflight_disposable_database",
        preflight,
    )
    monkeypatch.setitem(
        fixture_globals,
        "reset_application_tables",
        reset,
    )
    monkeypatch.setitem(
        fixture_globals,
        "_verify_application_tables_empty",
        verify_empty,
    )
    return fixture_function, events, engine


def test_airmonitor_metadata_inventory_is_complete() -> None:
    assert set(Base.metadata.tables) == APPLICATION_TABLE_NAMES


def test_reset_uses_one_metadata_complete_truncate_statement() -> None:
    reset_application_tables = _load_reset_function()
    engine = FakeResetEngine()

    asyncio.run(
        reset_application_tables(
            engine,
            Base.metadata,
            PERSISTENCE_RESET_FAILURE,
        )
    )

    assert engine.begin_calls == 1
    assert engine.events == [
        "begin",
        "transaction_enter",
        "execute",
        "transaction_exit",
    ]
    assert len(engine.statements) == 1
    sql = str(engine.statements[0])
    assert sql.upper().count("TRUNCATE") == 1
    for table in Base.metadata.tables.values():
        formatted_name = engine.dialect.identifier_preparer.format_table(
            table
        )
        assert formatted_name in sql


def test_reset_restarts_identity_without_cascade() -> None:
    reset_application_tables = _load_reset_function()
    engine = FakeResetEngine()

    asyncio.run(
        reset_application_tables(
            engine,
            Base.metadata,
            API_RESET_FAILURE,
        )
    )

    sql = str(engine.statements[0]).upper()
    assert "RESTART IDENTITY" in sql
    assert "CASCADE" not in sql


def test_reset_quotes_metadata_controlled_identifiers() -> None:
    reset_application_tables = _load_reset_function()
    metadata = MetaData()
    Table('Mixed "table"', metadata, Column("id", Integer))
    engine = FakeResetEngine()

    asyncio.run(
        reset_application_tables(
            engine,
            metadata,
            API_RESET_FAILURE,
        )
    )

    sql = str(engine.statements[0])
    table = next(iter(metadata.tables.values()))
    expected_identifier = (
        engine.dialect.identifier_preparer.format_table(table)
    )
    assert expected_identifier in sql
    assert expected_identifier == '"Mixed ""table"""'


def test_reset_rejects_empty_metadata_before_transaction() -> None:
    reset_application_tables = _load_reset_function()
    engine = FakeResetEngine()

    with pytest.raises(pytest.fail.Exception) as raised:
        asyncio.run(
            reset_application_tables(
                engine,
                MetaData(),
                PERSISTENCE_RESET_FAILURE,
            )
        )

    failure = raised.value
    assert str(failure) == PERSISTENCE_RESET_FAILURE
    assert failure.pytrace is False
    assert failure.__cause__ is None
    assert failure.__context__ is None
    assert failure.__suppress_context__ is True
    assert engine.begin_calls == 0
    assert engine.statements == []


def test_reset_failure_is_fixed_sanitized_and_unchained(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reset_application_tables = _load_reset_function()
    sentinel = "DRIVER_SQL_URL_PASSWORD_SENTINEL"
    engine = FakeResetEngine(
        execute_failure=RuntimeError(sentinel),
    )

    with pytest.raises(pytest.fail.Exception) as raised:
        asyncio.run(
            reset_application_tables(
                engine,
                Base.metadata,
                API_RESET_FAILURE,
            )
        )

    failure = raised.value
    captured = capsys.readouterr()
    assert str(failure) == API_RESET_FAILURE
    assert failure.pytrace is False
    assert failure.__cause__ is None
    assert failure.__context__ is None
    assert failure.__suppress_context__ is True
    assert sentinel not in str(failure)
    assert sentinel not in captured.out
    assert sentinel not in captured.err


@pytest.mark.parametrize("spec", SUITES, ids=lambda spec: spec.name)
def test_schema_revision_preflight_does_not_reject_stale_rows(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
) -> None:
    events: list[str] = []
    namespace = _load_suite_namespace(monkeypatch, spec, events)
    preflight = namespace["_preflight_disposable_database"]
    preflight_globals = preflight.__globals__
    engine = FakePreflightEngine()

    monkeypatch.setitem(
        preflight_globals,
        "inspect",
        lambda connection: FakeInspector(),
    )

    asyncio.run(preflight(engine))

    assert engine.connection_value.scalar_calls == 0


@pytest.mark.parametrize("spec", SUITES, ids=lambda spec: spec.name)
def test_target_validation_precedes_engine_construction(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
) -> None:
    fixture_function, events, unused_engine = _prepare_fixture(
        monkeypatch,
        spec,
    )
    fixture_generator = fixture_function("asyncio")

    assert events == ["target_validation"]

    async def drive_fixture() -> None:
        await anext(fixture_generator)
        await fixture_generator.aclose()

    asyncio.run(drive_fixture())

    assert events.index("target_validation") < events.index(
        "engine_construction"
    )


@pytest.mark.parametrize("spec", SUITES, ids=lambda spec: spec.name)
def test_schema_preflight_precedes_initial_reset(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
) -> None:
    fixture_function, events, unused_engine = _prepare_fixture(
        monkeypatch,
        spec,
    )
    fixture_generator = fixture_function("asyncio")

    async def drive_fixture() -> None:
        await anext(fixture_generator)
        await fixture_generator.aclose()

    asyncio.run(drive_fixture())

    assert events.index("schema_preflight") < events.index("reset")


@pytest.mark.parametrize("spec", SUITES, ids=lambda spec: spec.name)
def test_initial_reset_and_empty_check_precede_suite_body(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
) -> None:
    fixture_function, events, unused_engine = _prepare_fixture(
        monkeypatch,
        spec,
    )
    fixture_generator = fixture_function("asyncio")

    async def drive_fixture() -> None:
        await anext(fixture_generator)
        events.append("suite_body")
        await fixture_generator.aclose()

    asyncio.run(drive_fixture())

    assert events.index("schema_preflight") < events.index("reset")
    assert events.index("reset") < events.index("empty_verification")
    assert events.index("empty_verification") < events.index("suite_body")


@pytest.mark.parametrize("spec", SUITES, ids=lambda spec: spec.name)
def test_final_reset_precedes_dispose_after_success(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
) -> None:
    fixture_function, events, unused_engine = _prepare_fixture(
        monkeypatch,
        spec,
    )
    fixture_generator = fixture_function("asyncio")

    async def drive_fixture() -> None:
        await anext(fixture_generator)
        await fixture_generator.aclose()

    asyncio.run(drive_fixture())

    assert events.count("reset") == 2
    assert events.index("empty_verification") < max(
        index for index, event in enumerate(events) if event == "reset"
    )
    assert max(
        index for index, event in enumerate(events) if event == "reset"
    ) < events.index("dispose")


@pytest.mark.parametrize("spec", SUITES, ids=lambda spec: spec.name)
def test_final_reset_precedes_dispose_after_body_failure(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
) -> None:
    fixture_function, events, unused_engine = _prepare_fixture(
        monkeypatch,
        spec,
    )
    fixture_generator = fixture_function("asyncio")

    async def drive_fixture() -> None:
        await anext(fixture_generator)
        with pytest.raises(SuiteBodyFailure):
            await fixture_generator.athrow(
                SuiteBodyFailure("OFFLINE_BODY_FAILURE_SENTINEL")
            )

    asyncio.run(drive_fixture())

    assert events.count("reset") == 2
    assert max(
        index for index, event in enumerate(events) if event == "reset"
    ) < events.index("dispose")


@pytest.mark.parametrize("spec", SUITES, ids=lambda spec: spec.name)
def test_dispose_runs_after_preflight_failure(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
) -> None:
    fixture_function, events, unused_engine = _prepare_fixture(
        monkeypatch,
        spec,
        preflight_failure=RuntimeError(
            "PREFLIGHT_DRIVER_URL_PASSWORD_SENTINEL"
        ),
    )
    fixture_generator = fixture_function("asyncio")

    async def drive_fixture() -> pytest.fail.Exception:
        with pytest.raises(pytest.fail.Exception) as raised:
            await anext(fixture_generator)
        return raised.value

    failure = asyncio.run(drive_fixture())

    assert str(failure) == spec.preflight_failure_message
    assert failure.__cause__ is None
    assert failure.__context__ is None
    assert failure.__suppress_context__ is True
    assert events[-1] == "dispose"


@pytest.mark.parametrize("spec", SUITES, ids=lambda spec: spec.name)
def test_dispose_runs_after_initial_reset_failure(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
) -> None:
    fixture_function, events, unused_engine = _prepare_fixture(
        monkeypatch,
        spec,
        reset_fail_on_call=1,
    )
    fixture_generator = fixture_function("asyncio")

    async def drive_fixture() -> None:
        try:
            with pytest.raises(pytest.fail.Exception) as raised:
                await anext(fixture_generator)
        finally:
            await fixture_generator.aclose()
        assert str(raised.value) == spec.reset_failure_message

    asyncio.run(drive_fixture())

    assert events[-1] == "dispose"


@pytest.mark.parametrize("spec", SUITES, ids=lambda spec: spec.name)
def test_dispose_runs_after_final_reset_failure(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
) -> None:
    fixture_function, events, unused_engine = _prepare_fixture(
        monkeypatch,
        spec,
        reset_fail_on_call=2,
    )
    fixture_generator = fixture_function("asyncio")

    async def drive_fixture() -> pytest.fail.Exception:
        await anext(fixture_generator)
        with pytest.raises(pytest.fail.Exception) as raised:
            await fixture_generator.aclose()
        return raised.value

    failure = asyncio.run(drive_fixture())

    assert str(failure) == spec.reset_failure_message
    assert failure.__cause__ is None
    assert failure.__context__ is None
    assert failure.__suppress_context__ is True
    assert events[-1] == "dispose"


@pytest.mark.parametrize("spec", SUITES, ids=lambda spec: spec.name)
def test_final_reset_failure_after_body_failure_has_no_retained_context(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
) -> None:
    fixture_function, events, unused_engine = _prepare_fixture(
        monkeypatch,
        spec,
        reset_fail_on_call=2,
    )
    fixture_generator = fixture_function("asyncio")

    async def drive_fixture() -> pytest.fail.Exception:
        await anext(fixture_generator)
        with pytest.raises(pytest.fail.Exception) as raised:
            await fixture_generator.athrow(
                SuiteBodyFailure("OFFLINE_BODY_FAILURE_SENTINEL")
            )
        return raised.value

    failure = asyncio.run(drive_fixture())

    assert str(failure) == spec.reset_failure_message
    assert failure.__cause__ is None
    assert failure.__context__ is None
    assert failure.__suppress_context__ is True
    assert events[-1] == "dispose"


@pytest.mark.parametrize("spec", SUITES, ids=lambda spec: spec.name)
def test_second_simulated_activation_starts_from_empty_state(
    monkeypatch: pytest.MonkeyPatch,
    spec: SuiteSpec,
) -> None:
    state = {"rows": 0}
    fixture_function, events, unused_engine = _prepare_fixture(
        monkeypatch,
        spec,
        state=state,
    )

    async def drive_two_activations() -> None:
        first_generator = fixture_function("asyncio")
        await anext(first_generator)
        state["rows"] = 1
        await first_generator.aclose()

        second_generator = fixture_function("asyncio")
        await anext(second_generator)
        assert state["rows"] == 0
        await second_generator.aclose()

    asyncio.run(drive_two_activations())


def test_both_suites_reference_the_same_shared_reset_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_application_tables = _load_reset_function()
    namespaces = [
        _load_suite_namespace(monkeypatch, spec, [])
        for spec in SUITES
    ]

    assert all(
        namespace["reset_application_tables"]
        is reset_application_tables
        for namespace in namespaces
    )


def test_database_isolation_sources_exclude_forbidden_mutations() -> None:
    reset_module = Path(__file__).with_name(
        "integration_database_reset.py"
    )
    assert reset_module.is_file()
    sources = [
        reset_module.read_text(encoding="utf-8"),
        *[
            spec.module_path.read_text(encoding="utf-8")
            for spec in SUITES
        ],
    ]
    combined_source = "\n".join(sources).casefold()

    for forbidden in (
        "drop_all",
        "create_all",
        "alembic upgrade",
        "alembic downgrade",
        "create database",
        "drop database",
        "drop schema",
        " cascade",
    ):
        assert forbidden not in combined_source
    assert sum(
        source.upper().count("TRUNCATE")
        for source in sources
    ) == 1


def test_shared_reset_source_has_no_manual_table_inventory() -> None:
    reset_module = Path(__file__).with_name(
        "integration_database_reset.py"
    )
    assert reset_module.is_file()
    reset_source = reset_module.read_text(encoding="utf-8")

    for table_name in APPLICATION_TABLE_NAMES:
        assert table_name not in reset_source
