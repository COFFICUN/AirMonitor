@'
# AirMonitor Agent Instructions

## Repository context

AirMonitor v1 is the stable legacy implementation stored at the repository
root.

The following legacy assets are read-only reference material and must not be
modified unless the user explicitly requests it:

- root app.py;
- root sensor_data.db;
- legacy HTML, CSS, and JavaScript;
- firmware and Arduino files;
- certificates, private keys, credentials, and environment files;
- legacy Flask and SQLite implementation files.

AirMonitor v2 lives under backend/ and uses:

- FastAPI;
- PostgreSQL;
- SQLAlchemy async engine and sessions;
- Alembic;
- Pydantic Settings;
- pytest.

The current development branch is based on the completed Sprint 8
stabilization baseline.

## Current task

Telemetry Read API — Phase A: source audit, index analysis, and implementation
plan.

This is a documentation-only planning phase.

The approved product and API contract already exists at:

docs/specs/telemetry-read-api.md

Treat that specification as authoritative unless it directly contradicts
current production source. Report contradictions instead of silently changing
the approved contract.

## Approved MVP

Exactly two future endpoints:

- GET /api/v1/devices/{device_id}/sessions
- GET /api/v1/devices/{device_id}/measurements

Proposed operation IDs:

- list_device_sessions
- list_device_measurements

Do not add other endpoints to the MVP.

### Session ordering

Stable descending keyset ordering:

started_at DESC, id DESC

Filters:

- status;
- started_from;
- started_to;
- limit;
- cursor.

### Measurement ordering

Stable descending keyset ordering:

measured_at DESC, id DESC

Filters:

- session_id;
- measured_from;
- measured_to;
- limit;
- cursor.

### Pagination

- keyset pagination only;
- no offset pagination;
- default limit 100;
- minimum 1;
- maximum 500;
- fetch limit + 1 to determine next_cursor;
- cursor is exclusive;
- URL-safe;
- opaque to clients;
- versioned;
- filter-bound;
- must contain no credentials or secrets;
- malformed, unsupported, mismatched, or semantically invalid cursor produces
  safe 422.

Required keyset predicates:

For sessions after a cursor position:

started_at < cursor_started_at
OR (
    started_at = cursor_started_at
    AND id < cursor_id
)

For measurements after a cursor position:

measured_at < cursor_measured_at
OR (
    measured_at = cursor_measured_at
    AND id < cursor_id
)

### Time ranges

Use half-open UTC ranges:

[from, to)

Approved equality behavior:

- from greater than to is invalid and produces safe 422;
- from equal to to returns an empty page;
- device existence must still be established before returning the empty page.

All timestamps must be timezone-aware and normalized consistently with current
application behavior.

### Response envelope

Both endpoints return:

{
  "items": [],
  "next_cursor": null
}

Use exact current schema and ORM field names.

Do not invent response fields.

### Errors

Document and later preserve:

- 200 success;
- 404 unknown device;
- 422 invalid path identifier, query parameter, timestamp, limit, range, or
  cursor;
- safe generic 500;
- current ErrorResponse terminology.

All identifiers mapped to PostgreSQL INTEGER must remain within:

1..2147483647

### Query validation

The future implementation must reject:

- unknown query parameters;
- repeated scalar query parameters;
- invalid status values;
- invalid timestamp ranges;
- invalid cursor/filter combinations.

Inspect current FastAPI behavior and identify the exact implementation boundary
needed to enforce this contract.

Do not assume FastAPI rejects unknown query parameters automatically.

### Authorization

The current v2 backend has no authentication or authorization.

The read endpoints inherit the existing trusted-network model.

Do not:

- add authentication during this phase;
- treat cursor contents as authorization;
- approve public internet exposure;
- introduce rate limiting during this phase.

## Phase A scope

Create only:

- docs/reviews/telemetry-read-api-source-audit.md
- docs/plans/telemetry-read-api-implementation-plan.md

Do not modify:

- AGENTS.md after the scope commit;
- backend application code;
- backend tests;
- ORM models;
- Alembic revisions;
- requirements;
- environment templates;
- README;
- the approved API specification;
- legacy files;
- Agent Skills;
- Git state.

