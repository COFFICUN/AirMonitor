@'
# AirMonitor Agent Instructions

## Repository context

AirMonitor v1 is the stable legacy implementation stored at the repository
root.

Legacy assets are read-only unless the user explicitly requests changes:

- root app.py;
- root sensor_data.db;
- legacy frontend files;
- firmware and Arduino files;
- certificates, keys, credentials, and environment files;
- legacy Flask and SQLite files.

AirMonitor v2 lives under backend/ and uses FastAPI, PostgreSQL, async
SQLAlchemy, Alembic, Pydantic, and pytest.

Current branch:

feature/telemetry-read-api

## Governing documents

Read completely:

- docs/specs/telemetry-read-api.md
- docs/reviews/telemetry-read-api-source-audit.md
- docs/plans/telemetry-read-api-implementation-plan.md

The specification is the approved product contract.

The source audit defines the approved architecture and index strategy.

The implementation plan defines the approved test-first sequence.

Do not silently change approved decisions.

## Current task

Telemetry Read API — Phase B1.

This is an intentionally RED contract-test checkpoint.

Create only:

- backend/tests/test_telemetry_cursor.py
- backend/tests/test_telemetry_query_validation.py

Do not create or modify production code.

Do not implement:

- cursor codec;
- query models;
- query dependencies;
- routes;
- repositories;
- services;
- ORM models;
- Alembic migrations;
- indexes;
- settings;
- dependencies.

Stop after the failing tests are written and externally reviewed.

## Cursor v1 contract to lock with tests

Future production symbols:

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

Expected production module:

backend/app/services/telemetry_cursor.py

Exact cursor payload keys:

- f: normalized-filter fingerprint;
- p: last timestamp and identifier;
- r: resource kind;
- v: version 1.

Semantic payload:

{
  "f": "<sha256 fingerprint>",
  "p": ["2026-07-30T00:00:00.000000Z", 1],
  "r": "sessions",
  "v": 1
}

Wire format:

unpadded-base64url(UTF-8(canonical compact JSON))

Canonical JSON:

- sort_keys=True;
- separators=(",", ":");
- ensure_ascii=False;
- allow_nan=False.

Limits:

- encoded cursor maximum 2,048 ASCII characters;
- decoded cursor maximum 1,024 bytes;
- identifier range 1..2,147,483,647.

Timestamp format:

YYYY-MM-DDTHH:MM:SS.ffffffZ

Filter fingerprint:

- SHA-256;
- deterministic normalized filter document;
- includes resource kind;
- includes device_id;
- includes resource-specific filters;
- excludes limit;
- excludes cursor;
- contains no credentials or authorization information.

Cursor implementation must eventually be pure and standard-library only.

## Required cursor tests

Lock at minimum:

- sessions encode/decode round trip;
- measurements encode/decode round trip;
- deterministic encoding;
- canonical compact JSON;
- lexicographically sorted payload keys;
- UTF-8;
- URL-safe Base64 alphabet;
- absence of Base64 padding;
- exact canonical UTC timestamp;
- encoded size boundary;
- decoded size boundary;
- supported resource kinds;
- identifier minimum and maximum;
- fingerprint excludes limit;
- fingerprint excludes cursor;
- fingerprint changes when device_id changes;
- fingerprint changes when status changes;
- fingerprint changes when session_id changes;
- fingerprint changes when time filters change;
- duplicate JSON key rejection;
- unknown payload field rejection;
- missing payload field rejection;
- malformed Base64 rejection;
- padded Base64 rejection;
- non-ASCII cursor rejection;
- impossible Base64 length rejection;
- invalid UTF-8 rejection;
- malformed JSON rejection;
- trailing JSON rejection;
- NaN rejection;
- Infinity rejection;
- noncanonical JSON rejection;
- unsupported version rejection;
- Boolean version rejection;
- wrong resource-kind rejection;
- invalid position shape rejection;
- invalid timestamp rejection;
- noncanonical timestamp rejection;
- naive timestamp rejection;
- non-UTC timestamp rejection;
- invalid calendar timestamp rejection;
- Boolean identifier rejection;
- zero identifier rejection;
- negative identifier rejection;
- float identifier rejection;
- string identifier rejection;
- identifier above PostgreSQL INTEGER maximum rejection;
- malformed fingerprint rejection;
- fingerprint mismatch rejection;
- cursor position outside normalized time bounds rejection;
- cursor rejection for equal empty time range;
- cursor payload contains no credentials;
- cursor payload contains no database URL;
- cursor payload contains no token;
- cursor payload contains no settings;
- cursor payload contains no authorization state.

