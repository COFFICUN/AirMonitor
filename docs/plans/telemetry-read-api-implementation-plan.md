# Telemetry Read API Implementation Plan

**Plan date:** 2026-07-30

**Plan status:** historical Phase A plan; implementation, offline verification,
and guarded disposable PostgreSQL live verification are complete

**Authoritative contract:** `docs/specs/telemetry-read-api.md`

**Source audit:** `docs/reviews/telemetry-read-api-source-audit.md`

**Current verification:**
`docs/reviews/telemetry-read-api-final-verification.md`

The application layers and ordered index migration described by this plan are
implemented. The full offline suite, guarded OpenAPI checks, reversible live
migration cycle, exact PostgreSQL catalog checks, both integration suites, and
six representative `EXPLAIN (ANALYZE, BUFFERS)` shapes pass. The disposable
PostgreSQL 18.4 container was removed after verification. The historical phase
boundaries below are retained as planning provenance; the current root
instructions authorized the continuous completion macro phase.

**Current base:** `develop` at
`a83b065e1804e63798e714eac5496ecf957ba84f`

**Current scope commit:** `8028bd5972ace274c0a106b9ab32d0d798a45c7a`

## 1. Outcome and constraints

Implement exactly two read-only operations:

```text
GET /api/v1/devices/{device_id}/sessions
GET /api/v1/devices/{device_id}/measurements
```

Operation IDs:

```text
list_device_sessions
list_device_measurements
```

The implementation must:

- retain the existing nine operations unchanged;
- produce exactly eleven unique OpenAPI operations;
- use stable descending keyset pagination;
- reject unknown and repeated scalar query parameters;
- return only the existing session/measurement public fields;
- return the exact `{items, next_cursor}` envelope;
- use safe existing 404, 422, and 500 terminology;
- remain read-only;
- add the reviewed index migration;
- prove offline behavior before any live PostgreSQL run;
- use only approved disposable PostgreSQL targets for live verification.

It must not add:

- another endpoint;
- offset pagination;
- authentication or authorization;
- rate limiting;
- totals, page numbers, or aggregation;
- response fields;
- a dependency;
- write-path behavior.

## 2. Fixed architecture decisions

### 2.1 Dependency direction

```text
FastAPI routes
  -> query schemas and strict API query dependency
       -> pure cursor/filter primitives
  -> telemetry query services
       -> pure cursor/filter primitives
       -> repositories
            -> SQLAlchemy ORM / AsyncSession
```

Rules:

- routes contain no SQL or transaction logic;
- services contain no HTTP response encoding;
- repositories import no FastAPI;
- cursor code imports no FastAPI, SQLAlchemy session, settings, or database
  code;
- list services never call `begin`, `commit`, `rollback`, or `flush`;
- no read path acquires a write lock;
- no read path mutates an ORM entity.

### 2.2 Exact planned types and symbols

`backend/app/schemas/telemetry.py`:

```text
SessionListQuery
MeasurementListQuery
SessionListResponse
MeasurementListResponse
```

`backend/app/services/telemetry_cursor.py`:

```text
CursorResource
CursorPosition
CursorValidationError
SessionReadFilters
MeasurementReadFilters
SessionReadRequest
MeasurementReadRequest
normalize_session_filters
normalize_measurement_filters
encode_cursor
decode_cursor
```

`backend/app/api/query_validation.py`:

```text
strict_session_query_parameters
strict_measurement_query_parameters
resolve_session_read_request
resolve_measurement_read_request
```

`backend/app/services/telemetry.py`:

```text
TelemetryPage
SessionTelemetryQueryService
MeasurementTelemetryQueryService
```

`backend/app/api/dependencies.py`:

```text
get_session_telemetry_query_service
get_measurement_telemetry_query_service
```

Repository methods:

```text
MeasurementSessionRepository.list_for_device
RawMeasurementRepository.list_for_device
```

### 2.3 Query models

`SessionListQuery`:

| Field | Type/default |
|---|---|
| `status` | `active | completed | cancelled | None` |
| `started_from` | aware datetime or `None` |
| `started_to` | aware datetime or `None` |
| `limit` | integer, default 100, `1..500` |
| `cursor` | string or `None`, encoded length at most 2,048 |

`MeasurementListQuery`:

| Field | Type/default |
|---|---|
| `session_id` | positive PostgreSQL `INTEGER` or `None` |
| `measured_from` | aware datetime or `None` |
| `measured_to` | aware datetime or `None` |
| `limit` | integer, default 100, `1..500` |
| `cursor` | string or `None`, encoded length at most 2,048 |

Both models:

- use `extra="forbid"`;
- reject `from > to`;
- accept `from == to`;
- normalize only after awareness validation;
- exclude `limit` and `cursor` from filter fingerprints.

### 2.4 Strict raw query boundary

FastAPI/Pydantic query models do not reject repeated scalars. Each route
therefore declares a route-decorator dependency that:

1. reads `request.query_params.multi_items()`;
2. rejects a key outside the endpoint allowlist;
3. rejects a supported scalar seen more than once;
4. raises a sanitized `RequestValidationError`;
5. performs no database access.

The typed query dependency then validates and normalizes the values and
decodes any cursor into a pure read request.

### 2.5 Page construction

For either resource:

1. API query dependency validates raw/typed input and cursor;
2. service checks device existence;
3. service returns an empty page for equal bounds;
4. repository applies filters and exclusive cursor;
5. repository orders by timestamp descending, `id` descending;
6. repository fetches `limit + 1`;
7. service returns at most `limit`;
8. service emits a next cursor only when the extra row exists;
9. next cursor position comes from the last returned item.

### 2.6 Cursor v1

Exact payload:

```json
{"f":"fingerprint","p":["2026-07-30T00:00:00.000000Z",1],"r":"sessions","v":1}
```

Wire format:

```text
unpadded-base64url(UTF-8(canonical JSON))
```

Fixed limits:

```text
encoded <= 2048 ASCII characters
decoded <= 1024 bytes
position id in 1..2147483647
```

Canonical JSON:

```text
sort_keys=True
separators=(",", ":")
ensure_ascii=False
allow_nan=False
```

