@'
# AirMonitor Agent Instructions

## Repository context

AirMonitor v1 is the stable legacy implementation.

The following legacy assets are read-only reference material and must never be
modified unless the user explicitly requests it:

- root app.py;
- root sensor_data.db;
- legacy HTML, CSS, and JavaScript;
- firmware and Arduino files;
- certificates, keys, and secret files;
- Flask and SQLite implementation files.

AirMonitor v2 lives under backend/ and uses FastAPI, SQLAlchemy, Alembic,
PostgreSQL, Pydantic, and pytest.

## Current active task

Sprint 8 Phase C1 — Application Composition and Finite Telemetry.

Implement only:

- AUDIT-001: factory-provided settings must control the actual database engine
  and session factory used by requests;
- AUDIT-007 as part of AUDIT-001: the application-owned async engine must be
  disposed through FastAPI lifespan;
- AUDIT-002: non-finite telemetry must be rejected before any persistence
  operation.

Read the following report completely before changing code:

docs/reviews/sprint-8-full-codebase-audit.md

## Required skills and workflow

Start with `using-agent-skills` and choose the minimum sufficient installed
skills.

The preferred workflow is:

1. inspect the current implementation;
2. reproduce each accepted defect with focused failing tests;
3. confirm that each test fails for the intended reason;
4. make the smallest implementation change;
5. rerun focused tests;
6. run the complete offline backend suite;
7. perform an independent review/challenge pass;
8. report the final diff and verification results.

Use test-driven development. Do not implement a fix before proving the defect
with a failing regression test.

## Allowed production scope

Production changes are limited to files directly required for AUDIT-001,
AUDIT-002, and AUDIT-007, primarily:

- backend/app/main.py
- backend/app/db/__init__.py
- backend/app/db/session.py
- backend/app/db/dependencies.py
- backend/app/api/dependencies.py
- backend/app/schemas/_base.py
- backend/app/schemas/measurements.py
- backend/app/services/measurement.py
- backend/app/core/exceptions.py only if an existing domain-error mechanism
  cannot express the service-level finite-value rejection cleanly

Do not change unrelated production files.

## Allowed test scope

Tests may be added or modified only where directly required for the accepted
findings, including:

- backend/tests/test_config.py
- backend/tests/test_database.py
- backend/tests/test_api_dependencies.py
- backend/tests/test_api_architecture.py
- backend/tests/test_api_schemas.py
- backend/tests/test_api_routes.py
- backend/tests/test_api_openapi.py
- backend/tests/test_services.py
- backend/tests/test_health.py
- backend/tests/test_api_integration.py only for compatibility with the new
  application composition; do not change its database guard or cleanup policy
- one or two focused new test modules under backend/tests if that produces
  clearer regression coverage

Do not modify persistence guards, test-database policies, or unrelated tests.

## AUDIT-001 and AUDIT-007 acceptance criteria

The implementation must prove all of the following:

1. `create_application(application_settings)` constructs the database engine
   from that exact settings object.
2. The request session factory belongs to that exact application instance.
3. Two applications created with different sentinel database URLs do not share
   settings, engines, or session factories.
4. The request path does not call a process-global cached settings object to
   select the database target.
5. Creating/importing an application does not connect to PostgreSQL.
6. Generating OpenAPI does not connect to PostgreSQL.
7. One request still receives one request-scoped AsyncSession.
8. The application engine is disposed exactly once through lifespan.
9. Separate application lifecycles do not share an engine or connection pool.
10. The module-level `app` entrypoint remains usable by Uvicorn.
11. Existing dependency overrides used by tests remain supported.
12. No API path, request model, response model, status code, or operation ID
    changes.

Prefer application-owned state and dependency resolution over process-global
database caches.

## AUDIT-002 acceptance criteria

The implementation must prove all of the following:

1. JSON values that become positive or negative infinity are rejected with the
   existing safe 422 validation envelope.
2. Parser-supported NaN and Infinity forms are rejected.
3. Request validation rejects non-finite telemetry before the endpoint service
   is invoked.
4. Direct non-HTTP service calls also reject non-finite PM values.
5. Service-level rejection occurs before transaction entry and before any
   repository insert, session counter update, or runtime-state update.
6. Valid finite values retain existing behavior.
7. No post-commit response-serialization failure is possible from accepted PM
   values.
8. No PostgreSQL migration or database constraint is added in this phase.

Use a shared Pydantic request policy such as `allow_inf_nan=False` when it is
compatible with the current request models. Preserve all existing valid ranges.

## Explicitly forbidden in Phase C1

Do not:

- implement telemetry read endpoints;
- add or change routes;
- implement AUDIT-003 through AUDIT-014;
- change public error-envelope policy;
- change production hardening settings;
- change API integer limits;
- change session chronology rules;
- create or modify Alembic revisions;
- modify ORM tables, columns, constraints, indexes, or relationships;
- connect to PostgreSQL;
- create, drop, migrate, clean, or inspect a database;
- set test-database environment variables;
- install or update dependencies;
- modify requirements files;
- modify the audit report;
- modify README or other documentation;
- modify global or project Agent Skills;
- open or print secrets, credentials, certificates, keys, .env files, or
  database URLs;
- edit legacy files;
- perform Git write operations.

Git write operations include add, commit, push, pull, checkout, switch, merge,
rebase, reset, clean, stash, branch creation/deletion, tag operations, and
changes to Git configuration.

Read-only Git commands are allowed.

## Test environment

Use the existing Python environment only for command execution:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Do not modify that environment and do not run pip install.

Run tests from the Codex worktree backend directory. Use:

- `-B` or `PYTHONDONTWRITEBYTECODE=1`;
- `-p no:cacheprovider`;
- no live integration opt-in;
- no database URL environment variables.

The complete offline suite must pass. Live PostgreSQL suites must remain
skipped when their explicit opt-ins are absent.

## Required final verification

At minimum run:

1. focused regression tests for application composition and lifespan;
2. focused schema/API/service tests for non-finite telemetry;
3. the complete offline backend test suite;
4. `pip check`;
5. offline OpenAPI generation and operation-ID verification;
6. connection guards proving import, factory construction, lifespan setup, and
   OpenAPI generation do not connect;
7. source compilation without generated files in the repository;
8. `git diff --check`;
9. final tracked/untracked sensitive-path check;
10. read-only final diff and status inspection.

Expected API inventory remains:

- nine total OpenAPI operations;
- eight operations under `/api/v1`;
- one `/health` operation;
- unique operation IDs.

## Definition of done

Phase C1 is complete only when:

- focused failing tests reproduced AUDIT-001 and AUDIT-002 before implementation;
- AUDIT-001, AUDIT-002, and AUDIT-007 are fixed;
- all accepted criteria above are covered by tests;
- the full offline suite passes;
- no PostgreSQL connection occurred;
- no migration exists in the diff;
- no unrelated finding or feature was implemented;
- no legacy or sensitive file was touched;
- no dependency was changed;
- no Git write operation was performed by Codex;
- the final response lists every changed file, every test command and result,
  compatibility impact, remaining limitations, and the exact Git status.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8