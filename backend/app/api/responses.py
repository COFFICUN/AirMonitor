"""Reusable OpenAPI descriptions for the public error envelope."""

from typing import Any

from app.schemas.errors import ErrorResponse


ERROR_DESCRIPTIONS = {
    404: "The requested device or active session does not exist.",
    409: "The requested operation conflicts with domain state.",
    422: "The request body, path, or query data is invalid.",
    500: "An unexpected internal server error occurred.",
}


def error_responses(*status_codes: int) -> dict[int, dict[str, Any]]:
    declared_status_codes = dict.fromkeys((*status_codes, 500))
    return {
        status_code: {
            "model": ErrorResponse,
            "description": ERROR_DESCRIPTIONS[status_code],
        }
        for status_code in declared_status_codes
    }


__all__ = ["error_responses"]
