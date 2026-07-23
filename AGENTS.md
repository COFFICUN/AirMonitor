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

For the `feature/persistence-services` branch, implement only the transactional
persistence layer for the approved AirMonitor v2 PostgreSQL domain model.

The approved tables are:

- `devices`;
- `device_runtime_state`;
- `measurement_sessions`;
- `raw_measurements`.

Allowed changes:

- `AGENTS.md`;
- files inside `backend/`.

Legacy AirMonitor v1 files are read-only reference material and must not be
modified.

Required work:

- implement asynchronous SQLAlchemy repositories;
- implement transaction-safe application services;
- preserve the existing ORM models and initial Alembic migration;
- use the existing AsyncSession infrastructure;
- repositories must never commit transactions;
- service methods must define transaction boundaries;
- use row-level locking where required to prevent concurrent session-state
  conflicts;
- create a device and its runtime state in one transaction;
- start, complete, and cancel measurement sessions safely;
- allow at most one active session per device through service logic and row
  locking;
- record raw measurements only for an active session belonging to the same
  device;
- support optional source-message idempotency;
- update session sample_count and device last_seen_at atomically with a raw
  measurement;
- provide explicit domain exceptions;
- add unit and PostgreSQL integration tests;
- preserve all existing 61 tests.

Repositories may use `flush()` but must not call:

- `commit()`;
- `rollback()`;
- `begin()`.

Service methods may manage transactions using the supplied AsyncSession.

Do not implement:

- FastAPI routes;
- request or response schemas;
- HTTP error mapping;
- authentication or API keys;
- AQI or NowCast calculations;
- session summary averages;
- CSV export;
- SQLite data migration;
- frontend;
- firmware;
- Docker;
- background workers;
- additional database tables;
- additional Alembic revisions;
- changes to the approved ORM schema.

Live PostgreSQL integration verification is permitted only against a new
disposable local database whose name starts with
`airmonitor_persistence_test_`.

Before every live PostgreSQL write operation, Codex must request explicit
permission for the exact command.

The local `airmonitor` database must not be modified during Sprint 6.
  
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

Migration safety workflow:

- follow a strict test-first workflow;
- create migration tests before creating the initial revision;
- record the expected failing test run caused by the missing revision;
- implement the revision only after the expected failure;
- complete all unit, metadata, offline SQL, scope, and secret checks before any
  live PostgreSQL operation;
- after all offline checks pass, validate the migration against a disposable
  local PostgreSQL database;
- the disposable database name must start with
  `airmonitor_migration_test_`;
- perform upgrade, schema inspection, downgrade, and repeated upgrade only
  against the disposable database;
- delete only the disposable database after successful verification;
- after disposable-database verification succeeds, apply `upgrade head` to the
  local `airmonitor` development database;
- before applying the migration, verify that the target host is localhost or
  127.0.0.1 and that the target database name is exactly `airmonitor`;
- stop without modifying the target if it contains unexpected tables, data, or
  an incompatible Alembic state;
- never downgrade, drop, truncate, or recreate the local `airmonitor`
  development database;
- never connect to a remote or production PostgreSQL server.

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

Sprint 6 is complete when:

1. Repository classes exist for devices, runtime state, sessions, and raw
   measurements.
2. Repository methods use AsyncSession and SQLAlchemy 2.x statements.
3. Repositories never commit, rollback, or open transactions.
4. Service methods own transaction boundaries.
5. Creating a device also creates its runtime state atomically.
6. Starting a session updates runtime state atomically.
7. Starting a second active session for the same device is rejected.
8. Completing a session sets status, ended_at, disables measurement, and clears
   active_session_id atomically.
9. Cancelling a session performs the equivalent consistent state transition.
10. Raw measurements require an active session for the same device.
11. Duplicate non-null source_message_id values are handled idempotently or
    rejected with an explicit domain exception.
12. Recording a measurement increments sample_count and updates last_seen_at in
    the same transaction.
13. Inactive devices cannot start sessions or record measurements.
14. Missing devices and sessions produce explicit domain exceptions.
15. Concurrent session operations use appropriate row-level locking.
16. Unit tests cover repository statements and service behavior.
17. PostgreSQL integration tests pass against a disposable local database.
18. Integration tests cover successful and rejected state transitions.
19. The disposable database is removed after verification.
20. The local `airmonitor` database is not modified.
21. No new Alembic revision is created.
22. All existing backend tests remain passing.
23. `pip check`, `compileall`, and `git diff --check` pass.
24. No legacy, secret, `.env`, certificate, key, database, or dump file is
    modified or committed.
25. Codex performs no Git staging, commit, push, reset, restore, clean, or branch
    operation.