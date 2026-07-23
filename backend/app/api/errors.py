"""Central HTTP mappings for validation and domain failures."""

from dataclasses import dataclass

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    ActiveSessionAlreadyExistsError,
    ActiveSessionNotFoundError,
    AirMonitorDomainError,
    DeviceInactiveError,
    DeviceNotFoundError,
    DeviceRuntimeStateNotFoundError,
    DuplicateDeviceUIDError,
    DuplicateSourceMessageError,
    InvalidSessionTransitionError,
    InvalidTimestampError,
    SessionDoesNotBelongToDeviceError,
    SessionNotFoundError,
)


@dataclass(frozen=True)
class ErrorMapping:
    status_code: int
    code: str
    message: str


DOMAIN_ERROR_MAPPINGS: tuple[
    tuple[type[AirMonitorDomainError], ErrorMapping],
    ...,
] = (
    (
        DeviceNotFoundError,
        ErrorMapping(
            status.HTTP_404_NOT_FOUND,
            "device_not_found",
            "Device was not found.",
        ),
    ),
    (
        ActiveSessionNotFoundError,
        ErrorMapping(
            status.HTTP_404_NOT_FOUND,
            "active_session_not_found",
            "No active measurement session was found.",
        ),
    ),
    (
        DuplicateDeviceUIDError,
        ErrorMapping(
            status.HTTP_409_CONFLICT,
            "duplicate_device_uid",
            "A device with this UID already exists.",
        ),
    ),
    (
        DeviceInactiveError,
        ErrorMapping(
            status.HTTP_409_CONFLICT,
            "device_inactive",
            "Device is inactive.",
        ),
    ),
    (
        ActiveSessionAlreadyExistsError,
        ErrorMapping(
            status.HTTP_409_CONFLICT,
            "active_session_already_exists",
            "An active measurement session already exists.",
        ),
    ),
    (
        DuplicateSourceMessageError,
        ErrorMapping(
            status.HTTP_409_CONFLICT,
            "duplicate_source_message",
            "The source message has already been recorded.",
        ),
    ),
    (
        InvalidSessionTransitionError,
        ErrorMapping(
            status.HTTP_409_CONFLICT,
            "invalid_session_transition",
            "The requested measurement-session transition is invalid.",
        ),
    ),
    (
        SessionDoesNotBelongToDeviceError,
        ErrorMapping(
            status.HTTP_409_CONFLICT,
            "session_device_mismatch",
            "Measurement session does not belong to the device.",
        ),
    ),
    (
        InvalidTimestampError,
        ErrorMapping(
            status.HTTP_409_CONFLICT,
            "invalid_timestamp",
            "The supplied timestamp conflicts with session state.",
        ),
    ),
    (
        DeviceRuntimeStateNotFoundError,
        ErrorMapping(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_invariant_error",
            "An internal application invariant is unavailable.",
        ),
    ),
    (
        SessionNotFoundError,
        ErrorMapping(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_invariant_error",
            "An internal application invariant is unavailable.",
        ),
    ),
)


def _error_response(mapping: ErrorMapping) -> JSONResponse:
    return JSONResponse(
        status_code=mapping.status_code,
        content={
            "error": {
                "code": mapping.code,
                "message": mapping.message,
                "details": None,
            }
        },
    )


async def handle_domain_error(
    request: Request,
    error: AirMonitorDomainError,
) -> JSONResponse:
    del request
    for error_type, mapping in DOMAIN_ERROR_MAPPINGS:
        if isinstance(error, error_type):
            return _error_response(mapping)
    return _error_response(
        ErrorMapping(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_server_error",
            "An internal server error occurred.",
        )
    )


async def handle_request_validation_error(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    del request, error
    return _error_response(
        ErrorMapping(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "request_validation_error",
            "Request validation failed.",
        )
    )


async def handle_integrity_error(
    request: Request,
    error: IntegrityError,
) -> JSONResponse:
    del request, error
    return _error_response(
        ErrorMapping(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_server_error",
            "An internal server error occurred.",
        )
    )


def install_exception_handlers(application: FastAPI) -> None:
    """Install the public error contract once at application construction."""
    application.add_exception_handler(
        AirMonitorDomainError,
        handle_domain_error,
    )
    application.add_exception_handler(
        RequestValidationError,
        handle_request_validation_error,
    )
    application.add_exception_handler(
        IntegrityError,
        handle_integrity_error,
    )


__all__ = ["install_exception_handlers"]
