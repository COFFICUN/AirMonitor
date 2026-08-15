"""Stable public error response schemas."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


__all__ = ["ErrorDetail", "ErrorResponse"]
