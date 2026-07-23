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

For the `feature/initial-schema-migration` branch, implement only the initial
Alembic schema migration for the approved AirMonitor v2 SQLAlchemy models.

The approved ORM model contains exactly four domain tables:

- `devices`;
- `measurement_sessions`;
- `device_runtime_state`;
- `raw_measurements`.

Allowed changes:

- `AGENTS.md`;
- files inside `backend/`.

Legacy AirMonitor v1 files are read-only reference material and must not be
modified.

Required work:

- create exactly one initial Alembic revision;
- create the four approved tables in dependency-safe order;
- reproduce the approved ORM column types, nullability, server defaults,
  primary keys, foreign keys, unique constraints, check constraints, and
  indexes;
- use explicit stable names for all constraints and indexes;
- implement a complete reversible downgrade;
- add automated migration-structure and offline-SQL tests;
- verify upgrade and downgrade SQL without connecting to PostgreSQL;
- preserve all existing application and model tests.

The initial revision must be handwritten or carefully completed from the
approved ORM metadata.

Do not use Alembic autogenerate because no live database is available during
the Codex task.

Do not implement:

- application repositories or services;
- FastAPI endpoints;
- Pydantic API schemas;
- device authentication;
- data seeding;
- SQLite data migration;
- Docker;
- frontend or firmware changes;
- AQI or NowCast logic;
- additional tables;
- PostgreSQL extensions;
- triggers;
- production deployment.

Codex must not apply the migration to a live database. Actual local PostgreSQL
provisioning and `alembic upgrade head` will be performed manually only after
the revision has been reviewed and committed.
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

Sprint 5 is complete when:

1. Exactly one Alembic revision exists.
2. The revision has `down_revision = None`.
3. Upgrade creates exactly these four domain tables:
   `devices`, `measurement_sessions`, `device_runtime_state`, and
   `raw_measurements`.
4. Tables are created in dependency-safe order.
5. The migration matches the approved ORM metadata.
6. Primary keys, foreign keys, ON DELETE behavior, unique constraints, check
   constraints, server defaults, and indexes are explicitly represented.
7. Composite same-device foreign keys are preserved.
8. The session lifecycle constraint is preserved.
9. Downgrade removes all indexes and tables in dependency-safe reverse order.
10. Upgrade and downgrade SQL can be generated in PostgreSQL offline mode.
11. No live PostgreSQL connection is attempted during Codex implementation or
    verification.
12. No table, schema, user, role, extension, or database is created during the
    Codex task.
13. Migration tests require no PostgreSQL service or network access.
14. All existing backend tests remain passing.
15. Alembic reports exactly one head.
16. `pip check`, `compileall`, `git diff --check`, scope checks, generated-file
    checks, and secret checks pass.
17. No AirMonitor v1 file is modified.
18. No real `.env`, database, dump, certificate, key, credential, or secret is
    created or committed.
19. Codex does not stage, commit, push, switch branches, reset, restore, clean,
    stamp, upgrade, or downgrade a live database.
20. The initial migration tests were run before the revision existed and
    failed for the expected missing-revision reason.
21. All offline tests and SQL-generation checks passed before any live
    PostgreSQL operation.
22. A disposable local PostgreSQL database was used for an
    upgrade-downgrade-upgrade integration cycle.
23. The disposable database schema was inspected and matched the approved ORM
    metadata.
24. Only the disposable test database was dropped.
25. The local target was verified as localhost/127.0.0.1 and database
    `airmonitor`.
26. The target database was confirmed safe and empty before migration.
27. `alembic upgrade head` was successfully applied to the local development
    database.
28. `alembic current` reports the initial revision.
29. The local development database contains the four approved domain tables
    and `alembic_version`.
30. No live downgrade or destructive operation was performed against the
    local `airmonitor` database.