# Telemetry Read API Final Verification

Date: 2026-08-03

Checkout: detached `695c881b6a3602072eb694488d9fa8594165db00`

Verdict: the Telemetry Read API application, migration, guarded PostgreSQL
integration, and representative query plans are verified. All available
offline and live gates pass. No live-verification blocker remains.

## Implemented endpoints and route contracts

The current API exposes these read-only collection operations:

| Operation ID | Method and path | Supported filters |
| --- | --- | --- |
| `list_device_sessions` | `GET /api/v1/devices/{device_id}/sessions` | `status`, `started_from`, `started_to`, `limit`, `cursor` |
| `list_device_measurements` | `GET /api/v1/devices/{device_id}/measurements` | `session_id`, `measured_from`, `measured_to`, `limit`, `cursor` |

Identifiers are positive PostgreSQL integers. Timestamps are aware and
normalized to UTC. Time ranges are half-open: the lower bound is inclusive and
the upper bound is exclusive. Equal bounds produce an empty page only after
device existence is established. `limit` defaults to 100 and is constrained to
1 through 500. Unknown or repeated scalar query parameters are rejected.

Successful responses retain the exact `{items, next_cursor}` envelopes and the
established public item fields. An unknown device returns safe 404, invalid
input or cursor returns safe 422, and internal failures retain the sanitized 500
contract. Existing write routes and `GET /sessions/active` are unchanged.

## Cursor, ordering, and pagination

Sessions use stable `started_at DESC, id DESC` order. Measurements use stable
`measured_at DESC, id DESC` order. The exclusive cursor predicate is the grouped
timestamp-less-than or timestamp-equal-and-ID-less-than condition.

Cursors remain opaque, URL-safe, resource-bound, and bound to normalized
filters. Repositories request the public limit plus one row, return at most the
public limit, and emit `next_cursor` only when the extra row exists. The cursor
is created from the final returned item. No OFFSET pagination is used, and
neither endpoint can load an unbounded telemetry history.

## Device isolation and session-filter non-disclosure

Both repository statements retain a mandatory `device_id` predicate outside
the grouped cursor predicate. Measurement filtering also retains the optional
`session_id` predicate. The service does not perform a separate session
ownership lookup. A nonexistent session and a session owned by another device
therefore produce the same empty page without disclosing existence or ownership.
No new N+1 behavior or transaction control was introduced.

## Migration and index inventory

The current Alembic head is `a75caa2b44f5`, with
`down_revision = "a4f9c2e7d1b6"`. The revision contains only index operations.

Upgrade creates all four replacement indexes before dropping any superseded
index:

| Replacement index | Ordered key |
| --- | --- |
| `ix_measurement_sessions_device_id_started_at_id_desc` | `device_id ASC, started_at DESC, id DESC` |
| `ix_measurement_sessions_device_id_status_started_at_id_desc` | `device_id ASC, status ASC, started_at DESC, id DESC` |
| `ix_raw_measurements_device_id_measured_at_id_desc` | `device_id ASC, measured_at DESC, id DESC` |
| `ix_raw_measurements_session_id_measured_at_id_desc` | `session_id ASC, measured_at DESC, id DESC` |

It then drops exactly:

- `ix_measurement_sessions_device_id_started_at`;
- `ix_measurement_sessions_device_id_status`;
- `ix_raw_measurements_device_id_measured_at`;
- `ix_raw_measurements_session_id_measured_at`.

Downgrade recreates all four superseded indexes before dropping the four
replacements. PostgreSQL-dialect compilation and offline Alembic SQL preserve
the explicit descending expressions and exact operation order. The checkout
enforces ORM/Alembic performance-index parity, so the two model metadata
inventories use the same replacement definitions. The primary-source rationale
is recorded in
[`telemetry-read-api-index-research.md`](telemetry-read-api-index-research.md).

## Disposable PostgreSQL environment

Live verification used the official PostgreSQL 18 image, server version 18.4,
on `127.0.0.1:50460` with database
`airmonitor_api_test_f48308e18c87`. The container name was
`airmonitor-api-test-f48308e18c87`.

