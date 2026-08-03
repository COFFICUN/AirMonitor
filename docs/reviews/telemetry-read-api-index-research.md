# Telemetry Read API Index Research

Date: 2026-08-03

Status: source research and current-checkout convention audit complete; no live
PostgreSQL verification is claimed by this document.

## Scope and version baseline

This research covers the approved Telemetry Read API replacement indexes,
their Alembic and SQLAlchemy representation, PostgreSQL B-tree behavior, and
the evidence required from migration tests and live query plans.

The current checkout pins:

- FastAPI 0.139.1;
- SQLAlchemy 2.0.51;
- Alembic 1.18.5;
- asyncpg 0.31.0;
- pytest 8.4.2.

These versions come from
[`backend/requirements.txt`](../../backend/requirements.txt) and
[`backend/requirements-dev.txt`](../../backend/requirements-dev.txt).
The checkout does not pin a PostgreSQL server version. Any live verification
report must therefore record the sanitized server version actually tested and
interpret plans against that version's documentation. The PostgreSQL links in
this note target the current official manual rather than implying a locally
verified server version.

## Approved index inventory

The replacement inventory is:

| Index | Ordered key |
| --- | --- |
| `ix_measurement_sessions_device_id_started_at_id_desc` | `device_id ASC, started_at DESC, id DESC` |
| `ix_measurement_sessions_device_id_status_started_at_id_desc` | `device_id ASC, status ASC, started_at DESC, id DESC` |
| `ix_raw_measurements_device_id_measured_at_id_desc` | `device_id ASC, measured_at DESC, id DESC` |
| `ix_raw_measurements_session_id_measured_at_id_desc` | `session_id ASC, measured_at DESC, id DESC` |

