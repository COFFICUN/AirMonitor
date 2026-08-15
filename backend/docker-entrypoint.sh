#!/bin/sh
set -eu

: "${AIRMONITOR_DATABASE_URL:?AIRMONITOR_DATABASE_URL must be set}"

python - <<'PY'
import asyncio
import os

import asyncpg
from sqlalchemy.engine import make_url


database_url_text = os.environ["AIRMONITOR_DATABASE_URL"]
try:
    database_url = make_url(database_url_text)
    if database_url.drivername != "postgresql+asyncpg":
        raise ValueError
    asyncpg_dsn = database_url.set(drivername="postgresql").render_as_string(
        hide_password=False
    )
except Exception:
    raise SystemExit("Database configuration is invalid.") from None


async def wait_for_database() -> None:
    for attempt in range(1, 16):
        try:
            connection = await asyncpg.connect(dsn=asyncpg_dsn, timeout=2)
        except Exception:
            if attempt == 15:
                raise SystemExit(
                    "Database readiness check timed out."
                ) from None
            print(
                f"Database is not ready (attempt {attempt}/15).",
                flush=True,
            )
            await asyncio.sleep(2)
        else:
            await connection.close()
            return


asyncio.run(wait_for_database())
PY

python -m alembic upgrade head

exec python -m uvicorn app.main:app "$@"
