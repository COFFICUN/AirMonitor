"""Raw sensor-measurement ORM model."""

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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.db.models.device import Device
    from app.db.models.measurement_session import MeasurementSession


class RawMeasurement(Base):
    """An immutable sensor reading received from one device session."""

    __tablename__ = "raw_measurements"
    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "source_message_id",
            name="uq_raw_measurements_device_id_source_message_id",
        ),
        ForeignKeyConstraint(
            ("session_id", "device_id"),
            ("measurement_sessions.id", "measurement_sessions.device_id"),
            name="fk_raw_measurements_session_device",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "temperature IS NULL OR temperature BETWEEN -40 AND 85",
            name="ck_raw_measurements_temperature_range",
        ),
        CheckConstraint(
            "humidity IS NULL OR humidity BETWEEN 0 AND 100",
            name="ck_raw_measurements_humidity_range",
        ),
        CheckConstraint(
            "pm1 IS NULL OR pm1 >= 0",
            name="ck_raw_measurements_pm1_nonnegative",
        ),
        CheckConstraint(
            "pm25 IS NULL OR pm25 >= 0",
            name="ck_raw_measurements_pm25_nonnegative",
        ),
        CheckConstraint(
            "pm10 IS NULL OR pm10 >= 0",
            name="ck_raw_measurements_pm10_nonnegative",
        ),
        CheckConstraint(
            "pc0_3 IS NULL OR pc0_3 >= 0",
            name="ck_raw_measurements_pc0_3_nonnegative",
        ),
        CheckConstraint(
            "pc0_5 IS NULL OR pc0_5 >= 0",
            name="ck_raw_measurements_pc0_5_nonnegative",
        ),
        CheckConstraint(
            "pc1_0 IS NULL OR pc1_0 >= 0",
            name="ck_raw_measurements_pc1_0_nonnegative",
        ),
        CheckConstraint(
            "pc2_5 IS NULL OR pc2_5 >= 0",
            name="ck_raw_measurements_pc2_5_nonnegative",
        ),
        CheckConstraint(
            "pc5_0 IS NULL OR pc5_0 >= 0",
            name="ck_raw_measurements_pc5_0_nonnegative",
        ),
        CheckConstraint(
            "pc10 IS NULL OR pc10 >= 0",
            name="ck_raw_measurements_pc10_nonnegative",
        ),
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_raw_measurements_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="ck_raw_measurements_longitude_range",
        ),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) "
            "OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_raw_measurements_coordinates_paired",
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
            name="fk_raw_measurements_device_id_devices",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    session_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    source_message_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    pm1: Mapped[float | None] = mapped_column(Float, nullable=True)
    pm25: Mapped[float | None] = mapped_column(Float, nullable=True)
    pm10: Mapped[float | None] = mapped_column(Float, nullable=True)
    pc0_3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pc0_5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pc1_0: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pc2_5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pc5_0: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pc10: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    validation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    device: Mapped[Device] = relationship(
        "Device",
        back_populates="raw_measurements",
        foreign_keys=[device_id],
    )
    session: Mapped[MeasurementSession] = relationship(
        "MeasurementSession",
        back_populates="raw_measurements",
        foreign_keys=[session_id],
    )


Index(
    "ix_raw_measurements_device_id_measured_at_id_desc",
    RawMeasurement.__table__.c.device_id,
    RawMeasurement.__table__.c.measured_at.desc(),
    RawMeasurement.__table__.c.id.desc(),
)
Index(
    "ix_raw_measurements_session_id_measured_at_id_desc",
    RawMeasurement.__table__.c.session_id,
    RawMeasurement.__table__.c.measured_at.desc(),
    RawMeasurement.__table__.c.id.desc(),
)