PostgreSQL B-tree indexes are the index type that can directly return sorted
output. A forward or backward scan can reverse all columns together, while an
explicit mixed-direction definition is needed when adjacent keys have
different requested directions. Matching an `ORDER BY` is especially useful
with `LIMIT`, because PostgreSQL can retrieve the first rows without sorting
the complete qualifying set. [PostgreSQL: Indexes and
`ORDER BY`](https://www.postgresql.org/docs/current/indexes-ordering.html)

For multicolumn B-trees, equality constraints on leading columns, plus an
inequality constraint on the first non-equality column, most directly limit
the scanned index range. Constraints on later keys can still be checked, but
do not necessarily reduce the scanned portion. [PostgreSQL: Multicolumn
Indexes](https://www.postgresql.org/docs/current/indexes-multicolumn.html)

Consequently, the first three indexes structurally align with their device or
device/status equality prefixes and descending timestamp/identifier ordering.
The session-first raw-measurement index structurally aligns with session
equality and descending measurement ordering. These are structural
conclusions, not substitutes for representative live plans.

## Alembic and SQLAlchemy expression representation

Alembic 1.18.5 defines `Operations.create_index()` columns as accepting string
column names, `TextClause`, or `ColumnElement` expressions, and documents
expression indexes through SQLAlchemy expressions. [Alembic 1.18.5:
`Operations.create_index`](https://alembic.sqlalchemy.org/en/latest/ops.html#alembic.operations.Operations.create_index)

SQLAlchemy 2.0.51 documents expression-based `Index` definitions and gives
`table.c.somecol.desc()` as the descending-index form. [SQLAlchemy 2.0:
Functional Indexes](https://docs.sqlalchemy.org/en/20/core/constraints.html#functional-indexes)

A connection-free PostgreSQL-dialect compilation probe with the checkout's
pinned dependencies confirmed that both of these forms preserve the required
direction:

- Alembic `sa.column("measured_at").desc()` and
  `sa.column("id").desc()` expressions;
- SQLAlchemy bound model-column `.desc()` expressions.

Both compiled the ordered key as:

```sql
(device_id, measured_at DESC, id DESC)
```

The unadorned leading equality key has PostgreSQL's default ascending index
order, while the timestamp and identifier directions remain explicit.
[PostgreSQL: Indexes and
`ORDER BY`](https://www.postgresql.org/docs/current/indexes-ordering.html)

The migration should use SQLAlchemy expressions rather than flattening the
descending keys into plain unordered column-name strings. PostgreSQL-dialect
compilation and offline Alembic SQL must remain tests, because accepting an
expression object at the API boundary is not by itself proof of the final DDL.

## Migration ordering and reversibility

Alembic revision scripts declare their predecessor through `down_revision`,
and authors populate the `upgrade()` and `downgrade()` functions with the
directives Alembic invokes. Alembic does not independently choose a safe
within-revision order for replacing indexes. [Alembic 1.18.5: Create a
Migration Script](https://alembic.sqlalchemy.org/en/latest/tutorial.html#create-a-migration-script)

The new revision must therefore encode and test this exact sequence:

1. Upgrade creates all four replacement indexes.
2. Upgrade then drops exactly the four superseded indexes.
3. Downgrade recreates all four superseded indexes.
4. Downgrade then drops all four replacement indexes.

The new revision must have `down_revision = "a4f9c2e7d1b6"`, remain the single
head, and contain no unrelated schema operation. Downgrade behavior must be
implemented explicitly; Alembic treats it as author-provided down-revision
capability. [Alembic 1.18.5: Downgrading](https://alembic.sqlalchemy.org/en/latest/tutorial.html#downgrading)

## ORM metadata convention

This checkout enforces parity between explicit performance indexes in ORM
metadata and the schema represented at the Alembic head:

- [`backend/app/db/models/measurement_session.py`](../../backend/app/db/models/measurement_session.py)
  and
  [`backend/app/db/models/measurement.py`](../../backend/app/db/models/measurement.py)
  declare the current performance indexes;
- [`backend/tests/test_models.py`](../../backend/tests/test_models.py) asserts
  their exact inventory;
- [`backend/tests/test_migrations.py`](../../backend/tests/test_migrations.py)
  compares migration structure with `Base.metadata`.

The repository therefore does not follow a migration-only convention for
these indexes. The minimum conforming change is to replace the four model
index declarations with the four approved ordered definitions, without
duplicating them or changing unrelated model metadata.

## Migration-test implications

The existing migration tests were written for one revision and string-only
index columns. Adding a second revision requires the tests to distinguish
three contracts:

1. The committed initial revision remains unchanged and continues to describe
   its original index state.
2. The new revision performs the exact old-to-new and new-to-old transitions
   in the required operation order.
3. The complete migration history at the new head matches the updated ORM
   metadata.

The capture helper must accept and normalize SQLAlchemy index expressions,
compile them with the PostgreSQL dialect, and assert exact key order and
direction. Structural assertions should cover revision linkage, one head,
exact table/index names, create-before-drop event ordering, downgrade
recreate-before-drop ordering, and absence of unrelated operations.

Offline Alembic SQL remains necessary in addition to mocked-operation tests.
Alembic directives generate SQLAlchemy schema constructs and can run against a
configured output buffer without a live connection. [Alembic 1.18.5:
Operation Reference](https://alembic.sqlalchemy.org/en/latest/ops.html),
[Alembic 1.18.5: Offline
Mode](https://alembic.sqlalchemy.org/en/latest/offline.html)

Live integration preflight checks and their offline fakes that currently
expect the old head must also be updated to the new revision. This is a
checkout-derived test-infrastructure requirement, not evidence that a live
database has already been migrated.

## Session-first raw-measurement index

The session-filtered endpoint query must retain both predicates:

```sql
device_id = :device_id AND session_id = :session_id
```

The approved index starts with `session_id`, not `device_id`. PostgreSQL can
use that leading equality key to narrow the index range and use the following
descending keys for session measurement order. Since `device_id` is absent
from this index, the plan may apply device isolation as a residual filter.
This is acceptable only as a performance observation: removing the
`device_id` predicate would violate the endpoint's isolation contract.
Leading-key and later-key behavior follows PostgreSQL's documented
multicolumn B-tree rules. [PostgreSQL: Multicolumn
Indexes](https://www.postgresql.org/docs/current/indexes-multicolumn.html)

PostgreSQL automatically has an index for the referenced primary-key or
unique columns, but it does not automatically create an index on the
referencing side of a foreign key. The PostgreSQL manual notes that indexing
referencing columns is often appropriate because referenced-row updates or
deletes must locate matching child rows. A `session_id`-leading index provides
that lookup prefix, while the exact cost and chosen plan remain data-dependent.
[PostgreSQL: Foreign Keys](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)

## Honest `EXPLAIN (ANALYZE, BUFFERS)` interpretation

`EXPLAIN ANALYZE` executes the statement and reports actual row counts and
timing. `BUFFERS` reports shared, local, and temporary block hits, reads,
dirties, and writes; upper-node totals include their children. Node-level
timing itself can add overhead. [PostgreSQL:
`EXPLAIN`](https://www.postgresql.org/docs/current/sql-explain.html)

For each representative read, record at least:

- scan type and selected index, when present;
- `Index Cond` and residual `Filter`;
- `Rows Removed by Filter`;
- explicit sort nodes and sort keys;
- actual rows and loops;
- planning and execution time;
- relevant buffer hits and reads.

The normal planner result is the primary evidence. A sequential scan on a
tiny table does not demonstrate a defective index: PostgreSQL explicitly
warns that toy-sized examples do not extrapolate and that a one-page table is
normally cheaper to scan sequentially. [PostgreSQL: Examining Index
Usage](https://www.postgresql.org/docs/current/indexes-examine.html)

Planner-method switches are only diagnostic. PostgreSQL describes them as a
crude way to influence plans, and `enable_seqscan = off` merely discourages
sequential scans rather than making them impossible. [PostgreSQL: Using
`EXPLAIN`](https://www.postgresql.org/docs/current/using-explain.html),
[PostgreSQL: Planner Method
Configuration](https://www.postgresql.org/docs/current/runtime-config-query.html#RUNTIME-CONFIG-QUERY-ENABLE)

If a small safe dataset causes a sequential scan, a transaction-local
`SET LOCAL enable_seqscan = off` plan may supplement the normal plan as index
compatibility evidence. `SET LOCAL` lasts only for the current transaction.
The forced result must be labeled supplementary and must not be presented as a
production benchmark. [PostgreSQL:
`SET`](https://www.postgresql.org/docs/current/sql-set.html)

## Required evidence boundary

This research establishes API compatibility, repository convention, and the
expected structural relationship between the approved indexes and queries. It
does not establish actual planner choice, execution cost, live index inventory,
database revision state, or upgrade/downgrade success. Those claims require a
guarded local PostgreSQL migration cycle, catalog introspection, and
representative `EXPLAIN (ANALYZE, BUFFERS)` results on the actual sanitized
server version.
