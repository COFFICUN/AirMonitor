@'
# AirMonitor Agent Instructions

## Repository context

AirMonitor v1 at the repository root is stable legacy reference material and
must not be modified.

AirMonitor v2 lives under backend/ and uses FastAPI, PostgreSQL, async
SQLAlchemy, Alembic, Pydantic, and pytest.

Current feature branch:

feature/telemetry-read-api

## Governing documents and contracts

Read completely:

- docs/specs/telemetry-read-api.md
- docs/reviews/telemetry-read-api-source-audit.md
- docs/plans/telemetry-read-api-implementation-plan.md
- backend/app/services/telemetry_cursor.py
- backend/app/schemas/telemetry.py
- backend/app/api/query_validation.py
- backend/tests/test_telemetry_cursor.py
- backend/tests/test_telemetry_query_validation.py

Inspect existing repository, service, schema, error, and test conventions before
defining any new symbol.

The approved specification and implementation plan remain authoritative.

## Current task

Telemetry Read API — Phase C1.

This is an intentionally RED repository and service contract checkpoint.

Create only:

- backend/tests/test_telemetry_read_repositories.py
- backend/tests/test_telemetry_read_services.py

Do not modify production code.

Do not implement:

- repositories;
- query services;
- API routes;
- routers;
- response schemas;
- ORM models;
- indexes;
- Alembic revisions;
- settings;
- dependencies;
- integration tests.

Stop for manual external review after the RED checkpoint.

## Source-driven symbol rule

Before editing, inspect the approved implementation plan and current source.

Report the exact future:

- repository module paths;
- repository function or method names;
- service module paths;
- service function or method names;
- page/result value types;
- existing device-not-found exception type;
- existing AsyncSession ownership convention.

Do not invent competing names when the plan or current architecture already
defines them.

If the approved plan is genuinely ambiguous about a required public symbol,
report the ambiguity and stop before writing tests.

## Repository responsibility

Repository code in the future phase will perform read-only SQLAlchemy queries.

It must not:

- perform HTTP work;
- import FastAPI;
- encode or decode cursors;
- construct HTTP responses;
- own request validation;
- commit;
- rollback;
- flush;
- mutate ORM entities;
- update last_seen_at;
- update sample_count;
- change session status;
- change device runtime state.

The caller owns transaction/session lifecycle.

## Session repository contract

The future session-list query must support:

- required device_id equality;
- optional exact status;
- optional inclusive started_from;
- optional exclusive started_to;
- optional exclusive keyset cursor;
- stable ordering by started_at DESC, id DESC;
- fetching exactly limit + 1 rows.

Required cursor continuation semantics:

started_at < cursor_timestamp
OR (
    started_at = cursor_timestamp
    AND id < cursor_identifier
)

The repository must not:

- use OFFSET;
- order only by started_at;
- omit the id tie-breaker;
- perform device existence decisions;
- trim the extra row;
- create next_cursor.

## Measurement repository contract

The future measurement-list query must support:

- required device_id equality;
- optional session_id equality;
- optional inclusive measured_from;
- optional exclusive measured_to;
- optional exclusive keyset cursor;
- stable ordering by measured_at DESC, id DESC;
- fetching exactly limit + 1 rows.

Required cursor continuation semantics:

measured_at < cursor_timestamp
OR (
    measured_at = cursor_timestamp
    AND id < cursor_identifier
)

The repository must retain both predicates when session_id is supplied:

device_id = ?
AND session_id = ?

The repository must not:

- use OFFSET;
- omit device_id when session_id is present;
- order only by measured_at;
- omit the id tie-breaker;
- trim the extra row;
- encode next_cursor.

## Repository RED tests

Tests must cover at minimum:

### Sessions

- device predicate is always present;
- status predicate is optional and exact;
- started_from is inclusive;
- started_to is exclusive;
- both range predicates compose;
- cursor predicate is exclusive;
- equal timestamps use id as the tie-breaker;
- ordering is started_at DESC, id DESC;
- requested SQL limit is public limit + 1;
- no OFFSET;
- rows are returned in repository order;
- no commit, rollback, flush, or mutation occurs.

### Measurements

- device predicate is always present;
- session_id predicate is optional;
- device_id remains present with session_id;
- measured_from is inclusive;
- measured_to is exclusive;
- cursor predicate is exclusive;
- equal timestamps use id as the tie-breaker;
- ordering is measured_at DESC, id DESC;
- requested SQL limit is public limit + 1;
- no OFFSET;
- no commit, rollback, flush, or mutation occurs.