Decode order and error mapping are fixed by the source audit. The decoder
rejects duplicate keys, unknown fields, noncanonical bytes, malformed or
padded Base64, invalid UTF-8/JSON, wrong type/kind/version, invalid position,
filter mismatch, and position/filter semantic mismatch. All such failures map
to the existing safe 422 envelope.

### 2.7 Index migration

Create:

```text
ix_measurement_sessions_device_id_started_at_id_desc
  (device_id ASC, started_at DESC, id DESC)

ix_measurement_sessions_device_id_status_started_at_id_desc
  (device_id ASC, status ASC, started_at DESC, id DESC)

ix_raw_measurements_device_id_measured_at_id_desc
  (device_id ASC, measured_at DESC, id DESC)

ix_raw_measurements_session_id_measured_at_id_desc
  (session_id ASC, measured_at DESC, id DESC)
```

Remove after replacements exist:

```text
ix_measurement_sessions_device_id_started_at
ix_measurement_sessions_device_id_status
ix_raw_measurements_device_id_measured_at
ix_raw_measurements_session_id_measured_at
```

No old explicit index remains at the migrated head. The session-first raw
replacement is intentionally one index for three compatible access paths:

- equality on `session_id` followed by stable
  `measured_at DESC, id DESC` endpoint ordering;
- the existing `MAX(measured_at) WHERE session_id = ?` chronology query,
  which uses the same leading equality/time prefix;
- child-side composite-foreign-key lookup beginning with `session_id`.

The measurement repository must nevertheless keep both `device_id = ?` and
`session_id = ?` in endpoint SQL. `device_id` is required for correctness,
path scoping, and session non-disclosure. The relational invariant guarantees
that a globally unique session ID belongs to one device, so `device_id` need
not precede `session_id` in a second session-specific index.

The final four-index set remains conditional on representative PostgreSQL
`EXPLAIN (ANALYZE, BUFFERS)` evidence.

## 3. Dependency graph and checkpoints

```text
cursor/filter contract tests
  -> cursor/filter primitives
       -> strict API query boundary

repository/service contract tests
  -> repository keyset statements
       -> service page orchestration

API/OpenAPI contract tests
  -> response schemas/providers/routes

index migration tests
  -> ORM index metadata + Alembic revision

all offline checks
  -> approved disposable PostgreSQL checks
       -> documentation and final review
```

Checkpoints:

- Checkpoint A: cursor and strict query primitives green.
- Checkpoint B: repository and service behavior green/read-only.
- Checkpoint C: HTTP/OpenAPI contract green with eleven operations.
- Checkpoint D: ORM/Alembic index parity and offline migration SQL green.
- Checkpoint E: full offline suite green.
- Checkpoint F: disposable PostgreSQL verification reviewed.
- Checkpoint G: documentation and final code review approved.

## 4. Command conventions

Every Python command must use:

```powershell
$PY = (Resolve-Path '.\backend\.venv\Scripts\python.exe').Path
```

Every pytest invocation must include:

```text
-B -p no:cacheprovider
```

Before offline Python/pytest commands:

```powershell
$offlineEnvironmentNames = @(
    'AIRMONITOR_DATABASE_URL',
    'AIRMONITOR_RUN_PERSISTENCE_INTEGRATION',
    'AIRMONITOR_TEST_DATABASE_URL',
    'AIRMONITOR_API_TEST_DATABASE_URL',
    'AIRMONITOR_READ_API_TEST_DATABASE_URL'
)
foreach ($environmentName in $offlineEnvironmentNames) {
    Remove-Item -LiteralPath "Env:$environmentName" `
        -ErrorAction SilentlyContinue
}
```

Do not print any removed value. Stop if `backend/.env` exists; do not open it.

## 5. Phase 1 - Write failing cursor and query-validation tests

### Goal

Lock cursor v1, normalized-filter, timestamp/range, and strict query behavior
before implementation.

### Files allowed to change

- create `backend/tests/test_telemetry_cursor.py`;
- create `backend/tests/test_telemetry_query_validation.py`.

No production file changes.

### Tests written first

`test_telemetry_cursor.py`:

- session encode/decode round trip;
- measurement encode/decode round trip;
- deterministic canonical serialization;
- lexicographic keys and compact JSON;
- canonical UTC with exactly six fractional digits and `Z`;
- URL-safe alphabet;
- unpadded output;
- changed valid page size does not change the fingerprint;
- device/status/session/time filter changes do change the fingerprint;
- encoded length 2,049 rejected before decode;
- decoded length 1,025 rejected before JSON;
- malformed Base64;
- forbidden padding;
- non-ASCII cursor;
- invalid Base64 length;
- invalid UTF-8;
- malformed JSON;
- trailing JSON data;
- duplicate JSON keys;
- unknown cursor fields;
- missing cursor fields;
- noncanonical key order/whitespace/escaping;
- NaN/Infinity JSON constants;
- unsupported version;
- Boolean version;
- wrong resource kind;
- invalid position shape;
- invalid/noncanonical position timestamp;
- naive/offset/nonexistent calendar timestamp in the cursor;
- identifier 0, negative, max+1, Boolean, float, or string;
- cursor position maximum equals the shared PostgreSQL identifier maximum;
- malformed fingerprint and fingerprint mismatch;
- position outside lower/upper bounds;
- cursor on an equal empty range;
- no credential/database/token/settings fields.

`test_telemetry_query_validation.py`:

- allowed session query keys;
- allowed measurement query keys;
- every unknown key returns safe 422;
- every supported repeated scalar returns safe 422;
- repeated values are rejected even when identical;
- default limit 100;
- limit 1 and 500 accepted;
- limit 0 and 501 rejected;
- bounded positive `session_id`;
- valid status values;
- invalid/case-changed status;
- aware timestamps accepted;
- naive timestamps rejected;
- timezone normalization;
- `from < to` accepted;
- `from == to` accepted;
- `from > to` rejected;
- cursor/filter mismatch returns safe 422;
- query validation invokes no service/session.

### Implementation boundary

Tests may define only fixtures and black-box expectations. They must not
contain a second implementation of canonicalization or decoding.

### Commands

```powershell
Set-Location backend
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_telemetry_cursor.py `
    tests/test_telemetry_query_validation.py
```

