"""Reusable OpenAPI descriptions for the public error envelope."""

from typing import Any

from app.schemas.errors import ErrorResponse


ERROR_DESCRIPTIONS = {
    404: "The requested device or active session does not exist.",
    409: "The requested operation conflicts with domain state.",
    422: "The request body, path, or query data is invalid.",
    500: "A known internal invariant is unavailable.",
}


def error_responses(*status_codes: int) -> dict[int, dict[str, Any]]:
    return {
        status_code: {
            "model": ErrorResponse,
            "description": ERROR_DESCRIPTIONS[status_code],
        }
        for status_code in status_codes
    }


__all__ = ["error_responses"]