Directories may be created only when needed for the two approved documents.

## Required source audit

Read the approved specification completely.

Inspect current source for:

- API routers;
- endpoint dependencies;
- error handling;
- request validation;
- response schemas;
- session schemas;
- measurement schemas;
- device schemas;
- ORM models;
- repositories;
- services;
- transaction ownership;
- async database lifecycle;
- existing indexes and constraints;
- current Alembic migration;
- OpenAPI tests;
- service tests;
- repository tests;
- API tests;
- PostgreSQL integration tests;
- integration guards;
- existing pagination or encoding utilities;
- current dependencies.

Generate the OpenAPI schema offline.

Do not connect to PostgreSQL.

Do not read or print ambient database URL values.

## Index analysis

Create an exact inventory of current indexes and relevant constraints for:

- devices;
- measurement_sessions;
- raw_measurements.

Map every proposed query pattern to the current index inventory.

Analyze at minimum:

### Sessions

Device filter plus ordering:

device_id = ?
ORDER BY started_at DESC, id DESC

Optional status:

device_id = ?
AND status = ?
ORDER BY started_at DESC, id DESC

Optional time range:

device_id = ?
AND started_at >= ?
AND started_at < ?
ORDER BY started_at DESC, id DESC

Cursor continuation:

device_id = ?
AND (
    started_at < ?
    OR (started_at = ? AND id < ?)
)
ORDER BY started_at DESC, id DESC

### Measurements

Device filter plus ordering:

device_id = ?
ORDER BY measured_at DESC, id DESC

Optional session filter:

device_id = ?
AND session_id = ?
ORDER BY measured_at DESC, id DESC

Optional time range:

device_id = ?
AND measured_at >= ?
AND measured_at < ?
ORDER BY measured_at DESC, id DESC

Cursor continuation:

device_id = ?
AND (
    measured_at < ?
    OR (measured_at = ? AND id < ?)
)
ORDER BY measured_at DESC, id DESC

Do not claim an index is sufficient only because some indexed columns overlap.

Consider:

- equality column order;
- ordering column order;
- descending traversal;
- tie-breaking id;
- optional status;
- optional session_id;
- foreign-key indexes;
- write amplification;
- duplicate or redundant indexes;
- PostgreSQL btree behavior;
- migration downgrade safety.

The audit must reach one explicit conclusion:

1. existing indexes are sufficient and no migration is required; or
2. a reviewed Alembic migration is required.

If a migration is required, propose exact:

- index names;
- table names;
- ordered columns;
- sort directions;
- optional predicates;
- upgrade operations;
- downgrade operations;
- redundant indexes that should remain or be removed.

Do not create the migration during Phase A.

## Cursor design analysis

Derive an implementation-ready cursor boundary from the approved
specification.

Document:

- cursor version field;
- resource kind;
- last timestamp;
- last identifier;
- normalized filter fingerprint;
- encoding format;
- URL-safe Base64 behavior;
- padding policy;
- canonical JSON rules;
- maximum decoded and encoded size;
- integer validation;
- timestamp validation;
- resource-kind mismatch;
- filter mismatch;
- unsupported version;
- malformed Base64;
- malformed JSON;
- duplicate JSON keys;
- unknown cursor fields;
- safe error mapping.

Cursor data must not contain:

- passwords;
- database URLs;
- device credentials;
- access tokens;
- authorization state.

Do not implement the codec during Phase A.

## Architecture plan

Identify the exact future implementation files and responsibilities.

The plan must cover:

- query parameter schemas or dependencies;
- strict unknown/repeated query validation;
- list response schemas;
- cursor codec;
- filter normalization;
- repositories;
- services;
- routes;
- router registration;
- error mapping;
- OpenAPI operation IDs;
- tests;
- optional Alembic migration.

Preserve the current dependency direction.

Routes must not contain raw SQL or transaction logic.

Services must not manually encode HTTP responses.

Repositories must not depend on FastAPI.

Cursor code must not depend on SQLAlchemy sessions.

Read operations must not mutate:

- device runtime state;
- measurement sessions;
- raw measurements;
- sample_count;
- last_seen_at.