Follow current repository-test conventions.

Do not assert one entire dialect-specific SQL string when semantic statement
inspection is sufficient.

Do not create a fake second repository implementation inside tests.

## Service responsibility

The future service layer will orchestrate:

- device existence verification;
- empty-range handling;
- repository invocation;
- limit + 1 page trimming;
- has-more detection;
- next_cursor generation;
- immutable page/result construction.

Service code must not:

- contain SQL;
- depend on FastAPI;
- construct Response or JSONResponse;
- manage database commits;
- mutate persistence state.

## Device existence ordering

Device existence must be established before returning an empty page.

For from == to:

1. check that the device exists;
2. return an empty page for an existing device;
3. raise the existing safe device-not-found domain exception for an unknown
   device;
4. do not execute the telemetry list repository query.

## Service pagination contract

Given repository rows:

- zero through limit rows:
  - return all rows;
  - next_cursor is None;

- limit + 1 rows:
  - return only the first limit rows;
  - next_cursor is generated from the final returned row;
  - the extra row is not returned;
  - the extra row is not used as the cursor position.

Session cursor position uses:

- started_at;
- id.

Measurement cursor position uses:

- measured_at;
- id.

The service must preserve repository ordering.

## Service RED tests

Tests must cover at minimum:

- unknown device uses the current domain not-found exception;
- existing device with no rows returns empty page;
- equal range checks device existence first;
- equal range skips telemetry repository query;
- equal range for unknown device does not return an empty success;
- repository receives normalized filters and cursor position;
- repository receives public limit and applies the established limit + 1
  boundary according to current architecture;
- zero rows returns null cursor;
- exactly limit rows returns null cursor;
- limit + 1 rows returns only limit items;
- next_cursor is generated from the final returned item;
- extra row is not returned;
- extra row is not used for cursor generation;
- session page uses started_at and id;
- measurement page uses measured_at and id;
- filters are bound into generated cursor;
- service does not commit, rollback, flush, or mutate data;
- repository exceptions are not broadly swallowed;
- cursor encoder failures are not converted into fake success.

Use the approved cursor production functions instead of reproducing cursor
encoding inside service tests.

## Test-quality requirements

Tests must:

- be black-box contracts;
- follow current async pytest conventions;
- avoid PostgreSQL;
- avoid environment reads;
- avoid live integration activation;
- avoid duplicated SQL/query implementations;
- avoid duplicated cursor implementation;
- avoid HTTP route harnesses;
- use current ORM and response fields exactly;
- use current exception terminology exactly.

Mocks or fakes may record calls, but they must not recreate the production
query algorithm.

Do not change an existing fixture automatically.

If an existing shared fixture must change, report and stop.

## Expected RED boundary

Focused tests should fail only because the approved future repository and
service symbols do not yet exist.

Do not use:

- conditional imports;
- fallback implementations;
- skips;
- xfail;
- importlib workarounds.

Collection errors for missing approved production modules or symbols are
expected.

Other failures are not accepted.

## Verification

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest invocation must include:

-B -p no:cacheprovider

Do not connect to PostgreSQL.

Before editing run:

- full offline backend suite;
- relevant existing repository tests;
- relevant existing service tests;
- pip check;
- git diff --check.

Expected baseline:

- 730 passed;
- 2 skipped;
- OpenAPI 3.1.0;
- nine operations;
- nine unique operation IDs;
- Alembic head a4f9c2e7d1b6.

After editing run:

- both new focused test files;
- prove failures are only missing approved production symbols;
- all existing tests excluding the two new RED files;
- pip check;
- git diff --check;
- syntax and collection verification;
- scope scan;
- secret and local-path scan.

## Allowed changes

Only:

- backend/tests/test_telemetry_read_repositories.py
- backend/tests/test_telemetry_read_services.py

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

Phase C1 is complete only when:

- exactly two new test files exist;
- no production file changed;
- repository ordering and keyset contracts are covered;
- service pagination and empty-range contracts are covered;
- no cursor or repository implementation is duplicated in tests;
- focused tests are intentionally RED only for missing production symbols;
- existing offline suite remains green;
- no database or secret access occurs;
- Git index remains unchanged;
- work stops for manual external review.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8