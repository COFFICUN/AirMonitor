"""Shared helpers for transaction-safe application services."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import InvalidTimestampError


def as_utc(
    value: datetime | None,
    *,
    field_name: str,
) -> datetime:
    """Return an aware UTC value, using the current instant when omitted."""
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidTimestampError(
            field_name,
            "a timezone-aware value is required",
        )
    return value.astimezone(UTC)


def integrity_error_constraint_name(
    error: IntegrityError,
) -> str | None:
    """Find a structured constraint name without parsing error messages."""
    pending: list[object] = [error]
    visited: set[int] = set()

    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in visited:
            continue
        visited.add(identity)

        constraint_name = getattr(current, "constraint_name", None)
        if isinstance(constraint_name, str):
            return constraint_name

        for attribute_name in (
            "diag",
            "orig",
            "__cause__",
            "__context__",
        ):
            nested = getattr(current, attribute_name, None)
            if nested is not None:
                pending.append(nested)

    return None


def violates_constraint(
    error: IntegrityError,
    constraint_name: str,
) -> bool:
    """Return whether an integrity failure names the expected constraint."""
    return integrity_error_constraint_name(error) == constraint_name


__all__ = [
    "as_utc",
    "integrity_error_constraint_name",
    "violates_constraint",
]