### Expected result

Collection or assertions fail because the new production symbols do not yet
exist. Failures must correspond only to the new contract.

### Rollback or failure condition

- Stop if an existing test fails.
- Stop if a proposed test requires a new dependency.
- Remove only the two uncommitted new test files to return to baseline.

### Proposed commit message

No commit. This is an intentionally red local checkpoint; preserve the tests
for Phase 2 and commit only after the focused contract is green.

## 6. Phase 2A - Implement cursor and filter primitives

### Goal

Make cursor/filter tests green with a pure standard-library codec.

### Files allowed to change

- create `backend/app/services/telemetry_cursor.py`;
- `backend/tests/test_telemetry_cursor.py`;
- `backend/app/services/__init__.py` only if an existing export convention
  requires it.

### Tests written first

All cursor/filter tests from Phase 1 already fail before implementation. Add a
regression before each defect correction found while implementing.

### Implementation boundary

`telemetry_cursor.py` may import:

- standard-library encoding/hash/time modules;
- type/dataclass helpers.

The cursor protocol defines its fixed
`MAX_POSITION_ID = 2_147_483_647` invariant locally. A regression must assert
that it remains equal to the current PostgreSQL identifier maximum. This
avoids making the pure service primitive depend upward on the HTTP/Pydantic
schema layer.

It must not import:

- FastAPI/Starlette;
- SQLAlchemy or `AsyncSession`;
- settings/database modules;
- ORM models;
- Pydantic or HTTP schemas;
- authorization state.

Use exact type checks where Boolean must not pass as integer. Reject duplicate
JSON members through `object_pairs_hook`, constants through `parse_constant`,
and invalid Base64 through validated decoding. Require canonical
reserialization equality.

### Commands

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_telemetry_cursor.py
```

### Expected result

All cursor/filter tests pass. Query-validation tests remain red until Phase
2B.

### Rollback or failure condition

- Stop if the codec requires settings, sessions, ORM models, or a dependency.
- Stop if error messages contain decoded payload or fingerprint data.
- Revert only the uncommitted codec/test changes.

### Proposed commit message

`feat: add telemetry cursor v1 codec`

Commit body should record canonical JSON, dual size bounds, unsigned cursor
semantics, duplicate-key rejection, and filter binding.

## 7. Phase 2B - Implement strict query primitives

### Goal

Make query schema/raw singleton validation green without touching routes.

### Files allowed to change

- `backend/app/schemas/_base.py`;
- create `backend/app/schemas/telemetry.py`;
- create `backend/app/api/query_validation.py`;
- `backend/tests/test_telemetry_query_validation.py`;
- `backend/app/schemas/__init__.py`.

### Tests written first

The Phase 1 strict query tests remain the failing specification. Add exact
regressions for any FastAPI/Pydantic behavior discovered during implementation.

### Implementation boundary

- Add a shared positive PostgreSQL integer annotation rather than an
  unbounded integer.
- Query models use `extra="forbid"`, but raw query singleton checks remain
  mandatory.
- The raw dependency accepts endpoint-specific allowlists and counts
  `multi_items()`.
- Translate raw/cursor errors to `RequestValidationError`.
- Never include raw query values in constructed errors.
- Return pure `SessionReadRequest` or `MeasurementReadRequest` values from the
  resolver.
- No database/session/service lookup occurs.

### Commands

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_telemetry_query_validation.py `
    tests/test_api_schemas.py `
    tests/test_api_errors.py
```

### Expected result

Cursor and query-validation focused tests pass. Existing body-schema and error
contracts remain green.

### Rollback or failure condition

- Stop if unknown parameters are rejected only by a query model.
- Stop if repeated scalars still select first/last.
- Stop if reversed bounds can reach a service.
- Stop if equal bounds are rejected.
- Revert only this phase's schema/API dependency changes.

### Proposed commit message

`feat: enforce strict telemetry query parameters`

## 8. Checkpoint A - Cursor and strict query boundary

Run:

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_telemetry_cursor.py `
    tests/test_telemetry_query_validation.py `
    tests/test_api_schemas.py `
    tests/test_api_errors.py
```

Acceptance:

- all focused tests pass;
- malformed input always maps to safe 422;
- canonical output is deterministic;
- no dependency/session/database imports exist in the codec;
- `git diff --check` passes;
- manual review approves the cursor wire rules before repository work.

## 9. Phase 3 - Write failing repository and service tests

### Goal

Lock SQL shape, ordering, pagination, filtering, device existence, equal-range
ordering, next cursor behavior, and read-only behavior before data access code.

### Files allowed to change

- `backend/tests/test_repositories.py`;
- create `backend/tests/test_telemetry_services.py`;
- `backend/tests/test_query_services.py` only if shared read-only assertions
  need reuse.

No production file changes.

### Tests written first

Repository:

- sessions filtered by path device;
- optional status predicate;
- half-open `started_at` predicates;
- exclusive `(started_at, id)` cursor predicate;
- `ORDER BY started_at DESC, id DESC`;
- supplied bounded fetch limit;
- measurements filtered by path device;
- optional session predicate includes both device and session;
- the session-filtered statement keeps `device_id = ?` even though the
  reviewed index begins with `session_id`;
- half-open `measured_at` predicates;
- exclusive `(measured_at, id)` cursor predicate;
- `ORDER BY measured_at DESC, id DESC`;
- scalar ORM result list returned;
- no `FOR UPDATE`;
- no begin/commit/rollback/flush.

Services:

- device existence is checked first;
- unknown device raises `DeviceNotFoundError`;
- equal session range checks the device then returns empty without list query;
- equal measurement range does the same;
- repository receives `limit + 1`;
- no more than `limit` items returned;
- extra row causes a next cursor;
- cursor uses the last returned item, not the extra row;
- final page returns `next_cursor is None`;
- empty page returns exact empty result;
- all filters and cursor positions forwarded unchanged;
- an existing path device plus a nonexistent or other-device `session_id`
  returns an empty measurement page without a session-existence lookup;
- repeated pages contain no skipped/duplicate IDs under stable fixtures;
- service does not begin/commit/rollback/flush;
- protected ORM/runtime fields remain unchanged.

