# Sprint 8 Phase C4B — Live PostgreSQL Verification

**Verification date:** 2026-07-28

**PostgreSQL version:** 18.4

**Live verification branch:** `fix/sprint-8-c4b-integration-db-isolation`

The verified commits were later fast-forward merged into `feature/full-audit-stabilization`.

**C4B implementation baseline:** `22141510c3f27b600b7c80d27722d099a594ba46`

## Scope

Phase C4B verified the repaired persistence and API integration harnesses
against real, disposable local PostgreSQL targets. It also verified the
record-versus-terminal session serialization behavior that had previously
been supported only by mocked or static evidence.

This report records the approved verification facts. It intentionally omits
the generated role name, generated database names, passwords, database URLs,
administrator credentials, and all other local secrets.

## Relevant commits

| Commit | Purpose |
|---|---|
| `e488333334bae898fc0f7c46d41221fd9f939834` | Define the Sprint 8 Phase C4B1 scope |
| `5ad3ec8a703704f64f53c5f314b8c9a90f41c32c` | Isolate integration database state |
| `33e97b407f292a82a0bd23c0b0c653f00b1c9eed` | Align the API integration measurement timestamp with session chronology |
| `22141510c3f27b600b7c80d27722d099a594ba46` | Add and verify live session concurrency coverage |

The chronology correction changed the lifecycle integration test to use the
created session's `started_at` value for its first measurement instead of a
timestamp captured before the session existed.

## Disposable resources

The verification used:

- one temporary non-superuser PostgreSQL role;
- one disposable persistence database whose name used the approved
  `airmonitor_persistence_test_` prefix;
- one separate disposable API database whose name used the approved
  `airmonitor_api_test_` prefix.

Both targets were local, isolated from the protected application/development
database, and migrated to Alembic revision `a4f9c2e7d1b6`.

## Verified runs

| Suite or stage | Run | Result |
|---|---:|---|
| Persistence integration | 1 | 13 passed |
| Persistence integration | 2 | 13 passed |
| API integration, initial attempt | 1 | Exposed an outdated pre-session measurement timestamp in the test |
| Chronology correction | — | Test timestamp aligned with the created session's `started_at` |
| Final API integration | 1 | 6 passed |
| Final API integration | 2 | 6 passed |

The final six API tests include real PostgreSQL serialization coverage for all
four terminal/record orderings:

- complete obtains the terminal transition first, then a waiting record is
  rejected;
- cancel obtains the terminal transition first, then a waiting record is
  rejected;
- a record commits first, then complete rejects a contradictory earlier
  terminal timestamp;
- a record commits first, then cancel rejects a contradictory earlier
  terminal timestamp.

These cases exercise the shared device → runtime state → session lock order
against real PostgreSQL behavior.

## Cleanup and repeatability

After every persistence and API run, verification confirmed:

- all application tables were empty;
- identity sequences restarted;
- no cleanup used `CASCADE`;
- the next run began from clean application state.

The integration harness used the shared metadata-driven
`TRUNCATE ... RESTART IDENTITY` reset before and after each suite. Target
validation and schema/revision preflight occurred before the initial reset.

After all runs:

- both disposable databases were removed;
- the temporary non-superuser role was removed;
- no live database objects created for C4B remained.

## Offline baseline

The complete offline backend suite on the C4B implementation baseline
produced:

```text
550 passed, 2 skipped
```

The two skips are the live integration modules when their dedicated opt-ins
are absent. The result was reproduced during the Phase C4C pre-edit
verification with live integration disabled.

## Conclusion

Phase C4B established repeatable live persistence and API integration results,
verified cleanup and identity restart, and added real PostgreSQL evidence for
complete/cancel concurrency ordering. It did not add public API operations,
authentication, authorization, or telemetry read endpoints.

No statement in this report describes the condition of an unrelated
development, protected, staging, or production database.
