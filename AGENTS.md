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

Sprint 8 Phase C2A — Domain Boundaries.

Implement only:

- AUDIT-003: measurement timestamps and session terminal timestamps must form
  one consistent interval;
- AUDIT-004: public API integer inputs mapped to PostgreSQL INTEGER must respect
  the signed int32 range.

Read this report completely before changing code:

docs/reviews/sprint-8-full-codebase-audit.md

Phase C1 is already complete. Preserve its application-owned database state,
lifespan disposal, and non-finite telemetry validation.

## Approved domain decisions

### Session chronology

Use a strict timestamp policy with no implicit clock-skew allowance:

- measurement.measured_at must be greater than or equal to
  session.started_at;
- complete/cancel ended_at must be greater than or equal to the latest
  persisted measurement.measured_at;
- equality is valid;
- the rule applies to both completed and cancelled sessions;
- contradictory timestamps use the existing conflict/domain-error mechanism
  and the existing safe 409 envelope.

Do not add a configurable tolerance or silently adjust timestamps.

### PostgreSQL INTEGER range

Public integer inputs backed by PostgreSQL INTEGER must not exceed:

2_147_483_647

Keep the current lower bounds:

- identifiers remain greater than zero;
- particle counters remain greater than or equal to zero.

Do not migrate any column to BIGINT in this phase.

## Required workflow

Start with `using-agent-skills` and select the minimum sufficient installed
skills.

Use strict test-driven development:

1. inspect the current implementation;
2. add focused failing regression tests;
3. prove each test fails for the intended defect;
4. make the smallest coherent implementation change;
5. rerun focused tests;
6. run the complete offline backend suite;
7. perform a bounded adversarial review;
8. stop for manual external review.

Do not implement before the RED tests are demonstrated.

## Allowed production scope

Changes are limited to files directly required for AUDIT-003 and AUDIT-004,
primarily:

- backend/app/services/measurement.py
- backend/app/repositories/measurement.py
- backend/app/repositories/measurement_session.py
- backend/app/schemas/_base.py
- backend/app/schemas/measurements.py
- backend/app/schemas/sessions.py
- backend/app/api/v1/endpoints/devices.py
- backend/app/api/v1/endpoints/measurements.py
- backend/app/api/v1/endpoints/sessions.py
- backend/app/core/exceptions.py only if the existing domain-error mechanism
  cannot represent chronology conflicts cleanly

Modify only the minimum necessary subset.

## Allowed test scope

Tests may be added or modified only where directly required, including:

- backend/tests/test_api_schemas.py
- backend/tests/test_api_routes.py
- backend/tests/test_services.py
- backend/tests/test_repositories.py
- backend/tests/test_api_openapi.py
- backend/tests/test_api_errors.py
- backend/tests/test_api_integration.py only if existing guarded integration
  behavior requires compatibility changes
- one focused new test module if it materially improves clarity

Do not modify integration guards or database cleanup policy.

## AUDIT-003 acceptance criteria

Prove all of the following:

1. A measurement before the active session start is rejected.
2. A measurement exactly at session start is accepted.
3. Completing a session before its latest measurement is rejected.
4. Cancelling a session before its latest measurement is rejected.
5. Ending exactly at the latest measurement timestamp is accepted.
6. A failed chronology check leaves session state, runtime state, sample count,
   and raw measurements unchanged.
7. The latest-measurement check occurs inside the service-owned transaction
   while the established device → runtime → session lock order is preserved.
8. Record versus complete/cancel cannot create a measurement outside the
   terminal interval under the existing lock order.
9. Existing valid ingestion and session-transition behavior remains unchanged.
10. Contradictory timestamp requests use the existing safe 409 envelope.

Use the smallest query needed to retrieve the latest measurement timestamp.
Do not introduce unbounded result loading.

## AUDIT-004 acceptance criteria

Prove all of the following:

1. Path identifiers accept 2_147_483_647.
2. Path identifiers reject 2_147_483_648 with the existing safe 422 envelope.
3. All six particle-counter fields accept 2_147_483_647.
4. All six particle-counter fields reject 2_147_483_648.
5. Rejected values never invoke the endpoint service or repository.
6. Existing lower-bound behavior remains unchanged.
7. OpenAPI exposes the integer maximum.
8. No API route, operation ID, successful response, or valid request behavior
   changes.
9. No database migration is added.

Prefer shared constrained aliases or schema definitions over repeated magic
numbers when that can be done without unrelated refactoring.

## Explicitly forbidden

Do not:

- implement telemetry read endpoints;
- implement AUDIT-005 or later findings;
- change the generic error envelope;
- change production debug/echo settings;
- change authentication, authorization, CORS, Docker, CI, logging, or
  observability;
- add clock-skew tolerance;
- change session status semantics;
- migrate INTEGER columns to BIGINT;
- create or modify Alembic revisions;
- modify ORM columns, constraints, indexes, foreign keys, or relationships;
- connect to PostgreSQL;
- create, inspect, migrate, clean, or drop a database;
- set or read database URL values;
- install or update dependencies;
- modify requirements;
- modify the audit report;
- modify README or unrelated documentation;
- modify Agent Skills;
- modify legacy files, firmware, secrets, certificates, keys, or .env files;
- perform Git write operations.

Read-only Git commands are allowed.

## Test environment

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Do not change this environment.

Run tests with:

- `-B`;
- `-p no:cacheprovider`;
- live database opt-ins absent;
- all PostgreSQL integration suites skipped.

## Required verification

At minimum run:

1. focused service chronology tests;
2. focused API/schema int32 tests;
3. affected existing service, repository, route, schema, and OpenAPI tests;
4. the complete offline backend test suite;
5. pip check;
6. guarded offline OpenAPI generation;
7. import/OpenAPI no-connection guards;
8. source compilation without repository bytecode;
9. git diff --check;
10. sensitive/generated-path checks;
11. final read-only diff and status inspection.

Expected API inventory remains:

- nine total operations;
- eight under /api/v1;
- one /health operation;
- unique operation IDs.

## Definition of done

Phase C2A is complete only when:

- RED tests reproduce AUDIT-003 and AUDIT-004;
- both findings are fixed;
- strict chronology policy is enforced;
- int32 public boundaries are enforced;
- existing valid behavior remains compatible;
- the full offline suite passes;
- OpenAPI inventory remains unchanged;
- no PostgreSQL connection occurred;
- no migration or ORM change exists;
- no unrelated finding or feature was implemented;
- no dependency, legacy, sensitive, or documentation file was changed;
- Codex performed no Git write operation;
- final response lists failing tests, changed files, commands, results,
  compatibility impact, limitations, and exact Git status.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8