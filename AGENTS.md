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

For the `feature/database-foundation` branch, implement only the database
infrastructure foundation for AirMonitor v2.

Allowed changes:

- `AGENTS.md`
- `.gitignore`, only if required for database-related local files
- files inside `backend/`

Required work:

- add PostgreSQL database configuration;
- add SQLAlchemy 2 asynchronous engine infrastructure;
- add an asynchronous session factory;
- add a FastAPI dependency that yields database sessions;
- add a typed declarative ORM base;
- initialize Alembic with its asynchronous template;
- configure Alembic from application settings;
- add automated tests that do not require a running PostgreSQL server;
- preserve all existing application and health endpoint behavior.

Do not implement database tables, ORM domain models, migration revisions,
CRUD services, measurement endpoints, Docker, authentication, Redis, MQTT,
frontend migration, or data transfer from the legacy SQLite database during
this task.

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

Sprint 3 is complete when:

1. PostgreSQL configuration is defined through the existing Settings class.
2. The public `.env.example` contains only safe example database values.
3. SQLAlchemy uses an asynchronous PostgreSQL engine with asyncpg.
4. Engine and session-factory construction are separated into testable
   functions.
5. The session factory creates typed AsyncSession instances.
6. FastAPI has a reusable dependency that yields and closes a database session.
7. A typed SQLAlchemy DeclarativeBase exists.
8. Alembic is initialized with an asynchronous environment.
9. Alembic reads the database URL from application settings rather than storing
   a real credential in `alembic.ini`.
10. Alembic uses the declarative base metadata for future autogeneration.
11. No database tables or domain models are created.
12. No migration revision is generated.
13. Tests do not require a live PostgreSQL server.
14. All existing tests remain passing.
15. `pip check`, `git diff --check`, and Git scope verification pass.
16. No AirMonitor v1 file is modified.
17. No real database password, `.env`, database dump, certificate, or secret is
    created or committed.
18. Codex does not commit, push, switch branches, reset, or clean Git.