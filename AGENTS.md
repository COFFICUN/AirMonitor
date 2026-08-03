@'
# AirMonitor Agent Instructions

## Repository context

AirMonitor v1 at the repository root is stable legacy reference material.

Do not modify legacy v1 files.

AirMonitor v2 lives under backend/ and uses:

- FastAPI;
- PostgreSQL;
- async SQLAlchemy;
- Alembic;
- Pydantic;
- pytest.

Current feature branch:

feature/telemetry-read-api

The Telemetry Read API application layers are already implemented:

- strict query validation;
- normalized filters;
- opaque filter-bound cursors;
- read repositories;
- query services;
- response schemas;
- request-scoped service providers;
- session collection GET route;
- measurement collection GET route;
- OpenAPI contracts.

Current public endpoints:

GET /api/v1/devices/{device_id}/sessions

GET /api/v1/devices/{device_id}/measurements

The existing write and active-session routes must remain unchanged.

## Current macro task

Complete the remaining Telemetry Read API database, integration, performance,
documentation, and final-verification work in one continuous sprint.

Do not stop after intermediate RED or GREEN checkpoints.

Use intermediate checkpoints internally, but continue automatically while the
approved scope remains valid.

Stop only when:

1. the entire macro phase is complete; or
2. a genuine safety or environment blocker prevents further work.

Do not request manual review merely because a test is temporarily RED during
normal test-driven implementation.

## Governing sources

Read completely before editing:

