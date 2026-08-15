"""Connection-free tests for the AirMonitor Alembic migration chain."""

from __future__ import annotations

import ast
from collections import Counter
from contextlib import ExitStack, contextmanager
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
import re
from types import ModuleType
from typing import Any, Iterator
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import app.db.models
import pytest
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.db.base import Base


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
ALEMBIC_DIRECTORY = BACKEND_DIRECTORY / "alembic"
VERSIONS_DIRECTORY = ALEMBIC_DIRECTORY / "versions"
ALEMBIC_CONFIG_PATH = BACKEND_DIRECTORY / "alembic.ini"

EXPECTED_CREATE_ORDER = (
    "devices",
    "measurement_sessions",
    "device_runtime_state",
    "raw_measurements",
)
EXPECTED_DROP_ORDER = tuple(reversed(EXPECTED_CREATE_ORDER))
INITIAL_REVISION_ID = "a4f9c2e7d1b6"
EXPECTED_INITIAL_INDEXES = {
    "ix_measurement_sessions_device_id_started_at": (
        "measurement_sessions",
        ("device_id", "started_at"),
    ),
    "ix_measurement_sessions_device_id_status": (
        "measurement_sessions",
        ("device_id", "status"),
    ),
    "ix_raw_measurements_device_id_measured_at": (
        "raw_measurements",
        ("device_id", "measured_at"),
    ),
    "ix_raw_measurements_session_id_measured_at": (
        "raw_measurements",
        ("session_id", "measured_at"),
    ),
}
EXPECTED_INITIAL_INDEX_ORDER = tuple(EXPECTED_INITIAL_INDEXES)
EXPECTED_TELEMETRY_INDEXES = {
    "ix_measurement_sessions_device_id_started_at_id_desc": (
        "measurement_sessions",
        ("device_id", "started_at desc", "id desc"),
    ),
    "ix_measurement_sessions_device_id_status_started_at_id_desc": (
        "measurement_sessions",
        ("device_id", "status", "started_at desc", "id desc"),
    ),
    "ix_raw_measurements_device_id_measured_at_id_desc": (
        "raw_measurements",
        ("device_id", "measured_at desc", "id desc"),
    ),
    "ix_raw_measurements_session_id_measured_at_id_desc": (
        "raw_measurements",
        ("session_id", "measured_at desc", "id desc"),
    ),
}
EXPECTED_TELEMETRY_INDEX_ORDER = tuple(EXPECTED_TELEMETRY_INDEXES)
OBSOLETE_TABLES = {
    "aggregated_measurements",
    "measurements",
    "raw_session_links",
}
REVISION_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")
POSTGRESQL_DIALECT = postgresql.dialect()

FORBIDDEN_CONNECTION_TARGETS = (
    "sqlalchemy.create_engine",
    "sqlalchemy.engine_from_config",
    "sqlalchemy.ext.asyncio.create_async_engine",
    "sqlalchemy.ext.asyncio.async_engine_from_config",
    "sqlalchemy.engine.Engine.connect",
    "sqlalchemy.ext.asyncio.AsyncEngine.connect",
    "app.db.session.create_database_engine",
    "app.db.session.create_session_factory",
    "app.db.session.get_database_engine",
    "app.db.session.get_session_factory",
    "sqlalchemy.orm.sessionmaker",
    "sqlalchemy.ext.asyncio.async_sessionmaker",
    "sqlalchemy.sql.schema.MetaData.create_all",
    "asyncpg.connect",
)


@pytest.fixture(scope="module", autouse=True)
def migration_safety_guard() -> Iterator[None]:
    with _forbid_connections_and_runtime_settings():
        yield


@pytest.fixture(scope="module")
def revision_path() -> Path:
    revision_files = [
        path
        for path in VERSIONS_DIRECTORY.glob("*.py")
        if path.name != "__init__.py"
        and path.name.startswith(f"{INITIAL_REVISION_ID}_")
    ]

    assert len(revision_files) == 1, (
        "expected the one approved initial Alembic revision, found "
        f"{[path.name for path in revision_files]}"
    )
    return revision_files[0]


