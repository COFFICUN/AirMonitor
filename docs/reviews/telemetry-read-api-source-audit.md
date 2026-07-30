# Telemetry Read API Phase A Source Audit

**Audit date:** 2026-07-30

**Audit mode:** documentation-only, offline, no PostgreSQL access

**Reviewed revision:** `8028bd5972ace274c0a106b9ab32d0d798a45c7a`

**Base branch and commit:** `develop` at
`a83b065e1804e63798e714eac5496ecf957ba84f`

**Approved contract:** `docs/specs/telemetry-read-api.md`

**Implementation status:** not implemented

## 1. Executive conclusion

The current AirMonitor v2 source is ready for a test-first implementation of
the two approved telemetry read operations without changing its dependency
direction:

- routes resolve request-scoped dependencies and construct HTTP schemas;
- query services orchestrate read behavior without controlling transactions;
- repositories own SQLAlchemy statements but not transactions;
- ORM models and Alembic own the relational contract.

The approved public item contracts are already available as
`SessionResponse` and `MeasurementResponse`. Current timestamp and PostgreSQL
`INTEGER` validation primitives are reusable. Current safe 404, 422, and 500
terminology also matches the approved specification.

Two implementation boundaries need new code:

1. FastAPI 0.139.1 does not reject unknown scalar query parameters by default
   and selects the last value of a repeated scalar. A strict raw-query
   dependency is required in addition to typed Pydantic query models.
2. No current cursor or pagination utility exists. Cursor v1 needs a small
   pure codec with strict Base64url, canonical JSON, duplicate-key, size,
   resource, position, and filter-fingerprint validation.

**Migration decision: a reviewed Alembic migration is required.** The four
current explicit time/filter indexes omit the `id` ordering tie-break. The
approved unfiltered and optional-filter query shapes need four new ordered
composite indexes. All four current explicit indexes become redundant and
should be removed after their replacements exist. The replacement
`ix_raw_measurements_session_id_measured_at_id_desc` preserves the
`session_id` leading prefix needed by both the existing
`MAX(measured_at) WHERE session_id = ?` chronology query and child-side
foreign-key lookup while adding the API's `id` ordering tie-break.

No production code, tests, ORM model, migration, requirement, environment
template, README, approved specification, Agent Skill, legacy file, or Git
state was changed during this audit.

## 2. Scope and method

### 2.1 Repository identity

- Repository root:
  `<Codex-worktree>`
- Working directory:
  `<Codex-worktree>`
- HEAD is detached at
  `8028bd5972ace274c0a106b9ab32d0d798a45c7a`.
- The detached commit is `chore: define telemetry read API Phase A scope`.
- Its direct parent is `develop` at
  `a83b065e1804e63798e714eac5496ecf957ba84f`.
- Local and remote `feature/telemetry-read-api` refs point at the detached
  commit.
- Initial status was exactly `## HEAD (no branch)`.
- Initial porcelain-v2 status contained only:
  - `# branch.oid 8028bd5972ace274c0a106b9ab32d0d798a45c7a`
  - `# branch.head (detached)`

### 2.2 Governing instructions and selected skills

The only repository instruction file is the root `AGENTS.md`; no nested
`AGENTS.md` exists. It was read completely before any other repository file.

The requested skills were applied in this order:

1. `using-agent-skills`
2. `source-driven-development`
3. `api-and-interface-design`
4. `supabase-postgres-best-practices`
5. `planning-and-task-breakdown`
6. `code-review-and-quality`

The planning skill's generic `tasks/` convention is superseded by the
repository-specific requirement to create only this audit and
`docs/plans/telemetry-read-api-implementation-plan.md`.

### 2.3 Required material read completely

- `docs/specs/telemetry-read-api.md`
- `docs/reviews/sprint-8-full-codebase-audit.md`
- `docs/reviews/sprint-8-final-verification.md`
- `docs/reviews/sprint-8-c4b-live-verification.md`

The Sprint 8 full audit was re-read in bounded chunks after its first terminal
view was truncated. No conclusion relies on the truncated view.

### 2.4 No-connection safeguards

- Only
  `<repository-root>\backend\.venv\Scripts\python.exe`
  ran Python or pytest commands.
- The ordinary application database variable and all live-test target/opt-in
  variables were removed by name from verification subprocesses.
- No value of any database URL variable was read, printed, or inspected.
- An existence-only check established that `backend/.env` was absent.
- Guarded OpenAPI generation replaced asyncpg, synchronous SQLAlchemy,
  asynchronous SQLAlchemy, and `MetaData.create_all` connection/schema entry
  points with failures.
- The guarded call count remained zero.
- No PostgreSQL client, preflight, migration execution, database creation, or
  live integration suite ran.

## 3. Current stack and dependencies

Declared dependencies:

| Component | Version |
|---|---:|
| FastAPI | 0.139.1 |
| pydantic-settings | 2.14.2 |
| Uvicorn | 0.51.0 |
| SQLAlchemy asyncio | 2.0.51 |
| asyncpg | 0.31.0 |
| Alembic | 1.18.5 |
| httpx2 | 2.7.0 |
| pytest | 8.4.2 |

The approved interpreter reported:

| Component | Installed version |
|---|---:|
| Python | 3.13.7 |
| FastAPI | 0.139.1 |
| Pydantic | 2.13.4 |
| pydantic-settings | 2.14.2 |
| SQLAlchemy | 2.0.51 |
| Alembic | 1.18.5 |
| asyncpg | 0.31.0 |
| pytest | 8.4.2 |