- docs/specs/telemetry-read-api.md
- docs/reviews/telemetry-read-api-source-audit.md
- docs/plans/telemetry-read-api-implementation-plan.md
- backend/alembic.ini
- backend/alembic/env.py
- all existing backend/alembic/versions/*.py
- backend/app/db/models.py or the actual ORM model modules
- backend/app/repositories/measurement.py
- backend/app/repositories/measurement_session.py
- backend/app/services/telemetry_cursor.py
- backend/app/services/telemetry.py
- backend/app/schemas/telemetry.py
- backend/app/api/query_validation.py
- backend/app/api/dependencies.py
- backend/app/api/v1/endpoints/sessions.py
- backend/app/api/v1/endpoints/measurements.py
- all existing migration tests
- all existing PostgreSQL integration-test infrastructure
- backend/tests/test_telemetry_cursor.py
- backend/tests/test_telemetry_query_validation.py
- backend/tests/test_telemetry_read_repositories.py
- backend/tests/test_telemetry_read_services.py
- backend/tests/test_api_schemas.py
- backend/tests/test_api_routes.py
- backend/tests/test_api_openapi.py
- backend/tests/test_api_dependencies.py
- backend/tests/test_api_architecture.py

Use the current checkout as the source of truth.

Historical plans and prior reports are guidance only when they agree with the
current repository.

## Baseline before this macro phase

Expected offline baseline:

- 831 passed;
- 2 skipped.

Expected OpenAPI baseline:

- OpenAPI 3.1.0;
- 11 operations;
- 10 operations under /api/v1;
- 1 operation under /health;
- 11 unique operation IDs.

Current Alembic head before the new migration:

a4f9c2e7d1b6

Record the actual baseline before editing.

Do not assume counts when the current checkout reports something different.

## Macro phase deliverables

Complete all of the following in one worktree:

1. audit the existing indexes and migration conventions;
2. add migration-focused tests;
3. implement one new Alembic revision;
4. create the four approved composite indexes;
5. remove the four superseded indexes;
6. verify exact upgrade and downgrade behavior offline;
7. verify PostgreSQL dialect compilation;
8. run a safe local upgrade/downgrade/upgrade cycle;
9. introspect actual PostgreSQL indexes;
10. run representative EXPLAIN (ANALYZE, BUFFERS);
11. add or extend PostgreSQL integration tests for both GET endpoints;
12. verify pagination, filtering, ordering, isolation, and error behavior;
13. run all offline and applicable integration tests;
14. verify OpenAPI remains unchanged;
15. create a final verification report;
16. perform a complete architecture, security, and performance review.

Do not split these deliverables into separate manual phases.

## Exact new indexes

Create exactly these four PostgreSQL indexes.

### Measurement sessions base listing index

Name:

ix_measurement_sessions_device_id_started_at_id_desc

Columns and directions:

- device_id ASC;
- started_at DESC;
- id DESC.

Equivalent logical definition:

(device_id ASC, started_at DESC, id DESC)

### Measurement sessions status-filtered index

Name:

ix_measurement_sessions_device_id_status_started_at_id_desc

Columns and directions:

- device_id ASC;
- status ASC;
- started_at DESC;
- id DESC.

Equivalent logical definition:

(device_id ASC, status ASC, started_at DESC, id DESC)

### Raw measurements device listing index

Name:

ix_raw_measurements_device_id_measured_at_id_desc

Columns and directions:

- device_id ASC;
- measured_at DESC;
- id DESC.

Equivalent logical definition:

(device_id ASC, measured_at DESC, id DESC)

### Raw measurements session-filtered index

Name:

ix_raw_measurements_session_id_measured_at_id_desc

Columns and directions:

- session_id ASC;
- measured_at DESC;
- id DESC.

Equivalent logical definition:

(session_id ASC, measured_at DESC, id DESC)

The session-first raw-measurement index is intentional.

It supports:

- session-filtered telemetry reads;
- existing latest-measurement lookup by session_id;
- child-side foreign-key lookup behavior.

The measurement GET repository must still retain both:

- device_id;
- session_id.

Do not remove device isolation from endpoint SQL merely because the supporting
index begins with session_id.

## Superseded indexes

After the replacement indexes are created successfully, remove exactly:

- ix_measurement_sessions_device_id_started_at
- ix_measurement_sessions_device_id_status
- ix_raw_measurements_device_id_measured_at
- ix_raw_measurements_session_id_measured_at

Do not remove unrelated indexes.

Do not remove primary-key, uniqueness, foreign-key-supporting, idempotency, or
runtime-state indexes.

## Migration ordering

Upgrade must:

1. create all four replacement indexes;
2. only then drop the four superseded indexes.

Downgrade must:

1. recreate all four superseded indexes;
2. only then drop the four replacement indexes.

This ordering minimizes the interval in which a supported access path is
missing.

Use the repository’s existing Alembic naming and revision conventions.

The new revision must have:

- a unique revision ID;
- down_revision equal to the current head at implementation time;
- no branch labels unless current conventions require them;
- no unrelated schema operation.

Do not edit an already committed migration.

Create one new migration revision.

## Migration implementation requirements

The migration must preserve explicit descending index directions.

Do not silently reduce these indexes to unordered plain column-name lists if
that loses the required DESC expressions.

Use Alembic and SQLAlchemy expressions compatible with PostgreSQL and the
project’s current dependency versions.

Offline tests must prove:

- exact new index names;
- exact table names;
- exact column order;
- exact direction expressions;
- exact old index names;
- exact create-before-drop upgrade ordering;
- exact recreate-before-drop downgrade ordering;
- correct down_revision;
- no unrelated operation;
- one current Alembic head.

Avoid fragile full-file snapshots when structural inspection is sufficient.

## ORM metadata policy

First inspect whether this repository treats Alembic migrations or ORM metadata
as the authoritative source for non-constraint performance indexes.

Follow the existing convention.

Do not add duplicate ORM Index definitions merely to mirror the migration if
the current project keeps performance indexes migration-only.

If metadata parity is an established enforced project convention, update only
the minimum necessary model metadata and test it.

Explain the decision in the final report.

## Repository SQL contract

Do not change the approved repository query behavior unless a test reveals a
real defect.

Session listing must retain:

- MeasurementSession.device_id == device_id;
- optional exact status;
- started_at >= started_from;
- started_at < started_to;
- exclusive cursor predicate;
- ORDER BY started_at DESC, id DESC;
- LIMIT public_limit + 1;
- no OFFSET.

Measurement listing must retain:

- RawMeasurement.device_id == device_id;
- optional RawMeasurement.session_id == session_id;
- measured_at >= measured_from;
- measured_at < measured_to;
- exclusive cursor predicate;
- ORDER BY measured_at DESC, id DESC;
- LIMIT public_limit + 1;
- no OFFSET.

The exclusive cursor predicate remains logically:

timestamp < cursor_timestamp
OR (
    timestamp = cursor_timestamp
    AND id < cursor_identifier
)

Device isolation must remain outside and combined with the grouped cursor
predicate through AND semantics.

## PostgreSQL integration coverage

Use the existing integration-test infrastructure when present.

Do not create a competing database fixture system.

Add or extend focused integration coverage for both collection endpoints.

### Session endpoint integration coverage

Verify at minimum:

- unknown device returns safe 404;
- known device with no sessions returns 200 and an empty envelope;
- newest sessions are returned first;
- equal started_at values are ordered by id descending;
- status filtering is exact;
- started_from is inclusive;
- started_to is exclusive;
- first page returns at most the requested public limit;
- next_cursor is present only when an additional row exists;
- second page excludes all first-page rows;
- no duplicates occur between adjacent pages;
- no qualifying row is skipped;
- cursor remains bound to the original filters;
- data belonging to another device never appears;
- equal bounds still enforce device existence before returning an empty page;
- /sessions/active remains reachable and unchanged.

### Measurement endpoint integration coverage

Verify at minimum:

- unknown device returns safe 404;
- known device with no measurements returns an empty 200 envelope;
- newest measurements are returned first;
- equal measured_at values are ordered by id descending;
- session_id filtering is exact;
- measured_from is inclusive;
- measured_to is exclusive;
- keyset pagination has no duplicates and no skipped rows;
- cursor remains bound to the original filters;
- data belonging to another device never appears;
- session_id belonging to another device returns an empty page;
- nonexistent session_id returns an empty page;
- neither case reveals session existence or ownership;
- equal bounds still enforce device existence;
- the existing measurement POST operation remains unchanged.

Integration tests must use real PostgreSQL behavior where the project already
supports it.

Do not replace integration verification with SQLite.

## Local PostgreSQL safety policy

PostgreSQL access is explicitly authorized for this macro phase only under the
following safety conditions.

Before connecting:

1. resolve the target without printing credentials;
2. confirm the hostname is local, loopback, container-local, or an explicitly
   documented development database;
3. confirm the database is not production;
4. record only sanitized connection metadata;
5. do not print passwords, full URLs, tokens, certificates, or secrets.

Acceptable local targets include:

- localhost;
- 127.0.0.1;
- ::1;
- a project Docker Compose PostgreSQL service;
- an explicitly named AirMonitor test database.

Do not connect when:

- the host is remote and not explicitly documented as disposable development;
- the target is ambiguous;
- the database appears to contain production data;
- credentials would need to be exposed in output.

If a safe local PostgreSQL target is unavailable:

- complete all offline migration work;
- complete all tests that do not require a live database;
- do not fabricate integration or EXPLAIN success;
- report one clear environment blocker at the end;
- provide the exact safe command needed for the user to finish verification.

Do not stop early merely because the live database is unavailable. Finish all
other approved work first.

## Live migration verification

Against a safe local development or test PostgreSQL database:

1. capture the current Alembic revision;
2. apply upgrade to the new head;
3. confirm the database revision;
4. introspect pg_indexes or PostgreSQL catalogs;
5. confirm all four new indexes exist;
6. confirm all four old indexes do not exist;
7. confirm exact indexed column order and sort direction;
8. downgrade to the previous revision;
9. confirm the old indexes are restored;
10. confirm the new indexes are removed;
11. upgrade again to the new head;
12. confirm the final database state;
13. leave the local database at the new head unless the project convention
    requires restoration.

Do not run destructive table or data migrations.

Do not delete user measurement data.

## EXPLAIN verification

Run representative PostgreSQL:

EXPLAIN (ANALYZE, BUFFERS)

for the access patterns below.

### Sessions without status

WHERE device_id = ...
ORDER BY started_at DESC, id DESC
LIMIT ...

### Sessions with status

WHERE device_id = ...
AND status = ...
ORDER BY started_at DESC, id DESC
LIMIT ...

### Sessions with cursor

WHERE device_id = ...
AND (
    started_at < ...
    OR (
        started_at = ...
        AND id < ...
    )
)
ORDER BY started_at DESC, id DESC
LIMIT ...

### Measurements by device

WHERE device_id = ...
ORDER BY measured_at DESC, id DESC
LIMIT ...

### Measurements by device and session

WHERE device_id = ...
AND session_id = ...
ORDER BY measured_at DESC, id DESC
LIMIT ...

### Measurements with cursor

WHERE device_id = ...
AND (
    measured_at < ...
    OR (
        measured_at = ...
        AND id < ...
    )
)
ORDER BY measured_at DESC, id DESC
LIMIT ...

Record:

- scan type;
- selected index when applicable;
- sort nodes;
- rows examined;
- rows returned;
- execution time;
- relevant buffer information.

Do not make a false claim that a sequential scan on a tiny table proves the
index is defective.

When the local dataset is too small for the PostgreSQL planner to select an
index:

- state that clearly;
- use a disposable test database, temporary data, or transaction-rolled-back
  synthetic data when supported;
- optionally use transaction-local enable_seqscan = off only as supplementary
  index-compatibility evidence;
- do not present forced planner output as a real production benchmark.

The important structural proof is that the indexes support the filter prefix
and requested ordering without requiring an incompatible explicit sort.

## Performance acceptance

There must be no OFFSET pagination.

No query may load an unbounded telemetry history.

The SQL-level limit remains public limit + 1.

No new N+1 query behavior may be introduced.

No route or service may perform a separate session-ownership lookup for
measurement filtering.

No query may lose mandatory device isolation.

Do not add speculative caching or Redis.

## API and OpenAPI stability

After all changes, OpenAPI must remain:

- 3.1.0;
- 11 total operations;
- 10 under /api/v1;
- 1 under /health;
- 11 unique operation IDs.

The new operation IDs remain:

- list_device_sessions;
- list_device_measurements.

The existing nine operation contracts must remain structurally unchanged.

No new public endpoint is added in this macro phase.

No existing response field is added, removed, or renamed.

## Error and security behavior

Preserve safe responses:

- 404 for unknown device;
- 422 for invalid input or cursor;
- 500 with no internal detail leakage.

Do not expose:

- SQL;
- connection strings;
- exception internals;
- file-system paths;
- credentials;
- environment variables;
- ownership information for measurement session filters.

No authentication is added in this macro phase.

The current trusted/private-network assumption remains documented.

## Allowed changes

Expected changes may include:

- one new backend/alembic/versions/*.py migration;
- the existing canonical migration test file, or one focused new migration
  test file if no canonical file exists;
- existing PostgreSQL integration test files, or focused new integration test
  files following current project conventions;
- docs/reviews/telemetry-read-api-final-verification.md;
- narrowly scoped status updates in:
  - docs/specs/telemetry-read-api.md;
  - docs/plans/telemetry-read-api-implementation-plan.md.

Do not modify existing production application code unless a newly added test
demonstrates a real defect in the approved implementation.

When a real defect is found:

1. document the failing contract;
2. make the smallest correction;
3. rerun focused tests;
4. rerun the full suite;
5. report the additional production file explicitly.

Do not perform unrelated refactoring.

Do not rename established public symbols.

## Documentation deliverable

Create:

docs/reviews/telemetry-read-api-final-verification.md

It must contain:

- implemented endpoint summary;
- final route contracts;
- cursor and pagination behavior;
- device-isolation guarantees;
- migration revision and index inventory;
- upgrade/downgrade verification;
- sanitized PostgreSQL environment description;
- integration-test summary;
- EXPLAIN summary;
- OpenAPI inventory;
- offline test result;
- integration test result;
- Alembic head;
- known limitations;
- trusted/private-network security assumption;
- explicit statement that no OFFSET pagination is used;
- explicit statement that no separate session ownership lookup is used;
- any live-verification blocker, without inventing results.

Update the implementation plan status only where supported by completed
evidence.

Do not mark live PostgreSQL verification complete when it was not performed.

## Verification commands

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest command must include:

-B -p no:cacheprovider

Run at minimum:

1. migration-focused tests;
2. telemetry cursor tests;
3. telemetry query-validation tests;
4. telemetry repository tests;
5. telemetry service tests;
6. API schema tests;
7. API dependency tests;
8. API route tests;
9. OpenAPI tests;
10. API architecture tests;
11. all offline backend tests;
12. applicable PostgreSQL integration tests;
13. pip check;
14. git diff --check;
15. Alembic heads;
16. offline Alembic SQL generation when supported;
17. live upgrade/downgrade/upgrade when safe;
18. EXPLAIN verification when safe.

Expected original offline baseline before adding new tests:

831 passed, 2 skipped.

The final offline suite must have:

- zero failures;
- no unexpected new skips;
- at least all original 831 passing cases;
- all newly added offline tests passing.

Report actual counts rather than forcing an assumed final number.

## Static review gates

Run scans for:

- syntax errors;
- unresolved imports;
- broad exception handlers;
- transaction control in read routes or query services;
- repository imports in API routes;
- SQLAlchemy imports in API routes;
- OFFSET usage;
- unbounded telemetry SELECT statements;
- missing device_id predicates;
- secrets;
- credentials;
- database URLs;
- environment reads added by this phase;
- local absolute paths;
- trailing whitespace;
- missing final newline;
- accidental test skips or xfail;
- fallback implementations;
- integration activation from the offline suite.

Review the final diff across:

1. correctness;
2. readability;
3. architecture;
4. security;
5. performance;
6. migration reversibility;
7. operational safety.

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

Keep the Git index unchanged.

## Definition of done

This macro phase is complete only when:

- the migration contract is tested;
- one new reversible Alembic migration exists;
- all four replacement indexes are created;
- all four superseded indexes are removed;
- downgrade restores the prior index state;
- offline PostgreSQL-dialect verification passes;
- endpoint integration contracts are tested;
- all offline tests pass;
- all available safe local integration checks pass;
- EXPLAIN evidence is collected or one honest environment blocker is reported;
- OpenAPI remains exactly eleven operations;
- the final verification report is created;
- no unrelated code is changed;
- no secret is exposed;
- no Git write occurs;
- work stops once for manual external review at the end.

Do not stop at an intermediate RED checkpoint.

Do not stop immediately after the migration becomes GREEN.

Do not stop immediately after integration tests become GREEN.

Complete the entire macro phase before requesting review.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8