@pytest.fixture(scope="module")
def revision_module(revision_path: Path) -> ModuleType:
    module_name = f"airmonitor_migration_{revision_path.stem}"
    specification = spec_from_file_location(module_name, revision_path)

    assert specification is not None
    assert specification.loader is not None

    module = module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def telemetry_revision_path(revision_path: Path) -> Path:
    revision_files = sorted(
        path
        for path in VERSIONS_DIRECTORY.glob("*.py")
        if path.name != "__init__.py" and path != revision_path
    )

    assert len(revision_files) == 1, (
        "expected exactly one telemetry index revision after the initial "
        f"revision, found {[path.name for path in revision_files]}"
    )
    path = revision_files[0]
    assert path.name.endswith("_add_telemetry_read_indexes.py")
    return path


@pytest.fixture(scope="module")
def telemetry_revision_module(
    telemetry_revision_path: Path,
) -> ModuleType:
    module_name = f"airmonitor_migration_{telemetry_revision_path.stem}"
    specification = spec_from_file_location(
        module_name,
        telemetry_revision_path,
    )

    assert specification is not None
    assert specification.loader is not None

    module = module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script_directory(telemetry_revision_path: Path) -> ScriptDirectory:
    del telemetry_revision_path
    return ScriptDirectory.from_config(_alembic_config()[0])


@pytest.fixture(scope="module")
def migration_structure(
    revision_module: ModuleType,
) -> tuple[MetaData, dict[str, tuple[str, tuple[str, ...], bool]], list[tuple[str, str]]]:
    migration_metadata = MetaData()
    indexes: dict[str, tuple[str, tuple[str, ...], bool]] = {}
    events: list[tuple[str, str]] = []

    def capture_table(
        table_name: str,
        *elements: Any,
        **keywords: Any,
    ) -> Table:
        events.append(("table", table_name))
        return Table(table_name, migration_metadata, *elements, **keywords)

    def capture_index(
        index_name: str,
        table_name: str,
        columns: list[str] | tuple[str, ...],
        **keywords: Any,
    ) -> None:
        events.append(("index", index_name))
        indexes[index_name] = (
            table_name,
            tuple(columns),
            bool(keywords.get("unique", False)),
        )

    with (
        patch.object(
            revision_module.op,
            "create_table",
            side_effect=capture_table,
        ),
        patch.object(
            revision_module.op,
            "create_index",
            side_effect=capture_index,
        ),
        patch.object(
            revision_module.op,
            "execute",
            side_effect=AssertionError("unexpected raw migration SQL"),
        ),
    ):
        revision_module.upgrade()

    return migration_metadata, indexes, events


@pytest.fixture(scope="module")
def downgrade_events(revision_module: ModuleType) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []

    def capture_index(index_name: str, **keywords: Any) -> None:
        assert keywords.get("table_name") in EXPECTED_CREATE_ORDER
        events.append(("index", index_name))

    def capture_table(table_name: str, **keywords: Any) -> None:
        assert keywords == {}
        events.append(("table", table_name))

    with (
        patch.object(
            revision_module.op,
            "drop_index",
            side_effect=capture_index,
        ),
        patch.object(
            revision_module.op,
            "drop_table",
            side_effect=capture_table,
        ),
        patch.object(
            revision_module.op,
            "execute",
            side_effect=AssertionError("unexpected raw migration SQL"),
        ),
    ):
        revision_module.downgrade()

    return events


@pytest.fixture(scope="module")
def offline_upgrade_sql(revision_module: ModuleType) -> str:
    return _generate_offline_sql("upgrade", revision_module.revision)


@pytest.fixture(scope="module")
def offline_downgrade_sql(revision_module: ModuleType) -> str:
    return _generate_offline_sql(
        "downgrade",
        f"{revision_module.revision}:base",
    )


def _index_expression_signature(value: Any) -> str:
    if isinstance(value, str):
        return value.casefold()

    compiled = _normalized_sql(
        value.compile(
            dialect=POSTGRESQL_DIALECT,
            compile_kwargs={"literal_binds": True},
        )
    )
    for table_name in EXPECTED_CREATE_ORDER:
        compiled = compiled.replace(f"{table_name}.", "")
        compiled = compiled.replace(f'"{table_name}".', "")
    return compiled