The Python standard library already provides `base64`, `binascii`, `datetime`,
`hashlib`, `hmac`, `json`, and `re`. Cursor v1 requires no dependency change.

## 4. Current OpenAPI inventory

Guarded offline generation produced:

- OpenAPI version `3.1.0`;
- nine total operations;
- eight `/api/v1` operations;
- one `/health` operation;
- nine unique operation IDs;
- zero connection or schema-creation calls.

| Method | Path | Operation ID |
|---|---|---|
| `POST` | `/api/v1/devices` | `create_device` |
| `GET` | `/api/v1/devices/{device_id}` | `get_device` |
| `PATCH` | `/api/v1/devices/{device_id}/status` | `set_device_status` |
| `POST` | `/api/v1/devices/{device_id}/sessions` | `start_measurement_session` |
| `GET` | `/api/v1/devices/{device_id}/sessions/active` | `get_active_measurement_session` |
| `POST` | `/api/v1/devices/{device_id}/sessions/active/cancel` | `cancel_active_measurement_session` |
| `POST` | `/api/v1/devices/{device_id}/sessions/active/complete` | `complete_active_measurement_session` |
| `POST` | `/api/v1/devices/{device_id}/measurements` | `record_raw_measurement` |
| `GET` | `/health` | `get_health_health_get` |

The implementation must add only:

| Method | Path | Required operation ID |
|---|---|---|
| `GET` | `/api/v1/devices/{device_id}/sessions` | `list_device_sessions` |
| `GET` | `/api/v1/devices/{device_id}/measurements` | `list_device_measurements` |

The final inventory must contain eleven unique operations. The existing nine
operation IDs, paths, success status codes, request bodies, response schemas,
and documented error envelopes must remain unchanged.

Source and tests:

- `backend/app/api/router.py`
- `backend/app/api/v1/router.py`
- `backend/app/api/v1/endpoints/devices.py`
- `backend/app/api/v1/endpoints/sessions.py`
- `backend/app/api/v1/endpoints/measurements.py`
- `backend/tests/test_api_openapi.py`

## 5. Current source layout and dependency direction

```text
app.main
  -> app.api routers and exception handlers
       -> request/query schemas and API dependency providers
            -> read or write service
                 -> repository
                      -> SQLAlchemy ORM and AsyncSession
```

### 5.1 Application and async database lifecycle

`backend/app/main.py` creates one engine and one async session factory for
each application instance, stores both on `application.state`, and awaits
engine disposal in FastAPI lifespan cleanup.

`backend/app/db/dependencies.py` resolves the application-owned session
factory from `request.app.state`, opens one `AsyncSession`, yields it, and
closes it after the request.

`backend/app/db/session.py` configures:

- `expire_on_commit=False`;
- `autoflush=False`;
- `pool_pre_ping` from settings;
- `hide_parameters=True`.

Creating the engine does not connect. OpenAPI generation does not request a
session.

### 5.2 Route boundary

Routes:

- declare FastAPI path/body constraints;
- resolve services through `Depends`;
- call one service operation;
- convert declared scalar ORM attributes into response schemas.

They contain no raw SQL, repository construction, `begin`, `commit`,
`rollback`, or `flush`.

### 5.3 Service boundary

`DeviceService` and `MeasurementService` own write transactions through
`async with self._session.begin()`.

`DeviceQueryService` and `ActiveSessionQueryService` perform read
orchestration without:

- beginning or committing a transaction;
- rolling back;
- flushing;
- mutating ORM state.

Future telemetry query services belong beside these read services. They must
not manually construct `JSONResponse`, HTTP status codes, or error bodies.

### 5.4 Repository boundary

Repositories:

- construct SQLAlchemy expressions;
- execute reads and updates;
- add and flush new ORM entities where write services require generated
  identifiers;
- never own `begin`, `commit`, or `rollback`;
- never import FastAPI or `app.api`.

Future list statements belong in:

- `backend/app/repositories/measurement_session.py`;
- `backend/app/repositories/measurement.py`.

### 5.5 Existing read/write query affected by index design

`RawMeasurementRepository.get_latest_measured_at(session_id=...)` executes:

```sql
SELECT max(raw_measurements.measured_at)
FROM raw_measurements
WHERE raw_measurements.session_id = ?
```

`MeasurementService._transition_session` uses this query after acquiring the
device, runtime-state, and session locks. It enforces that a terminal
timestamp is not earlier than the latest measurement. Index replacement must
not regress this current write-path invariant.

## 6. Exact current ORM and public response fields

### 6.1 Devices

`Device` ORM fields:

| Field | ORM type | Null |
|---|---|---:|
| `id` | PostgreSQL `INTEGER` | no |
| `device_uid` | `VARCHAR(255)` | no |
| `name` | `VARCHAR(255)` | yes |
| `is_active` | `BOOLEAN` | no |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | no |

`DeviceResponse` exposes:

```text
id
device_uid
name
is_active
created_at
```

### 6.2 Measurement sessions

`MeasurementSession` ORM fields:

| Field | ORM type | Null |
|---|---|---:|
| `id` | PostgreSQL `INTEGER` | no |
| `device_id` | PostgreSQL `INTEGER` | no |
| `status` | `VARCHAR(20)` | no |
| `started_at` | `TIMESTAMP WITH TIME ZONE` | no |
| `ended_at` | `TIMESTAMP WITH TIME ZONE` | yes |
| `latitude` | `DOUBLE PRECISION` | no |
| `longitude` | `DOUBLE PRECISION` | no |
| `sample_count` | PostgreSQL `INTEGER` | no |
| `avg_temperature` | `DOUBLE PRECISION` | yes |
| `avg_humidity` | `DOUBLE PRECISION` | yes |
| `avg_pm1` | `DOUBLE PRECISION` | yes |
| `avg_pm25` | `DOUBLE PRECISION` | yes |
| `avg_pm10` | `DOUBLE PRECISION` | yes |
| `min_pm25` | `DOUBLE PRECISION` | yes |
| `max_pm25` | `DOUBLE PRECISION` | yes |
| `aqi_pm25` | PostgreSQL `INTEGER` | yes |
| `aqi_category` | `VARCHAR(50)` | yes |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | no |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | no |

Relationships are `device`, `raw_measurements`, and `active_runtime_state`.

Exact `SessionResponse` fields:

```text
id
device_id
status
started_at
ended_at
latitude
longitude
sample_count
created_at
```

`status` is typed as the literal union `active | completed | cancelled`.
`SessionResponse` intentionally excludes `updated_at`, summary/AQI fields,
relationships, and SQLAlchemy state.

### 6.3 Raw measurements

`RawMeasurement` ORM fields:

```text
id
device_id
session_id
source_message_id
measured_at
received_at
temperature
humidity
pm1
pm25
pm10
pc0_3
pc0_5
pc1_0
pc2_5
pc5_0
pc10
latitude
longitude
is_valid
validation_note
created_at
```

Relationships are `device` and `session`.

Exact `MeasurementResponse` fields are the same scalar names shown above.
It excludes relationships and SQLAlchemy state.

Source and tests:

- `backend/app/db/models/device.py`
- `backend/app/db/models/measurement_session.py`
- `backend/app/db/models/measurement.py`
- `backend/app/schemas/devices.py`
- `backend/app/schemas/sessions.py`
- `backend/app/schemas/measurements.py`
- `backend/tests/test_api_schemas.py`

## 7. Current validation and error conventions

### 7.1 Shared validation

`backend/app/schemas/_base.py` defines:

- `POSTGRES_INTEGER_MAX = 2_147_483_647`;
- `NonNegativePostgresInteger`;
- `AwareDatetime`;
- `RequestModel` with `extra="forbid"` and `allow_inf_nan=False`;
- `ORMResponseModel` with `from_attributes=True`.

Current path identifiers use:

```text
gt = 0
le = POSTGRES_INTEGER_MAX
```

`AwareDatetime` rejects values whose UTC offset cannot be determined.
`app.services._support.as_utc` converts valid aware datetimes with
`astimezone(UTC)`.

Future `device_id` and `session_id` input must reuse the shared PostgreSQL
integer maximum. Python's unbounded `int` must not reach a PostgreSQL
`INTEGER` bind unbounded.

### 7.2 Current error envelope

