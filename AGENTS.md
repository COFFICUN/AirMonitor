Set-Location "C:\Users\nazar\Desktop\AirMonitor"

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

Sprint 8 Phase C4A — Production Configuration Contract.

Implement only:

- complete AUDIT-006 by replacing literal database-URL comparison with
  structural production-target validation;
- close AUDIT-011 by removing the inert api_prefix setting while preserving
  the fixed /api/v1 route contract.

Read completely before changing files:

docs/reviews/sprint-8-full-codebase-audit.md
docs/reviews/sprint-8-final-verification.md

Preserve all completed Phase C1, C2A, C2B, and C3 behavior.

## Approved production database policy

Production must continue rejecting:

- debug=true;
- database_echo=true;
- the built-in development database target and its canonical equivalents.

The development target must be detected structurally rather than by raw string
equality.

Use an existing trusted URL parser such as SQLAlchemy URL parsing. Do not
implement database URL parsing using split(), regular expressions, or manual
credential extraction.

The structural comparison must account for:

- driver name normalization;
- decoded username;
- decoded password;
- normalized host;
- normalized port;
- decoded database name;
- PostgreSQL default port 5432 when the port is omitted;
- host case differences;
- a trailing dot in localhost;
- localhost, IPv4 loopback, and IPv6 loopback equivalence;
- percent-encoded equivalents;
- harmless query options that must not make the built-in target acceptable.

Do not resolve hostnames and do not perform DNS or network access.

Production URLs containing query keys that can override connection identity
must be rejected as ambiguous. At minimum cover:

- host;
- port;
- database;
- dbname;
- user;
- username;
- password;
- service;
- servicefile.

Query-key comparison must be case-insensitive.

The implementation must not print, log, format, interpolate, serialize, or
otherwise expose:

- database URLs;
- usernames;
- passwords;
- hosts;
- ports;
- database names;
- query values;
- parsed URL representations.

Validation failures must use short fixed messages with no input values.

Existing Settings input hiding and SQLAlchemy hide_parameters=True behavior
must remain intact.

Development and test configurations must retain their current behavior.

## Approved API-prefix policy

The public API contract remains fixed at:

/api/v1

Remove the inert api_prefix field rather than wiring it into router
composition.

Remove:

- Settings.api_prefix;
- its default value;
- its AIRMONITOR_API_PREFIX example entry;
- tests or assertions that represent it as a supported configuration option.

Do not:

- make routes environment-dependent;
- introduce a replacement prefix setting;
- change router prefixes;
- change paths;
- change operation IDs;
- change request or response schemas;
- change successful status codes.

A stale AIRMONITOR_API_PREFIX process variable must not change routes or
OpenAPI. It may be ignored as an unsupported environment variable according
to the existing settings-source behavior.

## Required workflow

Start with using-agent-skills and select the minimum sufficient installed
skills.

Use strict test-driven development:

1. inspect current settings defaults, validation, environment-source behavior,
   router composition, .env.example, and relevant tests;
2. add focused failing regression tests;
3. demonstrate that the failures correspond to AUDIT-006 and AUDIT-011;
4. implement the smallest coherent fix;
5. rerun focused tests;
6. run the complete offline backend suite;
7. perform a bounded adversarial review;
8. stop for manual external review.

Do not implement before RED failures are demonstrated.

## Allowed production scope

Modify only the minimum necessary subset of:

- backend/app/core/config.py
- backend/.env.example

The router should not require a production change because /api/v1 already is
the correct fixed contract. Stop and report before changing router code unless
current source evidence proves it is necessary.

## Allowed test scope

Modify only the minimum necessary subset of:

- backend/tests/test_config.py
- backend/tests/test_api_openapi.py
- backend/tests/test_application_composition.py
- backend/tests/test_api_routes.py
- one focused new configuration test module only when it materially improves
  clarity

Do not modify live integration guards or database cleanup behavior.

## AUDIT-006 acceptance criteria

Prove all of the following:

1. Production still rejects debug=true.
2. Production still rejects database_echo=true.
3. Production rejects the exact built-in development database URL.
4. Production rejects the equivalent URL when port 5432 is omitted.
5. Production rejects equivalent host case variants.
6. Production rejects localhost with a trailing dot.
7. Production rejects equivalent IPv4 loopback representation.
8. Production rejects equivalent IPv6 loopback representation.
9. Production rejects equivalent percent-encoded components.
10. Harmless query options do not bypass development-target rejection.
11. Target-identity override query keys are rejected in production.
12. Query-key matching is case-insensitive.
13. A genuinely distinct explicit PostgreSQL+asyncpg production target is
    accepted.
14. Existing driver validation remains intact.
15. Development and test continue accepting their current configurations.
16. Validation errors do not contain the candidate URL or any component,
    credential, query value, or sentinel.
17. Captured logs and stdout/stderr do not contain sensitive target values.
18. Validation performs no DNS lookup or network call.
19. Engine construction remains lazy and performs no connection.
20. hide_parameters=True remains enabled.

## AUDIT-011 acceptance criteria

Prove all of the following:

1. Settings no longer contains api_prefix.
2. The built-in settings defaults no longer contain api_prefix.
3. backend/.env.example no longer advertises AIRMONITOR_API_PREFIX.
4. Setting a synthetic AIRMONITOR_API_PREFIX does not change routes.
5. The public path remains /api/v1.
6. OpenAPI still contains nine total operations.
7. OpenAPI still contains eight /api/v1 operations and one /health operation.
8. Operation IDs remain unique and unchanged.
9. Request schemas, success response schemas, and successful status codes
   remain unchanged.
10. No replacement dynamic-prefix mechanism is introduced.

## Explicitly forbidden

Do not:

- implement AUDIT-010;
- modify integration database setup or cleanup;
- connect to PostgreSQL;
- inspect, create, migrate, clean, truncate, or drop a database;
- read or print real database environment-variable values;
- implement Telemetry Read API;
- change routes or operation IDs;
- change domain behavior or error codes;
- change chronology or integer-boundary behavior;
- change ORM models, constraints, indexes, relationships, or database types;
- create or modify Alembic revisions;
- modify README during this phase;
- modify the audit or final-verification reports;
- add authentication, authorization, CORS, rate limiting, logging, Docker, or
  CI;
- modify requirements or install dependencies;
- modify Agent Skills;
- modify legacy files, firmware, certificates, keys, secrets, or .env files;
- perform Git write operations.

Read-only Git commands are allowed.

## Test environment

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Do not modify this environment.

All pytest commands must use:

- -B;
- -p no:cacheprovider;
- no live integration opt-ins;
- no PostgreSQL connection;
- synthetic configuration values created only inside tests.

Do not read or print existing database environment-variable values.

## Required verification

At minimum run:

1. focused structural production-target tests;
2. focused sensitive-validation-output tests;
3. focused api_prefix-removal tests;
4. existing config and database-engine tests;
5. affected composition, route, and OpenAPI tests;
6. the complete offline backend suite;
7. pip check;
8. guarded OpenAPI generation;
9. import, factory, lifespan, and engine no-connection guards;
10. a guard proving no DNS or socket operation occurred during validation;
11. in-memory source compilation without repository bytecode;
12. git diff --check;
13. sensitive/generated-path checks;
14. final read-only diff and status inspection.

Current pre-change offline baseline:

- 356 passed;
- 2 skipped.

Expected public API inventory remains:

- OpenAPI 3.1.0;
- nine total operations;
- eight operations under /api/v1;
- one /health operation;
- unique operation IDs.

## Definition of done

Phase C4A is complete only when:

- RED tests reproduce the canonical-equivalent production-target bypass;
- RED tests reproduce the inert api_prefix configuration;
- production-target comparison is structural and sanitized;
- canonical variants of the built-in development target are rejected;
- ambiguous target-override query keys are rejected;
- api_prefix is removed from Settings and .env.example;
- the fixed /api/v1 API contract is preserved;
- the complete offline suite passes;
- no network or PostgreSQL connection occurs;
- no migration, ORM, integration-cleanup, dependency, README, legacy, or
  unrelated change occurs;
- Codex performs no Git write operation;
- the final response lists RED failures, changed files, exact commands and
  results, OpenAPI compatibility, no-network evidence, remaining limitations,
  and final Git status.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8