## Test plan

Design failing tests before implementation.

The test plan must include:

### Schema and validation

- exact response fields;
- limit defaults and bounds;
- PostgreSQL INTEGER boundaries;
- timezone-aware timestamps;
- from greater than to;
- from equal to to;
- invalid status;
- unknown query parameter;
- repeated scalar query parameter.

### Cursor codec

- encode/decode round trip;
- deterministic canonicalization;
- URL-safe output;
- no padding ambiguity;
- malformed Base64;
- oversized cursor;
- malformed JSON;
- duplicate keys;
- unknown fields;
- unsupported version;
- wrong resource kind;
- invalid timestamp;
- invalid identifier;
- filter fingerprint mismatch.

### Repository and service behavior

- stable descending ordering;
- identical timestamps ordered by id;
- limit + 1 behavior;
- correct next_cursor;
- final page has null cursor;
- no skipped rows;
- no duplicate rows;
- status filtering;
- session filtering;
- half-open time filtering;
- unknown device 404;
- equal range checks device existence before empty result;
- read-only behavior;
- no runtime-state mutation.

### API and OpenAPI

- both paths;
- both operation IDs;
- 200 responses;
- safe 404;
- safe 422;
- safe generic 500;
- response envelope;
- existing nine operations unchanged;
- final OpenAPI contains eleven unique operations.

### PostgreSQL integration

Plan live tests for:

- real ordering;
- tie-breaking;
- cursor continuation;
- repeated execution on disposable databases;
- cleanup;
- identity reset if existing suite contract still applies;
- any new migration and index existence.

Do not activate live tests during Phase A.

## Required documents

### Source audit

Create:

docs/reviews/telemetry-read-api-source-audit.md

Include:

- current branch and base commit;
- current OpenAPI inventory;
- current relevant source layout;
- exact ORM fields;
- exact response fields;
- current validation conventions;
- current error conventions;
- current repository/service boundaries;
- current index inventory;
- query-to-index analysis;
- cursor implementation constraints;
- contradictions or ambiguities;
- explicit migration decision;
- risks and blockers.

### Implementation plan

Create:

docs/plans/telemetry-read-api-implementation-plan.md

Use small reviewable phases.

At minimum:

1. failing cursor and query validation tests;
2. cursor and filter primitives;
3. failing repository/service tests;
4. repository queries;
5. service orchestration;
6. failing API/OpenAPI tests;
7. routes and schemas;
8. Alembic migration if required;
9. offline verification;
10. live disposable PostgreSQL verification;
11. documentation update;
12. review, commit, and merge sequence.

For every phase state:

- goal;
- files allowed to change;
- tests written first;
- implementation boundary;
- commands;
- expected result;
- rollback or failure condition;
- proposed commit message.

Do not combine the entire feature into one implementation commit.

## Verification

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest invocation must include:

-B -p no:cacheprovider

Run:

- full offline backend suite;
- OpenAPI tests;
- relevant schema tests;
- relevant service and repository tests;
- integration guard tests;
- pip check;
- Alembic heads;
- git diff --check.

Generate OpenAPI offline without database access.

Expected baseline before implementation:

- 550 passed;
- 2 skipped;
- OpenAPI 3.1.0;
- nine unique operations;
- eight under /api/v1;
- one /health;
- one Alembic head: a4f9c2e7d1b6.

## Safety

Do not:

- connect to PostgreSQL;
- create a database;
- run live integration tests;
- read or print database URL values;
- modify production code;
- modify tests;
- modify migrations;
- install dependencies;
- stage files;
- commit;
- push;
- create branches;
- modify Git configuration.

Read-only Git commands are allowed.

## Definition of done

Phase A is complete only when:

- both required documents exist;
- all factual claims are source-grounded;
- the exact current index inventory is documented;
- an explicit migration decision is made;
- cursor behavior is implementation-ready;
- strict query validation has a concrete implementation strategy;
- the work is divided into small test-first phases;
- no production or test file changed;
- offline baseline remains green;
- no sensitive information is exposed;
- final Git status is reported;
- work stops for manual external review.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8