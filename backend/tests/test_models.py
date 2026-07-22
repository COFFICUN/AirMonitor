"""Metadata-only tests for the AirMonitor relational domain model."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    inspect,
)

from app.db.base import Base
from app.db.models import (
    Device,
    DeviceRuntimeState,
    MeasurementSession,
    RawMeasurement,
)


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]

EXPECTED_COLUMNS = {
    "devices": {
        "id",
        "device_uid",
        "name",
        "is_active",
        "created_at",
        "updated_at",
    },
    "device_runtime_state": {
        "device_id",
        "measurement_enabled",
        "active_session_id",
        "fixed_latitude",
        "fixed_longitude",
        "measurement_started_at",
        "location_updated_at",
        "last_seen_at",
        "updated_at",
    },
    "measurement_sessions": {
        "id",
        "device_id",
        "status",
        "started_at",
        "ended_at",
        "latitude",
        "longitude",
        "sample_count",
        "avg_temperature",
        "avg_humidity",
        "avg_pm1",
        "avg_pm25",
        "avg_pm10",
        "min_pm25",
        "max_pm25",
        "aqi_pm25",
        "aqi_category",
        "created_at",
        "updated_at",
    },
    "raw_measurements": {
        "id",
        "device_id",
        "session_id",
        "source_message_id",
        "measured_at",
        "received_at",
        "temperature",
        "humidity",
        "pm1",
        "pm25",
        "pm10",
        "pc0_3",
        "pc0_5",
        "pc1_0",
        "pc2_5",
        "pc5_0",
        "pc10",
        "latitude",
        "longitude",
        "is_valid",
        "validation_note",
        "created_at",
    },
}

NULLABLE_COLUMNS = {
    "devices": {"name"},
    "device_runtime_state": {
        "active_session_id",
        "fixed_latitude",
        "fixed_longitude",
        "measurement_started_at",
        "location_updated_at",
        "last_seen_at",
    },
    "measurement_sessions": {
        "ended_at",
        "avg_temperature",
        "avg_humidity",
        "avg_pm1",
        "avg_pm25",
        "avg_pm10",
        "min_pm25",
        "max_pm25",
        "aqi_pm25",
        "aqi_category",
    },
    "raw_measurements": {
        "source_message_id",
        "temperature",
        "humidity",
        "pm1",
        "pm25",
        "pm10",
        "pc0_3",
        "pc0_5",
        "pc1_0",
        "pc2_5",
        "pc5_0",
        "pc10",
        "latitude",
        "longitude",
        "validation_note",
    },
}

TIMESTAMP_COLUMNS = {
    "devices": {"created_at", "updated_at"},
    "device_runtime_state": {
        "measurement_started_at",
        "location_updated_at",
        "last_seen_at",
        "updated_at",
    },
    "measurement_sessions": {
        "started_at",
        "ended_at",
        "created_at",
        "updated_at",
    },
    "raw_measurements": {"measured_at", "received_at", "created_at"},
}

EXPECTED_CHECK_SQL = {
    "device_runtime_state": {
        "ck_device_runtime_state_fixed_latitude_range": (
            "fixed_latitude is null or fixed_latitude between -90 and 90"
        ),
        "ck_device_runtime_state_fixed_longitude_range": (
            "fixed_longitude is null or fixed_longitude between -180 and 180"
        ),
        "ck_device_runtime_state_fixed_coordinates_paired": (
            "(fixed_latitude is null and fixed_longitude is null) "
            "or (fixed_latitude is not null and fixed_longitude is not null)"
        ),
    },
    "measurement_sessions": {
        "ck_measurement_sessions_status": (
            "status in ('active', 'completed', 'cancelled')"
        ),
        "ck_measurement_sessions_status_ended_at_consistency": (
            "(status = 'active' and ended_at is null) "
            "or (status in ('completed', 'cancelled') "
            "and ended_at is not null)"
        ),
        "ck_measurement_sessions_ended_at_order": (
            "ended_at is null or ended_at >= started_at"
        ),
        "ck_measurement_sessions_sample_count_nonnegative": (
            "sample_count >= 0"
        ),
        "ck_measurement_sessions_latitude_range": (
            "latitude between -90 and 90"
        ),
        "ck_measurement_sessions_longitude_range": (
            "longitude between -180 and 180"
        ),
        "ck_measurement_sessions_avg_temperature_range": (
            "avg_temperature is null or avg_temperature between -40 and 85"
        ),
        "ck_measurement_sessions_avg_humidity_range": (
            "avg_humidity is null or avg_humidity between 0 and 100"
        ),
        "ck_measurement_sessions_avg_pm1_nonnegative": (
            "avg_pm1 is null or avg_pm1 >= 0"
        ),
        "ck_measurement_sessions_avg_pm25_nonnegative": (
            "avg_pm25 is null or avg_pm25 >= 0"
        ),
        "ck_measurement_sessions_avg_pm10_nonnegative": (
            "avg_pm10 is null or avg_pm10 >= 0"
        ),
        "ck_measurement_sessions_min_pm25_nonnegative": (
            "min_pm25 is null or min_pm25 >= 0"
        ),
        "ck_measurement_sessions_max_pm25_nonnegative": (
            "max_pm25 is null or max_pm25 >= 0"
        ),
        "ck_measurement_sessions_pm25_min_max_order": (
            "min_pm25 is null or max_pm25 is null or min_pm25 <= max_pm25"
        ),
        "ck_measurement_sessions_aqi_pm25_range": (
            "aqi_pm25 is null or aqi_pm25 between 0 and 500"
        ),
    },
    "raw_measurements": {
        "ck_raw_measurements_temperature_range": (
            "temperature is null or temperature between -40 and 85"
        ),
        "ck_raw_measurements_humidity_range": (
            "humidity is null or humidity between 0 and 100"
        ),
        "ck_raw_measurements_pm1_nonnegative": "pm1 is null or pm1 >= 0",
        "ck_raw_measurements_pm25_nonnegative": "pm25 is null or pm25 >= 0",
        "ck_raw_measurements_pm10_nonnegative": "pm10 is null or pm10 >= 0",
        "ck_raw_measurements_pc0_3_nonnegative": "pc0_3 is null or pc0_3 >= 0",
        "ck_raw_measurements_pc0_5_nonnegative": "pc0_5 is null or pc0_5 >= 0",
        "ck_raw_measurements_pc1_0_nonnegative": "pc1_0 is null or pc1_0 >= 0",
        "ck_raw_measurements_pc2_5_nonnegative": "pc2_5 is null or pc2_5 >= 0",
        "ck_raw_measurements_pc5_0_nonnegative": "pc5_0 is null or pc5_0 >= 0",
        "ck_raw_measurements_pc10_nonnegative": "pc10 is null or pc10 >= 0",
        "ck_raw_measurements_latitude_range": (
            "latitude is null or latitude between -90 and 90"
        ),
        "ck_raw_measurements_longitude_range": (
            "longitude is null or longitude between -180 and 180"
        ),
        "ck_raw_measurements_coordinates_paired": (
            "(latitude is null and longitude is null) "
            "or (latitude is not null and longitude is not null)"
        ),
    },
}


def unique_constraints(
    table_name: str,
) -> set[tuple[str | None, tuple[str, ...]]]:
    """Return every unique constraint with its name and ordered columns."""
    table = Base.metadata.tables[table_name]
    return {
        (
            constraint.name,
            tuple(column.name for column in constraint.columns),
        )
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def named_check_constraints(table_name: str) -> dict[str, str]:
    """Return normalized SQL text for each named check constraint."""
    table = Base.metadata.tables[table_name]
    return {
        constraint.name: " ".join(str(constraint.sqltext).lower().split())
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name is not None
    }


def normalized_default(default: object) -> bool | int | str:
    """Normalize scalar and SQL-expression defaults for stable assertions."""
    argument = getattr(default, "arg")
    if isinstance(argument, (bool, int, str)):
        return argument
    return " ".join(str(argument).lower().split())


def test_model_package_registers_only_approved_tables() -> None:
    expected_tables = {
        "devices",
        "device_runtime_state",
        "measurement_sessions",
        "raw_measurements",
    }

    assert set(Base.metadata.tables) == expected_tables
    assert not {
        "measurements",
        "raw_session_links",
        "aggregated_measurements",
    }.intersection(Base.metadata.tables)


@pytest.mark.parametrize(
    ("model", "table_name"),
    [
        (Device, "devices"),
        (DeviceRuntimeState, "device_runtime_state"),
        (MeasurementSession, "measurement_sessions"),
        (RawMeasurement, "raw_measurements"),
    ],
)
def test_models_map_to_expected_tables(model: type[Base], table_name: str) -> None:
    assert model.__tablename__ == table_name
    assert inspect(model).local_table is Base.metadata.tables[table_name]


@pytest.mark.parametrize("table_name", EXPECTED_COLUMNS)
def test_tables_have_exact_columns(table_name: str) -> None:
    table = Base.metadata.tables[table_name]

    assert set(table.columns.keys()) == EXPECTED_COLUMNS[table_name]
    assert {column.name for column in table.columns if column.nullable} == (
        NULLABLE_COLUMNS[table_name]
    )


@pytest.mark.parametrize(
    ("table_name", "primary_key"),
    [
        ("devices", ("id",)),
        ("device_runtime_state", ("device_id",)),
        ("measurement_sessions", ("id",)),
        ("raw_measurements", ("id",)),
    ],
)
def test_primary_keys_are_explicit(
    table_name: str,
    primary_key: tuple[str, ...],
) -> None:
    table = Base.metadata.tables[table_name]

    assert tuple(column.name for column in table.primary_key.columns) == primary_key


def test_foreign_keys_have_expected_targets_names_and_delete_rules() -> None:
    expected_foreign_keys = {
        (
            "device_runtime_state",
            "fk_device_runtime_state_device_id_devices",
            ("device_id",),
            ("devices.id",),
            "CASCADE",
        ),
        (
            "device_runtime_state",
            "fk_device_runtime_state_active_session_device",
            ("active_session_id", "device_id"),
            ("measurement_sessions.id", "measurement_sessions.device_id"),
            "RESTRICT",
        ),
        (
            "measurement_sessions",
            "fk_measurement_sessions_device_id_devices",
            ("device_id",),
            ("devices.id",),
            "RESTRICT",
        ),
        (
            "raw_measurements",
            "fk_raw_measurements_device_id_devices",
            ("device_id",),
            ("devices.id",),
            "RESTRICT",
        ),
        (
            "raw_measurements",
            "fk_raw_measurements_session_device",
            ("session_id", "device_id"),
            ("measurement_sessions.id", "measurement_sessions.device_id"),
            "RESTRICT",
        ),
    }

    actual_foreign_keys = {
        (
            table.name,
            constraint.name,
            tuple(column.name for column in constraint.columns),
            tuple(element.target_fullname for element in constraint.elements),
            constraint.ondelete,
        )
        for table in Base.metadata.tables.values()
        for constraint in table.foreign_key_constraints
    }

    assert actual_foreign_keys == expected_foreign_keys


def test_relationship_cardinalities_and_inverse_mappings() -> None:
    expected_relationships = [
        (Device, "runtime_state", DeviceRuntimeState, False, "device"),
        (Device, "sessions", MeasurementSession, True, "device"),
        (Device, "raw_measurements", RawMeasurement, True, "device"),
        (DeviceRuntimeState, "device", Device, False, "runtime_state"),
        (
            DeviceRuntimeState,
            "active_session",
            MeasurementSession,
            False,
            "active_runtime_state",
        ),
        (MeasurementSession, "device", Device, False, "sessions"),
        (
            MeasurementSession,
            "raw_measurements",
            RawMeasurement,
            True,
            "session",
        ),
        (
            MeasurementSession,
            "active_runtime_state",
            DeviceRuntimeState,
            False,
            "active_session",
        ),
        (RawMeasurement, "device", Device, False, "raw_measurements"),
        (RawMeasurement, "session", MeasurementSession, False, "raw_measurements"),
    ]

    for model, name, target, uselist, back_populates in expected_relationships:
        relationship = inspect(model).relationships[name]
        assert relationship.mapper.class_ is target
        assert relationship.uselist is uselist
        assert relationship.back_populates == back_populates


def test_only_runtime_state_uses_orm_delete_cascade() -> None:
    runtime_relationship = inspect(Device).relationships["runtime_state"]
    assert "delete" in runtime_relationship.cascade
    assert "delete-orphan" in runtime_relationship.cascade
    assert runtime_relationship.passive_deletes is True
    assert runtime_relationship.single_parent is True

    historical_collections = [
        inspect(Device).relationships["sessions"],
        inspect(Device).relationships["raw_measurements"],
        inspect(MeasurementSession).relationships["raw_measurements"],
        inspect(MeasurementSession).relationships["active_runtime_state"],
    ]
    for relationship in historical_collections:
        assert relationship.passive_deletes == "all"

    for model in (Device, DeviceRuntimeState, MeasurementSession, RawMeasurement):
        for relationship in inspect(model).relationships:
            if model is Device and relationship.key == "runtime_state":
                continue
            assert "delete" not in relationship.cascade
            assert "delete-orphan" not in relationship.cascade


def test_composite_session_relationships_have_distinct_write_columns() -> None:
    expected_write_columns = [
        (RawMeasurement, "device", {"device_id"}),
        (RawMeasurement, "session", {"session_id"}),
        (DeviceRuntimeState, "device", {"device_id"}),
        (DeviceRuntimeState, "active_session", {"active_session_id"}),
    ]

    for model, relationship_name, expected_columns in expected_write_columns:
        relationship = inspect(model).relationships[relationship_name]
        actual_columns = {
            local_column.name
            for _, local_column in relationship.synchronize_pairs
        }
        assert actual_columns == expected_columns


def test_unique_constraints_support_identity_and_duplicate_protection() -> None:
    actual_constraints = {
        (table_name, constraint_name, columns)
        for table_name in Base.metadata.tables
        for constraint_name, columns in unique_constraints(table_name)
    }
    assert actual_constraints == {
        ("devices", "uq_devices_device_uid", ("device_uid",)),
        (
            "device_runtime_state",
            "uq_device_runtime_state_active_session_id",
            ("active_session_id",),
        ),
        (
            "measurement_sessions",
            "uq_measurement_sessions_id_device_id",
            ("id", "device_id"),
        ),
        (
            "raw_measurements",
            "uq_raw_measurements_device_id_source_message_id",
            ("device_id", "source_message_id"),
        ),
    }
    assert Base.metadata.tables["raw_measurements"].c.source_message_id.nullable


def test_expected_indexes_are_present_without_unique_constraint_duplicates() -> None:
    expected_indexes = {
        "ix_measurement_sessions_device_id_started_at": (
            "device_id",
            "started_at",
        ),
        "ix_measurement_sessions_device_id_status": ("device_id", "status"),
        "ix_raw_measurements_device_id_measured_at": (
            "device_id",
            "measured_at",
        ),
        "ix_raw_measurements_session_id_measured_at": (
            "session_id",
            "measured_at",
        ),
    }
    actual_indexes = {
        index.name: tuple(column.name for column in index.columns)
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }

    assert actual_indexes == expected_indexes
    assert all(
        index.unique is False
        for table in Base.metadata.tables.values()
        for index in table.indexes
    )

    unique_signatures = {
        columns
        for table_name in Base.metadata.tables
        for _, columns in unique_constraints(table_name)
    }
    assert not unique_signatures.intersection(actual_indexes.values())


def test_all_timestamp_columns_are_timezone_aware() -> None:
    actual_timestamps = {}
    for table_name, table in Base.metadata.tables.items():
        timestamp_names = {
            column.name
            for column in table.columns
            if isinstance(column.type, DateTime)
        }
        actual_timestamps[table_name] = timestamp_names
        for column_name in timestamp_names:
            assert table.c[column_name].type.timezone is True

    assert actual_timestamps == TIMESTAMP_COLUMNS
    assert Base.metadata.tables["measurement_sessions"].c.ended_at.nullable


def test_columns_use_expected_portable_value_types() -> None:
    expected_integer_columns = {
        "devices": {"id"},
        "device_runtime_state": {"device_id", "active_session_id"},
        "measurement_sessions": {"id", "device_id", "sample_count", "aqi_pm25"},
        "raw_measurements": {
            "id",
            "device_id",
            "session_id",
            "pc0_3",
            "pc0_5",
            "pc1_0",
            "pc2_5",
            "pc5_0",
            "pc10",
        },
    }
    expected_float_columns = {
        "device_runtime_state": {"fixed_latitude", "fixed_longitude"},
        "measurement_sessions": {
            "latitude",
            "longitude",
            "avg_temperature",
            "avg_humidity",
            "avg_pm1",
            "avg_pm25",
            "avg_pm10",
            "min_pm25",
            "max_pm25",
        },
        "raw_measurements": {
            "temperature",
            "humidity",
            "pm1",
            "pm25",
            "pm10",
            "latitude",
            "longitude",
        },
    }

    for table_name, columns in expected_integer_columns.items():
        table = Base.metadata.tables[table_name]
        assert all(isinstance(table.c[name].type, Integer) for name in columns)

    for table_name, columns in expected_float_columns.items():
        table = Base.metadata.tables[table_name]
        assert all(isinstance(table.c[name].type, Float) for name in columns)

    assert isinstance(Base.metadata.tables["devices"].c.is_active.type, Boolean)
    assert isinstance(
        Base.metadata.tables["device_runtime_state"].c.measurement_enabled.type,
        Boolean,
    )
    assert isinstance(
        Base.metadata.tables["raw_measurements"].c.is_valid.type,
        Boolean,
    )
    assert type(Base.metadata.tables["raw_measurements"].c.validation_note.type) is Text
    for table_name, column_name in [
        ("devices", "device_uid"),
        ("devices", "name"),
        ("measurement_sessions", "status"),
        ("measurement_sessions", "aqi_category"),
        ("raw_measurements", "source_message_id"),
    ]:
        assert isinstance(
            Base.metadata.tables[table_name].c[column_name].type,
            String,
        )


def test_defaults_cover_direct_inserts_and_orm_updates() -> None:
    expected_defaults = {
        ("devices", "is_active"): (True, "true"),
        ("devices", "created_at"): ("now()", "now()"),
        ("devices", "updated_at"): ("now()", "now()"),
        ("device_runtime_state", "measurement_enabled"): (False, "false"),
        ("device_runtime_state", "updated_at"): ("now()", "now()"),
        ("measurement_sessions", "status"): ("active", "active"),
        ("measurement_sessions", "started_at"): ("now()", "now()"),
        ("measurement_sessions", "sample_count"): (0, "0"),
        ("measurement_sessions", "created_at"): ("now()", "now()"),
        ("measurement_sessions", "updated_at"): ("now()", "now()"),
        ("raw_measurements", "received_at"): ("now()", "now()"),
        ("raw_measurements", "is_valid"): (True, "true"),
        ("raw_measurements", "created_at"): ("now()", "now()"),
    }

    actual_python_defaults = {
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if column.default is not None
    }
    actual_server_defaults = {
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if column.server_default is not None
    }
    assert actual_python_defaults == set(expected_defaults)
    assert actual_server_defaults == set(expected_defaults)

    for (table_name, column_name), expected in expected_defaults.items():
        column = Base.metadata.tables[table_name].c[column_name]
        assert normalized_default(column.default) == expected[0]
        assert normalized_default(column.server_default) == expected[1]

    for table_name in ("devices", "device_runtime_state", "measurement_sessions"):
        onupdate = Base.metadata.tables[table_name].c.updated_at.onupdate
        assert onupdate is not None
        assert normalized_default(onupdate) == "now()"

    measured_at = Base.metadata.tables["raw_measurements"].c.measured_at
    assert measured_at.default is None
    assert measured_at.server_default is None


def test_check_constraints_cover_approved_integrity_rules() -> None:
    assert all(
        constraint.name is not None
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert named_check_constraints("devices") == {}
    assert {
        table_name: named_check_constraints(table_name)
        for table_name in EXPECTED_CHECK_SQL
    } == EXPECTED_CHECK_SQL


def test_model_import_has_no_engine_session_or_connection_side_effects() -> None:
    script = dedent(
        """
        from contextlib import ExitStack
        from importlib import import_module
        import sys
        from types import ModuleType
        from unittest.mock import Mock
        from unittest.mock import patch

        session_module = ModuleType("app.db.session")
        session_mocks = {
            name: Mock(name=name)
            for name in (
                "create_async_engine",
                "create_database_engine",
                "create_session_factory",
                "get_database_engine",
                "get_session_factory",
            )
        }
        for name, mock in session_mocks.items():
            setattr(session_module, name, mock)
        sys.modules["app.db.session"] = session_module

        asyncpg_module = ModuleType("asyncpg")
        asyncpg_connect = Mock(name="asyncpg_connect")
        asyncpg_module.connect = asyncpg_connect
        sys.modules["asyncpg"] = asyncpg_module

        targets = (
            "sqlalchemy.create_engine",
            "sqlalchemy.engine_from_config",
            "sqlalchemy.ext.asyncio.create_async_engine",
            "sqlalchemy.ext.asyncio.async_engine_from_config",
            "sqlalchemy.orm.sessionmaker",
            "sqlalchemy.ext.asyncio.async_sessionmaker",
            "sqlalchemy.sql.schema.MetaData.create_all",
            "sqlalchemy.engine.Engine.connect",
            "sqlalchemy.ext.asyncio.AsyncEngine.connect",
        )

        with ExitStack() as stack:
            mocks = [stack.enter_context(patch(target)) for target in targets]
            import_module("app.db.models")

        called_targets = [
            target for target, mock in zip(targets, mocks, strict=True)
            if mock.called
        ]
        called_targets.extend(
            name for name, mock in session_mocks.items() if mock.called
        )
        if asyncpg_connect.called:
            called_targets.append("asyncpg.connect")
        if called_targets:
            raise AssertionError(called_targets)
        """
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIRECTORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr


def test_mapper_configuration_emits_no_sqlalchemy_warnings() -> None:
    script = dedent(
        """
        import warnings

        from sqlalchemy.exc import SAWarning
        from sqlalchemy.orm import configure_mappers

        warnings.simplefilter("error", SAWarning)

        import app.db.models

        configure_mappers()
        """
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIRECTORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr


def test_no_alembic_revision_exists() -> None:
    revision_files = sorted(
        path.name
        for path in (BACKEND_DIRECTORY / "alembic" / "versions").glob("*.py")
        if path.name != "__init__.py"
    )

    assert revision_files == []
