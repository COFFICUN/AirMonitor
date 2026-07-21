"""Initialize the local AirMonitor SQLite database.

The production measurement database is intentionally excluded from Git because it
can contain geolocation and sensor history. This script creates a clean database
for a new local installation and registers the default device expected by app.py.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "sensor_data.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


def initialize_database() -> None:
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")

    schema = SCHEMA_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema)
        connection.commit()

    print(f"AirMonitor database is ready: {DATABASE_PATH}")


if __name__ == "__main__":
    initialize_database()
