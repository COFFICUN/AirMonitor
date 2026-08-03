@'
# AirMonitor Agent Instructions

## Repository context

AirMonitor v1 at the repository root is stable legacy reference material and
must not be modified.

AirMonitor v2 lives under backend/ and uses FastAPI, PostgreSQL, async
SQLAlchemy, Alembic, Pydantic, and pytest.

Current feature branch:

feature/telemetry-read-api

## Governing contracts

Read completely:

- docs/specs/telemetry-read-api.md
- docs/reviews/telemetry-read-api-source-audit.md
- docs/plans/telemetry-read-api-implementation-plan.md
- backend/app/services/telemetry_cursor.py
- backend/app/services/telemetry.py
- backend/app/schemas/telemetry.py
- backend/app/api/query_validation.py
- backend/app/api/dependencies.py
- backend/app/api/v1/endpoints/sessions.py
- backend/app/api/v1/endpoints/measurements.py
- backend/tests/test_api_schemas.py
- backend/tests/test_api_routes.py
- backend/tests/test_api_openapi.py
- backend/tests/test_api_dependencies.py
- backend/tests/test_api_architecture.py

The approved Phase D1 tests must not be weakened.

## Current task

Telemetry Read API — Phase D3.

Implement only the two approved telemetry collection GET routes.

Do not modify tests.

Do not implement indexes or Alembic migrations in this phase.

## Allowed production changes

Modify only:

- backend/app/api/v1/endpoints/sessions.py
- backend/app/api/v1/endpoints/measurements.py

Do not modify or create any other file.

## Exact session route

Add:

GET /api/v1/devices/{device_id}/sessions

Function name:

list_device_sessions

Operation ID:

list_device_sessions

Return annotation and response model:

SessionListResponse

Required dependencies:

- strict_session_query_parameters
- resolve_session_read_request
- get_session_telemetry_query_service

The exact Depends target set must contain only those three dependencies.

Use strict_session_query_parameters as a decorator dependency.

The resolver supplies the exact SessionReadRequest instance.

The service provider supplies SessionTelemetryQueryService.

Await exactly:

service.list_sessions(read_request=read_request)

Construct:

SessionListResponse(
    items=list(page.items),
    next_cursor=page.next_cursor,
)

Preserve item ordering.

Do not modify page items.

Do not encode or decode cursors in the route.

## Exact measurement route

Add:

GET /api/v1/devices/{device_id}/measurements

Function name:

list_device_measurements

Operation ID:

list_device_measurements

Return annotation and response model:

MeasurementListResponse

Required dependencies:

- strict_measurement_query_parameters
- resolve_measurement_read_request
- get_measurement_telemetry_query_service

The exact Depends target set must contain only those three dependencies.

Use strict_measurement_query_parameters as a decorator dependency.

Await exactly:

service.list_measurements(read_request=read_request)

Construct:

MeasurementListResponse(
    items=list(page.items),
    next_cursor=page.next_cursor,
)

Preserve item ordering.

Do not perform a separate lookup or ownership check for session_id.

## Path handling

Use the existing project convention for a positive bounded PostgreSQL INTEGER
device_id path parameter.

Do not introduce a second path type or competing alias.

The maximum remains:

2_147_483_647

## Query parameters

Do not declare telemetry query parameters directly in route signatures.

They must come exclusively from:

- resolve_session_read_request
- resolve_measurement_read_request

Approved session query parameters:

- status
- started_from
- started_to
- limit
- cursor

Approved measurement query parameters:

- session_id
- measured_from
- measured_to
- limit
- cursor

## Strict raw-query guard

Decorator dependencies must run before the service:

Sessions:

Depends(strict_session_query_parameters)

Measurements:

Depends(strict_measurement_query_parameters)

Unknown or repeated query parameters must produce safe 422 responses without
calling the service.

## Response and error documentation

Both GET routes document exactly:

- 200
- 404
- 422
- 500

Do not document 409.

Reuse the current project error-response helpers and descriptions where they
produce the exact approved response set.

Success responses use the concrete list response models.

## Compatibility

Do not alter any existing POST route.

The existing static route:

GET /api/v1/devices/{device_id}/sessions/active

must remain reachable and unchanged.

The two new GET operations share paths with existing POST operations but use a
different HTTP method.

## Architecture boundary

Routes must not:

- import repositories;
- import SQLAlchemy;
- import AsyncSession;
- call select, where, order_by, limit or offset;
- perform device existence checks themselves;
- perform session ownership checks;
- begin, commit, rollback or flush;
- catch broad exceptions;
- encode or decode cursors;
- return dict or Any;
- create database sessions.

Routes are thin HTTP adapters only.

## Expected final behavior

All approved Phase D1 API tests become GREEN.

Expected focused API result:

- 186 passed.

Expected full offline suite:

- 831 passed;
- 2 skipped.

OpenAPI:

- 3.1.0;
- 11 total operations;
- 10 under /api/v1;
- 1 under /health;
- 11 unique operation IDs.

New operation IDs:

- list_device_sessions;
- list_device_measurements.

Existing nine operation contracts remain unchanged.

Alembic head remains:

a4f9c2e7d1b6

## Verification environment

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest command must include:

-B -p no:cacheprovider

Do not connect to PostgreSQL.

Do not activate integration suites.

## Required implementation order

1. run the five D1 files and record the 40-failure baseline;
2. inspect existing endpoint conventions;
3. implement the session GET route only;
4. run session telemetry route and OpenAPI cases;
5. implement the measurement GET route only;
6. run measurement telemetry route and OpenAPI cases;
7. run all five D1 files;
8. run telemetry cursor/query-validation tests;
9. run repository/service tests;
10. run the full offline backend suite;
11. run OpenAPI tests;
12. run pip check;
13. run git diff --check;
14. run syntax, architecture, scope, secret, database URL,
    environment-read and local-path scans.

## Git restrictions

Do not:

- stage;
- commit;
- push;
- reset;
- clean;
- stash;
- create or delete branches;
- modify Git configuration.

Read-only Git commands are allowed.

## Definition of done

Phase D3 is complete only when:

- exactly two approved endpoint files changed;
- no tests changed;
- both collection GET routes work;
- exact response envelopes are returned;
- service methods are awaited exactly once;
- unknown and repeated query parameters never call services;
- equal ranges reach the service;
- active-session route remains compatible;
- OpenAPI contains exactly eleven operations;
- all offline tests pass;
- no PostgreSQL or Git write occurs;
- Git index remains unchanged;
- work stops for manual external review.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8