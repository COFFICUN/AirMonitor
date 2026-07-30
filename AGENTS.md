@'
# AirMonitor Agent Instructions

## Repository context

AirMonitor v1 at the repository root is stable legacy reference material and
must not be modified.

AirMonitor v2 lives under backend/ and uses FastAPI, PostgreSQL, async
SQLAlchemy, Alembic, Pydantic, and pytest.

Current branch:

feature/telemetry-read-api

## Governing documents

Read completely:

- docs/specs/telemetry-read-api.md
- docs/reviews/telemetry-read-api-source-audit.md
- docs/plans/telemetry-read-api-implementation-plan.md
- backend/tests/test_telemetry_cursor.py
- backend/tests/test_telemetry_query_validation.py

The two telemetry test files are the approved Phase B1 contract.

## Current task

Telemetry Read API — Phase B2.

Implement only:

- cursor v1 primitives;
- normalized telemetry read filters and request values;
- strict raw query validation;
- typed telemetry query models;
- pure request resolvers.

Do not implement routes, repositories, read services, ORM changes, indexes, or
Alembic migrations.

## Required pre-implementation RED addition

Before creating production code, add a parameterized test proving that cursor
positions exactly equal to the normalized lower time bound are accepted for:

- sessions;
- measurements.

This locks half-open range behavior:

[from, to)

The lower bound is inclusive and the upper bound is exclusive.

Run the focused test and record the intentional missing-production-module RED
before implementation.

## Allowed production files

Create:

- backend/app/services/telemetry_cursor.py
- backend/app/schemas/telemetry.py
- backend/app/api/query_validation.py

Modify only when required by current export conventions:

- backend/app/services/__init__.py
- backend/app/schemas/__init__.py
- backend/app/schemas/_base.py

Allowed tests:

- backend/tests/test_telemetry_cursor.py
- backend/tests/test_telemetry_query_validation.py

Do not modify other files.

## Approved public symbols

From app.services.telemetry_cursor:

- CursorResource
- CursorPosition
- CursorValidationError
- SessionReadFilters
- MeasurementReadFilters
- SessionReadRequest
- MeasurementReadRequest
- normalize_session_filters
- normalize_measurement_filters
- encode_cursor
- decode_cursor

From app.schemas.telemetry:

- SessionListQuery
- MeasurementListQuery

From app.api.query_validation:

- strict_session_query_parameters
- strict_measurement_query_parameters
- resolve_session_read_request
- resolve_measurement_read_request

## Cursor value structure

CursorPosition fields, in order:

- timestamp
- identifier

SessionReadRequest and MeasurementReadRequest fields, in order:

- filters
- limit
- position

Use immutable plain values such as frozen dataclasses where appropriate.

## Cursor payload

Exact keys:

- f
- p
- r
- v

Exact semantic structure:

{
  "f": "<filter fingerprint>",
  "p": ["2026-07-30T00:00:00.000000Z", 1],
  "r": "sessions",
  "v": 1
}

Wire format:

unpadded-base64url(UTF-8(canonical compact JSON))

Canonical JSON:

- sort_keys=True
- separators=(",", ":")
- ensure_ascii=False
- allow_nan=False

Limits:

- encoded cursor <= 2,048 ASCII characters;
- decoded payload <= 1,024 bytes;
- identifier range 1..2,147,483,647.

Exact timestamp format:

YYYY-MM-DDTHH:MM:SS.ffffffZ

## Fingerprint clarification

The B1 known vectors are authoritative.

Session default filter document:

{"device_id":7,"started_from":null,"started_to":null,"status":null}

Expected fingerprint:

Fyo9RltXgZFinDACG7SKuXhr-Q32CVEDDYbC8Cqwsxc

Measurement default filter document:

{"device_id":7,"measured_from":null,"measured_to":null,"session_id":null}

Expected fingerprint:

ARdRoG52q4S4U3swx-AGuessvtbNE602TFCaubU_aMA

Fingerprint:

- SHA-256 of canonical normalized filter JSON;
- Base64url without padding;
- excludes limit;
- excludes cursor position;
- contains no credentials or authorization state.

The resource kind is bound separately through the exact payload field r and
must be validated independently.

Do not add the resource field inside the fingerprint document because that
would violate the approved known vectors.

