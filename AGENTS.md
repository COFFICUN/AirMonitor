# AirMonitor Agent Instructions

## Project context

AirMonitor is an IoT air-quality monitoring system.

The repository currently contains:

- AirMonitor v1: the stable diploma implementation based on Flask and SQLite;
- AirMonitor v2: a new portfolio-oriented implementation that will use FastAPI,
  PostgreSQL, SQLAlchemy, Alembic, Docker, tests, and CI/CD.

AirMonitor v1 must remain functional and must not be rewritten during the
initial AirMonitor v2 migration.


## Current task scope

For the `feature/domain-models` branch, implement only the SQLAlchemy ORM
domain models for AirMonitor v2.

The legacy Flask and SQLite implementation has already been audited. It is
read-only reference material and must not be modified.

Allowed changes:

- `AGENTS.md`
- files inside `backend/`

Legacy files such as `app.py`, `sensor_data.db`, `index.html`, firmware files,
certificates, and other AirMonitor v1 files may be inspected but must not be
modified.

Required work:

- implement the approved AirMonitor v2 relational domain model;
- use typed SQLAlchemy 2 declarative mappings;
- define columns, primary keys, foreign keys, relationships, constraints,
  indexes, defaults, nullability, and delete behavior explicitly;
- register every model in `Base.metadata`;
- add automated tests for the complete metadata structure;
- preserve all existing application behavior and tests.

Approved AirMonitor v2 entities:

- `devices`;
- `device_runtime_state`;
- `measurement_sessions`;
- `raw_measurements`.

Approved schema simplifications:

- do not recreate the obsolete legacy `measurements` table;
- do not recreate `raw_session_links`;
- store `session_id` directly in `raw_measurements`;
- do not recreate `aggregated_measurements` during this sprint;
- aggregated time-series storage will be designed later if it becomes
  necessary.

Important design requirements:

- `DeviceRuntimeState` is a one-to-one child of `Device`;
- `MeasurementSession` belongs to one `Device`;
- `RawMeasurement` belongs to one `Device` and one `MeasurementSession`;
- an active session has `ended_at = NULL`;
- all timestamps are timezone-aware;
- `measured_at` and `received_at` are separate fields;
- runtime `last_seen_at` and `location_updated_at` are separate fields;
- devices are deactivated through `is_active` rather than normally deleted;
- historical measurements must be protected from accidental cascading deletion;
- future duplicate protection must be supported through a nullable
  `source_message_id`;
- no engine or database connection may be created during model import.

Do not implement:

- Alembic migration revisions;
- PostgreSQL table creation;
- PostgreSQL provisioning;
- CRUD repositories;
- service-layer logic;
- FastAPI routes;
- Pydantic API schemas;
- device authentication;
- AQI or NowCast calculations;
- legacy data migration;
- Docker;
- frontend changes;
- firmware changes.

## Protected legacy files

Do not modify these AirMonitor v1 files:

- `app.py`
- `index.html`
- `test1_final.ino`
- `init_db.py`
- `schema.sql`
- root `requirements.txt`
- `secrets.example.h`

## Sensitive files

Never open, read, display, copy, modify, or include content from:

- `secrets.h`
- `.env`
- `.env.*`, except public example templates
- `*.pem`
- `*.key`
- `*.db`
- `*.sqlite`
- `*.sqlite3`
- `.venv/`
- `venv/`

Never print credentials, Wi-Fi settings, private keys, certificates,
database contents, or local secrets.

## Technical requirements

- Use Python 3.13.
- Use FastAPI.
- Use `APIRouter` for route organization.
- Use an application factory function.
- Use type hints for public functions.
- Use Pydantic response models where appropriate.
- Keep modules small and focused.
- Avoid unnecessary abstractions.
- Do not duplicate logic.
- Use pytest for automated tests.
- Use FastAPI `TestClient` for endpoint tests.
- Keep runtime and development dependencies separate.
- Add meaningful docstrings only where they explain design intent.
- Do not add trivial comments that repeat the code.

## Git safety

Do not:

- commit changes;
- push changes;
- amend commits;
- rebase;
- reset;
- run `git clean`;
- force push;
- change branches;
- modify Git configuration.

The user will review and commit changes manually.

## Commands

Create the backend environment from the repository root:

```powershell
py -3.13 -m venv backend/.venv

## Definition of done

Sprint 4 is complete when:

1. Four SQLAlchemy ORM models are implemented:
   `Device`, `DeviceRuntimeState`, `MeasurementSession`, and
   `RawMeasurement`.
2. `Base.metadata` contains exactly four domain tables:
   `devices`, `device_runtime_state`, `measurement_sessions`, and
   `raw_measurements`.
3. Models use SQLAlchemy 2 `Mapped`, `mapped_column`, and `relationship`.
4. Primary keys, foreign keys, nullability, defaults, indexes, unique
   constraints, and check constraints are explicitly defined.
5. `DeviceRuntimeState` is enforced as a one-to-one relationship with
   `Device`.
6. `RawMeasurement.session_id` directly references
   `measurement_sessions.id`.
7. The obsolete `measurements`, `raw_session_links`, and
   `aggregated_measurements` tables are not recreated.
8. Timestamp fields use timezone-aware SQLAlchemy types.
9. Active sessions support `ended_at = NULL`.
10. `measured_at` and `received_at` are separate.
11. `last_seen_at` and `location_updated_at` are separate.
12. Check constraints cover humidity, temperature, particle values,
    coordinates, session dates, and sample counts.
13. Indexes support the expected device, session, and timestamp queries.
14. Historical measurements are protected from accidental cascading deletion.
15. Importing models does not create an engine, session, network connection,
    or database connection.
16. Automated tests verify tables, columns, keys, constraints, indexes,
    relationships, timestamp types, and import side effects.
17. All existing backend tests remain passing.
18. No Alembic revision is created.
19. No PostgreSQL database, schema, table, user, or role is created or modified.
20. `pip check`, `compileall`, `alembic history`, `alembic heads`,
    `git diff --check`, scope checks, and secret checks pass.
21. No AirMonitor v1 file is modified.
22. No `.env`, database, dump, certificate, private key, credential, or secret
    is created or committed.
23. Codex does not stage, commit, push, switch branches, reset, restore, or
    clean Git.