The target was created during this verification, bound to loopback only, used a
cryptographically random password generated in process, and stored the database
on tmpfs without a named or persistent volume. The username, password, and full
connection URL were never printed or written to the repository. The existing
protected `airmonitor` application database was not connected to.

Rollback-heavy 500,000-row evidence generation exhausted the first 1 GiB tmpfs
instance after its valid plans had been collected. The disposable instance was
removed and recreated under the same sanitized target identity with a 2 GiB
tmpfs; it was migrated from blank to head and its four catalog definitions were
reverified before the final evidence run. No persistent or user data existed.

After all live work, the healthy container was removed with its nonpersistent
storage. No container whose name begins with `airmonitor-api-test-` remained.

## Live migration cycle and catalog evidence

On the blank database, `alembic current` reported no applied revision. Upgrade
to `a4f9c2e7d1b6` succeeded and the live catalog contained exactly the four
superseded performance indexes:

| Previous-revision index | Live ordered key |
| --- | --- |
| `ix_measurement_sessions_device_id_started_at` | `device_id, started_at` |
| `ix_measurement_sessions_device_id_status` | `device_id, status` |
| `ix_raw_measurements_device_id_measured_at` | `device_id, measured_at` |
| `ix_raw_measurements_session_id_measured_at` | `session_id, measured_at` |

Upgrade to `a75caa2b44f5` succeeded. `pg_indexes` definitions contained exactly
the four replacement keys listed above, including every explicit `DESC`, and
none of the four superseded names. Downgrade to `a4f9c2e7d1b6` restored the old
set and removed the replacement set. Final upgrade to `a75caa2b44f5` restored
the replacement set and left the database at the single head.

These are actual PostgreSQL catalog results, not conclusions inferred from
offline SQL.

## PostgreSQL integration results

The API suite ran at the final head with its existing guarded preflight and
metadata-derived reset behavior:

- 9 collected, 9 passed, 0 skipped;
- preflight confirmed the exact schema and `a75caa2b44f5`;
- cleanup left all four application tables empty.

The persistence suite initially rejected the shared
`airmonitor_api_test_*` target because its guard accepted only the historical
`airmonitor_persistence_test_*` prefix. A focused RED test reproduced that
policy mismatch. The minimum correction lets the persistence guard accept both
dedicated disposable prefixes while retaining its exact driver, loopback host,
forbidden target-override, and sanitized-error rules. The guard/reset set then
passed 68 tests.

The final persistence result was:

- 13 collected, 13 passed, 0 skipped;
- preflight confirmed the exact schema and `a75caa2b44f5`;
- cleanup left all four application tables empty.

The final API suite was also rerun after the guard correction and passed all
nine tests. Both suites used the same disposable database sequentially. No
SQLite substitute or guard bypass was used.

## EXPLAIN (ANALYZE, BUFFERS) evidence

The final normal-planner run used 10,000 sessions and 105,000 measurements,
including 5,010 measurements in the target session. `ANALYZE` was run before
the plans. All data and evidence queries were enclosed in one explicit
transaction, which was rolled back; the post-rollback counts were zero.

Rows examined below are scan-node actual rows plus rows removed by filter or
index recheck. Times are milliseconds. All values are actual PostgreSQL 18.4
normal-planner results.

| Query shape | Scan and selected index | Sort | Examined / returned | Planning / execution | Shared hit / read |
| --- | --- | --- | ---: | ---: | ---: |
| Sessions by device | Index Scan; `ix_measurement_sessions_device_id_started_at_id_desc` | No | 25 / 25 | 0.243 / 0.025 | 3 / 0 |
| Sessions by device and status | Index Scan; `ix_measurement_sessions_device_id_status_started_at_id_desc` | No | 25 / 25 | 0.134 / 0.040 | 3 / 0 |
| Sessions with cursor | Index Scan; `ix_measurement_sessions_device_id_started_at_id_desc` | No | 65 / 25 | 0.118 / 0.042 | 3 / 0 |
| Measurements by device | Index Scan; `ix_raw_measurements_device_id_measured_at_id_desc` | No | 101 / 101 | 0.231 / 0.069 | 104 / 0 |
| Measurements by device and session | Index Scan; `ix_raw_measurements_session_id_measured_at_id_desc` | No | 25 / 25 | 0.099 / 0.044 | 5 / 0 |
| Measurements with cursor | Index Scan; `ix_raw_measurements_device_id_measured_at_id_desc` | No | 496 / 101 | 0.114 / 0.208 | 459 / 0 |

