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

For the `feature/device-measurement-api` branch, implement only the versioned
REST API layer for the approved AirMonitor v2 device, session, and raw
measurement workflow.

The existing Sprint 6 repositories and transactional services are the approved
business-logic layer. API routes must use those services and must not duplicate
their business rules.

Approved endpoints:

- `POST /api/v1/devices`;
- `GET /api/v1/devices/{device_id}`;
- `PATCH /api/v1/devices/{device_id}/status`;
- `POST /api/v1/devices/{device_id}/sessions`;
- `GET /api/v1/devices/{device_id}/sessions/active`;
- `POST /api/v1/devices/{device_id}/sessions/active/complete`;
- `POST /api/v1/devices/{device_id}/sessions/active/cancel`;
- `POST /api/v1/devices/{device_id}/measurements`.

Allowed changes:

- `AGENTS.md`;
- files inside `backend/`.

Legacy AirMonitor v1 files are read-only reference material and must not be
modified.

Required architecture:

- preserve the current FastAPI application and `/health` endpoint;
- register all new routes under `/api/v1`;
- use separate Pydantic request and response schemas;
- configure request schemas to reject unknown fields;
- configure ORM response schemas to read scalar model attributes safely;
- use explicit response models and status codes;
- add dependency providers for sessions, services, and read-only query
  services;
- create one AsyncSession per HTTP request;
- session dependencies must yield and close sessions but must not commit or
  roll back successful service operations;
- write routes must call the existing Sprint 6 services directly without
  performing preliminary database queries;
- read routes must use read-only query services rather than repositories
  directly;
- query services must not commit, roll back, open write transactions, or use
  row-level locks;
- routes must not contain SQLAlchemy statements, transaction management, or
  business-state checks;
- centralize domain-exception to HTTP-response mapping;
- centralize FastAPI request-validation error formatting;
- do not expose SQL, table names, connection URLs, credentials, tracebacks, or
  raw IntegrityError messages;
- preserve the existing Sprint 6 duplicate-source behavior:
  duplicate non-null source_message_id values produce
  DuplicateSourceMessageError;
- preserve all existing repository and service behavior.

Approved HTTP status behavior:

- successful resource creation: `201 Created`;
- successful read or state transition: `200 OK`;
- invalid request body, path, or query data: `422 Unprocessable Entity`;
- missing device or active session: `404 Not Found`;
- duplicate device UID: `409 Conflict`;
- inactive device: `409 Conflict`;
- existing active session: `409 Conflict`;
- duplicate source message: `409 Conflict`;
- invalid session transition or timestamp: `409 Conflict`;
- missing runtime state or another broken internal invariant: safe
  `500 Internal Server Error` without internal details.

Approved error envelope:

```json
{
  "error": {
    "code": "stable_machine_readable_code",
    "message": "Safe human-readable message.",
    "details": null
  }
}
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

Sprint 7 is complete when:

1. All eight approved `/api/v1` endpoints exist.
2. The existing `/health` endpoint still works.
3. Request and response Pydantic schemas are separated.
4. Unknown request fields are rejected.
5. Path device IDs must be positive.
6. Coordinate limits and coordinate-pair rules are enforced.
7. Naive datetime values are rejected.
8. Decimal-backed values have stable tested JSON representations.
9. Every endpoint declares an explicit response model.
10. Creation endpoints return 201.
11. Read and transition endpoints return 200.
12. Write routes use Sprint 6 services.
13. Read routes use read-only query services.
14. Routes contain no SQLAlchemy statements.
15. Routes contain no transaction management.
16. Routes do not call repositories directly.
17. One AsyncSession is created per request.
18. Session dependencies do not automatically commit service operations.
19. Domain exceptions are mapped centrally.
20. Validation errors use the approved error envelope.
21. Expected 404, 409, and 422 responses are represented in OpenAPI.
22. Internal database details are never returned to clients.
23. Application import performs no database connection.
24. Application startup performs no migration or metadata creation.
25. Offline route tests use dependency overrides and no PostgreSQL.
26. OpenAPI generation is tested.
27. The current backend baseline remains passing.
28. The guarded PostgreSQL HTTP integration suite passes.
29. The integration suite uses only AIRMONITOR_API_TEST_DATABASE_URL.
30. The full HTTP lifecycle passes on a disposable database.
31. Duplicate device, inactive device, second session, duplicate measurement,
    invalid request, completion, cancellation, and post-completion rejection
    are covered.
32. Persisted rows and rollback behavior are verified.
33. The disposable database is removed after verification.
34. The protected `airmonitor` database is not connected to or modified.
35. ORM models are unchanged.
36. Existing repositories and transactional services are unchanged unless a
    separately approved blocking defect is found.
37. No Alembic revision is created.
38. Alembic remains at sole head a4f9c2e7d1b6.
39. pip check passes.
40. compileall passes.
41. git diff --check passes.
42. Scope, generated-file, revision-count, and secret audits pass.
43. Legacy files, frontend, firmware, `.env`, certificates, keys, databases,
    and dumps are not modified or committed.
44. Codex performs no Git write operation.