## Cursor decoder

Validate in a fail-closed sequence:

1. exact input type;
2. ASCII;
3. encoded-size limit;
4. no padding;
5. Base64url alphabet and possible length;
6. strict Base64 decoding;
7. decoded-size limit;
8. strict UTF-8;
9. JSON object only;
10. duplicate-member rejection;
11. NaN and Infinity rejection;
12. exact fields f, p, r, v;
13. canonical reserialization equality;
14. exact integer version 1, excluding Boolean;
15. exact supported string resource;
16. expected-resource match;
17. exact two-member position array;
18. canonical UTC timestamp;
19. exact bounded integer identifier, excluding Boolean;
20. fingerprint shape;
21. fingerprint equality;
22. normalized time-bound compatibility.

All failures must raise one sanitized CursorValidationError.

Do not expose:

- raw cursor;
- payload;
- fingerprint;
- parser error;
- query values;
- credentials.

## Purity boundary

app.services.telemetry_cursor may use only standard-library facilities for:

- base64;
- json;
- hashlib;
- datetime;
- dataclasses;
- enums/literals;
- typing.

It must not import:

- FastAPI;
- Starlette;
- Pydantic;
- SQLAlchemy;
- AsyncSession;
- ORM models;
- settings;
- database modules;
- authentication state.

## Query models

SessionListQuery:

- status
- started_from
- started_to
- limit
- cursor

MeasurementListQuery:

- session_id
- measured_from
- measured_to
- limit
- cursor

Requirements:

- extra="forbid";
- limit default 100;
- limit range 1..500;
- cursor length <= 2,048;
- session_id range 1..2,147,483,647;
- status exactly active, completed, or cancelled;
- reject naive timestamps;
- normalize aware timestamps to UTC;
- accept from < to;
- accept from == to;
- reject from > to.

Reuse or add a shared bounded PostgreSQL INTEGER annotation in
app.schemas._base without changing existing field behavior.

## Strict raw query dependencies

Inspect:

request.query_params.multi_items()

Use separate allowlists.

Sessions:

- status
- started_from
- started_to
- limit
- cursor

Measurements:

- session_id
- measured_from
- measured_to
- limit
- cursor

Reject:

- unknown keys;
- cross-endpoint keys;
- any repeated supported scalar;
- repeated identical values.

Common keys limit and cursor are accepted for both resources.

Raw validation performs no database, service, repository, session, or settings
access.

## Resolvers

Resolvers:

- receive bounded device_id;
- receive the typed query model;
- normalize filters;
- decode cursor when present;
- return SessionReadRequest or MeasurementReadRequest;
- keep limit outside the fingerprint;
- map cursor failures into the existing sanitized HTTP 422 flow;
- perform no database work.

Use existing RequestValidationError handling conventions.

Do not manually return an HTTP response.

## Scope exclusions

Do not modify or implement:

- API routes;
- router registration;
- repositories;
- telemetry query services;
- response-list schemas;
- ORM models;
- Alembic;
- indexes;
- requirements;
- settings;
- integration tests;
- README;
- approved documents;
- legacy files.

## Verification

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest invocation must include:

-B -p no:cacheprovider

Do not connect to PostgreSQL.

Do not activate live integration tests.

Run:

1. the new lower-bound RED test before implementation;
2. both telemetry focused files;
3. existing API schema and API error tests;
4. full offline backend suite;
5. pip check;
6. guarded OpenAPI tests;
7. git diff --check;
8. import-boundary scan;
9. scope scan;
10. secret and local-path scan.

Expected OpenAPI remains:

- 3.1.0;
- nine operations;
- eight under /api/v1;
- one /health;
- nine unique operation IDs.

## Git restrictions

Do not stage, commit, push, create branches, reset, clean, stash, or modify Git
configuration.

Read-only Git commands are allowed.

## Definition of done

Phase B2 is complete only when:

- the lower-bound contract was added before implementation;
- all telemetry cursor tests pass;
- all telemetry query-validation tests pass;
- existing API schema/error tests pass;
- full offline suite passes;
- OpenAPI remains unchanged;
- no route, repository, ORM, migration, or dependency change occurs;
- cursor module remains pure;
- no database access occurs;
- final output reports changed files and exact Git status;
- work stops for manual external review.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8