The session-filtered measurement query retained both `device_id` and
`session_id`. The cursor queries retained grouped `AND (less-than OR
equal-and-ID-less-than)` precedence. No query required an explicit Sort when
the intended ordered index was selected.

With only 50 target-session rows, the normal planner initially chose a Bitmap
Index/Heap Scan on the correct session-first index plus a small top-N Sort.
Increasing only that representative session history to 5,010 rows led the
normal planner to choose the order-preserving Index Scan shown above. No
`enable_seqscan`, `enable_bitmapscan`, or other forced planner evidence was used.
These synthetic timings demonstrate structural compatibility, not a production
benchmark.

## Verification results

Baseline before the macro implementation:

- offline backend: 831 passed, 2 skipped;
- OpenAPI: 3.1.0, 11 operations, 10 under `/api/v1`, 1 under `/health`, and
  11 unique operation IDs;
- Alembic head: `a4f9c2e7d1b6`.

Current verified results:

| Gate | Result |
| --- | --- |
| Migration and model tests | 48 passed before live continuation; included again in the final offline suite |
| Integration guard and reset tests after shared-target correction | 68 passed |
| API PostgreSQL integration | 9 passed, 0 skipped |
| Persistence PostgreSQL integration | 13 passed, 0 skipped |
| Full offline backend suite after correction | 840 passed, 2 skipped |
| OpenAPI inventory | 3.1.0; 11 operations; 10 `/api/v1`; 1 `/health`; 11 unique IDs; zero connection/schema calls |
| Alembic graph | one base and one head, `a75caa2b44f5` |
| Offline Alembic upgrade/downgrade SQL | passed; exact ordered index transition |
| Live migration and catalog cycle | passed |
| Six normal-planner EXPLAIN shapes | passed; intended index selected; no Sort |
| `pip check` | no broken requirements |
| `git diff --check` | passed |

The final offline suite adds nine passing cases over the original 831-case
baseline and introduces no unexpected skip. The two live integration modules
remain intentionally skipped when their dedicated activation variables are
absent.

## Architecture, security, and performance review

The final review found no remaining critical or required issue across
correctness, readability, architecture, security, performance, migration
reversibility, operational safety, documentation accuracy, or repository
cleanliness.

- Only ORM index metadata changed in production application files; public
  route, service, repository, schema, and cursor behavior did not change.
- The additional correction is isolated to persistence test-target validation
  and its focused offline test.
- Routes contain no repository or SQLAlchemy imports and no transaction logic.
- Query services contain no begin, commit, rollback, or flush operation.
- Repository SQL retains mandatory device isolation, grouped exclusive cursor
  predicates, descending order, and bounded `limit + 1` reads.
- No OFFSET, count query, speculative cache, session-ownership lookup, or
  unbounded telemetry select was added.
- Error and database guards do not expose connection URLs, credentials, SQL,
  internal exceptions, ownership information, or local target details.
- Upgrade and downgrade preserve access-path coverage by creating replacements
  before dropping the indexes they supersede.

## Known limitations and security assumption

The API retains the documented trusted/private-network deployment assumption;
authentication and authorization are outside this macro phase. EXPLAIN timings
come from synthetic data on a disposable local PostgreSQL 18.4 server and are
not a production latency benchmark. The plans do prove that each approved index
supports its target filter/order shape without an incompatible Sort under the
representative normal planner. The historical implementation plan's additional
chronology `MAX(measured_at)` and child-side foreign-key lookup plan checks were
outside the six endpoint query shapes required by the completion macro and are
not claimed as live plan evidence.

No Git index write, stage, commit, push, reset, clean, stash, branch operation,
or Git configuration change was performed.