`ErrorResponse` is:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": null
  }
}
```

Relevant mappings:

| Condition | Status | Code | Message |
|---|---:|---|---|
| missing path device | 404 | `device_not_found` | `Device was not found.` |
| invalid request | 422 | `request_validation_error` | `Request validation failed.` |
| unexpected failure | 500 | `internal_server_error` | `An internal server error occurred.` |

The request-validation handler discards raw Pydantic/FastAPI errors. Cursor,
parameter-name, repeated-value, parser, SQL, and server-state details are
therefore not exposed.

`backend/app/api/responses.py` always adds a documented 500 response and
allows routes to declare 404, 409, and 422 envelopes.

### 7.3 Actual FastAPI query behavior

An offline runtime probe against FastAPI 0.139.1 and Pydantic 2.13.4 proved:

| Probe | Actual result |
|---|---|
| scalar route with unknown query key | 200; key ignored |
| scalar route with `limit=1&limit=2` | 200; `limit == 2` |
| Pydantic query model with `extra="forbid"` and unknown key | 422 |
| same strict model with `limit=1&limit=2` | 200; `limit == 2` |

This agrees with FastAPI's documented query-model support and Starlette's
immutable multidict request interface. A query model can forbid unknown keys,
but it does not enforce singleton occurrence.

## 8. Strict query validation boundary

### 8.1 Required strategy

Each new GET route needs both:

1. a route-decorator dependency that inspects
   `request.query_params.multi_items()`; and
2. a typed Pydantic query model declared with `Query()`.

The raw dependency must:

- use an endpoint-specific immutable allowlist;
- reject a key outside that allowlist;
- count every raw occurrence;
- reject any supported scalar whose count is greater than one;
- raise `RequestValidationError` without including raw values;
- perform no database access;
- execute before the endpoint body.

Session allowlist:

```text
status
started_from
started_to
limit
cursor
```

Measurement allowlist:

```text
session_id
measured_from
measured_to
limit
cursor
```

The typed models must then validate:

- literal session status;
- positive bounded `session_id`;
- aware timestamps;
- `limit` default 100, minimum 1, maximum 500;
- cursor string presence and 2,048-character input bound;
- reversed ranges.

`from > to` is a request-validation error. `from == to` remains valid and
must not be rejected by the schema.

### 8.2 Ordering with device existence

The query dependency validates and normalizes all request data before any
database call. The query service then:

1. establishes that the path device exists;
2. returns an empty page for an equal range;
3. otherwise queries the requested resource.

This preserves both FastAPI's validation-before-endpoint behavior and the
approved rule that an equal range does not bypass a missing-device 404.

## 9. Current database constraints and indexes

This inventory is source-level ORM/Alembic evidence. No deployed database was
introspected.

### 9.1 `devices`

Constraints:

| Kind | Source name | Columns / target |
|---|---|---|
| primary key | unnamed in source | `(id)` |
| unique | `uq_devices_device_uid` | `(device_uid)` |

PostgreSQL creates a unique backing index for the primary key and named unique
constraint. There is no explicit index, foreign key, or check constraint on
this table.

### 9.2 `measurement_sessions`

Key and foreign-key constraints:

| Kind | Name | Columns / target |
|---|---|---|
| primary key | unnamed in source | `(id)` |
| unique | `uq_measurement_sessions_id_device_id` | `(id, device_id)` |
| foreign key | `fk_measurement_sessions_device_id_devices` | `(device_id) -> devices(id)`, `RESTRICT` |

Named checks:

```text
ck_measurement_sessions_status
ck_measurement_sessions_status_ended_at_consistency
ck_measurement_sessions_ended_at_order
ck_measurement_sessions_sample_count_nonnegative
ck_measurement_sessions_latitude_range
ck_measurement_sessions_longitude_range
ck_measurement_sessions_avg_temperature_range
ck_measurement_sessions_avg_humidity_range
ck_measurement_sessions_avg_pm1_nonnegative
ck_measurement_sessions_avg_pm25_nonnegative
ck_measurement_sessions_avg_pm10_nonnegative
ck_measurement_sessions_min_pm25_nonnegative
ck_measurement_sessions_max_pm25_nonnegative
ck_measurement_sessions_pm25_min_max_order
ck_measurement_sessions_aqi_pm25_range
```

Explicit non-unique indexes:

| Name | Ordered keys | Partial predicate |
|---|---|---|
| `ix_measurement_sessions_device_id_started_at` | `(device_id ASC, started_at ASC)` | none |
| `ix_measurement_sessions_device_id_status` | `(device_id ASC, status ASC)` | none |

Both explicit indexes lead with the session table's foreign-key column.

### 9.3 `raw_measurements`

Key and foreign-key constraints:

| Kind | Name | Columns / target |
|---|---|---|
| primary key | unnamed in source | `(id)` |
| unique | `uq_raw_measurements_device_id_source_message_id` | `(device_id, source_message_id)` |
| foreign key | `fk_raw_measurements_device_id_devices` | `(device_id) -> devices(id)`, `RESTRICT` |
| composite foreign key | `fk_raw_measurements_session_device` | `(session_id, device_id) -> measurement_sessions(id, device_id)`, `RESTRICT` |

Named checks:

```text
ck_raw_measurements_temperature_range
ck_raw_measurements_humidity_range
ck_raw_measurements_pm1_nonnegative
ck_raw_measurements_pm25_nonnegative
ck_raw_measurements_pm10_nonnegative
ck_raw_measurements_pc0_3_nonnegative
ck_raw_measurements_pc0_5_nonnegative
ck_raw_measurements_pc1_0_nonnegative
ck_raw_measurements_pc2_5_nonnegative
ck_raw_measurements_pc5_0_nonnegative
ck_raw_measurements_pc10_nonnegative
ck_raw_measurements_latitude_range
ck_raw_measurements_longitude_range
ck_raw_measurements_coordinates_paired
```

Explicit non-unique indexes:

| Name | Ordered keys | Partial predicate |
|---|---|---|
| `ix_raw_measurements_device_id_measured_at` | `(device_id ASC, measured_at ASC)` | none |
| `ix_raw_measurements_session_id_measured_at` | `(session_id ASC, measured_at ASC)` | none |

The device FK has device-leading explicit and unique indexes. The composite
session/device FK has an index beginning with `session_id`; it does not have
an exact `(session_id, device_id)` key.

### 9.4 Alembic parity and head

`backend/alembic/versions/a4f9c2e7d1b6_create_initial_airmonitor_schema.py`
matches the ORM declarations above, including:

- all relevant columns and PostgreSQL types;
- primary, unique, foreign-key, and check constraints;
- all four explicit indexes;
- dependency-safe table creation;
- index-first, reverse-dependency downgrade.

Alembic has one base/head:

```text
a4f9c2e7d1b6
```

## 10. Query-to-index analysis

PostgreSQL B-tree indexes are most efficient when leading columns have
equality constraints followed by the first range/order column. A B-tree can
scan backward, so an all-ascending `(timestamp, id)` suffix could satisfy an
all-descending order. The current problem is not the absence of explicit
`DESC`; it is the absence of `id` and, for optional filters, the required
equality prefix.

An index matching `ORDER BY ... LIMIT n` can return the first bounded rows
without sorting all matches. Bitmap combination of separate indexes does not
preserve the approved key order.

### 10.1 Session queries

| Approved query | Current candidate | Ordered-prefix analysis | Decision |
|---|---|---|---|
| `device_id = ? ORDER BY started_at DESC, id DESC` | `(device_id, started_at)` | `device_id` equality and timestamp traversal match; `id` tie-break is absent | insufficient |
| `device_id = ? AND status = ? ORDER BY started_at DESC, id DESC` | `(device_id, status)` | both equality predicates match; no ordering suffix | insufficient |
| same status query using both current indexes | bitmap/index combination | may filter, but does not emit `(started_at, id)` order | insufficient |
| device plus `started_at >= ? AND started_at < ?` | `(device_id, started_at)` | range is useful; `id` tie-break is absent | insufficient |
| cursor continuation on `(started_at, id)` | `(device_id, started_at)` | first cursor key is indexed; second cursor key is absent | insufficient |

The unique index `(id, device_id)` is ordered from `id`, so it cannot serve a
device-leading history scan.

### 10.2 Measurement queries

| Approved query | Current candidate | Ordered-prefix analysis | Decision |
|---|---|---|---|
| `device_id = ? ORDER BY measured_at DESC, id DESC` | `(device_id, measured_at)` | device/time match; `id` tie-break is absent | insufficient |
| `device_id = ? AND session_id = ? ORDER BY measured_at DESC, id DESC` | `(session_id, measured_at)` | `session_id` equality and time traversal are useful; `id` is absent. `device_id` remains a required correctness/path-scope predicate even though it need not lead the index because one globally unique session ID belongs to one device | insufficient |
| device plus `measured_at >= ? AND measured_at < ?` | `(device_id, measured_at)` | range is useful; `id` tie-break is absent | insufficient |
| cursor continuation on `(measured_at, id)` | `(device_id, measured_at)` | first cursor key is indexed; second cursor key is absent | insufficient |

The unique `(device_id, source_message_id)` index can filter a device prefix
but cannot provide measurement-time order. The primary key can provide ID
order alone but cannot provide device/time order. Neither overlap is
sufficient.

For the session-filtered endpoint shape, the approved replacement is
`(session_id ASC, measured_at DESC, id DESC)`. Equality on `session_id`
exposes the complete ordering suffix for stable keyset traversal. The
repository must still emit both `device_id = ?` and `session_id = ?`:
`device_id` is part of the API's correctness and non-disclosure boundary.
The database invariant behind
`(session_id, device_id) -> measurement_sessions(id, device_id)`, together
with the globally unique session primary key, guarantees that matching rows
for one `session_id` have one device. The device predicate can therefore be
applied as a correctness filter without requiring a second device/session
index.

### 10.3 Required keyset predicates

Repositories must express the approved exclusive predicates:

```sql
started_at < :cursor_started_at
OR (
    started_at = :cursor_started_at
    AND id < :cursor_id
)
```

and:

```sql
measured_at < :cursor_measured_at
OR (
    measured_at = :cursor_measured_at
    AND id < :cursor_id
)
```

The final statement order must be the matching timestamp descending followed
by `id` descending, and the SQL limit must be the validated client limit plus
one.

## 11. Explicit migration decision and design

### 11.1 Decision

**A reviewed Alembic migration is required.**

The approved specification requires a migration when no approved deployment
cardinality/distribution profile and read-latency objective exist. Neither is
present in current source or approved documentation. The current indexes also
fail the deterministic ordered-prefix analysis directly.

### 11.2 New indexes

| Name | Table | Ordered key columns | Predicate |
|---|---|---|---|
| `ix_measurement_sessions_device_id_started_at_id_desc` | `measurement_sessions` | `(device_id ASC, started_at DESC, id DESC)` | none |
| `ix_measurement_sessions_device_id_status_started_at_id_desc` | `measurement_sessions` | `(device_id ASC, status ASC, started_at DESC, id DESC)` | none |
| `ix_raw_measurements_device_id_measured_at_id_desc` | `raw_measurements` | `(device_id ASC, measured_at DESC, id DESC)` | none |
| `ix_raw_measurements_session_id_measured_at_id_desc` | `raw_measurements` | `(session_id ASC, measured_at DESC, id DESC)` | none |

No partial status index is appropriate because the API accepts all three
statuses and the status distribution/target selectivity is not approved.

No covering `INCLUDE` columns are proposed. Both response items contain many
columns, especially raw measurements; copying the full response into indexes
would materially increase write amplification and storage without approved
index-only-scan evidence.

### 11.3 Redundancy handling

Remove after replacement indexes exist:

```text
ix_measurement_sessions_device_id_started_at
ix_measurement_sessions_device_id_status
ix_raw_measurements_device_id_measured_at
ix_raw_measurements_session_id_measured_at
```

No old explicit index remains after the replacements exist.

`ix_raw_measurements_session_id_measured_at_id_desc` replaces, rather than
duplicates, `ix_raw_measurements_session_id_measured_at`. Its leading
`session_id` equality column and first ordering column support the current
terminal-transition `MAX(measured_at) WHERE session_id = ?` query: PostgreSQL
can traverse directly to the greatest `measured_at` value for the session,
and the trailing `id` does not weaken that prefix. The same leading column
also preserves the child-side lookup prefix for the composite foreign key.
For endpoint reads, equality on `session_id` exposes
`measured_at DESC, id DESC`; the repository still applies `device_id = ?`
for path scoping and correctness.

### 11.4 Upgrade

Within the normal transactional Alembic revision:

1. create all four new indexes;
2. drop all four superseded indexes.

Creating replacements first avoids an intentional coverage gap and allows a
transaction failure to preserve the old schema.

The migration should use explicit descending SQLAlchemy/Alembic column
expressions for the timestamp and `id` suffixes. It must not use raw
interpolated identifiers or runtime ORM imports.

### 11.5 Downgrade

Within the downgrade:

1. recreate all four old indexes;
2. drop the four new indexes;

The downgrade restores the exact pre-feature source inventory before removing
new coverage.

### 11.6 Operational trade-offs

- Four wider indexes add insert/update WAL, page writes, storage, cache
  pressure, vacuum work, and migration build time.
- Removing all four narrower indexes keeps the explicit-index count unchanged
  and avoids two simultaneous session-specific raw-measurement indexes.
- The new session-first raw index adds the `id` tie-break while preserving the
  old index's chronology-query and foreign-key lookup prefixes.
- Ordinary transactional index creation matches current migration practices
  and preserves rollback simplicity, but it requires an approved maintenance
  window for write blocking.
- `CREATE INDEX CONCURRENTLY` is not proposed without an approved
  high-availability requirement and a separately reviewed Alembic autocommit,
  failure-recovery, and downgrade design.
- Representative disposable-data `EXPLAIN (ANALYZE, BUFFERS)` remains a
  release gate for both endpoint query families, the existing
  `MAX(measured_at)` chronology query, and the session/device child-side
  lookup shape. The final index set is conditional on that evidence; Phase A
  made no live performance claim.

## 12. Cursor v1 implementation boundary

### 12.1 Constants and payload

```text
CURSOR_VERSION = 1
MAX_ENCODED_CURSOR_CHARS = 2048
MAX_DECODED_CURSOR_BYTES = 1024
POSTGRES_INTEGER_MAX = 2147483647
RESOURCE_KIND = "sessions" | "measurements"
```

The exact v1 object members are:

```json
{
  "f": "normalized-filter fingerprint",
  "p": ["canonical UTC ordering timestamp", 1],
  "r": "sessions",
  "v": 1
}
```

The object must have exactly the keys `f`, `p`, `r`, and `v`. Unknown or
missing fields are invalid.

### 12.2 Canonical timestamp

All filter and position timestamps use:

```text
YYYY-MM-DDTHH:MM:SS.ffffffZ
```

Rules:

- input must be timezone-aware;
- normalize with `astimezone(UTC)`;
- emit exactly six fractional digits;
- emit literal `Z`;
- cursor decode must enforce the exact lexical form;
- calendar parsing must succeed;
- parse-and-format round trip must reproduce the original string.

### 12.3 Canonical filter documents

Sessions:

```json
{
  "device_id": 1,
  "started_from": null,
  "started_to": null,
  "status": null
}
```

Measurements:

```json
{
  "device_id": 1,
  "measured_from": null,
  "measured_to": null,
  "session_id": null
}
```

Rules:

- keys sort lexicographically;
- omitted filters become explicit JSON `null`;
- timestamps use the canonical UTC form;
- identifiers are ordinary decimal JSON integers;
- `limit` and `cursor` are absent;
- UTF-8 encoding;
- no insignificant whitespace;
- no NaN or Infinity.

The fingerprint is:

```text
unpadded-base64url(SHA-256(canonical-filter-JSON-bytes))
```

The SHA-256 fingerprint has exactly 43 unpadded Base64url ASCII characters.

### 12.4 Canonical payload JSON

Encoder settings:

```text
sort_keys=True
separators=(",", ":")
ensure_ascii=False
allow_nan=False
UTF-8 strict encoding
```

All v1 values are ASCII after timestamp/filter normalization, but UTF-8 is
still the defined byte encoding.

The decoder must reserialize the validated payload canonically and require
byte-for-byte equality with the decoded input. This rejects:

- alternate key order;
- insignificant whitespace;
- alternate escaping;
- noncanonical numeric representations;
- any otherwise equivalent noncanonical JSON.

### 12.5 Base64url and padding

Encoding:

1. serialize canonical payload bytes;
2. use RFC 4648 URL-safe alphabet (`-` and `_`);
3. remove all trailing `=`;
4. return ASCII text.

Decoding:

1. reject a non-ASCII string;
2. reject an empty string;
3. reject input longer than 2,048 characters before decoding;
4. accept only `[A-Za-z0-9_-]`;
5. reject any external `=` padding;
6. reject a length whose remainder modulo four is one;
7. restore the minimum required padding internally;
8. call strict Base64 decoding with validation enabled;
9. reject decoded payloads longer than 1,024 bytes before JSON parsing.

Python's `urlsafe_b64decode` alone is not sufficient because strict
non-alphabet rejection requires `b64decode(..., altchars=b"-_",
validate=True)`.

### 12.6 Strict JSON decode

The decoder must:

- decode UTF-8 strictly;
- use `object_pairs_hook` to reject a repeated key at every object level;
- use `parse_constant` to reject `NaN`, `Infinity`, and `-Infinity`;
- reject malformed JSON;
- require a top-level object;
- reject missing and unknown fields;
- reject noncanonical decoded bytes.

This is required because Python's default JSON decoder accepts repeated names
and retains the last value.

### 12.7 Field and semantic validation order

After structural/canonical validation:

1. `v` must have exact Python/JSON integer type, not Boolean, and equal `1`;
2. `r` must have string type and equal the endpoint's expected resource kind;
3. `f` must have string type and the exact 43-character Base64url digest
   shape;
4. `p` must be a JSON array of exactly two members;
5. `p[0]` must be a valid exact canonical UTC timestamp;
6. `p[1]` must have exact integer type, not Boolean, in
   `1..2_147_483_647`;
7. compute the expected fingerprint from the normalized path/filter document;
8. compare fingerprints with `hmac.compare_digest`;
9. require the cursor timestamp to satisfy the normalized half-open time
   filter, when present;
10. reject any cursor for an equal empty range because no valid returned
    position can exist.

A cursor position is not required to name a currently existing row. The
approved unsigned format is intentionally constructible and is not proof of
server issuance. Database existence lookup would turn the cursor into a
stateful/authorization-like mechanism not approved by the contract.

### 12.8 Resource and filter binding

Reject with safe 422:

- a sessions cursor on the measurements endpoint or the inverse;
- another path `device_id`;
- changed status/session/time filters;
- invalid identifier or timestamp;
- unsupported version;
- fingerprint mismatch;
- malformed/oversized/noncanonical encoding.

Changing only `limit` is valid because it is not fingerprinted.

### 12.9 Safe error mapping

The pure codec should raise one internal `CursorValidationError` with no
parser payload or exception text in its public representation. The API query
dependency translates it to `RequestValidationError`. The installed request
validation handler then returns exactly:

```json
{
  "error": {
    "code": "request_validation_error",
    "message": "Request validation failed.",
    "details": null
  }
}
```

The cursor module must not import FastAPI, SQLAlchemy, `AsyncSession`,
settings, credentials, or authorization state.

### 12.10 Prohibited cursor data

Cursor and filter documents must not contain:

- passwords;
- database URLs or target names;
- device credentials;
- API/access tokens;
- authorization state;
- application settings;
- SQL text;
- exception detail.

## 13. Future architecture and exact responsibilities

The implementation plan provides phased file permissions. The intended final
boundary is:

| File | Future responsibility |
|---|---|
| `backend/app/schemas/_base.py` | add/reuse a positive bounded PostgreSQL integer type |
| `backend/app/schemas/telemetry.py` | strict query models and two concrete list envelopes |
| `backend/app/api/query_validation.py` | raw unknown/repeated scalar query dependency and safe validation adapter |
| `backend/app/services/telemetry_cursor.py` | pure normalized filters, fingerprinting, cursor v1 codec and validation |
| `backend/app/repositories/measurement_session.py` | bounded ordered session list statement |
| `backend/app/repositories/measurement.py` | bounded ordered measurement list statement |
| `backend/app/services/telemetry.py` | device existence, equal-range behavior, limit+1 page construction and next cursor |
| `backend/app/api/dependencies.py` | request-scoped telemetry query service providers |
| `backend/app/api/v1/endpoints/sessions.py` | approved session GET route and response conversion |
| `backend/app/api/v1/endpoints/measurements.py` | approved measurement GET route and response conversion |
| `backend/app/db/models/measurement_session.py` | final reviewed session index metadata |
| `backend/app/db/models/measurement.py` | final reviewed measurement index metadata |
| `backend/alembic/versions/<revision>_add_telemetry_read_indexes.py` | reversible index migration |

The new endpoints fit the existing routers; no router registration file needs
another include.

Read services must never change:

```text
DeviceRuntimeState.measurement_enabled
DeviceRuntimeState.active_session_id
DeviceRuntimeState.measurement_started_at
DeviceRuntimeState.last_seen_at
MeasurementSession.status
MeasurementSession.ended_at
MeasurementSession.sample_count
RawMeasurement fields
```

## 14. Test inventory and required additions

### 14.1 Existing relevant suites

| Area | Current files |
|---|---|
| schema | `backend/tests/test_api_schemas.py` |
| OpenAPI | `backend/tests/test_api_openapi.py` |
| API routes | `backend/tests/test_api_routes.py` |
| errors | `backend/tests/test_api_errors.py` |
| dependencies/architecture | `backend/tests/test_api_dependencies.py`, `backend/tests/test_api_architecture.py` |
| query services | `backend/tests/test_query_services.py` |
| repositories | `backend/tests/test_repositories.py` |
| write services | `backend/tests/test_services.py` |
| ORM/index metadata | `backend/tests/test_models.py` |
| Alembic/offline DDL | `backend/tests/test_migrations.py` |
| integration guards/reset | `backend/tests/test_api_integration_guard.py`, `backend/tests/test_persistence_guard.py`, `backend/tests/test_integration_database_reset.py` |
| guarded PostgreSQL HTTP | `backend/tests/test_api_integration.py` |
| guarded PostgreSQL persistence | `backend/tests/test_persistence_integration.py` |

The live harness validates a local disposable target, checks schema/head,
resets every ORM table with metadata-driven
`TRUNCATE ... RESTART IDENTITY`, excludes `CASCADE`, and resets again after
the suite.

### 14.2 New/future test files

Proposed focused files:

- `backend/tests/test_telemetry_cursor.py`;
- `backend/tests/test_telemetry_query_validation.py`;
- `backend/tests/test_telemetry_services.py`.

Existing suites should be extended for repository SQL, HTTP routes, OpenAPI,
models/migration, architecture, and guarded PostgreSQL behavior.

The existing API integration suite and target guard should be extended rather
than inventing a third live-target policy. Although
`AIRMONITOR_READ_API_TEST_DATABASE_URL` appears in environment cleanup and
existence inventories, no current suite, validator, or approved database-name
prefix uses it.

## 15. Contradictions, ambiguities, and decisions

### 15.1 Direct contract/source contradictions

None found.

The current source agrees with the approved contract on:

- all public item field names;
- status values;
- aware/UTC timestamp conventions;
- positive PostgreSQL integer bounds;
- ErrorResponse terminology;
- no authentication/authorization;
- trusted-network deployment only;
- nine-operation OpenAPI baseline;
- read-only service/repository direction.

### 15.2 FastAPI strictness gap

The approved contract requires behavior that FastAPI does not provide by
default. This is an implementation gap, not a contract contradiction. The
raw multidict dependency in Section 8 is mandatory.

### 15.3 Canonical cursor ambiguity

The approved contract defines canonical JSON output but does not explicitly
say whether noncanonical equivalent input is accepted. Cursor v1 should reject
it by canonical byte comparison. Accepting alternate forms would create
multiple wire representations and weaken deterministic tests.

### 15.4 Duplicate JSON members

The approved specification lists malformed/invalid payloads but does not name
duplicate members. The user-approved Phase A requirements explicitly require
duplicate-key rejection. Python's last-value behavior makes that rejection a
necessary strict-parser rule.

### 15.5 Historical three-index suggestion

The Sprint 8 full audit suggested three future tie-break indexes before the
final read contract existed. The approved status filter requires a second
session index. External Phase A review then rejected a device/session raw
index coexisting with the old session/time index because that would create
two session-specific indexes. The reviewed decision is four one-for-one
replacement indexes and removal of all four old explicit indexes.

### 15.6 Equal ranges and cursors

An equal range without a cursor is valid after device existence and returns an
empty page. A cursor bound to an equal range is semantically invalid because
no previous item can exist in that result set. It should return safe 422
before device lookup.

### 15.7 Live target naming

`AIRMONITOR_READ_API_TEST_DATABASE_URL` has no implemented guard or prefix
contract. The implementation plan uses the proven
`AIRMONITOR_API_TEST_DATABASE_URL` harness for HTTP read tests. A separate
read target would require its own explicitly approved guard phase.

## 16. Risks and blockers

### 16.1 Phase A blockers

None. Both planning documents can be completed without database access.

### 16.2 Implementation/release blockers

- The reviewed migration must be approved before implementation reaches the
  live verification gate.
- A representative disposable dataset and read-latency objective are not yet
  approved.
- Live plan evidence must cover unfiltered/selective variants, first/later
  pages, and limits 100 and 500 with
  `EXPLAIN (ANALYZE, BUFFERS)`.
- Standard index creation requires an approved write-maintenance window, or a
  separate concurrent-index design.
- The session-first replacement remains conditional on representative live
  plans proving the session-filtered endpoint query with both predicates, the
  existing chronology aggregate, and the child-side foreign-key lookup shape.
- Public internet deployment remains prohibited because authentication,
  authorization, and rate limiting are absent.

### 16.3 Correctness risks to test explicitly

- Boolean values passing Python `int` checks unless exact types are enforced.
- timezone offsets producing multiple equivalent cursor representations;
- Base64 decoders discarding invalid characters unless strict validation is
  enabled;
- JSON duplicate keys and non-standard numeric constants;
- route dependencies catching unknown parameters but not repeats;
- cursor fingerprinting accidentally including `limit` or `cursor`;
- computing next cursor from the extra row instead of the last returned row;
- equal-range shortcuts returning 200 before checking device existence;
- session filters exposing another device's session existence;
- reads accidentally invoking write methods or mutating identity-map state;
- accidentally removing `device_id = ?` from session-filtered endpoint SQL
  because the chosen index begins with `session_id`;
- replacing the old session/time index without proving that
  `ix_raw_measurements_session_id_measured_at_id_desc` preserves terminal
  chronology and child-side foreign-key lookup performance.

## 17. Pre-edit verification record

All pytest commands included `-B -p no:cacheprovider`.

| Check | Result |
|---|---|
| backend `.env` existence-only check | absent |
| live database target/opt-in variables | removed by name |
| full offline backend suite | `550 passed, 2 skipped in 7.15s` |
| OpenAPI tests | `7 passed in 1.45s` |
| schema/query-service/repository/service tests | `161 passed in 1.15s` |
| integration guard/reset tests | `67 passed in 1.29s` |
| `pip check` | no broken requirements |
| guarded OpenAPI | 3.1.0; nine operations; unique IDs |
| guarded connection/schema calls | zero |
| Alembic heads | one head: `a4f9c2e7d1b6` |
| initial `git diff --check` | exit 0, no output |
| initial `git diff --stat` | empty |
| initial Git status | `## HEAD (no branch)` |
| PostgreSQL access | none |