### Implementation boundary

Repository tests inspect compiled PostgreSQL SQL and bound structure, not
implementation-private helper names. Service tests use repositories as mocks
and assert behavior/read-only calls.

### Commands

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_repositories.py `
    tests/test_telemetry_services.py `
    tests/test_query_services.py
```

### Expected result

Only the new repository/service tests fail for missing symbols/behavior.

### Rollback or failure condition

- Stop if an existing write repository/service test fails.
- Stop if a test assumes offset pagination or total counts.
- Revert only uncommitted test changes.

### Proposed commit message

No commit. Preserve the red tests through Phases 4 and 5, then commit each
green implementation slice separately.

## 10. Phase 4 - Implement repository queries

### Goal

Make repository SQL tests green with bounded, unlocked, parameterized
SQLAlchemy statements.

### Files allowed to change

- `backend/app/repositories/measurement_session.py`;
- `backend/app/repositories/measurement.py`;
- `backend/tests/test_repositories.py`.

### Tests written first

The repository tests from Phase 3 must be red before either repository is
edited.

### Implementation boundary

Each `list_for_device` method:

- accepts explicit typed arguments, not FastAPI/Pydantic request objects;
- always applies `device_id`;
- conditionally applies endpoint filters;
- conditionally applies the exact exclusive OR keyset predicate;
- orders by timestamp descending then ID descending;
- applies the caller's `fetch_limit`;
- executes once;
- returns `result.scalars().all()`;
- never locks or changes transaction state.

No raw SQL strings. No offset. No relationship loading.

For measurement session filtering, do not reshape the predicate to match the
index by dropping `device_id`. The repository must emit both path-device and
session predicates; the session-first index choice relies on the database
invariant, not on weakening API scoping.

### Commands

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_repositories.py
```

### Expected result

All repository tests pass, including existing write repository contracts.
Telemetry service tests remain red.

### Rollback or failure condition

- Stop if compiled SQL lacks either ordering key.
- Stop if optional session filtering omits path `device_id`.
- Stop if a repository imports FastAPI or owns a transaction.
- Revert the two repository edits.

### Proposed commit message

`feat: add bounded telemetry repository queries`

## 11. Phase 5 - Implement service orchestration

### Goal

Make telemetry service tests green while preserving read-only behavior.

### Files allowed to change

- create `backend/app/services/telemetry.py`;
- `backend/tests/test_telemetry_services.py`;
- `backend/app/services/__init__.py` only if required by current exports.

### Tests written first

All service cases from Phase 3 must fail before `telemetry.py` exists.

### Implementation boundary

Each service owns:

- unlocked device existence lookup;
- equal-range empty-page ordering;
- repository call with `limit + 1`;
- trimming to `limit`;
- next cursor construction from last returned row.

The service returns an internal `TelemetryPage`, not a FastAPI response or
Pydantic HTTP envelope. It does not verify cursor wire input; the API boundary
already produced a validated pure read request. It may call the pure encoder
for the next cursor.

### Commands

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_telemetry_services.py `
    tests/test_query_services.py `
    tests/test_services.py
```

### Expected result

All telemetry and existing query/write service tests pass.

### Rollback or failure condition

- Stop if equal range skips device lookup.
- Stop if next cursor uses the extra row.
- Stop if any session/runtime/measurement state changes.
- Stop if a query service imports FastAPI.
- Revert only the new service/test changes.

### Proposed commit message

`feat: orchestrate read-only telemetry pages`

## 12. Checkpoint B - Repository/service behavior

Run:

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_repositories.py `
    tests/test_query_services.py `
    tests/test_telemetry_services.py `
    tests/test_services.py
```

Acceptance:

- exact descending order and exclusive predicates compile;
- filters are correct;
- limit+1 and cursor construction are correct;
- equal range checks device first;
- no read mutation or transaction ownership exists;
- repository/service layer-policy tests remain green.

## 13. Phase 6 - Write failing API and OpenAPI tests

### Goal

Lock public response fields, errors, routes, operation IDs, query
documentation, and compatibility before exposing endpoints.

### Files allowed to change

- `backend/tests/test_api_schemas.py`;
- `backend/tests/test_api_routes.py`;
- `backend/tests/test_api_openapi.py`;
- `backend/tests/test_api_dependencies.py`;
- `backend/tests/test_api_architecture.py`.

No production file changes.

### Tests written first

Schemas:

- `SessionListResponse` exact fields `items`, `next_cursor`;
- session item exact existing fields;
- `MeasurementListResponse` exact fields `items`, `next_cursor`;
- measurement item exact existing fields;
- no totals/page/offset/internal fields;
- JSON timestamp/numeric types remain stable.

Routes:

- both GET paths return 200;
- exact envelopes and public item fields;
- default/explicit limit forwarding;
- all filters forwarding;
- safe unknown-device 404;
- valid nonexistent or other-device `session_id` returns empty 200 without
  revealing session ownership;
- safe malformed path/query/cursor 422;
- safe generic 500;
- unknown/repeated parameters never call service;
- equal range calls service so device existence remains enforceable;
- no route collision with session `active`;
- no protected state mutation through mocked service/page.

Dependencies/architecture:

- both providers reuse the request-scoped `AsyncSession`;
- cursor module has no FastAPI/SQLAlchemy session imports;
- repositories have no FastAPI imports;
- routes have no SQL/transaction calls.

OpenAPI:

- both paths and GET methods;
- operation IDs exactly `list_device_sessions` and
  `list_device_measurements`;
- 200/404/422/500 response sets;
- success response references concrete list envelope schemas;
- query parameter types, bounds, defaults, and status enum;
- path/session IDs show PostgreSQL maximum;
- existing nine contracts byte/structure-equivalent to the captured baseline;
- eleven total operations, ten under `/api/v1`, one `/health`;
- eleven unique IDs.

### Implementation boundary

HTTP tests override telemetry service providers. They must not instantiate a
database session. OpenAPI tests retain connection/schema failure guards.

### Commands

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_api_schemas.py `
    tests/test_api_routes.py `
    tests/test_api_openapi.py `
    tests/test_api_dependencies.py `
    tests/test_api_architecture.py
```

