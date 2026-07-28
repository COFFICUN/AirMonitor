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
- certificates, keys, secrets, and environment files;
- legacy Flask and SQLite implementation files.

AirMonitor v2 lives under backend/ and uses FastAPI, SQLAlchemy, Alembic,
PostgreSQL, Pydantic, and pytest.

## Current active task

Sprint 8 Phase C4C — Documentation and Telemetry Read API Contract.

This is a documentation-only phase.

Implement only:

- close AUDIT-014 by rewriting README.md against the verified AirMonitor v2
  implementation;
- document the completed C4B live PostgreSQL verification;
- create a source-grounded specification for the future Telemetry Read API.

Read completely:

- docs/reviews/sprint-8-full-codebase-audit.md
- docs/reviews/sprint-8-final-verification.md
- current README.md
- backend application, configuration, migration, requirements, tests, and
  OpenAPI sources necessary to verify documentation claims.

Preserve all completed Phase C1, C2A, C2B, C3, C4A, and C4B behavior.

## Documentation scope

Modify only:

- README.md
- docs/reviews/sprint-8-c4b-live-verification.md
- docs/specs/telemetry-read-api.md

The docs/reviews and docs/specs directories may be created only if needed.

Do not modify:

- AGENTS.md after the scope commit;
- backend application code;
- backend tests;
- ORM models;
- Alembic revisions;
- requirements;
- environment templates;
- legacy files;
- Agent Skills.

## README requirements

Rewrite README.md so it accurately documents the current repository.

It must clearly distinguish:

- AirMonitor v1 legacy assets at the repository root;
- AirMonitor v2 under backend/;
- main as the stable legacy line;
- develop and feature branches as the v2 development workflow.

Document the verified v2 architecture:

- FastAPI;
- PostgreSQL;
- SQLAlchemy async engine and sessions;
- Alembic;
- Pydantic settings;
- pytest;
- application-owned database engine/session lifecycle.

Document the current hardware context without inventing new behavior:

- M5Stack/ESP32;
- PMSA003 particulate sensor;
- SHT30 temperature/humidity sensor;
- mobile air-quality and microclimate monitoring.

Document current backend capabilities:

- health;
- device creation and retrieval;
- device status update;
- session start, active-session retrieval, complete and cancel;
- raw measurement ingestion;
- safe error envelopes;
- chronology enforcement;
- finite telemetry validation;
- PostgreSQL INTEGER boundaries.

List the exact current nine OpenAPI operations by inspecting the source or
generated schema.

Do not describe future read endpoints as already implemented.

Document setup using the actual repository files:

- supported Python version;
- virtual environment creation;
- requirements installation;
- PostgreSQL database preparation;
- environment configuration;
- Alembic upgrade;
- Uvicorn start command;
- health verification.

Do not include real credentials, passwords, local user-specific paths, or
database URLs.

Document supported settings exactly as they exist after C4A.

Do not advertise api_prefix.

Document test commands:

- focused and complete offline pytest;
- pip check;
- integration tests as explicit opt-in only.

Document integration-test safety:

- dedicated disposable URLs;
- approved local hosts;
- required disposable database prefixes;
- persistence explicit opt-in;
- API integration activation;
- initial and final TRUNCATE;
- RESTART IDENTITY;
- no CASCADE;
- never use the protected or development database.

Document deployment limitations:

- current API has no authentication or authorization;
- public exposure is not approved;
- private or trusted-network use only;
- Docker, CI, Redis, aggregation, forecast, AQI read APIs, and telemetry
  history endpoints must not be presented as implemented unless current source
  proves otherwise.

Document Git and secret safety:

- do not commit .env;
- do not commit certificates, keys, database dumps, or passwords;
- use .env.example as a template only.

## C4B live-verification report

Create:

docs/reviews/sprint-8-c4b-live-verification.md

Record only verified facts.

Include:

- date of verification;
- PostgreSQL 18.4;
- source branch;
- relevant C4B commits identified through read-only Git history;
- one temporary non-superuser role;
- two separate disposable databases;
- the approved database-name prefixes;
- Alembic revision a4f9c2e7d1b6;
- persistence integration run twice with 13 passing tests each time;
- API integration initially exposing an outdated measurement timestamp in the
  test;
- the chronology test correction;
- final API integration run twice with 6 passing tests each time;
- cleanup verification after every run;
- empty application tables after every run;
- identity restart verification;
- final removal of both databases and temporary role;
- final offline suite result from the C4B implementation baseline;
- no remaining live database objects.

Do not include:

- generated role name;
- generated database names beyond approved prefixes;
- passwords;
- database URLs;
- administrator credentials;
- local secrets.

Explain that the six API tests include real PostgreSQL serialization coverage
for:

- terminal transition first, then record;
- record first, then terminal transition;
- complete;
- cancel.

## Telemetry Read API contract

Create:

docs/specs/telemetry-read-api.md

This is a design specification, not an implementation report.

Approved MVP endpoints:

- GET /api/v1/devices/{device_id}/sessions
- GET /api/v1/devices/{device_id}/measurements

Do not add other endpoints to the MVP.

### Sessions endpoint

Required stable ordering:

started_at DESC, id DESC

Supported filters:

- status;
- started_from;
- started_to;
- limit;
- cursor.

### Measurements endpoint

Required stable ordering:

measured_at DESC, id DESC

Supported filters:

- session_id;
- measured_from;
- measured_to;
- limit;
- cursor.

### Pagination contract

Use keyset pagination.

Do not use offset pagination.

Required behavior:

- default limit: 100;
- minimum limit: 1;
- maximum limit: 500;
- cursor is exclusive;
- cursor is URL-safe;
- cursor is opaque to clients;
- cursor is versioned;
- cursor includes the last ordering tuple;
- cursor binds to normalized filters through a fingerprint or equivalent
  deterministic validation;
- reusing a cursor with different filters returns safe 422;
- malformed, unsupported-version, or semantically invalid cursor returns safe
  422;
- cursor content must not contain secrets;
- valid pagination must not skip or duplicate rows under stable stored data.

Use these ordering tuples:

- sessions: (started_at, id);
- measurements: (measured_at, id).

### Time filter contract

Use half-open ranges:

[from, to)

Required validation:

- from may equal to only if the product decision explicitly chooses an empty
  result; otherwise document and reject it consistently;
- from greater than to is invalid;
- all timestamps must be timezone-aware;
- normalize timestamps consistently with existing application behavior.

Choose and document one exact equality policy after inspecting existing
validation conventions. Do not leave it ambiguous.

### Response contract

Both endpoints return:

{
  "items": [...],
  "next_cursor": null | string
}

Use exact current ORM/schema field names by inspecting source.

Do not invent fields.

Document which fields appear in:

- session list items;
- raw measurement list items.

Do not expose internal SQLAlchemy state.

### Error contract

Document:

- 200 success;
- 404 device not found;
- 422 invalid path, filters, limit, timestamps, or cursor;
- safe generic 500.

Use existing ErrorResponse terminology.

Do not invent new domain error codes without explicit justification.

### Integer boundaries

All identifiers mapped to PostgreSQL INTEGER must retain:

- greater than zero;
- maximum 2,147,483,647.

### Authorization and deployment policy

The current v2 API does not implement authentication or authorization.

The MVP read endpoints inherit the current trusted-network model.

Document explicitly:

- no authentication is added by the read feature;
- public internet exposure is not approved;
- a dedicated authentication/authorization and rate-limiting phase is required
  before public deployment;
- cursor data is not an authorization mechanism.

### Data and performance policy

The read implementation must be read-only.

It must not mutate:

- runtime state;
- sessions;
- measurements;
- sample_count;
- last_seen_at.

Before implementation, inspect existing indexes against the proposed filter and
ordering patterns.

Do not claim existing indexes are sufficient unless source evidence proves it.

The future implementation phase must either:

- demonstrate suitable existing index coverage; or
- add a reviewed Alembic migration.

Do not introduce aggregation, AQI, forecast, NowCast, map clustering, CSV
export, or retention behavior into this MVP.

### Compatibility

Proposed operation IDs:

- list_device_sessions;
- list_device_measurements.

The implementation would increase the OpenAPI inventory from nine operations
to eleven.

Existing paths, operation IDs, requests, responses, and successful status
codes must remain unchanged.

## Required workflow

Use source-driven documentation.

Before editing:

1. report repository root, worktree, detached HEAD, and base branch;
2. report exact Git status;
3. list loaded instructions;
4. inspect README and all source files needed to support documentation;
5. generate the current OpenAPI schema offline;
6. inspect settings, requirements, Alembic revision, tests, and integration
   guards;
7. identify every factual statement that must be corrected.

Do not copy stale statements from the current README.

Do not claim planned features are implemented.

After editing:

1. compare README claims against current source;
2. compare endpoint inventory against generated OpenAPI;
3. verify setting names against Settings;
4. verify test commands against repository layout;
5. verify integration prefixes and opt-ins against guard source;
6. verify the C4B report against Git history and approved user-provided
   verification facts;
7. verify the read specification contains no implementation claim;
8. run the complete offline backend suite;
9. run pip check;
10. run git diff --check;
11. scan changed docs for secrets, local absolute paths, URLs containing
    credentials, generated temporary identifiers, and stale api_prefix text;
12. stop for manual external review.

## Test environment

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest command must use:

-B -p no:cacheprovider

Do not activate live integration tests.

Do not read or print ambient database URL values.

## Explicitly forbidden

Do not:

- modify production or test code;
- implement Telemetry Read API;
- add authentication;
- add dependencies;
- change routes or OpenAPI;
- modify ORM or Alembic;
- create or connect to PostgreSQL;
- run live integration tests;
- modify .env.example;
- include credentials or temporary database identifiers;
- rewrite audit history;
- perform Git write operations.

Read-only Git commands are allowed.

## Definition of done

Phase C4C is complete only when:

- README accurately describes current AirMonitor v2;
- AUDIT-014 is closed;
- C4B live verification is documented without secrets;
- Telemetry Read API decisions are explicit and implementation-ready;
- no production or test file changed;
- current OpenAPI still contains nine operations;
- complete offline tests pass;
- no sensitive information is introduced;
- Codex performs no Git write operation;
- final output lists changed files, verification commands, results,
  documentation limitations, and exact Git status.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8