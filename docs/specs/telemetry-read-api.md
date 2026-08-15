# Telemetry Read API — Approved MVP Design Contract

**Status:** implemented; offline and guarded disposable PostgreSQL live
verification complete

**Implemented today:** yes

**Current OpenAPI baseline:** 3.1.0, eleven operations with eleven unique
operation IDs

This specification remains the public contract for the first AirMonitor v2
telemetry read MVP. The two approved routes and their application layers are
implemented. The ordered index migration and guarded PostgreSQL integration
coverage are verified against PostgreSQL 18.4, including the reversible live
migration cycle, exact catalog inventory, both integration suites, and all six
representative `EXPLAIN (ANALYZE, BUFFERS)` shapes.

## Approved endpoints

The MVP contains exactly two new operations:

| Method | Path | Proposed operation ID |
|---|---|---|
| `GET` | `/api/v1/devices/{device_id}/sessions` | `list_device_sessions` |
| `GET` | `/api/v1/devices/{device_id}/measurements` | `list_device_measurements` |

Implementation increased the OpenAPI inventory from nine operations to
eleven. All existing paths, operation IDs, request and response schemas, and
successful status codes remain unchanged.

## Shared request rules

### Integer boundaries

`device_id` and `session_id` map to PostgreSQL `INTEGER`. They must be:

- greater than zero; and
- no greater than `2,147,483,647`.

The implementation must reuse the existing PostgreSQL integer boundary
terminology and validators instead of introducing an unbounded Python integer
at the API boundary.

### Timestamp normalization and ranges

All query timestamps must be timezone-aware. The application must normalize
them to UTC in the same manner as current service timestamps.

Both endpoints use half-open ranges:

```text
[from, to)
```

The lower bound is inclusive and the upper bound is exclusive.

The equality policy is:

- `from < to`: valid range;
- `from == to`: valid empty range after device existence is established,
  returning `200` with `items: []` and `next_cursor: null`;
- `from > to`: invalid, returning a safe `422`.

Accepting equality is consistent with the current chronology convention,
which rejects only timestamps that are strictly earlier than an established
boundary. For list filters, the mathematically exact half-open interval with
equal bounds is empty. A missing path device still returns `404`; equal bounds
do not bypass the device-existence contract.

### Query parameter strictness

Only the query parameters listed for each endpoint are accepted. Unknown
query parameters return safe `422` rather than being ignored.

Every supported parameter is a singleton. Repeating `status`, a time bound,
`session_id`, `limit`, or `cursor` in one request returns safe `422`; the
implementation must not silently select the first or last occurrence.

### Device existence

With otherwise valid request input, a missing `device_id` returns `404` using
the existing `ErrorResponse` contract. An existing device with no matching
rows returns `200` with an empty page.

FastAPI request validation occurs before the endpoint body. An invalid path,
filter, timestamp, limit, or cursor therefore returns `422` without requiring
a device lookup.

## Sessions endpoint

```http
GET /api/v1/devices/{device_id}/sessions
```

### Filters

| Parameter | Type | Meaning |
|---|---|---|
| `status` | `active`, `completed`, or `cancelled` | Include only sessions with the exact current status value |
| `started_from` | timezone-aware datetime | Include `started_at >= started_from` |
| `started_to` | timezone-aware datetime | Include `started_at < started_to` |
| `limit` | integer | Page size; default 100, minimum 1, maximum 500 |
| `cursor` | opaque URL-safe string | Continue after the previous page |

Omitted filters do not constrain their corresponding columns.

### Ordering

The stable order is:

```text
started_at DESC, id DESC
```

The ordering tuple is `(started_at, id)`. Both columns participate in the
cursor so equal timestamps remain deterministic.

For an exclusive cursor position `(cursor_started_at, cursor_id)`, the next
page predicate is logically:

```text
started_at < cursor_started_at
OR (started_at = cursor_started_at AND id < cursor_id)
```

The endpoint must not use offset pagination.

### Session list item

Each `items` element uses exactly the existing public `SessionResponse` field
names:

```json
{
  "id": 1,
  "device_id": 1,
  "status": "completed",
  "started_at": "2026-07-28T10:00:00Z",
  "ended_at": "2026-07-28T10:30:00Z",
  "latitude": 0.0,
  "longitude": 0.0,
  "sample_count": 0,
  "created_at": "2026-07-28T10:00:00Z"
}
```

The values above illustrate types only. The read feature must not add dormant
ORM summary fields such as averages, AQI fields, `updated_at`, relationships,
or SQLAlchemy state to the session list item.

## Measurements endpoint

```http
GET /api/v1/devices/{device_id}/measurements
```

### Filters

| Parameter | Type | Meaning |
|---|---|---|
| `session_id` | bounded positive integer | Include only rows for this session and path device |
| `measured_from` | timezone-aware datetime | Include `measured_at >= measured_from` |
| `measured_to` | timezone-aware datetime | Include `measured_at < measured_to` |
| `limit` | integer | Page size; default 100, minimum 1, maximum 500 |
| `cursor` | opaque URL-safe string | Continue after the previous page |

