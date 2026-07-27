"""Central exception-to-HTTP response mapping tests."""

from collections.abc import Callable

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import install_exception_handlers
from app.core.exceptions import (
    ActiveSessionAlreadyExistsError,
    ActiveSessionNotFoundError,
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


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _error_application(error_factory: Callable[[], Exception]) -> FastAPI:
    application = FastAPI()
    install_exception_handlers(application)

    @application.get("/failure")
    async def failure() -> None:
        raise error_factory()

    @application.get("/validated/{item_id}")
    async def validated(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    @application.post("/write-only")
    async def write_only() -> None:
        return None

    return application


SENSITIVE_ERROR_TEXT = (
    "PHASE_C2B_SENTINEL "
    "SELECT secret_column FROM secret_table "
    "DATABASE_URL_MARKER SECRET_USERNAME SECRET_PASSWORD "
    "uq_secret_constraint C:\\internal\\private.py traceback"
)
SENSITIVE_RESPONSE_MARKERS = (
    "phase_c2b_sentinel",
    "select secret_column",
    "database_url_marker",
    "secret_username",
    "secret_password",
    "uq_secret_constraint",
    "c:\\internal\\private.py",
    "traceback",
)


def _assert_sanitized_internal_server_error(response: Response) -> None:
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An internal server error occurred.",
            "details": None,
        }
    }
    serialized = response.text.casefold()
    for marker in SENSITIVE_RESPONSE_MARKERS:
        assert marker not in serialized


@pytest.mark.anyio
async def test_unknown_route_uses_safe_not_found_envelope() -> None:
    transport = ASGITransport(
        app=_error_application(lambda: AssertionError("unused"))
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/unknown-route")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "The requested resource was not found.",
            "details": None,
        }
    }


@pytest.mark.anyio
async def test_wrong_method_uses_safe_envelope_and_preserves_allow() -> None:
    transport = ASGITransport(
        app=_error_application(lambda: AssertionError("unused"))
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/write-only")

    assert response.status_code == 405
    assert response.headers["allow"] == "POST"
    assert response.json() == {
        "error": {
            "code": "method_not_allowed",
            "message": "The requested method is not allowed.",
            "details": None,
        }
    }


@pytest.mark.anyio
async def test_runtime_errors_use_sanitized_internal_server_envelope() -> None:
    transport = ASGITransport(
        app=_error_application(
            lambda: RuntimeError(SENSITIVE_ERROR_TEXT)
        ),
        raise_app_exceptions=False,
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/failure")

    _assert_sanitized_internal_server_error(response)


@pytest.mark.anyio
async def test_sqlalchemy_non_integrity_errors_use_sanitized_envelope() -> None:
    transport = ASGITransport(
        app=_error_application(
            lambda: SQLAlchemyError(SENSITIVE_ERROR_TEXT)
        ),
        raise_app_exceptions=False,
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/failure")

    _assert_sanitized_internal_server_error(response)


@pytest.mark.anyio
async def test_framework_http_500_uses_sanitized_internal_envelope() -> None:
    transport = ASGITransport(
        app=_error_application(
            lambda: StarletteHTTPException(
                status_code=500,
                detail=SENSITIVE_ERROR_TEXT,
            )
        ),
        raise_app_exceptions=False,
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/failure")

    _assert_sanitized_internal_server_error(response)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error_factory", "status_code", "code", "message"),
    [
        (
            lambda: DeviceNotFoundError(5),
            404,
            "device_not_found",
            "Device was not found.",
        ),
        (
            lambda: ActiveSessionNotFoundError(5),
            404,
            "active_session_not_found",
            "No active measurement session was found.",
        ),
        (
            lambda: DuplicateDeviceUIDError("SECRET-UID"),
            409,
            "duplicate_device_uid",
            "A device with this UID already exists.",
        ),
        (
            lambda: DeviceInactiveError(5),
            409,
            "device_inactive",
            "Device is inactive.",
        ),
        (
            lambda: ActiveSessionAlreadyExistsError(5),
            409,
            "active_session_already_exists",
            "An active measurement session already exists.",
        ),
        (
            lambda: DuplicateSourceMessageError(5, "SECRET-MESSAGE"),
            409,
            "duplicate_source_message",
            "The source message has already been recorded.",
        ),
        (
            lambda: InvalidSessionTransitionError(7, "active", "completed"),
            409,
            "invalid_session_transition",
            "The requested measurement-session transition is invalid.",
        ),
        (
            lambda: SessionDoesNotBelongToDeviceError(7, 5),
            409,
            "session_device_mismatch",
            "Measurement session does not belong to the device.",
        ),
        (
            lambda: InvalidTimestampError("ended_at", "SECRET-REASON"),
            409,
            "invalid_timestamp",
            "The supplied timestamp conflicts with session state.",
        ),
        (
            lambda: DeviceRuntimeStateNotFoundError(5),
            500,
            "internal_invariant_error",
            "An internal application invariant is unavailable.",
        ),
        (
            lambda: SessionNotFoundError(7),
            500,
            "internal_invariant_error",
            "An internal application invariant is unavailable.",
        ),
    ],
)
async def test_domain_errors_use_stable_safe_envelopes(
    error_factory: Callable[[], Exception],
    status_code: int,
    code: str,
    message: str,
) -> None:
    transport = ASGITransport(app=_error_application(error_factory))

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/failure")

    assert response.status_code == status_code
    assert response.json() == {
        "error": {
            "code": code,
            "message": message,
            "details": None,
        }
    }
    serialized = response.text
    assert "SECRET" not in serialized
    assert "traceback" not in serialized.casefold()


@pytest.mark.anyio
async def test_request_validation_errors_use_safe_envelope() -> None:
    transport = ASGITransport(
        app=_error_application(lambda: AssertionError("unused"))
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/validated/not-an-integer")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "request_validation_error",
            "message": "Request validation failed.",
            "details": None,
        }
    }
    assert "not-an-integer" not in response.text


@pytest.mark.anyio
async def test_unmapped_integrity_errors_are_sanitized() -> None:
    error = IntegrityError(
        "INSERT INTO secret_table",
        {},
        RuntimeError("SECRET constraint and database URL"),
    )
    transport = ASGITransport(app=_error_application(lambda: error))

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/failure")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An internal server error occurred.",
            "details": None,
        }
    }
    assert "secret" not in response.text.casefold()
