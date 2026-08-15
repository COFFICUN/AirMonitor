"""Shared application-table reset support for live integration tests."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncEngine


async def reset_application_tables(
    engine: AsyncEngine,
    metadata: MetaData,
    failure_message: str,
) -> None:
    """Empty every registered application table inside one transaction."""
    try:
        tables = tuple(metadata.tables.values())
        if not tables:
            raise ValueError("application metadata has no tables")

        preparer = engine.dialect.identifier_preparer
        table_names = ", ".join(
            preparer.format_table(table) for table in tables
        )
        statement = text(
            f"TRUNCATE TABLE {table_names} RESTART IDENTITY"
        )
        async with engine.begin() as connection:
            await connection.execute(statement)
    except Exception:
        pass
    else:
        return

    failure = pytest.fail.Exception(
        failure_message,
        pytrace=False,
    )
    raise failure from None


__all__ = ["reset_application_tables"]
