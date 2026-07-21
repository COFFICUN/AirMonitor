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

For the `feature/app-configuration` branch, implement only the centralized
application configuration layer for AirMonitor v2.

Allowed changes:

- `AGENTS.md`
- `.gitignore`, only when required for safe environment-file handling
- files inside `backend/`

Required work:

- add centralized settings using `pydantic-settings`;
- add a public `backend/.env.example` template;
- keep the real `backend/.env` ignored;
- use settings for FastAPI metadata and the health response;
- add automated configuration tests;
- preserve the existing `/health` public response contract.

Do not implement PostgreSQL, SQLAlchemy, Alembic, Docker, authentication,
Redis, MQTT, frontend migration, or new business API endpoints during this
task.

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

Sprint 2 is complete when:

1. Application settings are defined in `backend/app/core/config.py`.
2. Settings use `pydantic-settings`.
3. Environment variables use the `AIRMONITOR_` prefix.
4. A safe `backend/.env.example` exists.
5. The real `backend/.env` is ignored by Git.
6. FastAPI title, version, and debug mode come from settings.
7. The `/health` response uses configured service name and version.
8. Existing health behavior remains backward compatible.
9. Tests verify default settings and environment-variable overrides.
10. All tests pass.
11. No AirMonitor v1 file is modified.
12. No secret or private local file is committed.
13. Codex does not commit or push changes.