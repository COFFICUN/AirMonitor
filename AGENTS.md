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
- backend/app/repositories/measurement.py
- backend/app/repositories/measurement_session.py
- backend/tests/test_telemetry_cursor.py
- backend/tests/test_telemetry_query_validation.py
- backend/tests/test_telemetry_read_repositories.py
- backend/tests/test_telemetry_read_services.py

Inspect existing schema, dependency-provider, route, OpenAPI, error, and
architecture test conventions before editing.

## Current task

Telemetry Read API — Phase D1.

This is an intentionally RED public API and OpenAPI contract checkpoint.

Modify only:

- backend/tests/test_api_schemas.py
- backend/tests/test_api_routes.py
- backend/tests/test_api_openapi.py
- backend/tests/test_api_dependencies.py
- backend/tests/test_api_architecture.py

Do not modify production code.

Do not create new test files.

Stop for manual external review after the RED checkpoint.

## Future public response schemas

The future module remains:

backend/app/schemas/telemetry.py

Approved future response symbols:

- SessionListResponse
- MeasurementListResponse

SessionListResponse exact fields:

- items: list[SessionResponse]
- next_cursor: str | None

MeasurementListResponse exact fields:

- items: list[MeasurementResponse]
- next_cursor: str | None

Reuse the existing concrete item schemas:

- app.schemas.sessions.SessionResponse
- app.schemas.measurements.MeasurementResponse

Do not create competing session or measurement item schemas.

Do not add:

- total;
- page;
- offset;
- has_more;
- count;
- internal IDs beyond fields already present in the existing item schemas;
- metadata dictionaries.

The response envelope contains exactly:

{
  "items": [...],
  "next_cursor": null
}

or:

{
  "items": [...],
  "next_cursor": "<opaque cursor>"
}

## Exact session item fields

The existing SessionResponse fields remain authoritative:

- id
- device_id
- status
- started_at
- ended_at
- latitude
- longitude
- sample_count
- created_at

Do not add or remove item fields.

## Exact measurement item fields

The existing MeasurementResponse fields remain authoritative:

- id
- device_id
- session_id
- source_message_id
- measured_at
- received_at
- temperature
- humidity
- pm1
- pm25
- pm10
- pc0_3
- pc0_5
- pc1_0
- pc2_5
- pc5_0
- pc10
- latitude
- longitude
- is_valid
- validation_note
- created_at

Do not add or remove item fields.

## Future service providers

Future provider symbols in backend/app/api/dependencies.py:

- get_session_telemetry_query_service
- get_measurement_telemetry_query_service

Each provider:

- receives the existing request-scoped AsyncSession dependency;
- constructs the matching query service;
- passes that exact session object to the service;
- creates no additional session;
- performs no query or transaction work.

## Exact routes

Future routes:

GET /api/v1/devices/{device_id}/sessions

Operation ID:

list_device_sessions

GET /api/v1/devices/{device_id}/measurements

Operation ID:

list_device_measurements

Both return HTTP 200.

Both document exactly:

- 200
- 404
- 422
- 500

Existing common framework responses may be represented through the current
project response helpers, but no extra domain status such as 409 is introduced
for these reads.

## Session route behavior

The future session GET operation:

- uses the existing bounded positive PostgreSQL INTEGER device_id path;
- applies strict_session_query_parameters as a decorator dependency;
- depends on resolve_session_read_request;
- depends on get_session_telemetry_query_service;
- awaits exactly one list_sessions(read_request=...) call;
- converts service ORM items through SessionResponse;
- returns SessionListResponse;
- preserves page order;
- returns page.next_cursor unchanged.

Approved query parameters:

- status
- started_from
- started_to
- limit
- cursor

## Measurement route behavior

The future measurement GET operation:

- uses the existing bounded positive PostgreSQL INTEGER device_id path;
- applies strict_measurement_query_parameters as a decorator dependency;
- depends on resolve_measurement_read_request;
- depends on get_measurement_telemetry_query_service;
- awaits exactly one list_measurements(read_request=...) call;
- converts service ORM items through MeasurementResponse;
- returns MeasurementListResponse;
- preserves page order;
- returns page.next_cursor unchanged.

Approved query parameters:

- session_id
- measured_from
- measured_to
- limit
- cursor

## HTTP behavior to lock in tests

Tests must cover:

- both GET paths return 200;
- exact response envelope;
- exact public item fields;
- JSON datetime and numeric serialization;
- default limit forwarding;
- explicit limit forwarding;
- all approved filters forwarding;
- next_cursor forwarding;
- empty list behavior;
- safe unknown-device 404;
- malformed path/query/cursor safe 422;
- generic failure safe 500;
- unknown query parameter never calls service;
- repeated query parameter never calls service;
- repeated identical query parameter never calls service;
- equal from/to reaches the service so device existence remains enforceable;
- service receives the exact resolved read_request;
- service is awaited exactly once;
- no mutation or transaction method is called.

For measurements:

- a valid nonexistent session_id produces an empty 200 page;
- a valid session_id belonging to another device also produces an empty 200
  page;
- the endpoint must not reveal whether the session exists or who owns it.

This behavior is implemented by normal device-scoped repository filtering, not
by a separate session ownership error.

## Route compatibility

The existing static route:

GET /api/v1/devices/{device_id}/sessions/active

must remain unchanged and reachable.

The new collection route must not collide with it.

Do not change the existing nine operation contracts.

## OpenAPI contract

After future implementation OpenAPI must contain:

- version 3.1.0;
- 11 total operations;
- 10 under /api/v1;
- 1 under /health;
- 11 unique operation IDs.

New operation IDs are exactly:

- list_device_sessions
- list_device_measurements

Success responses must reference concrete list envelope schemas.

OpenAPI tests must verify:

- both GET paths;
- exact operation IDs;
- 200/404/422/500 documented responses;
- query parameter names;
- query parameter types;
- limit default 100;
- limit minimum 1;
- limit maximum 500;
- cursor maximum length 2048;
- status enum active/completed/cancelled;
- device_id PostgreSQL INTEGER maximum;
- session_id PostgreSQL INTEGER maximum;
- timestamps represented as date-time values.

Capture and compare the existing nine operation contracts before adding new
assertions. They must remain structurally equivalent.

Do not use fragile whole-document snapshotting when targeted structural
comparison is sufficient.

## Architecture tests

Add assertions proving future routes:

- do not import repositories;
- do not import SQLAlchemy statement builders;
- do not call select, where, order_by, limit, offset, begin, commit, rollback,
  flush, or delete;
- do not instantiate AsyncSession;
- depend on service providers;
- use concrete response models, not dict or Any.

Retain existing architecture policies.

## Test implementation boundary

API tests must override the future service providers.

They must not:

- instantiate a real database session;
- contact PostgreSQL;
- read database URLs;
- activate integration suites;
- duplicate query-service behavior;
- duplicate cursor encoding;
- modify global environment values without exact restoration;
- rely on route implementation internals beyond the public dependency
  contract.

Use production cursor helpers when a valid cursor is required.

## Expected RED boundary

Existing tests must remain green.

New assertions may fail only because the approved future symbols and GET
operations do not exist yet:

- SessionListResponse;
- MeasurementListResponse;
- get_session_telemetry_query_service;
- get_measurement_telemetry_query_service;
- GET session list route;
- GET measurement list route.

No syntax failure, unrelated import failure, PostgreSQL access, or existing
contract regression is acceptable.

Do not use:

- conditional imports;
- fallback implementations;
- skips;
- xfail;
- importlib workarounds.

## Baseline

Before editing:

- full offline suite: 782 passed, 2 skipped;
- OpenAPI 3.1.0;
- 9 operations;
- 8 /api/v1 operations;
- 1 /health operation;
- 9 unique operation IDs;
- Alembic head a4f9c2e7d1b6.

## Verification

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest command must include:

-B -p no:cacheprovider

Do not connect to PostgreSQL.

Before editing run:

- full offline suite;
- API schema tests;
- API route tests;
- OpenAPI tests;
- dependency tests;
- architecture tests;
- pip check;
- git diff --check.

After editing run:

- all five modified API test files;
- classify every intentional RED failure;
- prove existing assertions remain green;
- run the existing suite excluding only newly added telemetry assertions when
  technically necessary;
- run pip check;
- run git diff --check;
- run syntax parsing;
- run scope scan;
- run secret and local-path scans.

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

Phase D1 is complete only when:

- exactly the five approved test files changed;
- no production file changed;
- schema envelope contracts are covered;
- dependency providers are covered;
- both route contracts are covered;
- unknown/repeated parameters are proven to avoid service calls;
- equal ranges are proven to reach the service;
- existing active-session route remains compatible;
- existing nine OpenAPI contracts remain unchanged;
- future OpenAPI inventory is fixed at eleven operations;
- focused failures concern only approved missing production boundaries;
- no PostgreSQL or Git write occurs;
- work stops for manual external review.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8