Exact commands are recorded in the implementation plan.

## 18. Authoritative references

Official documentation supporting non-obvious conclusions:

- [FastAPI query parameter models and forbidding extras](https://fastapi.tiangolo.com/tutorial/query-param-models/#forbid-extra-query-parameters)
- [FastAPI dependencies in path operation decorators](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/)
- [Starlette request query parameters as an immutable multidict](https://www.starlette.io/requests/#query-parameters)
- [PostgreSQL multicolumn B-tree leading-column behavior](https://www.postgresql.org/docs/current/indexes-multicolumn.html)
- [PostgreSQL indexes and ORDER BY/LIMIT](https://www.postgresql.org/docs/current/indexes-ordering.html)
- [PostgreSQL foreign-key and constraint behavior](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)
- [SQLAlchemy index definitions and ordered expressions](https://docs.sqlalchemy.org/en/20/core/constraints.html#sqlalchemy.schema.Index)
- [Alembic `create_index` operation](https://alembic.sqlalchemy.org/en/1.18.5/ops.html#alembic.operations.Operations.create_index)
- [Python strict Base64 decoding and URL-safe alphabet](https://docs.python.org/3/library/base64.html)
- [Python canonical JSON controls and strict decode hooks](https://docs.python.org/3/library/json.html)

## 19. Audit verdict

The approved two-operation contract is source-compatible with the stabilized
backend, but it is not implementable to the required strictness through
FastAPI defaults or current indexes alone.

Proceed only after manual review of:

1. the raw query-validation dependency;
2. the cursor v1 strict-parser boundary;
3. the create-four/remove-four replacement index migration;
4. the phased test-first implementation plan;
5. the future disposable-data plan and operational index-build strategy.

Phase A stops after the two required documents and final offline/scope checks.
