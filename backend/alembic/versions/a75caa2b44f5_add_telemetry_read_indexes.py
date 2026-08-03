"""add telemetry read indexes

Revision ID: a75caa2b44f5
Revises: a4f9c2e7d1b6
Create Date: 2026-08-03 14:58:17.818112

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a75caa2b44f5"
down_revision: Union[str, Sequence[str], None] = "a4f9c2e7d1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace telemetry indexes with stable keyset-order coverage."""
    op.create_index(
        "ix_measurement_sessions_device_id_started_at_id_desc",
        "measurement_sessions",
        (
            "device_id",
            sa.column("started_at").desc(),
            sa.column("id").desc(),
        ),
        unique=False,
    )
    op.create_index(
        "ix_measurement_sessions_device_id_status_started_at_id_desc",
        "measurement_sessions",
        (
            "device_id",
            "status",
            sa.column("started_at").desc(),
            sa.column("id").desc(),
        ),
        unique=False,
    )
    op.create_index(
        "ix_raw_measurements_device_id_measured_at_id_desc",
        "raw_measurements",
        (
            "device_id",
            sa.column("measured_at").desc(),
            sa.column("id").desc(),
        ),
        unique=False,
    )
    op.create_index(
        "ix_raw_measurements_session_id_measured_at_id_desc",
        "raw_measurements",
        (
            "session_id",
            sa.column("measured_at").desc(),
            sa.column("id").desc(),
        ),
        unique=False,
    )

    op.drop_index(
        "ix_measurement_sessions_device_id_started_at",
        table_name="measurement_sessions",
    )
    op.drop_index(
        "ix_measurement_sessions_device_id_status",
        table_name="measurement_sessions",
    )
    op.drop_index(
        "ix_raw_measurements_device_id_measured_at",
        table_name="raw_measurements",
    )
    op.drop_index(
        "ix_raw_measurements_session_id_measured_at",
        table_name="raw_measurements",
    )


def downgrade() -> None:
    """Restore the original telemetry index inventory."""
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

    op.drop_index(
        "ix_measurement_sessions_device_id_started_at_id_desc",
        table_name="measurement_sessions",
    )
    op.drop_index(
        "ix_measurement_sessions_device_id_status_started_at_id_desc",
        table_name="measurement_sessions",
    )
    op.drop_index(
        "ix_raw_measurements_device_id_measured_at_id_desc",
        table_name="raw_measurements",
    )
    op.drop_index(
        "ix_raw_measurements_session_id_measured_at_id_desc",
        table_name="raw_measurements",
    )