### Expected result

Only new telemetry API assertions fail.

### Rollback or failure condition

- Stop if an existing operation contract changes.
- Stop if FastAPI assigns generated operation IDs.
- Stop if response fields differ from current public item schemas.
- Revert only new uncommitted test assertions.

### Proposed commit message

No commit. Preserve the red API tests through Phases 7A and 7B.

## 14. Phase 7A - Add list schemas and service providers

### Goal

Make response schema and dependency-provider tests green without adding
routes.

### Files allowed to change

- `backend/app/schemas/telemetry.py`;
- `backend/app/schemas/__init__.py`;
- `backend/app/api/dependencies.py`;
- `backend/tests/test_api_schemas.py`;
- `backend/tests/test_api_dependencies.py`.

### Tests written first

The schema/provider tests from Phase 6 must be red before edits.

### Implementation boundary

- Define two concrete list envelope models, not an untyped dictionary.
- `items` is `list[SessionResponse]` or `list[MeasurementResponse]`.
- `next_cursor` is `str | None`.
- Providers construct the matching telemetry query service with the shared
  request session.
- Do not add router includes.

### Commands

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_api_schemas.py `
    tests/test_api_dependencies.py
```

### Expected result

Schema/provider tests pass. Route/OpenAPI tests remain red because GET
operations do not yet exist.

### Rollback or failure condition

- Stop if envelope models add optional/extra fields.
- Stop if provider dependencies create more than one session.
- Revert only this phase's schema/provider changes.

### Proposed commit message

`feat: define telemetry list response contracts`

## 15. Phase 7B - Add routes

### Goal

Expose exactly the two approved GET operations and make API/OpenAPI tests
green.

### Files allowed to change

- `backend/app/api/v1/endpoints/sessions.py`;
- `backend/app/api/v1/endpoints/measurements.py`;
- `backend/tests/test_api_routes.py`;
- `backend/tests/test_api_openapi.py`;
- `backend/tests/test_api_architecture.py`.

### Tests written first

The route/OpenAPI/architecture tests from Phase 6 remain red until route
implementation.

### Implementation boundary

Each GET route:

- reuses the existing bounded path ID annotation;
- declares the strict raw query dependency in the decorator;
- depends on the typed read-request resolver;
- depends on the matching telemetry query service;
- awaits one service call;
- converts ORM items through the existing item response model;
- returns the concrete list envelope;
- declares exact operation ID and 404/422/500 responses.

The existing router composition already includes both endpoint modules. Do
not change `app/api/router.py` or `app/api/v1/router.py`.

### Commands

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_api_routes.py `
    tests/test_api_openapi.py `
    tests/test_api_architecture.py `
    tests/test_api_errors.py
```

### Expected result

All API/OpenAPI focused tests pass with eleven unique operations and the
existing nine unchanged.

### Rollback or failure condition

- Stop if route order makes `/sessions/active` resolve as a dynamic
  identifier.
- Stop if an endpoint declares a raw dictionary response.
- Stop if either route contains SQL or transaction calls.
- Revert only route/test edits.

### Proposed commit message

`feat: expose telemetry read API routes`

## 16. Checkpoint C - HTTP/OpenAPI contract

Run:

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_telemetry_cursor.py `
    tests/test_telemetry_query_validation.py `
    tests/test_telemetry_services.py `
    tests/test_api_schemas.py `
    tests/test_api_routes.py `
    tests/test_api_openapi.py `
    tests/test_api_dependencies.py `
    tests/test_api_architecture.py `
    tests/test_api_errors.py
```

Acceptance:

- exact two new paths/IDs only;
- exact envelopes and item fields;
- safe 404/422/500;
- strict unknown/repeated behavior;
- eleven unique operations;
- existing nine operation contracts unchanged;
- guarded OpenAPI generation makes zero connection calls.

## 17. Phase 8 - Add the reviewed Alembic index migration

### Goal

Bring ORM metadata and database migration source into exact parity with the
approved keyset query shapes.

### Files allowed to change

- `backend/app/db/models/measurement_session.py`;
- `backend/app/db/models/measurement.py`;
- create
  `backend/alembic/versions/<generated_revision>_add_telemetry_read_indexes.py`;
- `backend/tests/test_models.py`;
- `backend/tests/test_migrations.py`.

### Tests written first

Before changing metadata/migration:

- update revision graph expectation from one initial revision to one root and
  one new head;
- assert new revision `down_revision == "a4f9c2e7d1b6"`;
- assert exact four new index names/tables/key order/directions;
- assert exact four old indexes removed at final metadata/head;
- assert the old and new raw session-specific indexes never coexist at the
  final metadata/head;
- assert the new raw session index begins with `session_id` and continues
  with `measured_at DESC, id DESC`;
- assert no partial predicates;
- assert upgrade creates replacements before dropping old indexes;
- assert downgrade recreates old indexes before dropping new indexes;
- assert offline upgrade/downgrade SQL has exact index inventory/order;
- assert no database/schema/role/extension/trigger operations;
- assert offline generation never loads runtime settings or connects;
- assert ORM final metadata equals migrated head inventory.

Run the tests red before editing ORM/revision files.

### Implementation boundary

- Generate one Alembic revision ID through normal workflow only after manual
  approval; do not invent or reuse an ID.
- The revision is self-contained and imports no application ORM model.
- Use `op.create_index`/`op.drop_index` with explicit ordered SQLAlchemy
  expressions.
- Use regular transactional operations.
- Create four new indexes before dropping all four old indexes.
- Downgrade reverses coverage safely.
- Recreate all four old indexes before dropping all four new indexes during
  downgrade.
- Replace `ix_raw_measurements_session_id_measured_at` with
  `ix_raw_measurements_session_id_measured_at_id_desc`; do not retain both.

### Commands

Red check:

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_models.py `
    tests/test_migrations.py
```

After implementation:

```powershell
& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_models.py `
    tests/test_migrations.py

& $PY -B -m alembic -c alembic.ini heads --verbose
& $PY -B -m alembic -c alembic.ini history --verbose
& $PY -B -m alembic -c alembic.ini upgrade head --sql
& $PY -B -m alembic -c alembic.ini `
    downgrade '<generated_revision>:a4f9c2e7d1b6' --sql