Tests must not contain a second implementation of:

- cursor encoding;
- cursor decoding;
- fingerprint generation;
- timestamp normalization;
- canonical serialization.

Tests may decode cursor wire bytes only for exact protocol assertions.

## Query validation contract

Future query models:

- SessionListQuery
- MeasurementListQuery

Expected module:

backend/app/schemas/telemetry.py

Future raw query boundary:

- strict_session_query_parameters
- strict_measurement_query_parameters
- resolve_session_read_request
- resolve_measurement_read_request

Expected module:

backend/app/api/query_validation.py

Session query keys:

- status
- started_from
- started_to
- limit
- cursor

Measurement query keys:

- session_id
- measured_from
- measured_to
- limit
- cursor

The raw dependency must eventually inspect:

request.query_params.multi_items()

It must reject:

- every unknown query key;
- every supported scalar key repeated more than once;
- repeated identical values;
- raw query values in error messages.

Pydantic query models must use:

extra="forbid"

## Required query tests

Lock at minimum:

- exact session allowlist;
- exact measurement allowlist;
- unknown session parameter rejected;
- unknown measurement parameter rejected;
- repeated supported scalar rejected;
- repeated identical scalar rejected;
- default limit 100;
- limit 1 accepted;
- limit 500 accepted;
- limit 0 rejected;
- limit 501 rejected;
- bounded positive session_id;
- session_id zero rejected;
- session_id above 2,147,483,647 rejected;
- active status accepted;
- completed status accepted;
- cancelled status accepted;
- invalid status rejected;
- case-changed status rejected;
- aware timestamps accepted;
- naive timestamps rejected;
- equivalent timezone offsets normalized consistently;
- from less than to accepted;
- from equal to to accepted;
- from greater than to rejected;
- cursor/filter mismatch rejected;
- safe 422 flow;
- validation performs no database access;
- validation performs no session access;
- validation performs no service access;
- validation performs no repository access;
- validation errors expose no raw query values;
- validation errors expose no cursor payload.

## Phase B1 test quality requirements

Tests must:

- be black-box contract tests;
- have meaningful names;
- avoid external dependencies;
- avoid PostgreSQL;
- avoid environment-value reads;
- avoid duplicated production logic;
- follow current pytest conventions;
- use shared fixtures only when they already exist;
- not weaken assertions to simplify future implementation.

If an existing fixture must be modified, report the requirement and stop.
Do not modify it automatically.

## Required workflow

Before editing:

1. report repository root;
2. report worktree path;
3. report detached HEAD and base commit;
4. report exact Git status;
5. list every loaded AGENTS.md;
6. list selected skills and order;
7. run the current offline baseline;
8. run pip check;
9. inspect current schema, error, and test conventions;
10. report the planned test structure;
11. explain how production logic will not be duplicated;
12. report the expected missing-symbol RED boundary.

After editing:

1. run both new test files;
2. confirm failures are only missing approved production symbols;
3. run all existing tests while excluding both new files;
4. run pip check;
5. run git diff --check;
6. verify exactly two new files exist;
7. scan for credentials, database URLs, local paths, and secrets;
8. report test count and line count;
9. report final Git status and diff stat;
10. stop for manual review.

## Test commands

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest command must include:

-B -p no:cacheprovider

Do not activate live integration tests.

Do not connect to PostgreSQL.

Do not read or print ambient database URL values.

Expected existing baseline:

- 550 passed;
- 2 skipped;
- OpenAPI 3.1.0;
- nine unique operations;
- eight under /api/v1;
- one /health;
- one Alembic head: a4f9c2e7d1b6.

## Allowed changes

Only:

- backend/tests/test_telemetry_cursor.py
- backend/tests/test_telemetry_query_validation.py

## Forbidden changes

Do not modify:

- AGENTS.md after the scope commit;
- backend/app;
- existing tests;
- backend/alembic;
- requirements;
- settings;
- README;
- approved specifications, audits, or plans;
- legacy files;
- Agent Skills;
- Git configuration.

## Git restrictions

Do not:

- stage;
- commit;
- push;
- create or delete branches;
- reset;
- clean;
- stash;
- modify Git configuration.

Read-only Git commands are allowed.

## Definition of done

Phase B1 is complete only when:

- exactly two new test files exist;
- no production file changed;
- approved contracts are comprehensively covered;
- tests do not duplicate production implementation;
- focused tests are intentionally RED only because approved symbols do not
  exist;
- existing offline tests remain green;
- no database or secret access occurs;
- Git index remains unchanged;
- work stops for manual external review.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8