A syntactically valid `session_id` that has no matching measurement for the
path device produces an empty page. It must not expose whether that session
belongs to another device.

### Ordering

The stable order is:

```text
measured_at DESC, id DESC
```

The ordering tuple is `(measured_at, id)`.

For an exclusive cursor position `(cursor_measured_at, cursor_id)`, the next
page predicate is logically:

```text
measured_at < cursor_measured_at
OR (measured_at = cursor_measured_at AND id < cursor_id)
```

The endpoint must not use offset pagination.

### Raw measurement list item

Each `items` element uses exactly the existing public `MeasurementResponse`
field names:

```json
{
  "id": 1,
  "device_id": 1,
  "session_id": 1,
  "source_message_id": null,
  "measured_at": "2026-07-28T10:00:00Z",
  "received_at": "2026-07-28T10:00:01Z",
  "temperature": null,
  "humidity": null,
  "pm1": null,
  "pm25": null,
  "pm10": null,
  "pc0_3": null,
  "pc0_5": null,
  "pc1_0": null,
  "pc2_5": null,
  "pc5_0": null,
  "pc10": null,
  "latitude": null,
  "longitude": null,
  "is_valid": true,
  "validation_note": null,
  "created_at": "2026-07-28T10:00:01Z"
}
```

The list item must not expose ORM relationships, identity-map state, or other
internal SQLAlchemy attributes.

## Response envelope

Both operations return `200` with:

```json
{
  "items": [],
  "next_cursor": null
}
```

`items` contains the endpoint-specific public list items. `next_cursor` is
either `null` when no later row exists or an opaque string for the next page.
The MVP does not return a total count, page number, offset, or total-page
count.

## Keyset pagination contract

### Page construction

The implementation must:

1. apply the normalized path and endpoint filters;
2. apply the exclusive cursor predicate when a cursor is supplied;
3. order by the endpoint's timestamp and `id`, both descending;
4. fetch at most `limit + 1` rows;
5. return at most `limit` items;
6. set `next_cursor` only when the extra row proves another page exists;
7. build the next cursor from the last item actually returned, not from the
   extra row.

Under stable stored data, following valid cursors must neither skip nor
duplicate rows.

### Concurrent-write consistency

Pagination does not provide a cross-request database snapshot. The no-skip and
no-duplicate guarantee applies only while the filtered stored data and both
ordering columns remain stable.

During concurrent writes:

- a new row ordered before a cursor can be absent from the remainder of an
  in-progress traversal; clients restart from the first page to discover it;
- a newly inserted row ordered after the cursor may appear on a later page;
- non-ordering item fields, such as session status or `sample_count`, may
  reflect a newer committed value on a later request;
- changing an ordering timestamp outside the approved service paths voids the
  stable-data guarantee.

The implementation does not acquire write locks or create a long-running
snapshot merely to paginate.

### Cursor wire properties

The cursor must be:

- URL-safe;
- opaque to clients;
- versioned;
- exclusive;
- resource-specific;
- bound to the path device and normalized filters;
- free of credentials, keys, tokens, database information, or other secrets.

The first cursor format version must logically contain:

```text
version
resource kind
last ordering timestamp
last ordering id
normalized-filter fingerprint
```

Version 1 uses:

```text
unpadded-base64url(UTF-8(canonical JSON payload))
```

The canonical payload has these short internal members:

```json
{
  "f": "normalized-filter fingerprint",
  "p": ["canonical UTC ordering timestamp", 1],
  "r": "sessions",
  "v": 1
}
```

`r` is either `sessions` or `measurements`. `p` is the matching endpoint's
last ordering tuple. Canonical JSON uses lexicographically ordered object
keys, no insignificant whitespace, UTF-8, ordinary decimal integers, and UTC
timestamps with exactly six fractional digits followed by `Z`.

The encoded query value must not exceed 2,048 ASCII characters. Its decoded
JSON payload must not exceed 1,024 bytes. An oversized encoded value returns
safe `422` before base64 or JSON decoding; an oversized decoded payload
returns safe `422` before JSON parsing or fingerprint validation.

The external client contract remains the opaque cursor string. Clients must
not decode, construct, or depend on the version-1 member names or layout.

### Filter normalization and binding

Before fingerprinting, the implementation must create a deterministic filter
document.

For sessions it contains:

```text
device_id
status or null
started_from normalized to UTC or null
started_to normalized to UTC or null
```

For measurements it contains:

```text
device_id
session_id or null
measured_from normalized to UTC or null
measured_to normalized to UTC or null
```

Timestamps in the fingerprint input must use one canonical UTC
representation with exactly six fractional digits followed by `Z`. The
normalized documents are canonical JSON objects with lexicographically
ordered keys, explicit nulls, no insignificant whitespace, and UTF-8
encoding.

Version 1 uses the unpadded base64url encoding of the SHA-256 digest of that
canonical document as `f`.

`limit` and `cursor` are not filters and are excluded from the fingerprint.
Clients may therefore request a different valid page size while continuing a
cursor, without changing the filtered result set.

A cursor for another endpoint, another `device_id`, or different normalized
filters is semantically invalid and returns safe `422`.

