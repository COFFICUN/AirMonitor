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
- certificates, keys, and secret files;
- Flask and SQLite implementation files.

AirMonitor v2 lives under backend/ and uses FastAPI, SQLAlchemy, Alembic,
PostgreSQL, Pydantic, and pytest.

## Current active task

Sprint 8 Phase C3 — Test Infrastructure Hardening.

Implement only:

- AUDIT-008: the persistence integration suite must use the dedicated
  AIRMONITOR_TEST_DATABASE_URL variable and ignore the application database
  variable;
- AUDIT-009: persistence preflight connection failures must be sanitized and
  must not retain credential-bearing exception cause or context;
- AUDIT-012: replace the false-positive dependency-override cleanup test with
  a test of the real cleanup mechanism;
- AUDIT-013: isolate the health contract test from ambient settings.

Read completely before changing files:

docs/reviews/sprint-8-full-codebase-audit.md

Preserve all completed Phase C1, C2A, and C2B behavior.

## Approved database-test variable policy

Persistence integration tests must use only:

AIRMONITOR_TEST_DATABASE_URL

They must not consume:

AIRMONITOR_DATABASE_URL

The application database variable may be present in the process, but the
persistence integration suite must ignore it.

Do not read, print, log, or include the value of any real database environment
variable in reports or error messages.

Tests may use synthetic sentinel URLs created entirely inside the test process.

Preserve all existing persistence target protections:

- postgresql+asyncpg driver requirement;
- local-host restriction;
- protected database rejection;
- disposable database naming requirement;
- rejection of target-changing URL query parameters;
- explicit live-test opt-in.

## Approved preflight failure policy

A connection/preflight failure must produce a short fixed message that does
not include:

- database URL;
- username;
- password;
- database name;
- host or port;
- query parameters;
- driver exception representation;
- SQL text;
- filesystem paths;
- arbitrary sentinel text.

The raised exception must not retain the original exception through
`__cause__` or `__context__`.

Use `raise ... from None` or an equivalent mechanism that is proven by tests.

Do not connect to PostgreSQL during this phase.

## Approved dependency-override cleanup policy

Replace the existing false-positive cleanup test.

The new test must exercise the same fixture/helper used by the test
application and verify that dependency overrides are restored after an
exception.

The test must fail if the actual cleanup logic is removed.

Do not write a test that manually performs the restoration it claims to test.

A small test-only context manager or helper is allowed when:

- the real fixture uses it;
- its cleanup is implemented with `try/finally`;
- the regression test exercises that same helper;
- no production module depends on it.

## Approved health-test isolation policy

Health tests must construct explicit settings with `_env_file=None`.

Conflicting ambient values for service name, version, environment, debug, or
other supported settings must not affect the expected health response.

Do not change the production health endpoint contract.

## Required workflow

Start with `using-agent-skills` and select the minimum sufficient installed
skills.

Use test-driven development:

1. inspect the current test guards and fixtures;
2. add focused tests that expose each accepted defect;
3. run them and confirm the intended failures;
4. make the smallest test-infrastructure changes;
5. rerun focused tests;
6. run the complete offline suite;
7. perform a bounded adversarial review;
8. stop for manual external review.

Do not implement before RED failures are demonstrated.

## Allowed production scope

No production application change is expected.

Production files under backend/app must not be modified unless a test-only
solution is demonstrably impossible. Stop and report instead of changing
production code without authorization.

## Allowed test scope

Changes are limited to the minimum necessary subset of:

- backend/tests/persistence_guard.py
- backend/tests/test_persistence_guard.py
- backend/tests/test_persistence_integration.py
- backend/tests/api_integration_guard.py only if a shared safe helper is
  clearly preferable and existing API guard behavior remains unchanged
- backend/tests/test_api_integration_guard.py only for compatible regression
  coverage
- backend/tests/test_api_routes.py
- backend/tests/test_health.py
- backend/tests/conftest.py if it exists or is justified as a small shared
  test-only fixture module
