"""Measurement-session ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.db.models.device import Device, DeviceRuntimeState
    from app.db.models.measurement import RawMeasurement


class MeasurementSession(Base):
    """A device sampling interval and its rolling summary values."""

    __tablename__ = "measurement_sessions"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "device_id",
            name="uq_measurement_sessions_id_device_id",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'cancelled')",
            name="ck_measurement_sessions_status",
        ),
        CheckConstraint(
            "(status = 'active' AND ended_at IS NULL) "
            "OR (status IN ('completed', 'cancelled') "
            "AND ended_at IS NOT NULL)",
            name="ck_measurement_sessions_status_ended_at_consistency",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_measurement_sessions_ended_at_order",
        ),
        CheckConstraint(
            "sample_count >= 0",
            name="ck_measurement_sessions_sample_count_nonnegative",
        ),
        CheckConstraint(
            "latitude BETWEEN -90 AND 90",
            name="ck_measurement_sessions_latitude_range",
        ),
        CheckConstraint(
            "longitude BETWEEN -180 AND 180",
            name="ck_measurement_sessions_longitude_range",
        ),
        CheckConstraint(
            "avg_temperature IS NULL "
            "OR avg_temperature BETWEEN -40 AND 85",
            name="ck_measurement_sessions_avg_temperature_range",
        ),
        CheckConstraint(
            "avg_humidity IS NULL OR avg_humidity BETWEEN 0 AND 100",
            name="ck_measurement_sessions_avg_humidity_range",
        ),
        CheckConstraint(
            "avg_pm1 IS NULL OR avg_pm1 >= 0",
            name="ck_measurement_sessions_avg_pm1_nonnegative",
        ),
        CheckConstraint(
            "avg_pm25 IS NULL OR avg_pm25 >= 0",
            name="ck_measurement_sessions_avg_pm25_nonnegative",
        ),
        CheckConstraint(
            "avg_pm10 IS NULL OR avg_pm10 >= 0",
            name="ck_measurement_sessions_avg_pm10_nonnegative",
        ),
        CheckConstraint(
            "min_pm25 IS NULL OR min_pm25 >= 0",
            name="ck_measurement_sessions_min_pm25_nonnegative",
        ),
        CheckConstraint(
            "max_pm25 IS NULL OR max_pm25 >= 0",
            name="ck_measurement_sessions_max_pm25_nonnegative",
        ),
        CheckConstraint(
            "min_pm25 IS NULL OR max_pm25 IS NULL "
            "OR min_pm25 <= max_pm25",
            name="ck_measurement_sessions_pm25_min_max_order",
        ),
        CheckConstraint(
            "aqi_pm25 IS NULL OR aqi_pm25 BETWEEN 0 AND 500",
            name="ck_measurement_sessions_aqi_pm25_range",
        ),
        Index(
            "ix_measurement_sessions_device_id_started_at",
            "device_id",
            "started_at",
        ),
        Index(
            "ix_measurement_sessions_device_id_status",
            "device_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
    )
    device_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "devices.id",
            name="fk_measurement_sessions_device_id_devices",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    avg_temperature: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    avg_humidity: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    avg_pm1: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_pm25: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_pm10: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_pm25: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_pm25: Mapped[float | None] = mapped_column(Float, nullable=True)
    aqi_pm25: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aqi_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    device: Mapped[Device] = relationship(
        "Device",
        back_populates="sessions",
        foreign_keys=[device_id],
    )
    raw_measurements: Mapped[list[RawMeasurement]] = relationship(
        "RawMeasurement",
        back_populates="session",
        cascade="save-update, merge",
        foreign_keys="RawMeasurement.session_id",
        passive_deletes="all",
    )
    active_runtime_state: Mapped[DeviceRuntimeState | None] = relationship(
        "DeviceRuntimeState",
        back_populates="active_session",
        cascade="save-update, merge",
        foreign_keys="DeviceRuntimeState.active_session_id",
        passive_deletes="all",
        uselist=False,
    )
