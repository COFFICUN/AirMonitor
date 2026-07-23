"""create initial AirMonitor schema

Revision ID: a4f9c2e7d1b6
Revises:
Create Date: 2026-07-23

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4f9c2e7d1b6"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the approved AirMonitor domain schema."""
    op.create_table(
        "devices",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "device_uid",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_uid",
            name="uq_devices_device_uid",
        ),
    )

    op.create_table(
        "measurement_sessions",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "device_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "latitude",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "longitude",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "sample_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "avg_temperature",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "avg_humidity",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "avg_pm1",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "avg_pm25",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "avg_pm10",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "min_pm25",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "max_pm25",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "aqi_pm25",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "aqi_category",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'cancelled')",
            name="ck_measurement_sessions_status",
        ),
        sa.CheckConstraint(
            "(status = 'active' AND ended_at IS NULL) "
            "OR (status IN ('completed', 'cancelled') "
            "AND ended_at IS NOT NULL)",
            name=(
                "ck_measurement_sessions_"
                "status_ended_at_consistency"
            ),
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_measurement_sessions_ended_at_order",
        ),
        sa.CheckConstraint(
            "sample_count >= 0",
            name="ck_measurement_sessions_sample_count_nonnegative",
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90",
            name="ck_measurement_sessions_latitude_range",
        ),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180",
            name="ck_measurement_sessions_longitude_range",
        ),
        sa.CheckConstraint(
            "avg_temperature IS NULL "
            "OR avg_temperature BETWEEN -40 AND 85",
            name="ck_measurement_sessions_avg_temperature_range",
        ),
        sa.CheckConstraint(
            "avg_humidity IS NULL OR avg_humidity BETWEEN 0 AND 100",
            name="ck_measurement_sessions_avg_humidity_range",
        ),
        sa.CheckConstraint(
            "avg_pm1 IS NULL OR avg_pm1 >= 0",
            name="ck_measurement_sessions_avg_pm1_nonnegative",
        ),
        sa.CheckConstraint(
            "avg_pm25 IS NULL OR avg_pm25 >= 0",
            name="ck_measurement_sessions_avg_pm25_nonnegative",
        ),
        sa.CheckConstraint(
            "avg_pm10 IS NULL OR avg_pm10 >= 0",
            name="ck_measurement_sessions_avg_pm10_nonnegative",
        ),
        sa.CheckConstraint(
            "min_pm25 IS NULL OR min_pm25 >= 0",
            name="ck_measurement_sessions_min_pm25_nonnegative",
        ),
        sa.CheckConstraint(
            "max_pm25 IS NULL OR max_pm25 >= 0",
            name="ck_measurement_sessions_max_pm25_nonnegative",
        ),
        sa.CheckConstraint(
            "min_pm25 IS NULL OR max_pm25 IS NULL "
            "OR min_pm25 <= max_pm25",
            name="ck_measurement_sessions_pm25_min_max_order",
        ),
        sa.CheckConstraint(
            "aqi_pm25 IS NULL OR aqi_pm25 BETWEEN 0 AND 500",
            name="ck_measurement_sessions_aqi_pm25_range",
        ),
        sa.ForeignKeyConstraint(
            ("device_id",),
            ("devices.id",),
            name="fk_measurement_sessions_device_id_devices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "device_id",
            name="uq_measurement_sessions_id_device_id",
        ),
    )

    op.create_table(
        "device_runtime_state",
        sa.Column(
            "device_id",
            sa.Integer(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "measurement_enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "active_session_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "fixed_latitude",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "fixed_longitude",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "measurement_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "location_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fixed_latitude IS NULL "
            "OR fixed_latitude BETWEEN -90 AND 90",
            name="ck_device_runtime_state_fixed_latitude_range",
        ),
        sa.CheckConstraint(
            "fixed_longitude IS NULL "
            "OR fixed_longitude BETWEEN -180 AND 180",
            name="ck_device_runtime_state_fixed_longitude_range",
        ),
        sa.CheckConstraint(
            "(fixed_latitude IS NULL AND fixed_longitude IS NULL) "
            "OR (fixed_latitude IS NOT NULL "
            "AND fixed_longitude IS NOT NULL)",
            name="ck_device_runtime_state_fixed_coordinates_paired",
        ),
        sa.ForeignKeyConstraint(
            ("active_session_id", "device_id"),
            (
                "measurement_sessions.id",
                "measurement_sessions.device_id",
            ),
            name="fk_device_runtime_state_active_session_device",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ("device_id",),
            ("devices.id",),
            name="fk_device_runtime_state_device_id_devices",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("device_id"),
        sa.UniqueConstraint(
            "active_session_id",
            name="uq_device_runtime_state_active_session_id",
        ),
    )

    op.create_table(
        "raw_measurements",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "device_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "source_message_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "measured_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "temperature",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "humidity",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "pm1",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "pm25",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "pm10",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "pc0_3",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "pc0_5",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "pc1_0",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "pc2_5",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "pc5_0",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "pc10",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "latitude",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "longitude",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "is_valid",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "validation_note",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "temperature IS NULL OR temperature BETWEEN -40 AND 85",
            name="ck_raw_measurements_temperature_range",
        ),
        sa.CheckConstraint(
            "humidity IS NULL OR humidity BETWEEN 0 AND 100",
            name="ck_raw_measurements_humidity_range",
        ),
        sa.CheckConstraint(
            "pm1 IS NULL OR pm1 >= 0",
            name="ck_raw_measurements_pm1_nonnegative",
        ),
        sa.CheckConstraint(
            "pm25 IS NULL OR pm25 >= 0",
            name="ck_raw_measurements_pm25_nonnegative",
        ),
        sa.CheckConstraint(
            "pm10 IS NULL OR pm10 >= 0",
            name="ck_raw_measurements_pm10_nonnegative",
        ),
        sa.CheckConstraint(
            "pc0_3 IS NULL OR pc0_3 >= 0",
            name="ck_raw_measurements_pc0_3_nonnegative",
        ),
        sa.CheckConstraint(
            "pc0_5 IS NULL OR pc0_5 >= 0",
            name="ck_raw_measurements_pc0_5_nonnegative",
        ),
        sa.CheckConstraint(
            "pc1_0 IS NULL OR pc1_0 >= 0",
            name="ck_raw_measurements_pc1_0_nonnegative",
        ),
        sa.CheckConstraint(
            "pc2_5 IS NULL OR pc2_5 >= 0",
            name="ck_raw_measurements_pc2_5_nonnegative",
        ),
        sa.CheckConstraint(
            "pc5_0 IS NULL OR pc5_0 >= 0",
            name="ck_raw_measurements_pc5_0_nonnegative",
        ),
        sa.CheckConstraint(
            "pc10 IS NULL OR pc10 >= 0",
            name="ck_raw_measurements_pc10_nonnegative",
        ),
        sa.CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_raw_measurements_latitude_range",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="ck_raw_measurements_longitude_range",
        ),
        sa.CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) "
            "OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_raw_measurements_coordinates_paired",
        ),
        sa.ForeignKeyConstraint(
            ("device_id",),
            ("devices.id",),
            name="fk_raw_measurements_device_id_devices",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ("session_id", "device_id"),
            (
                "measurement_sessions.id",
                "measurement_sessions.device_id",
            ),
            name="fk_raw_measurements_session_device",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id",
            "source_message_id",
            name=(
                "uq_raw_measurements_"
                "device_id_source_message_id"
            ),
        ),
    )

    op.create_index(
        "ix_measurement_sessions_device_id_started_at",
        "measurement_sessions",
        ("device_id", "started_at"),
        unique=False,
    )
    op.create_index(
        "ix_measurement_sessions_device_id_status",
        "measurement_sessions",
        ("device_id", "status"),
        unique=False,
    )
    op.create_index(
        "ix_raw_measurements_device_id_measured_at",
        "raw_measurements",
        ("device_id", "measured_at"),
        unique=False,
    )
    op.create_index(
        "ix_raw_measurements_session_id_measured_at",
        "raw_measurements",
        ("session_id", "measured_at"),
        unique=False,
    )


def downgrade() -> None:
    """Remove the approved AirMonitor domain schema."""
    op.drop_index(
        "ix_raw_measurements_session_id_measured_at",
        table_name="raw_measurements",
    )
    op.drop_index(
        "ix_raw_measurements_device_id_measured_at",
        table_name="raw_measurements",
    )
    op.drop_index(
        "ix_measurement_sessions_device_id_status",
        table_name="measurement_sessions",
    )
    op.drop_index(
        "ix_measurement_sessions_device_id_started_at",
        table_name="measurement_sessions",
    )
    op.drop_table("raw_measurements")
    op.drop_table("device_runtime_state")
    op.drop_table("measurement_sessions")
    op.drop_table("devices")