- one small focused test-only helper module under backend/tests if required

Do not modify live database cleanup/provisioning behavior. AUDIT-010 remains
deferred.

## AUDIT-008 acceptance criteria

Prove all of the following:

1. Persistence integration tests read AIRMONITOR_TEST_DATABASE_URL.
2. AIRMONITOR_DATABASE_URL is ignored by the persistence suite.
3. Setting only AIRMONITOR_DATABASE_URL cannot activate or target persistence
   integration tests.
4. Setting the dedicated variable with the required opt-in follows the existing
   target validation path.
5. Missing dedicated configuration produces only a fixed safe message or skip.
6. No database URL value appears in test output or exception text.
7. Existing driver, host, query-parameter, protected-name, and prefix guards
   remain intact.
8. No PostgreSQL connection occurs in offline tests.

## AUDIT-009 acceptance criteria

Prove all of the following:

1. A synthetic connection/preflight exception containing a sentinel URL,
   username, password, database name, and driver text is sanitized.
2. The public failure message contains none of those values.
3. The resulting exception has no retained `__cause__`.
4. The resulting exception has no retained `__context__`.
5. The safe API integration preflight behavior remains unchanged.
6. No live connection is attempted.

## AUDIT-012 acceptance criteria

Prove all of the following:

1. The actual application fixture/helper restores its previous dependency
   overrides after normal use.
2. It restores the overrides after an exception inside the fixture context.
3. Pre-existing overrides are restored exactly, not merely cleared.
4. Overrides added during the context do not leak.
5. The regression fails if the real `finally` restoration is removed.
6. Existing route tests retain their current behavior.

## AUDIT-013 acceptance criteria

Prove all of the following:

1. The health test creates explicit isolated Settings.
2. `_env_file=None` is used.
3. Conflicting environment variables do not change the expected response.
4. Existing module-level application behavior is not modified.
5. The health endpoint response contract remains unchanged.

## Explicitly forbidden

Do not:

- implement AUDIT-010 automated database creation or cleanup;
- connect to PostgreSQL;
- create, inspect, migrate, truncate, clean, or drop a database;
- set a real database URL;
- print or read existing database URL values;
- implement telemetry read endpoints;
- change production error handlers or production settings;
- modify routes, schemas, services, repositories, ORM models, or migrations;
- change authentication, CORS, Docker, CI, logging, or observability;
- modify requirements or install dependencies;
- modify the audit report or README;
- modify Agent Skills;
- modify legacy files, firmware, secrets, certificates, keys, or .env files;
- perform Git write operations.

Read-only Git commands are allowed.

## Test environment

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Do not modify the environment.

Use:

- `-B`;
- `-p no:cacheprovider`;
- no live-test activation;
- no PostgreSQL connection;
- synthetic environment values only inside focused tests.

## Required verification

At minimum run:

1. focused persistence-variable tests;
2. focused preflight-sanitization tests;
3. focused override-cleanup tests;
4. isolated health tests;
5. affected guard, route, health, and offline integration tests;
6. the complete offline backend suite;
7. pip check;
8. guarded import/OpenAPI no-connection tests;
9. in-memory/source compilation without generated bytecode;
10. git diff --check;
11. sensitive/generated-path checks;
12. final read-only diff and status inspection.

The expected public API inventory remains:

- nine total operations;
- eight under /api/v1;
- one /health;
- unique operation IDs.

## Definition of done

Phase C3 is complete only when:

- RED tests reproduce AUDIT-008, AUDIT-009, AUDIT-012, and AUDIT-013;
- the dedicated persistence variable is enforced;
- persistence preflight failures are safely sanitized;
- real dependency-override cleanup is tested;
- health tests are environment-independent;
- the full offline suite passes;
- no PostgreSQL connection occurs;
- no production application file changes;
- no migration, dependency, documentation, legacy, or sensitive changes;
- Codex performs no Git write operation;
- the final response lists RED failures, changed files, exact commands/results,
  compatibility impact, remaining limitations, and exact Git status.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8