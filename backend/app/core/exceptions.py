"""Domain exceptions for persistence and measurement workflows."""

from __future__ import annotations


class AirMonitorDomainError(Exception):
    """Base class for application-level domain failures."""


class DeviceNotFoundError(AirMonitorDomainError):
    def __init__(self, device_id: int | None = None) -> None:
        self.device_id = device_id
        message = (
            "Device was not found."
            if device_id is None
            else f"Device {device_id} was not found."
        )
        super().__init__(message)


class DeviceInactiveError(AirMonitorDomainError):
    def __init__(self, device_id: int | None = None) -> None:
        self.device_id = device_id
        message = (
            "Device is inactive."
            if device_id is None
            else f"Device {device_id} is inactive."
        )
        super().__init__(message)


class DuplicateDeviceUIDError(AirMonitorDomainError):
    def __init__(self, device_uid: str | None = None) -> None:
        self.device_uid = device_uid
        message = (
            "A device with this UID already exists."
            if device_uid is None
            else f"A device with UID {device_uid!r} already exists."
        )
        super().__init__(message)


class DeviceRuntimeStateNotFoundError(AirMonitorDomainError):
    def __init__(self, device_id: int | None = None) -> None:
        self.device_id = device_id
        message = (
            "Device runtime state was not found."
            if device_id is None
            else f"Runtime state for device {device_id} was not found."
        )
        super().__init__(message)


class ActiveSessionAlreadyExistsError(AirMonitorDomainError):
    def __init__(self, device_id: int | None = None) -> None:
        self.device_id = device_id
        message = (
            "An active measurement session already exists."
            if device_id is None
            else f"Device {device_id} already has an active session."
        )
        super().__init__(message)


class ActiveSessionNotFoundError(AirMonitorDomainError):
    def __init__(self, device_id: int | None = None) -> None:
        self.device_id = device_id
        message = (
            "No active measurement session was found."
            if device_id is None
            else f"Device {device_id} has no active session."
        )
        super().__init__(message)


class SessionNotFoundError(AirMonitorDomainError):
    def __init__(self, session_id: int | None = None) -> None:
        self.session_id = session_id
        message = (
            "Measurement session was not found."
            if session_id is None
            else f"Measurement session {session_id} was not found."
        )
        super().__init__(message)


class SessionDoesNotBelongToDeviceError(AirMonitorDomainError):
    def __init__(
        self,
        session_id: int | None = None,
        device_id: int | None = None,
    ) -> None:
        self.session_id = session_id
        self.device_id = device_id
        if session_id is None or device_id is None:
            message = "Measurement session does not belong to the device."
        else:
            message = (
                f"Measurement session {session_id} does not belong "
                f"to device {device_id}."
            )
        super().__init__(message)


class DuplicateSourceMessageError(AirMonitorDomainError):
    def __init__(
        self,
        device_id: int | None = None,
        source_message_id: str | None = None,
    ) -> None:
        self.device_id = device_id
        self.source_message_id = source_message_id
        if device_id is None or source_message_id is None:
            message = "The source message has already been recorded."
        else:
            message = (
                f"Source message {source_message_id!r} has already been "
                f"recorded for device {device_id}."
            )
        super().__init__(message)


class InvalidSessionTransitionError(AirMonitorDomainError):
    def __init__(
        self,
        session_id: int | None = None,
        current_status: str | None = None,
        target_status: str | None = None,
    ) -> None:
        self.session_id = session_id
        self.current_status = current_status
        self.target_status = target_status
        message = "The requested measurement-session transition is invalid."
        if current_status is not None and target_status is not None:
            message = (
                f"Measurement session {session_id} cannot transition "
                f"from {current_status!r} to {target_status!r}."
            )
        super().__init__(message)


class InvalidTimestampError(AirMonitorDomainError):
    def __init__(
        self,
        field_name: str = "timestamp",
        reason: str | None = None,
    ) -> None:
        self.field_name = field_name
        self.reason = reason
        message = f"{field_name} is invalid."
        if reason is not None:
            message = f"{field_name} is invalid: {reason}."
        super().__init__(message)


__all__ = [
    "ActiveSessionAlreadyExistsError",
    "ActiveSessionNotFoundError",
    "AirMonitorDomainError",
    "DeviceInactiveError",
    "DeviceNotFoundError",
    "DeviceRuntimeStateNotFoundError",
    "DuplicateDeviceUIDError",
    "DuplicateSourceMessageError",
    "InvalidSessionTransitionError",
    "InvalidTimestampError",
    "SessionDoesNotBelongToDeviceError",
    "SessionNotFoundError",
]