Version 1 opacity is a client-usage rule, not confidentiality or proof that
the server issued the value. Its unkeyed fingerprint binds filters but does
not prevent a client from constructing another otherwise valid position.
The server must therefore treat every decoded value as untrusted and validate
all fields and bounds. This does not expand the filtered device result set and
is not an authorization boundary. If tamper evidence is later required, it
must use a server-held integrity key and a new cursor version with an explicit
key-rotation and expiry policy.

### Cursor validation

The following return safe `422` using the existing request-validation error
terminology:

- malformed URL-safe encoding;
- encoded or decoded size above the version-1 limits;
- invalid payload shape or types;
- unsupported cursor version;
- wrong resource kind;
- an ordering timestamp that is missing or invalid;
- an ordering ID outside the positive PostgreSQL `INTEGER` range;
- a filter fingerprint mismatch;
- any other semantically invalid cursor.

Cursor decoding must never expose parser exceptions, payload internals, SQL,
or server state in the response. Cursor data is not an authentication or
authorization mechanism. Signing or encrypting a cursor would not replace
access control.

## Error contract

Both endpoints use the current `ErrorResponse` shape:

```json
{
  "error": {
    "code": "request_validation_error",
    "message": "Request validation failed.",
    "details": null
  }
}
```

| Status | Meaning |
|---:|---|
| `200` | Successful page, including an empty page |
| `404` | Path device does not exist |
| `422` | Invalid path, status, session ID, time filter, range, limit, or cursor |
| `500` | Safe generic unexpected server error |

The implementation must reuse existing error terminology:

- `device_not_found` for a missing path device;
- `request_validation_error` for invalid request/query/cursor input;
- `internal_server_error` for an unexpected failure.

No new domain error code is approved by this specification.

## Authorization and deployment policy

The current v2 API has no authentication or authorization. The read MVP does
not add either control and inherits the current trusted-network deployment
model.

- Public internet exposure is not approved.
- A dedicated authentication, authorization, and rate-limiting phase is
  required before public deployment.
- Cursor content does not establish identity, permission, or ownership.
- A future authorization layer must check the path device independently of
  any cursor payload.

## Read-only data policy

The implementation must be read-only. Listing sessions or measurements must
not mutate:

- application runtime state;
- devices;
- measurement sessions;
- raw measurements;
- `sample_count`;
- `last_seen_at`.

Query services must not commit, flush, increment counters, update timestamps,
or acquire write locks merely to produce a page.

## Index and performance preconditions

Current source defines these relevant two-column indexes:

- `measurement_sessions(device_id, started_at)`;
- `measurement_sessions(device_id, status)`;
- `raw_measurements(device_id, measured_at)`;
- `raw_measurements(session_id, measured_at)`.

None includes the `id` tie-break required by the approved stable ordering.
This specification therefore does **not** claim that existing indexes are
sufficient.

Before implementation, the future phase must inspect actual PostgreSQL plans
for:

- sessions by device with and without `status`, ordered by
  `(started_at, id)`;
- measurements by device with and without `session_id`, ordered by
  `(measured_at, id)`;
- the same queries with half-open time bounds and exclusive cursor
  predicates.

The evidence package must:

- state the disposable dataset's session and measurement cardinality,
  per-device distribution, timestamp distribution, and status distribution;
- justify why that dataset represents the approved target deployment;
- exercise unfiltered and selective variants, first and later pages, and
  limits 100 and 500;
- capture `EXPLAIN (ANALYZE, BUFFERS)` for every required query shape;
- show that plans avoid a sequential scan or full result-set sort whose work
  grows with all matching history merely to return one bounded page.

The implementation phase must either:

1. demonstrate suitable existing index coverage on representative,
   disposable data; or
2. add a reviewed Alembic migration for the required composite indexes.

Candidate index shapes may include the path/filter columns followed by the
ordering tuple, but their exact set, direction, migration strategy, write
cost, and query plans require review. No index is approved as already present
or sufficient by this document.

If no deployment cardinality/distribution profile and read-latency objective
have been approved, a small-database plan is not sufficient evidence. The
implementation must then add a reviewed composite-index migration or stop for
an explicit performance decision.

## Explicit non-goals

The MVP does not include:

- additional endpoints;
- aggregation;
- AQI or NowCast;
- forecasts;
- map clustering;
- CSV export;
- retention or deletion behavior;
- offset pagination;
- authentication, authorization, or rate limiting;
- changes to write-path behavior.

## Future implementation acceptance checks

An implementation is conformant only if it proves:

- the existing nine-operation contract is unchanged;
- exactly the two approved operations are added with the proposed IDs;
- response item fields match the current public schemas;
- path/filter integers retain PostgreSQL boundaries;
- all timestamps are aware and normalized consistently;
- equal time bounds return the approved empty page;
- reversed bounds and invalid cursors return safe `422`;
- cursors cannot be reused across endpoints, devices, or changed filters;
- duplicate ordering timestamps paginate without skips or duplicates under
  stable stored data;
- reads do not mutate any protected state;
- index coverage is demonstrated or delivered through a reviewed migration;
- offline and disposable PostgreSQL tests cover the contract.