@pytest.fixture(scope="module")
def telemetry_upgrade_events(
    telemetry_revision_module: ModuleType,
) -> list[tuple[str, str, str, tuple[str, ...]]]:
    events: list[tuple[str, str, str, tuple[str, ...]]] = []

    def capture_create(
        index_name: str,
        table_name: str,
        columns: list[Any] | tuple[Any, ...],
        **keywords: Any,
    ) -> None:
        assert keywords == {"unique": False}
        events.append(
            (
                "create",
                index_name,
                table_name,
                tuple(
                    _index_expression_signature(column)
                    for column in columns
                ),
            )
        )

    def capture_drop(index_name: str, **keywords: Any) -> None:
        table_name = keywords.pop("table_name")
        assert keywords == {}
        events.append(("drop", index_name, table_name, ()))

    with (
        patch.object(
            telemetry_revision_module.op,
            "create_index",
            side_effect=capture_create,
        ),
        patch.object(
            telemetry_revision_module.op,
            "drop_index",
            side_effect=capture_drop,
        ),
        patch.object(
            telemetry_revision_module.op,
            "execute",
            side_effect=AssertionError("unexpected raw migration SQL"),
        ),
    ):
        telemetry_revision_module.upgrade()

    return events


@pytest.fixture(scope="module")
def telemetry_downgrade_events(
    telemetry_revision_module: ModuleType,
) -> list[tuple[str, str, str, tuple[str, ...]]]:
    events: list[tuple[str, str, str, tuple[str, ...]]] = []

    def capture_create(
        index_name: str,
        table_name: str,
        columns: list[Any] | tuple[Any, ...],
        **keywords: Any,
    ) -> None:
        assert keywords == {"unique": False}
        events.append(
            (
                "create",
                index_name,
                table_name,
                tuple(
                    _index_expression_signature(column)
                    for column in columns
                ),
            )
        )

    def capture_drop(index_name: str, **keywords: Any) -> None:
        table_name = keywords.pop("table_name")
        assert keywords == {}
        events.append(("drop", index_name, table_name, ()))

    with (
        patch.object(
            telemetry_revision_module.op,
            "create_index",
            side_effect=capture_create,
        ),
        patch.object(
            telemetry_revision_module.op,
            "drop_index",
            side_effect=capture_drop,
        ),
        patch.object(
            telemetry_revision_module.op,
            "execute",
            side_effect=AssertionError("unexpected raw migration SQL"),
        ),
    ):
        telemetry_revision_module.downgrade()

    return events


@pytest.fixture(scope="module")
def offline_telemetry_upgrade_sql(
    revision_module: ModuleType,
    telemetry_revision_module: ModuleType,
) -> str:
    return _generate_offline_sql(
        "upgrade",
        f"{revision_module.revision}:{telemetry_revision_module.revision}",
    )


@pytest.fixture(scope="module")
def offline_telemetry_downgrade_sql(
    revision_module: ModuleType,
    telemetry_revision_module: ModuleType,
) -> str:
    return _generate_offline_sql(
        "downgrade",
        f"{telemetry_revision_module.revision}:{revision_module.revision}",
    )


def _alembic_config() -> tuple[Config, StringIO, StringIO]:
    stdout = StringIO()
    output_buffer = StringIO()
    config = Config(
        str(ALEMBIC_CONFIG_PATH),
        stdout=stdout,
        output_buffer=output_buffer,
    )
    config.set_main_option("script_location", str(ALEMBIC_DIRECTORY))
    config.set_main_option("prepend_sys_path", str(BACKEND_DIRECTORY))
    config.set_main_option(
        "sqlalchemy.url",
        "postgresql+asyncpg://localhost/airmonitor_offline_validation",
    )
    return config, stdout, output_buffer


