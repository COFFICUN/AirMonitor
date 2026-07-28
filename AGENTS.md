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

Sprint 8 Phase C4B1 — Offline Integration Database Isolation.

Implement only AUDIT-010:

- make persistence integration repeatable against one approved disposable
  PostgreSQL database;
- make API integration repeatable against one approved disposable PostgreSQL
  database;
- clean application tables before and after each integration suite;
- restore an empty database after normal completion and test-body failure;
- reset PostgreSQL identity sequences.

This first pass is strictly offline.

Do not connect to PostgreSQL during this Codex session.

Read completely:

docs/reviews/sprint-8-full-codebase-audit.md
docs/reviews/sprint-8-final-verification.md

Preserve all completed Phase C1, C2A, C2B, C3, and C4A behavior.

## Approved isolation policy

Each live integration suite must follow this order:

1. require its explicit live-test opt-in;
2. require its dedicated test database URL;
3. validate the target with the existing disposable-database guard;
4. construct its test engine;
5. run its existing schema and Alembic preflight;
6. reset all AirMonitor application tables;
7. verify the application tables are empty;
8. yield control to the integration suite;
9. reset all AirMonitor application tables in a finally path;
10. dispose the engine in an outer finally path.

No destructive database action may occur before target validation and schema
preflight succeed.

## Approved reset operation

Use one test-only PostgreSQL TRUNCATE operation containing every table from
AirMonitor ORM metadata.

Required behavior:

- derive the table inventory from the existing SQLAlchemy Base metadata;
- include every AirMonitor application table;
- execute one TRUNCATE statement;
- use RESTART IDENTITY;
- do not use CASCADE;
- execute inside an explicit transaction;
- await transaction completion;
- do not maintain a separate manually duplicated table-name list.

The currently expected table inventory is:

- devices;
- device_runtime_state;
- measurement_sessions;
- raw_measurements.

The implementation must fail closed if metadata has no tables or if reset
execution fails.

Do not use:

- Base.metadata.drop_all;
- Base.metadata.create_all;
- Alembic upgrade or downgrade;
- database creation or deletion;
- schema deletion;
- CASCADE;
- row-by-row DELETE;
- production application settings.

## Error-sanitization policy

Use fixed messages only.

Persistence suite:

- `Persistence integration database preflight failed.`
- `Persistence integration database reset failed.`

API suite:

- `API integration database preflight failed.`
- `API integration database reset failed.`

A raw driver, SQLAlchemy, SQL, URL, host, port, username, password, database
name, filesystem path, or sentinel value must not appear in the public failure.

Sanitized failures must not retain the original exception through __cause__ or
__context__.

Engine disposal must still run when preflight, initial reset, suite execution,
or final reset raises.

## Shared test-only implementation

A small shared module under backend/tests is allowed and preferred when both
integration suites use the exact same reset logic.

Production application modules under backend/app must not depend on the test
helper.

The shared helper may accept:

- an AsyncEngine or AsyncConnection;
- SQLAlchemy MetaData;
- a fixed suite-specific safe error message.

It must not:

- read environment variables;
- create its own application settings;
- decide whether a target is safe;
- connect before the calling suite completes target validation;
- log or render a database URL.

## Required workflow

Start with using-agent-skills and select the minimum sufficient installed
skills.

Use strict test-driven development:

1. inspect both integration fixtures and existing guards;
2. design focused offline regression tests;
3. demonstrate RED failures;
4. implement the smallest shared test-only reset mechanism;
5. integrate it into both suite fixtures;
6. run focused offline tests;
7. run the complete offline suite;
8. perform a bounded adversarial review;
9. stop for manual external review.

Do not implement before RED failures are demonstrated.

## Allowed files

Modify only the minimum necessary subset of:

- backend/tests/persistence_guard.py
- backend/tests/api_integration_guard.py
- backend/tests/test_persistence_integration.py
- backend/tests/test_api_integration.py
- backend/tests/test_persistence_guard.py
- backend/tests/test_api_integration_guard.py
- one new shared test-only helper module under backend/tests
- one new focused offline test module for database reset behavior

No production application file change is expected.

Stop and report instead of modifying backend/app.

## Acceptance criteria

