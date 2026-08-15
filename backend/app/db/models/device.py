"""Device identity and mutable runtime-state models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    false,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.db.models.measurement import RawMeasurement
    from app.db.models.measurement_session import MeasurementSession


class Device(Base):
    """A physical monitor with a stable public identifier."""

    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("device_uid", name="uq_devices_device_uid"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
    )
    device_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
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

    runtime_state: Mapped[DeviceRuntimeState | None] = relationship(
        "DeviceRuntimeState",
        back_populates="device",
        cascade="all, delete-orphan",
        foreign_keys="DeviceRuntimeState.device_id",
        passive_deletes=True,
        single_parent=True,
        uselist=False,
    )
    sessions: Mapped[list[MeasurementSession]] = relationship(
        "MeasurementSession",
        back_populates="device",
        cascade="save-update, merge",
        foreign_keys="MeasurementSession.device_id",
        passive_deletes="all",
    )
    raw_measurements: Mapped[list[RawMeasurement]] = relationship(
        "RawMeasurement",
        back_populates="device",
        cascade="save-update, merge",
        foreign_keys="RawMeasurement.device_id",
        passive_deletes="all",
    )


class DeviceRuntimeState(Base):
    """Replaceable operational state with no independent history."""

    __tablename__ = "device_runtime_state"
    __table_args__ = (
        UniqueConstraint(
            "active_session_id",
            name="uq_device_runtime_state_active_session_id",
        ),
        # Portable composite SET NULL would also null the device primary key.
        ForeignKeyConstraint(
            ("active_session_id", "device_id"),
            ("measurement_sessions.id", "measurement_sessions.device_id"),
            name="fk_device_runtime_state_active_session_device",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "fixed_latitude IS NULL "
            "OR fixed_latitude BETWEEN -90 AND 90",
            name="ck_device_runtime_state_fixed_latitude_range",
        ),
        CheckConstraint(
            "fixed_longitude IS NULL "
            "OR fixed_longitude BETWEEN -180 AND 180",
            name="ck_device_runtime_state_fixed_longitude_range",
        ),
        CheckConstraint(
            "(fixed_latitude IS NULL AND fixed_longitude IS NULL) "
            "OR (fixed_latitude IS NOT NULL "
            "AND fixed_longitude IS NOT NULL)",
            name="ck_device_runtime_state_fixed_coordinates_paired",
        ),
    )

    device_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "devices.id",
            name="fk_device_runtime_state_device_id_devices",
            ondelete="CASCADE",
        ),
        primary_key=True,
        autoincrement=False,
        nullable=False,
    )
    measurement_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    active_session_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    fixed_latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    fixed_longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    measurement_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    location_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
        back_populates="runtime_state",
        foreign_keys=[device_id],
    )
    active_session: Mapped[MeasurementSession | None] = relationship(
        "MeasurementSession",
        back_populates="active_runtime_state",
        cascade="save-update, merge",
        foreign_keys=[active_session_id],
    )
