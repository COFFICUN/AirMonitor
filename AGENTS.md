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

Sprint 8 Phase C2B — API Error Contract and Production Hardening.

Implement only:

- AUDIT-005: complete the public error envelope for framework HTTP errors and
  unexpected server errors, and align OpenAPI documentation;
- AUDIT-006: reject unsafe production settings and hide SQL parameters.

Read completely before changing code:

docs/reviews/sprint-8-full-codebase-audit.md

Preserve all completed Phase C1 and C2A behavior.

## Approved HTTP error policy

Framework-level errors must use the existing ErrorResponse envelope.

Required mappings:

- unknown route:
  - status 404;
  - code `not_found`;
  - safe fixed message;
- method not allowed:
  - status 405;
  - code `method_not_allowed`;
  - safe fixed message;
  - preserve the `Allow` header;
- unexpected application/server failure:
  - status 500;
  - code `internal_server_error`;
  - safe fixed message.

Never expose:

- exception text;
- traceback content;
- SQL statements or parameters;
- database URLs;
- usernames or passwords;
- constraint names;
- internal filesystem paths;
- sentinel values included in thrown exceptions.

Existing domain-error, validation-error, and IntegrityError behavior must remain
unchanged.

All eight /api/v1 operations must document a generic safe 500 response using
the existing ErrorResponse schema. Do not change operation IDs, routes, request
models, success responses, or successful status codes.

## Approved production configuration policy

When environment is production, settings validation must reject:

- debug=true;
- database_echo=true;
- the unchanged built-in development database URL.

The async SQLAlchemy engine must be constructed with parameter hiding enabled:

hide_parameters=True

This applies independently of environment.

Development and test behavior must remain compatible.

Do not print, log, inspect, or expose database URL values.

## Required workflow

Start with `using-agent-skills` and select the minimum sufficient installed
skills.

Use strict test-driven development:

1. inspect current handlers, settings, engine creation, and OpenAPI responses;
2. add focused failing regression tests;
3. prove failures correspond to AUDIT-005 and AUDIT-006;
4. implement the smallest coherent fix;
5. rerun focused tests;
6. run the complete offline backend suite;
7. perform a bounded adversarial review;
8. stop for manual external review.

Do not implement before RED tests are demonstrated.

## Allowed production scope

Modify only files directly required, primarily:

- backend/app/api/errors.py
- backend/app/api/responses.py
- backend/app/api/router.py
- backend/app/api/v1/router.py
- backend/app/api/v1/endpoints/devices.py
- backend/app/api/v1/endpoints/measurements.py
- backend/app/api/v1/endpoints/sessions.py
- backend/app/schemas/errors.py
- backend/app/core/config.py
- backend/app/db/session.py
- backend/app/main.py

Use only the minimum necessary subset.

## Allowed test scope

Tests may be added or modified only where directly required, including:

- backend/tests/test_api_errors.py
- backend/tests/test_api_openapi.py
- backend/tests/test_api_routes.py
- backend/tests/test_config.py
- backend/tests/test_database.py
- backend/tests/test_application_composition.py
- one focused new test module if it materially improves clarity

Do not modify integration guards or database cleanup behavior.

## AUDIT-005 acceptance criteria

Prove all of the following:

1. Unknown routes return the ErrorResponse envelope with status 404.
2. Wrong methods return the ErrorResponse envelope with status 405.
3. The 405 response preserves the correct Allow header.
4. A synthetic RuntimeError returns a sanitized 500 ErrorResponse.
5. A synthetic SQLAlchemy non-IntegrityError returns the same sanitized 500.
6. Exception messages, SQL, URLs, credentials, constraint names, paths, and
   sentinel values do not appear in response bodies.
7. Existing domain-error responses remain unchanged.
8. Existing request-validation responses remain unchanged.
9. Existing IntegrityError responses remain unchanged.
10. All eight /api/v1 operations document the generic ErrorResponse 500.
11. OpenAPI operation count, paths, operation IDs, request models, successful
    status codes, and successful response schemas remain unchanged.
12. Debug-mode behavior is not relied on for production safety.

## AUDIT-006 acceptance criteria

Prove all of the following:

1. Production plus debug=true is rejected during Settings validation.
2. Production plus database_echo=true is rejected.
3. Production plus the unchanged built-in database URL is rejected.
4. A production configuration with debug=false, echo=false, and an explicit
   non-default PostgreSQL+asyncpg URL is accepted.
5. Development/test configurations retain current behavior.
6. Engine construction always passes hide_parameters=True.
7. Engine construction remains lazy and does not connect.
8. No database URL or credential is printed into failures or captured logs.
9. Application-owned engine/session behavior from Phase C1 remains intact.
10. No database, migration, or API success contract changes.

## Explicitly forbidden

Do not:

- implement telemetry read endpoints;
- implement AUDIT-008 or later findings;
- implement authentication or authorization;
- add CORS;
- add rate limiting;
- add Docker or CI;
- introduce structured logging or observability architecture;
- redesign the error schema;
- change existing domain error codes;
- change chronology or integer-boundary behavior;
- change routes or operation IDs;
- create or modify Alembic revisions;
- modify ORM models, constraints, indexes, relationships, or database types;
- connect to PostgreSQL;
- create, inspect, migrate, clean, or drop a database;
- install or update dependencies;
- modify requirements;
- modify the audit report or README;
- modify Agent Skills;
- modify legacy files, firmware, secrets, certificates, keys, or .env files;
- perform Git write operations.

Read-only Git commands are allowed.

## Test environment

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Do not change this environment.

Run tests with:

- -B;
- -p no:cacheprovider;
- no live PostgreSQL opt-ins;
- no dependency installation.

Do not read or print database URL values.

## Required verification

At minimum run:

1. focused framework/generic error tests;
2. focused production-settings tests;
3. focused engine-construction tests;
4. affected error, route, config, database, OpenAPI, and composition tests;
5. the complete offline backend suite;
6. pip check;
7. guarded offline OpenAPI generation;
8. import/factory/lifespan/OpenAPI no-connection guards;
9. in-memory/source compilation without repository bytecode;
10. git diff --check;
11. sensitive/generated-path checks;
12. final read-only diff and status inspection.

Expected OpenAPI inventory remains:

- nine total operations;
- eight operations under /api/v1;
- one /health operation;
- unique operation IDs.

## Definition of done

Phase C2B is complete only when:

- RED tests reproduce AUDIT-005 and AUDIT-006;
- both findings are fixed;
- framework and generic failures use the approved safe envelope;
- unsafe production settings fail closed;
- SQL parameters are hidden;
- existing domain/validation/integrity behavior remains compatible;
- the complete offline suite passes;
- OpenAPI inventory remains unchanged;
- no PostgreSQL connection occurs;
- no migration, ORM, dependency, legacy, or unrelated file changes;
- Codex performs no Git write operation;
- the final response lists RED failures, changed files, exact commands and
  results, compatibility impact, remaining limitations, and final Git status.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8