Prove offline through mocks, fake engines, fake connections, fixture generators,
and fail-fast network guards:

1. Both suites use the same shared reset implementation.
2. Target validation occurs before engine construction or reset execution.
3. Schema/Alembic preflight occurs before the first reset.
4. Initial reset occurs before the suite body.
5. Final reset occurs after normal suite completion.
6. Final reset occurs after an exception from the suite body.
7. Engine disposal occurs after normal completion.
8. Engine disposal occurs after preflight failure.
9. Engine disposal occurs after initial reset failure.
10. Engine disposal occurs after suite-body failure.
11. Engine disposal occurs after final reset failure.
12. The reset statement contains every table in Base metadata.
13. The reset is one TRUNCATE statement.
14. The reset uses RESTART IDENTITY.
15. The reset does not contain CASCADE.
16. No drop_all, create_all, Alembic mutation, database creation, or database
    deletion occurs.
17. Reset failure messages are fixed and sanitized.
18. Reset failures have no retained __cause__.
19. Reset failures have no retained __context__.
20. Raw SQLAlchemy/driver sentinel values do not appear in captured output.
21. A stale non-empty database no longer causes the suite to fail before reset.
22. A post-reset emptiness check still fails closed if tables are not empty.
23. Existing protected-target, local-host, driver, query, prefix, and opt-in
    guards remain unchanged.
24. No live integration suite is activated during offline verification.
25. No PostgreSQL, DNS, socket, asyncpg, engine connection, or schema creation
    occurs during this phase.
26. Public API and OpenAPI remain unchanged.
27. ORM models and Alembic files remain unchanged.

## Explicitly deferred live acceptance

Do not attempt these during this Codex session:

- creating a disposable PostgreSQL database;
- running persistence integration live;
- running API integration live;
- running either suite twice;
- testing real PostgreSQL TRUNCATE behavior;
- testing real identity restart;
- testing live record-versus-terminal concurrency.

These are Phase C4B2 and require manual authorization after external review.

## Explicitly forbidden

Do not:

- connect to PostgreSQL;
- read or print database environment-variable values;
- set live integration opt-ins;
- use a real or synthetic reachable PostgreSQL URL;
- create, inspect, migrate, clean, truncate, or drop a live database;
- modify production application code;
- modify ORM models;
- modify Alembic revisions;
- modify requirements;
- install dependencies;
- implement Docker or CI;
- modify README;
- implement Telemetry Read API;
- modify API routes or schemas;
- modify Agent Skills;
- modify legacy files, firmware, certificates, keys, secrets, or .env files;
- perform Git write operations.

Read-only Git commands are allowed.

## Test environment

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest command must use:

- -B;
- -p no:cacheprovider.

No live integration opt-in may be set.

Do not read or print existing database environment-variable values.

## Required verification

At minimum run:

1. focused shared-reset unit tests;
2. focused persistence-fixture lifecycle tests;
3. focused API-fixture lifecycle tests;
4. focused sanitization and exception-chaining tests;
5. existing persistence and API guard tests;
6. both integration modules in skip-only offline mode;
7. affected test-infrastructure modules;
8. complete offline backend suite;
9. pip check;
10. guarded import/OpenAPI/engine/no-connection probes;
11. in-memory source compilation;
12. git diff --check;
13. sensitive/generated-path checks;
14. final read-only diff and status inspection.

Current pre-change baseline:

- 519 passed;
- 2 skipped.

Expected public API inventory:

- OpenAPI 3.1.0;
- nine total operations;
- eight under /api/v1;
- one /health;
- unique operation IDs.

## Definition of done

Phase C4B1 is complete only when:

- AUDIT-010 cleanup behavior is implemented for both integration suites;
- all cleanup behavior is proven offline;
- destructive work cannot occur before target and schema validation;
- cleanup is guaranteed through fixture finally paths;
- identity sequences are reset;
- error output is sanitized;
- full offline verification passes;
- no PostgreSQL or network operation occurs;
- no production, migration, ORM, requirement, README, legacy, or unrelated file
  change occurs;
- Codex performs no Git write operation;
- final output lists RED failures, implementation, changed files, exact test
  results, no-connection evidence, limitations, and final Git status.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8