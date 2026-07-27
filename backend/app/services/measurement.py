"""Transactional measurement-session and raw-measurement operations."""

from datetime import UTC, datetime
from math import isfinite

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ActiveSessionAlreadyExistsError,
    ActiveSessionNotFoundError,
    DeviceInactiveError,
    DeviceNotFoundError,
    DeviceRuntimeStateNotFoundError,
    DuplicateSourceMessageError,
    InvalidSessionTransitionError,
    InvalidTimestampError,
    SessionDoesNotBelongToDeviceError,
    SessionNotFoundError,
)
from app.db.models import MeasurementSession, RawMeasurement
from app.repositories.device import (
    DeviceRepository,
    DeviceRuntimeStateRepository,
)
from app.repositories.measurement import RawMeasurementRepository
from app.repositories.measurement_session import MeasurementSessionRepository
from app.services._support import as_utc, violates_constraint


SOURCE_MESSAGE_UNIQUE_CONSTRAINT = (
    "uq_raw_measurements_device_id_source_message_id"
)


class MeasurementService:
    """Coordinate measurement state transitions in single transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.device_repository = DeviceRepository(session)
        self.runtime_state_repository = DeviceRuntimeStateRepository(session)
        self.session_repository = MeasurementSessionRepository(session)
        self.measurement_repository = RawMeasurementRepository(session)

    async def start_session(
        self,
        *,
        device_id: int,
        latitude: float,
        longitude: float,
        started_at: datetime | None = None,
    ) -> MeasurementSession:
        async with self._session.begin():
            device = await self.device_repository.get_by_id_for_update(
                device_id
            )
            if device is None:
                raise DeviceNotFoundError(device_id=device_id)
            if not device.is_active:
                raise DeviceInactiveError(device_id=device_id)

            runtime_state = (
                await self.runtime_state_repository.get_for_update(device_id)
            )
            if runtime_state is None:
                raise DeviceRuntimeStateNotFoundError(device_id=device_id)
            if (
                runtime_state.measurement_enabled
                or runtime_state.active_session_id is not None
            ):
                raise ActiveSessionAlreadyExistsError(device_id=device_id)

            normalized_started_at = _normalize_timestamp(
                started_at,
                field_name="started_at",
            )
            measurement_session = await self.session_repository.create(
                device_id=device_id,
                latitude=latitude,
                longitude=longitude,
                started_at=normalized_started_at,
            )
            runtime_state.measurement_enabled = True
            runtime_state.active_session_id = measurement_session.id
            runtime_state.measurement_started_at = normalized_started_at
            return measurement_session

    async def complete_session(
        self,
        *,
        device_id: int,
        ended_at: datetime | None = None,
    ) -> MeasurementSession:
        """Complete the session and clear runtime ``measurement_started_at``."""
        async with self._session.begin():
            return await self._transition_session(
                device_id=device_id,
                target_status="completed",
                ended_at=ended_at,
            )

    async def cancel_session(
        self,
        *,
        device_id: int,
        ended_at: datetime | None = None,
    ) -> MeasurementSession:
        """Cancel the session and clear runtime ``measurement_started_at``."""
        async with self._session.begin():
            return await self._transition_session(
                device_id=device_id,
                target_status="cancelled",
                ended_at=ended_at,
            )

    async def record_measurement(
        self,
        *,
        device_id: int,
        measured_at: datetime,
        source_message_id: str | None = None,
        temperature: float | None = None,
        humidity: float | None = None,
        pm1: float | None = None,
        pm25: float | None = None,
        pm10: float | None = None,
        pc0_3: int | None = None,
        pc0_5: int | None = None,
        pc1_0: int | None = None,
        pc2_5: int | None = None,
        pc5_0: int | None = None,
        pc10: int | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        is_valid: bool = True,
        validation_note: str | None = None,
    ) -> RawMeasurement:
        """Raise ``DuplicateSourceMessageError`` for a duplicate non-null ID."""
        _validate_finite_pm_values(pm1=pm1, pm25=pm25, pm10=pm10)
        try:
            async with self._session.begin():
                device = (
                    await self.device_repository.get_by_id_for_update(
                        device_id
                    )
                )
                if device is None:
                    raise DeviceNotFoundError(device_id=device_id)
                if not device.is_active:
                    raise DeviceInactiveError(device_id=device_id)

                runtime_state = (
                    await self.runtime_state_repository.get_for_update(
                        device_id
                    )
                )
                if runtime_state is None:
                    raise DeviceRuntimeStateNotFoundError(
                        device_id=device_id
                    )
                if (
                    not runtime_state.measurement_enabled
                    or runtime_state.active_session_id is None
                ):
                    raise ActiveSessionNotFoundError(device_id=device_id)

                measurement_session = (
                    await self.session_repository.get_by_id_for_update(
                        runtime_state.active_session_id
                    )
                )
                if measurement_session is None:
                    raise SessionNotFoundError(
                        session_id=runtime_state.active_session_id
                    )
                _validate_session_ownership(
                    measurement_session,
                    device_id=device_id,
                )
                if measurement_session.status != "active":
                    raise InvalidSessionTransitionError(
                        session_id=measurement_session.id,
                        current_status=measurement_session.status,
                        target_status="recording",
                    )

                if measured_at is None:
                    raise InvalidTimestampError(
                        field_name="measured_at",
                        reason="a value is required",
                    )
                normalized_measured_at = _normalize_timestamp(
                    measured_at,
                    field_name="measured_at",
                )
                if source_message_id is not None:
                    existing = (
                        await self.measurement_repository
                        .get_by_source_message_id(
                            device_id,
                            source_message_id,
                        )
                    )
                    if existing is not None:
                        raise DuplicateSourceMessageError(
                            device_id=device_id,
                            source_message_id=source_message_id,
                        )

                measurement = await self.measurement_repository.create(
                    device_id=device_id,
                    session_id=measurement_session.id,
                    source_message_id=source_message_id,
                    measured_at=normalized_measured_at,
                    temperature=temperature,
                    humidity=humidity,
                    pm1=pm1,
                    pm25=pm25,
                    pm10=pm10,
                    pc0_3=pc0_3,
                    pc0_5=pc0_5,
                    pc1_0=pc1_0,
                    pc2_5=pc2_5,
                    pc5_0=pc5_0,
                    pc10=pc10,
                    latitude=latitude,
                    longitude=longitude,
                    is_valid=is_valid,
                    validation_note=validation_note,
                )
                await self.session_repository.increment_sample_count(
                    session_id=measurement_session.id
                )
                runtime_state.last_seen_at = datetime.now(UTC)
                return measurement
        except IntegrityError as error:
            if violates_constraint(
                error,
                SOURCE_MESSAGE_UNIQUE_CONSTRAINT,
            ):
                raise DuplicateSourceMessageError(
                    device_id=device_id,
                    source_message_id=source_message_id,
                ) from error
            raise

    async def _transition_session(
        self,
        *,
        device_id: int,
        target_status: str,
        ended_at: datetime | None,
    ) -> MeasurementSession:
        device = await self.device_repository.get_by_id_for_update(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id=device_id)

        runtime_state = await self.runtime_state_repository.get_for_update(
            device_id
        )
        if runtime_state is None:
            raise DeviceRuntimeStateNotFoundError(device_id=device_id)
        if (
            not runtime_state.measurement_enabled
            or runtime_state.active_session_id is None
        ):
            raise ActiveSessionNotFoundError(device_id=device_id)

        measurement_session = (
            await self.session_repository.get_by_id_for_update(
                runtime_state.active_session_id
            )
        )
        if measurement_session is None:
            raise SessionNotFoundError(
                session_id=runtime_state.active_session_id
            )
        _validate_session_ownership(
            measurement_session,
            device_id=device_id,
        )
        if measurement_session.status != "active":
            raise InvalidSessionTransitionError(
                session_id=measurement_session.id,
                current_status=measurement_session.status,
                target_status=target_status,
            )

        normalized_ended_at = _normalize_timestamp(
            ended_at,
            field_name="ended_at",
        )
        if normalized_ended_at < measurement_session.started_at:
            raise InvalidTimestampError(
                field_name="ended_at",
                reason="must not be earlier than the session start",
            )

        measurement_session.status = target_status
        measurement_session.ended_at = normalized_ended_at
        runtime_state.measurement_enabled = False
        runtime_state.active_session_id = None
        runtime_state.measurement_started_at = None
        return measurement_session


def _normalize_timestamp(
    value: datetime | None,
    *,
    field_name: str,
) -> datetime:
    try:
        return as_utc(value, field_name=field_name)
    except InvalidTimestampError:
        raise
    except (TypeError, ValueError) as error:
        raise InvalidTimestampError(
            field_name=field_name,
            reason="must be timezone-aware",
        ) from error


def _validate_session_ownership(
    measurement_session: MeasurementSession,
    *,
    device_id: int,
) -> None:
    if measurement_session.device_id != device_id:
        raise SessionDoesNotBelongToDeviceError(
            session_id=measurement_session.id,
            device_id=device_id,
        )


def _validate_finite_pm_values(
    *,
    pm1: float | None,
    pm25: float | None,
    pm10: float | None,
) -> None:
    for field_name, value in (
        ("pm1", pm1),
        ("pm25", pm25),
        ("pm10", pm10),
    ):
        if value is not None and not isfinite(value):
            raise ValueError(f"{field_name} must be finite")