```

The offline SQL commands must use only the placeholder URL in `alembic.ini`;
they must not load runtime settings or connect. Replace
`<generated_revision>` with the reviewed revision ID; Alembic offline
downgrade requires the explicit source-to-target range.

### Expected result

- model/migration tests pass;
- one root `a4f9c2e7d1b6`;
- one new head;
- offline SQL contains only the approved index changes;
- no connection occurs.

### Rollback or failure condition

- Stop if the old raw session/time index remains at the migrated head.
- Stop if the new raw session replacement does not begin with `session_id`.
- Stop if final metadata retains a superseded index.
- Stop if upgrade drops old coverage before new coverage exists.
- Stop if downgrade cannot restore the exact old inventory.
- Stop if concurrent index operations appear without a separate approval.
- Revert the new revision and the two ORM metadata edits.

### Proposed commit message

`perf: add telemetry keyset indexes`

Commit body should list four new and four removed indexes, explain the
one-for-one session-first raw replacement and preserved
chronology/foreign-key prefixes, state that endpoint SQL retains both device
and session predicates, and record transactional build implications plus the
required live plan evidence.

## 18. Checkpoint D - Migration parity

Acceptance:

- ORM/head migration parity passes;
- one new Alembic head only;
- upgrade/downgrade order is reversible;
- exact index names stay under PostgreSQL's identifier limit;
- no partial/covering/unapproved object exists;
- the new session-first raw index preserves the chronology aggregate and
  child-side foreign-key lookup prefixes without retaining the old index;
- repository SQL still contains both `device_id` and `session_id`.

## 19. Phase 9 - Full offline verification

### Goal

Prove the complete implementation without PostgreSQL access.

### Files allowed to change

No feature file unless a failing test exposes a defect. Any fix must first add
or sharpen the smallest regression test and must be committed in its owning
phase, not hidden in a verification commit.

### Tests written first

No new behavior is introduced here. Every failure is treated as a missing
regression or implementation defect and routed back to the owning phase.

### Implementation boundary

Offline only. Remove target/opt-in variables by name. Stop if `backend/.env`
exists. Do not open it.

### Commands

```powershell
Set-Location backend

& $PY -B -m pytest -q -p no:cacheprovider

& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_api_openapi.py

& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_api_schemas.py `
    tests/test_telemetry_cursor.py `
    tests/test_telemetry_query_validation.py

& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_repositories.py `
    tests/test_query_services.py `
    tests/test_telemetry_services.py `
    tests/test_services.py

& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_api_integration_guard.py `
    tests/test_persistence_guard.py `
    tests/test_integration_database_reset.py

& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_models.py `
    tests/test_migrations.py

& $PY -B -m pip check
& $PY -B -m alembic -c alembic.ini heads --verbose
& $PY -B -m alembic -c alembic.ini history --verbose
```

Guarded OpenAPI must additionally assert:

```text
OpenAPI 3.1.0
11 total operations
10 /api/v1 operations
1 /health operation
11 unique operation IDs
0 connection/schema calls
```

From the repository root:

```powershell
git diff --check
git status --short --branch
git diff --stat
```

### Expected result

- full offline suite passes with only intentionally skipped live modules;
- focused suites pass;
- pip check passes;
- one new Alembic head;
- OpenAPI inventory is exact;
- whitespace check passes;
- only approved implementation/test/migration files are changed.

### Rollback or failure condition

- No baseline adjustment to make failures disappear.
- No skipped offline regression.
- No update to expected OpenAPI inventory unless it is exactly the approved
  two operations.
- Route a failure back to its smallest owning phase and rerun all checks.

### Proposed commit message

No verification-only commit. If no defect is found, record results in the
review description. If a defect is found, use the owning phase's imperative
commit message.

## 20. Checkpoint E - Offline release gate

Manual review must confirm:

- all test-first contracts exist;
- no hidden offset/count query exists;
- cursor errors are safe;
- no public field drift;
- no read mutation;
- no dependency addition;
- exact migration inventory;
- existing nine OpenAPI contracts unchanged.

Do not proceed to live verification without approval and a disposable target.

## 21. Phase 10 - Live disposable PostgreSQL verification

### Goal

Verify PostgreSQL ordering, tie-breaking, cursor traversal, migration/index
existence, repeatability, cleanup, and representative query plans.

### Authorization

This phase is not authorized by Phase A. It requires a separate manual
approval and externally provisioned local disposable PostgreSQL database.
Never use the protected `airmonitor` database.

### Files allowed to change

- `backend/tests/test_api_integration.py`;
- `backend/tests/test_api_integration_guard.py` only if a guard regression is
  required;
- `backend/tests/test_integration_database_reset.py` only if metadata/head
  expectations require it;
- create
  `docs/reviews/telemetry-read-api-live-verification.md`.

Avoid pushing `test_api_integration.py` beyond a reviewable file size. If the
new cases would take it near 1,000 lines, first extract a focused shared
integration fixture in a separate reviewed test-infrastructure commit rather
than duplicating guards/reset logic.

### Tests written first

Live HTTP/database cases:

- real descending session order;
- real descending measurement order;
- equal timestamps tie-break by descending ID;
- first page and every continuation;
- limit+1 and exact next cursor;
- final null cursor;
- full traversal has no skipped/duplicate IDs;
- status filter;
- session filter scoped to the path device;
- nonexistent and other-device session filters return an indistinguishable
  empty page for an existing path device;
- half-open time filters;
- unknown device 404;
- equal range existing device empty;
- equal range missing device 404;
- cursor wrong resource/device/filter 422;
- protected runtime/session/measurement fields unchanged;
- exact new index existence and old-index absence;
- new session-first raw index has exact
  `(session_id ASC, measured_at DESC, id DESC)` keys;
- old `ix_raw_measurements_session_id_measured_at` is absent at the new head;
- endpoint SQL and observed behavior retain both `device_id` and
  `session_id` scoping;
- identity reset and clean second run.

Migration lifecycle:

- old head -> new head;
- inspect exactly four new indexes and absence of all four old indexes;
- downgrade to `a4f9c2e7d1b6`;
- inspect restoration of exactly all four old indexes and absence of all four
  new indexes;
- re-upgrade to new head;
- run API integration twice;
- cleanup after success and injected failure.

Plan evidence:

- dataset session count and measurement count;
- per-device row distribution;
- timestamp duplication/distribution;
- status distribution;
- rationale against target deployment;
- unfiltered and selective variants;
- first and later pages;
- limits 100 and 500;
- `EXPLAIN (ANALYZE, BUFFERS)` for every required shape;
- representative session-filtered endpoint plans retain
  `device_id = ? AND session_id = ?` and use the session-first replacement
  for bounded `measured_at DESC, id DESC` traversal;
- representative `MAX(measured_at) WHERE session_id = ?` plans use the new
  session-first replacement without full-history work;
- representative child-side lookup plans for
  `session_id = ? AND device_id = ?` benefit from the same `session_id`
  prefix;
- no sequential scan/full-history sort whose work grows with all matches to
  return one bounded page.

### Implementation boundary

- Reuse the existing validated local API integration target and
  metadata-driven reset.
- No credentials/URLs in logs or reports.
- Use bounded `statement_timeout`.
- Store only sanitized plan facts and SQL shapes.
- Do not claim production performance from an unrepresentative tiny dataset.

### Commands

The operator injects approved target values securely without echoing them.
After the guard validates the target:

```powershell
Set-Location backend