@contextmanager
def _forbid_connections_and_runtime_settings() -> Iterator[None]:
    def forbidden_call(target: str) -> Any:
        def fail(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            raise AssertionError(
                f"offline migration attempted forbidden call: {target}"
            )

        return fail

    with ExitStack() as stack:
        for target in FORBIDDEN_CONNECTION_TARGETS:
            stack.enter_context(patch(target, new=forbidden_call(target)))
        stack.enter_context(
            patch(
                "app.core.config.get_settings",
                new=forbidden_call("app.core.config.get_settings"),
            )
        )
        yield


def _generate_offline_sql(operation: str, destination: str) -> str:
    config, _, output_buffer = _alembic_config()

    if operation == "upgrade":
        command.upgrade(config, destination, sql=True)
    elif operation == "downgrade":
        command.downgrade(config, destination, sql=True)
    else:
        raise AssertionError(f"unsupported operation: {operation}")

    return output_buffer.getvalue()


def _normalized_sql(value: Any) -> str:
    return " ".join(str(value).lower().split())


def _compiled_type(column: Any) -> str:
    return _normalized_sql(column.type.compile(dialect=POSTGRESQL_DIALECT))


def _server_default(column: Any) -> tuple[str, str] | None:
    if column.server_default is None:
        return None

    argument = column.server_default.arg
    if isinstance(argument, str):
        return "scalar", argument
    return (
        "sql",
        _normalized_sql(
            argument.compile(
                dialect=POSTGRESQL_DIALECT,
                compile_kwargs={"literal_binds": True},
            )
        ),
    )


def _constraint_signatures(table: Table) -> set[tuple[Any, ...]]:
    signatures: set[tuple[Any, ...]] = set()
    for constraint in table.constraints:
        columns = tuple(column.name for column in constraint.columns)
        if isinstance(constraint, PrimaryKeyConstraint):
            signatures.add(("primary_key", constraint.name, columns))
        elif isinstance(constraint, UniqueConstraint):
            signatures.add(("unique", constraint.name, columns))
        elif isinstance(constraint, ForeignKeyConstraint):
            signatures.add(
                (
                    "foreign_key",
                    constraint.name,
                    columns,
                    tuple(
                        element.target_fullname
                        for element in constraint.elements
                    ),
                    constraint.ondelete,
                )
            )
        elif isinstance(constraint, CheckConstraint):
            signatures.add(
                (
                    "check",
                    constraint.name,
                    _normalized_sql(constraint.sqltext),
                )
            )
        else:
            raise AssertionError(
                f"unexpected constraint on {table.name}: {constraint!r}"
            )
    return signatures


def _named_metadata_constraints() -> set[str]:
    return {
        constraint.name
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if constraint.name is not None
    }


def _ddl_names(sql: str, operation: str, object_type: str) -> list[str]:
    optional_if_exists = r"(?:\s+if\s+exists)?" if operation == "drop" else ""
    pattern = re.compile(
        rf"\b{operation}\s+{object_type}{optional_if_exists}\s+"
        r'(?:"[^"]+"\.)?(?:"(?P<quoted>[^"]+)"|(?P<plain>[a-z_][a-z0-9_]*))',
        flags=re.IGNORECASE,
    )
    return [
        (match.group("quoted") or match.group("plain")).lower()
        for match in pattern.finditer(sql)
    ]


def test_initial_revision_file_exists(revision_path: Path) -> None:
    assert revision_path.parent == VERSIONS_DIRECTORY


def test_revision_identifiers_are_valid_and_initial(
    revision_path: Path,
    revision_module: ModuleType,
) -> None:
    assert REVISION_ID_PATTERN.fullmatch(revision_module.revision)
    assert revision_path.name.startswith(f"{revision_module.revision}_")
    assert revision_module.down_revision is None
    assert revision_module.branch_labels is None
    assert revision_module.depends_on is None


def test_telemetry_revision_identifiers_are_valid_and_linear(
    telemetry_revision_path: Path,
    telemetry_revision_module: ModuleType,
) -> None:
    assert REVISION_ID_PATTERN.fullmatch(telemetry_revision_module.revision)
    assert telemetry_revision_module.revision != INITIAL_REVISION_ID
    assert telemetry_revision_path.name.startswith(
        f"{telemetry_revision_module.revision}_"
    )
    assert telemetry_revision_module.down_revision == INITIAL_REVISION_ID
    assert telemetry_revision_module.branch_labels is None
    assert telemetry_revision_module.depends_on is None


def test_alembic_reports_one_base_and_one_telemetry_head(
    revision_module: ModuleType,
    telemetry_revision_module: ModuleType,
    script_directory: ScriptDirectory,
) -> None:
    assert script_directory.get_bases() == [revision_module.revision]
    assert script_directory.get_heads() == [
        telemetry_revision_module.revision
    ]
    assert [
        revision.revision
        for revision in script_directory.walk_revisions()
    ] == [
        telemetry_revision_module.revision,
        revision_module.revision,
    ]


def test_alembic_history_and_heads_include_linear_revision_chain(
    revision_module: ModuleType,
    telemetry_revision_module: ModuleType,
) -> None:
    history_config, history_stdout, _ = _alembic_config()
    heads_config, heads_stdout, _ = _alembic_config()

    command.history(history_config)
    command.heads(heads_config)

    history_lines = history_stdout.getvalue().splitlines()
    heads_output = heads_stdout.getvalue()
    assert history_lines == [
        (
            f"{revision_module.revision} -> "
            f"{telemetry_revision_module.revision} (head), "
            "add telemetry read indexes"
        ),
        (
            f"<base> -> {revision_module.revision}, "
            "create initial AirMonitor schema"
        ),
    ]
    assert revision_module.revision not in heads_output
    assert heads_output.count(telemetry_revision_module.revision) == 1


def test_initial_upgrade_structure_matches_initial_contract(
    migration_structure: tuple[
        MetaData,
        dict[str, tuple[str, tuple[str, ...], bool]],
        list[tuple[str, str]],
    ],
) -> None:
    migration_metadata, indexes, _ = migration_structure

    assert set(migration_metadata.tables) == set(Base.metadata.tables)
    for table_name, orm_table in Base.metadata.tables.items():
        migration_table = migration_metadata.tables[table_name]
        assert tuple(migration_table.c.keys()) == tuple(orm_table.c.keys())
        assert _constraint_signatures(migration_table) == (
            _constraint_signatures(orm_table)
        )

        for column_name, orm_column in orm_table.c.items():
            migration_column = migration_table.c[column_name]
            assert _compiled_type(migration_column) == _compiled_type(orm_column)
            assert migration_column.nullable is orm_column.nullable
            assert migration_column.primary_key is orm_column.primary_key
            assert migration_column.autoincrement == orm_column.autoincrement
            assert _server_default(migration_column) == (
                _server_default(orm_column)
            )
            assert migration_column.default is None
            assert migration_column.onupdate is None

    assert indexes == {
        index_name: (table_name, columns, False)
        for index_name, (table_name, columns) in (
            EXPECTED_INITIAL_INDEXES.items()
        )
    }


def test_upgrade_creation_order_is_dependency_safe(
    migration_structure: tuple[
        MetaData,
        dict[str, tuple[str, tuple[str, ...], bool]],
        list[tuple[str, str]],
    ],
) -> None:
    _, _, events = migration_structure
    table_events = [event for event in events if event[0] == "table"]
    index_events = [event for event in events if event[0] == "index"]

    assert table_events == [
        ("table", table_name) for table_name in EXPECTED_CREATE_ORDER
    ]
    assert Counter(index_events) == Counter(
        ("index", index_name)
        for index_name in EXPECTED_INITIAL_INDEXES
    )
    assert events == [*table_events, *index_events]


def test_downgrade_drops_indexes_then_tables_in_reverse_order(
    downgrade_events: list[tuple[str, str]],
) -> None:
    index_events = [
        event for event in downgrade_events if event[0] == "index"
    ]
    table_events = [
        event for event in downgrade_events if event[0] == "table"
    ]

    assert Counter(index_events) == Counter(
        ("index", index_name)
        for index_name in EXPECTED_INITIAL_INDEXES
    )
    assert table_events == [
        ("table", table_name) for table_name in EXPECTED_DROP_ORDER
    ]
    assert downgrade_events == [*index_events, *table_events]


def test_migration_tables_compile_as_postgresql_ddl(
    migration_structure: tuple[
        MetaData,
        dict[str, tuple[str, tuple[str, ...], bool]],
        list[tuple[str, str]],
    ],
) -> None:
    migration_metadata, _, _ = migration_structure

    compiled_tables = {
        table_name: str(
            CreateTable(migration_metadata.tables[table_name]).compile(
                dialect=POSTGRESQL_DIALECT
            )
        )
        for table_name in EXPECTED_CREATE_ORDER
    }

    assert set(compiled_tables) == set(EXPECTED_CREATE_ORDER)
    assert all("CREATE TABLE" in ddl for ddl in compiled_tables.values())


def test_offline_upgrade_creates_only_approved_domain_tables(
    offline_upgrade_sql: str,
) -> None:
    created_tables = _ddl_names(offline_upgrade_sql, "create", "table")
    domain_tables = [
        table_name
        for table_name in created_tables
        if table_name != "alembic_version"
    ]

    assert domain_tables == list(EXPECTED_CREATE_ORDER)
    assert not OBSOLETE_TABLES.intersection(created_tables)


def test_offline_upgrade_contains_every_named_constraint_once(
    offline_upgrade_sql: str,
) -> None:
    normalized_sql = offline_upgrade_sql.lower()

    for constraint_name in _named_metadata_constraints():
        assert (
            len(
                re.findall(
                    rf"\bconstraint\s+{re.escape(constraint_name.lower())}\b",
                    normalized_sql,
                )
            )
            == 1
        ), constraint_name


def test_offline_upgrade_creates_each_approved_index_once(
    offline_upgrade_sql: str,
) -> None:
    created_indexes = _ddl_names(offline_upgrade_sql, "create", "index")

    assert Counter(created_indexes) == Counter(
        EXPECTED_INITIAL_INDEXES.keys()
    )
    assert "create unique index" not in _normalized_sql(offline_upgrade_sql)


def test_offline_downgrade_drops_indexes_and_tables_in_reverse_order(
    offline_downgrade_sql: str,
) -> None:
    dropped_indexes = _ddl_names(offline_downgrade_sql, "drop", "index")
    dropped_tables = [
        table_name
        for table_name in _ddl_names(
            offline_downgrade_sql,
            "drop",
            "table",
        )
        if table_name != "alembic_version"
    ]

    assert Counter(dropped_indexes) == Counter(
        EXPECTED_INITIAL_INDEXES.keys()
    )
    assert dropped_tables == list(EXPECTED_DROP_ORDER)
    assert offline_downgrade_sql.lower().find("drop index") < (
        offline_downgrade_sql.lower().find("drop table")
    )


def test_offline_sql_contains_no_out_of_scope_database_objects(
    offline_upgrade_sql: str,
    offline_downgrade_sql: str,
) -> None:
    combined_sql = _normalized_sql(
        f"{offline_upgrade_sql}\n{offline_downgrade_sql}"
    )
    forbidden_patterns = (
        r"\bcreate\s+database\b",
        r"\bcreate\s+extension\b",
        r"\bcreate\s+role\b",
        r"\bcreate\s+schema\b",
        r"\bcreate\s+trigger\b",
        r"\bcreate\s+user\b",
        r"\bdrop\s+database\b",
        r"\bdrop\s+extension\b",
        r"\bdrop\s+role\b",
        r"\bdrop\s+schema\b",
        r"\bdrop\s+user\b",
    )

    assert not any(
        re.search(pattern, combined_sql)
        for pattern in forbidden_patterns
    )


def test_offline_generation_never_uses_runtime_settings_or_connections(
    offline_upgrade_sql: str,
    offline_downgrade_sql: str,
) -> None:
    assert offline_upgrade_sql
    assert offline_downgrade_sql


def test_telemetry_upgrade_has_exact_create_then_drop_operations(
    telemetry_upgrade_events: list[
        tuple[str, str, str, tuple[str, ...]]
    ],
) -> None:
    expected_creates = [
        ("create", index_name, table_name, expressions)
        for index_name, (table_name, expressions) in (
            EXPECTED_TELEMETRY_INDEXES.items()
        )
    ]
    expected_drops = [
        ("drop", index_name, table_name, ())
        for index_name, (table_name, _) in (
            EXPECTED_INITIAL_INDEXES.items()
        )
    ]

    assert telemetry_upgrade_events == [
        *expected_creates,
        *expected_drops,
    ]


def test_telemetry_downgrade_has_exact_recreate_then_drop_operations(
    telemetry_downgrade_events: list[
        tuple[str, str, str, tuple[str, ...]]
    ],
) -> None:
    expected_recreates = [
        ("create", index_name, table_name, expressions)
        for index_name, (table_name, expressions) in (
            EXPECTED_INITIAL_INDEXES.items()
        )
    ]
    expected_drops = [
        ("drop", index_name, table_name, ())
        for index_name, (table_name, _) in (
            EXPECTED_TELEMETRY_INDEXES.items()
        )
    ]

    assert telemetry_downgrade_events == [
        *expected_recreates,
        *expected_drops,
    ]


def test_telemetry_head_index_inventory_matches_orm_metadata() -> None:
    orm_indexes = {
        index.name: (
            table.name,
            tuple(
                _index_expression_signature(expression)
                for expression in index.expressions
            ),
            bool(index.unique),
        )
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    expected_indexes = {
        index_name: (table_name, expressions, False)
        for index_name, (table_name, expressions) in (
            EXPECTED_TELEMETRY_INDEXES.items()
        )
    }

    assert orm_indexes == expected_indexes
    assert not set(EXPECTED_INITIAL_INDEXES).intersection(orm_indexes)


def test_telemetry_revision_uses_only_index_operations(
    telemetry_revision_path: Path,
) -> None:
    syntax_tree = ast.parse(
        telemetry_revision_path.read_text(encoding="utf-8")
    )
    functions = {
        node.name: node
        for node in syntax_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"upgrade", "downgrade"}
    }
    assert set(functions) == {"upgrade", "downgrade"}

    for function in functions.values():
        operation_names = [
            node.func.attr
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "op"
        ]
        assert Counter(operation_names) == Counter(
            {"create_index": 4, "drop_index": 4}
        )


def test_offline_telemetry_upgrade_preserves_postgresql_index_contract(
    offline_telemetry_upgrade_sql: str,
) -> None:
    assert _ddl_names(
        offline_telemetry_upgrade_sql,
        "create",
        "index",
    ) == list(EXPECTED_TELEMETRY_INDEX_ORDER)
    assert _ddl_names(
        offline_telemetry_upgrade_sql,
        "drop",
        "index",
    ) == list(EXPECTED_INITIAL_INDEX_ORDER)

    normalized_sql = _normalized_sql(offline_telemetry_upgrade_sql)
    for index_name, (table_name, expressions) in (
        EXPECTED_TELEMETRY_INDEXES.items()
    ):
        definition = (
            f"create index {index_name} on {table_name} "
            f"({', '.join(expressions)})"
        )
        assert definition in normalized_sql

    assert "create unique index" not in normalized_sql


def test_offline_telemetry_downgrade_restores_postgresql_index_contract(
    offline_telemetry_downgrade_sql: str,
) -> None:
    assert _ddl_names(
        offline_telemetry_downgrade_sql,
        "create",
        "index",
    ) == list(EXPECTED_INITIAL_INDEX_ORDER)
    assert _ddl_names(
        offline_telemetry_downgrade_sql,
        "drop",
        "index",
    ) == list(EXPECTED_TELEMETRY_INDEX_ORDER)

    normalized_sql = _normalized_sql(offline_telemetry_downgrade_sql)
    for index_name, (table_name, expressions) in (
        EXPECTED_INITIAL_INDEXES.items()
    ):
        definition = (
            f"create index {index_name} on {table_name} "
            f"({', '.join(expressions)})"
        )
        assert definition in normalized_sql

    assert "create unique index" not in normalized_sql


def test_offline_telemetry_sql_contains_only_index_ddl(
    offline_telemetry_upgrade_sql: str,
    offline_telemetry_downgrade_sql: str,
) -> None:
    combined_sql = _normalized_sql(
        f"{offline_telemetry_upgrade_sql}\n"
        f"{offline_telemetry_downgrade_sql}"
    )

    assert not _ddl_names(combined_sql, "create", "table")
    assert not _ddl_names(combined_sql, "drop", "table")
    for object_type in (
        "database",
        "extension",
        "role",
        "schema",
        "trigger",
        "user",
    ):
        assert not re.search(
            rf"\b(?:create|drop)\s+{object_type}\b",
            combined_sql,
        )