& $PY -B -m alembic -c alembic.ini upgrade head

& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_api_integration.py

& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_api_integration.py

& $PY -B -m alembic -c alembic.ini downgrade a4f9c2e7d1b6
& $PY -B -m alembic -c alembic.ini upgrade head

& $PY -B -m pytest -q -p no:cacheprovider `
    tests/test_api_integration.py
```

Then rerun the complete offline command set with all live variables removed by
name.

### Expected result

- every live case passes;
- two consecutive activations start empty and reset identities;
- migration downgrade/re-upgrade is exact;
- no disposable object remains after external cleanup;
- plans use the reviewed indexes for representative bounded queries;
- the new session-first raw index proves endpoint ordering, chronology, and
  child-side lookup support without a duplicate old session/time index;
- sanitized live report contains no local target or credential value.

### Rollback or failure condition

- Abort on any guard/preflight mismatch.
- Abort if target is not local, disposable, prefix-approved, and distinct from
  the protected database.
- Abort if dataset/profile/latency objective is not approved.
- Abort if any required plan scales with full matching history.
- Abort if the session-filtered endpoint drops the `device_id` predicate or
  the new session-first index does not support any of its three required
  access paths.
- Abort if cleanup or identity reset fails.
- Downgrade only the disposable database; never operate on another target.
- Revisit the migration/index set through a new review rather than adding an
  ad hoc fifth/sixth query index.

### Proposed commit message

`test: verify telemetry reads on PostgreSQL`

The live report may be included in the same commit only if it records the
exact verified implementation state and contains no secrets or local target
identifiers.

## 22. Checkpoint F - Live evidence gate

Manual database/performance review must approve:

- target/dataset representativeness;
- exact explain plans and buffers;
- session-filtered endpoint plans with both device and session predicates;
- chronology MAX and child-side lookup plans using the single new
  session-first raw index;
- absence of the rejected duplicate session-specific index design;
- index build/write cost;
- migration maintenance-window policy;
- repeatability and cleanup;
- no public deployment claim.

## 23. Phase 11 - Documentation update

### Goal

Make documentation reflect the verified implementation without changing the
approved behavior.

### Files allowed to change

- `docs/specs/telemetry-read-api.md`;
- `README.md`;
- `docs/reviews/telemetry-read-api-live-verification.md`;
- this implementation plan only to mark completed evidence, if the project
  uses plan status updates.

### Tests written first

No code behavior. Add/extend a documentation verification checklist before
editing:

- two endpoints and operation IDs exact;
- cursor remains opaque and unsigned;
- no auth/public deployment claim;
- migration head and index names exact;
- test commands exact;
- live target details absent;
- links and paths valid.

### Implementation boundary

- Change the approved spec's implementation-status/evidence sections only;
  do not silently change its contract.
- README describes current v2 behavior and safe test commands.
- Live report records sanitized dataset/plan/results.
- Do not include credentials, database URLs, generated target names, or
  machine-specific paths other than an explicitly approved interpreter
  command if required.

### Commands

```powershell
git diff --check

rg -n --hidden `
    "(BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|postgresql(\\+asyncpg)?://[^[:space:]]+@|api[_-]?key[[:space:]]*[:=]|access[_-]?token[[:space:]]*[:=])" `
    docs README.md

rg -n "C:\\Users\\|/Users/|/home/" `
    docs README.md
```

Review every hit; do not print secret-bearing file contents to classify a
match.

### Expected result

- docs match verified code/OpenAPI/migration;
- no sensitive/local target value;
- no unapproved behavior change;
- whitespace check passes.

### Rollback or failure condition

- Stop if docs require changing the approved contract.
- Stop if a live result is incomplete or unsanitized.
- Revert documentation-only edits; do not alter code to match inaccurate
  prose.

### Proposed commit message

`docs: document telemetry read API`

## 24. Phase 12 - Review, commit, and merge sequence

### Goal

Perform a five-axis review, preserve small green commits, and stop for human
approval before merge.

### Files allowed to change

Only files already in the approved implementation scope. Review fixes must
remain in the owning layer and include a regression test.

### Tests written first

For each correctness defect discovered in review, add the smallest failing
regression before the fix. Do not add tests for formatting preferences.

### Implementation boundary

- Review and fix only files already changed by the approved feature phases.
- Keep every correction in its owning route, schema, codec, service,
  repository, ORM, migration, test, or documentation layer.
- Do not use final review to add endpoints, fields, dependencies, indexes, or
  deployment behavior outside the approved contract.
- Do not stage, commit, merge, or otherwise write Git state until the
  corresponding manual gate explicitly authorizes it.

### Review axes

Correctness:

- exact contract;
- range/cursor edges;
- stable order;
- no skipped/duplicate stable traversal;
- safe errors;
- migration reversibility.

Readability:

- explicit names and types;
- no duplicate cursor/query logic;
- no oversized endpoint functions;
- no pass-through abstractions.

Architecture:

- dependency direction preserved;
- routes/services/repositories/codec own the right concerns;
- no feature logic in shared modules beyond the bounded integer annotation;
- no repository transaction ownership.

Security:

- every external value validated at the boundary;
- no parser/SQL/credential leakage;
- cursor treated as untrusted and not authorization;
- no public deployment claim.

Performance:

- bounded limit+1;
- no count/offset;
- exact index prefixes;
- no N+1;
- four replacements remove all four old indexes;
- no duplicate session-specific raw index;
- session-first index supports endpoint, chronology, and foreign-key lookup
  shapes while endpoint SQL retains device scoping;
- write amplification and final index set justified by representative live
  plans.

### Commit sequence

Recommended green commits:

1. `feat: add telemetry cursor v1 codec`
2. `feat: enforce strict telemetry query parameters`
3. `feat: add bounded telemetry repository queries`
4. `feat: orchestrate read-only telemetry pages`
5. `feat: define telemetry list response contracts`
6. `feat: expose telemetry read API routes`
7. `perf: add telemetry keyset indexes`
8. `test: verify telemetry reads on PostgreSQL`
9. `docs: document telemetry read API`

Do not commit red-only checkpoints. Do not squash the entire feature into one
implementation commit. Refactoring unrelated code is not allowed in these
commits.

### Commands

Rerun all Phase 9 commands, then:

```powershell
git diff --check
git status --short --branch
git diff --stat
git diff --name-only
git log --oneline --decorate -15
```

After external review only:

```text
stage one approved commit group
review staged diff
commit with the proposed imperative message
repeat for each group
merge only after all offline/live/documentation gates are approved
```

The exact Git write commands are intentionally not prescribed or authorized
by Phase A.

### Expected result

- no Critical or Required review finding remains;
- all tests/checks pass;
- commit history is small and searchable;
- only approved files changed;
- human reviewer explicitly approves merge.

### Rollback or failure condition

- Do not merge with a red test, unreviewed migration, incomplete live
  evidence, secret/path hit, or required finding.
- Revert only the offending commit group.
- If the contract itself needs revision, stop and return to a separately
  approved specification phase.

### Proposed commit message

No extra "review" commit. Review fixes use the owning commit where history can
still be amended safely, or a narrowly named follow-up commit after review.

## 25. Test coverage matrix

| Required behavior | Planned phase/tests |
|---|---|
| exact response fields | Phase 6 schema/API tests |
| limit default/bounds | Phases 1, 6 |
| PostgreSQL integer bounds | Phases 1, 6 |
| aware timestamps/UTC | Phases 1, 2 |
| reversed/equal ranges | Phases 1, 3, 6, 10 |
| invalid status | Phases 1, 6 |
| unknown query | Phases 1, 6 |
| repeated scalar query | Phases 1, 6 |
| cursor round trip/determinism | Phases 1, 2 |
| URL-safe/no-padding | Phases 1, 2 |
| malformed/oversized Base64 | Phases 1, 2 |
| malformed/duplicate/unknown JSON | Phases 1, 2 |
| version/resource/timestamp/ID/fingerprint errors | Phases 1, 2 |
| stable descending repository order | Phases 3, 4, 10 |
| identical timestamp ID tie | Phases 3, 4, 10 |
| limit+1/next cursor/final null | Phases 3, 5, 10 |
| no skip/duplicate traversal | Phases 3, 5, 10 |
| status/session/time filters, including session non-disclosure | Phases 3-6, 10 |
| unknown device 404 | Phases 3, 5, 6, 10 |
| equal range device-first | Phases 3, 5, 6, 10 |
| read-only/no mutation | Phases 3, 5, 6, 10 |
| both paths/IDs/responses | Phases 6, 7 |
| existing nine unchanged | Phases 6, 7, 9 |
| final eleven unique operations | Phases 6, 7, 9 |
| real ordering/cursor/repeatability | Phase 10 |
| migration/index existence | Phases 8, 10 |
| cleanup/identity reset | Phase 10 |
| representative explain plans | Phase 10 |

## 26. Final acceptance checklist

- [x] Exactly two GET operations added.
- [x] Existing nine operations unchanged.
- [x] Eleven unique operation IDs.
- [x] Exact existing item fields.
- [x] Exact `{items, next_cursor}` envelopes.
- [x] Unknown and repeated query parameters return safe 422.
- [x] All IDs remain within PostgreSQL `INTEGER`.
- [x] All query timestamps are aware and normalized to UTC.
- [x] Reversed ranges return 422.
- [x] Equal ranges check device existence before empty 200.
- [x] Cursor v1 is canonical, strict, URL-safe, unpadded, versioned,
      resource/filter-bound, and secret-free.
- [x] Stable descending keyset order uses timestamp and ID.
- [x] Fetch uses limit+1 and next cursor uses last returned item.
- [x] No offset/count query.
- [x] Reads perform no mutation or transaction control.
- [x] Exactly four new indexes replace all four old explicit indexes.
- [x] The only session-specific raw index at the new head is
      `ix_raw_measurements_session_id_measured_at_id_desc`.
- [x] Session-filtered endpoint SQL retains both `device_id` and `session_id`.
- [ ] Live plans validate endpoint ordering, chronology MAX, and child-side
      lookup use of the session-first raw index.
- [x] ORM/Alembic parity and reversible downgrade.
- [x] Full offline suite green with approved interpreter.
- [x] Guarded OpenAPI generation makes no connection.
- [x] Disposable PostgreSQL suite passes twice and cleans/reset identities.
- [x] Representative `EXPLAIN (ANALYZE, BUFFERS)` approved.
- [x] Documentation contains no secret/local target.
- [x] Five-axis review complete.
- [ ] Manual external review approves each gate.

## 27. Historical Phase A stop

At the time this plan was written, it did not authorize implementation, Git
writes, PostgreSQL access, or live integration activation. That historical
boundary was superseded by the current root completion instructions. The
completed offline and disposable live results are recorded in the final
verification report.
