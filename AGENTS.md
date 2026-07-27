# AirMonitor Agent Instructions

## Project context

AirMonitor is an IoT air-quality monitoring system.

The repository currently contains:

- AirMonitor v1: the stable diploma implementation based on Flask and SQLite;
- AirMonitor v2: a new portfolio-oriented implementation that will use FastAPI,
  PostgreSQL, SQLAlchemy, Alembic, Docker, tests, and CI/CD.

AirMonitor v1 must remain functional and must not be rewritten during the
initial AirMonitor v2 migration.


## Current task scope

For the `feature/full-audit-stabilization` branch, the current task is
Sprint 8 Phase A: a complete read-only audit of the AirMonitor v2 codebase.

The purpose of this phase is to identify and prove real correctness,
architecture, security, performance, PostgreSQL, API, configuration, testing,
and maintainability issues before any bug fix or new endpoint is implemented.

This phase is review-only.

Codex must not fix, refactor, generate, format, rename, move, delete, or
otherwise modify production code, tests, migrations, configuration, firmware,
frontend, or legacy files.

AirMonitor legacy Flask/SQLite files, including `app.py`, `sensor_data.db`,
certificates, the old HTML/JavaScript frontend, and related code, are read-only
reference material. They must not be modified or proposed as replacement
implementations.

The authoritative implementation under review is AirMonitor v2 based on:

- FastAPI;
- Pydantic;
- SQLAlchemy async;
- PostgreSQL;
- Alembic;
- pytest;
- the approved four-table domain model;
- the existing Sprint 6 repositories and services;
- the existing Sprint 7 versioned REST API.

Current verified baseline:

- `246 passed, 2 skipped`;
- sole Alembic head `a4f9c2e7d1b6`;
- eight approved `/api/v1` operations;
- protected database `airmonitor` must not be used during the audit.

The audit must cover:

### Architecture

- application composition;
- package boundaries;
- router, schema, service, repository, ORM, and migration responsibilities;
- dependency direction;
- domain invariants;
- duplicated logic;
- hidden coupling;
- unsafe abstraction leaks;
- maintainability and readiness for future read APIs, authentication, ESP32,
  frontend, aggregation, AQI, and observability.

### FastAPI and API contracts

- router registration;
- path conflicts;
- status codes;
- request and response schemas;
- OpenAPI accuracy;
- operation ID uniqueness;
- documented error responses;
- validation behavior;
- exception handling;
- application import behavior;
- dependency lifecycle;
- one AsyncSession per request;
- response serialization after commit;
- preservation of the existing public contract.

### Services and transactions

- transaction ownership;
- commit and rollback behavior;
- lock ordering;
- concurrent session creation;
- inactive-device behavior;
- duplicate source-message handling;
- session lifecycle transitions;
- runtime-state consistency;
- partial-write risks;
- exception translation;
- session reuse after failed operations;
- timezone handling.

### Repositories and SQLAlchemy

- repository transaction boundaries;
- query correctness;
- locking semantics;
- lazy loading;
- expired attributes;
- unbounded queries;
- unnecessary round trips;
- broad exception handling;
- relationship loading;
- identity-map assumptions;
- coupling to FastAPI or HTTP concerns.

### PostgreSQL and Alembic

- exact ORM-to-migration parity;
- primary keys;
- unique constraints;
- check constraints;
- foreign keys;
- composite foreign keys;
- delete behavior;
- foreign-key indexes;
- current query indexes;
- future telemetry read-query indexes;
- timestamp types;
- numeric types;
- expected raw-measurement growth;
- migration upgrade and downgrade symmetry;
- role privileges and protected-database safety.

Do not create a migration during Phase A.

### Security

- tracked secrets;
- environment-variable handling;
- exception leakage;
- URL, username, password, SQL, constraint-name, and connection-parameter
  exposure;
- unsafe serialization;
- SQL injection risk;
- mass-assignment risk;
- unknown request fields;
- integration-test database guards;
- accidental connection to `airmonitor`;
- missing authentication as a deployment limitation;
- public-exposure risks;
- sensitive generated files.

### Performance

- unnecessary database queries;
- N+1 behavior;
- lock duration;
- connection and session lifecycle;
- missing or redundant indexes;
- expensive count or offset patterns;
- future pagination requirements;
- large raw-measurement tables;
- response payload growth;
- application import and startup cost.

### Tests

- behavioral coverage;
- false-positive tests;
- excessive implementation coupling;
- fragile AST/source tests;
- mock-only confidence;
- transaction and rollback coverage;
- concurrency coverage;
- test-order independence;
- dependency override cleanup;
- environment isolation;
- false skips;
- guarded PostgreSQL integration behavior;
- credential-safe failures;
- resource cleanup;
- missing regression scenarios.

### Configuration and dependencies

- settings design;
- default values;
- environment precedence;
- unsafe defaults;
- dependency pinning;
- unused dependencies;
- package compatibility;
- reproducibility;
- deployment readiness.

### Project and Git hygiene

- `.gitignore`;
- tracked generated files;
- databases;
- certificates;
- virtual environments;
- caches;
- secrets;
- duplicated files;
- obsolete scaffolding;
- documentation drift;
- branch and CI readiness.

### Product readiness

The audit must separately report what is still required for:

- telemetry read endpoints;
- cursor pagination;
- API authentication;
- ESP32 integration;
- frontend v2;
- CORS;
- Docker;
- CI;
- logging and observability;
- aggregation, AQI, and NowCast.

The review must classify findings as:

- critical;
- high;
- medium;
- low;
- informational.

Each finding must contain:

1. stable finding ID;
2. severity;
3. confidence level;
4. exact file and line range;
5. affected component;
6. factual evidence;
7. reproduction scenario or static proof;
8. real user, data, security, or maintenance impact;
9. minimal recommended fix;
10. required regression test;
11. API compatibility impact;
12. database or migration impact;
13. whether it should be fixed in Sprint 8;
14. whether further verification is required.

A concern must not be reported as a confirmed bug unless it is supported by
code evidence, a failing test, a reproducible scenario, or a documented
invariant violation.

Potential improvements, preferences, and speculative refactors must be clearly
separated from confirmed defects.

Allowed changes during Phase A:

- `AGENTS.md`;
- one audit report:
  `docs/reviews/sprint-8-full-codebase-audit.md`.

No ADR is required during the initial review.

Do not:

- modify production code;
- modify tests;
- add endpoints;
- add schemas;
- add repositories or services;
- modify ORM models;
- modify Alembic;
- create a migration;
- connect to PostgreSQL;
- run SQL;
- create or drop databases;
- modify environment variables;
- modify frontend or firmware;
- modify legacy files;
- install or update dependencies;
- run automatic formatters that write files;
- perform Git write operations.

Codex must not perform Git staging, commit, push, reset, restore, clean, branch,
worktree, merge, rebase, cherry-pick, tag, or configuration operations.


## Sensitive files

Never open, read, display, copy, modify, or include content from:

- `secrets.h`
- `.env`
- `.env.*`, except public example templates
- `*.pem`
- `*.key`
- `*.db`
- `*.sqlite`
- `*.sqlite3`
- `.venv/`
- `venv/`

Never print credentials, Wi-Fi settings, private keys, certificates,
database contents, or local secrets.

## Technical requirements

- Use Python 3.13.
- Use FastAPI.
- Use `APIRouter` for route organization.
- Use an application factory function.
- Use type hints for public functions.
- Use Pydantic response models where appropriate.
- Keep modules small and focused.
- Avoid unnecessary abstractions.
- Do not duplicate logic.
- Use pytest for automated tests.
- Use FastAPI `TestClient` for endpoint tests.
- Keep runtime and development dependencies separate.
- Add meaningful docstrings only where they explain design intent.
- Do not add trivial comments that repeat the code.

Migration safety workflow:

- follow a strict test-first workflow;
- create migration tests before creating the initial revision;
- record the expected failing test run caused by the missing revision;
- implement the revision only after the expected failure;
- complete all unit, metadata, offline SQL, scope, and secret checks before any
  live PostgreSQL operation;
- after all offline checks pass, validate the migration against a disposable
  local PostgreSQL database;
- the disposable database name must start with
  `airmonitor_migration_test_`;
- perform upgrade, schema inspection, downgrade, and repeated upgrade only
  against the disposable database;
- delete only the disposable database after successful verification;
- after disposable-database verification succeeds, apply `upgrade head` to the
  local `airmonitor` development database;
- before applying the migration, verify that the target host is localhost or
  127.0.0.1 and that the target database name is exactly `airmonitor`;
- stop without modifying the target if it contains unexpected tables, data, or
  an incompatible Alembic state;
- never downgrade, drop, truncate, or recreate the local `airmonitor`
  development database;
- never connect to a remote or production PostgreSQL server.

## Git safety

Do not:

- commit changes;
- push changes;
- amend commits;
- rebase;
- reset;
- run `git clean`;
- force push;
- change branches;
- modify Git configuration.

The user will review and commit changes manually.

## Commands

Create the backend environment from the repository root:

```powershell
py -3.13 -m venv backend/.venv

## Definition of done

Sprint 8 Phase A is complete when:

1. The complete AirMonitor v2 backend architecture has been reviewed.
2. Every production Python file has been inspected.
3. Every backend test file has been inspected.
4. ORM models and the sole Alembic revision have been compared field by field.
5. FastAPI routes, schemas, dependencies, exception handlers, and OpenAPI have
   been reviewed.
6. Services and repositories have been reviewed for transaction and locking
   correctness.
7. Security and credential-leak risks have been reviewed.
8. PostgreSQL constraints and indexes have been inventoried exactly.
9. Current and future query patterns have been mapped to index coverage.
10. Test quality and missing regression scenarios have been reviewed.
11. Configuration, dependencies, `.gitignore`, and repository hygiene have
    been reviewed.
12. Legacy files remain unchanged.
13. No production file, test, migration, environment variable, or database has
    been modified.
14. Every confirmed finding contains evidence, impact, fix, and regression-test
    guidance.
15. Speculative improvements are separated from confirmed defects.
16. Findings are classified as critical, high, medium, low, or informational.
17. A prioritized stabilization plan is included.
18. Readiness gaps for read API, authentication, ESP32, frontend, Docker, CI,
    CORS, aggregation, and observability are documented.
19. The report explicitly states which findings should be fixed immediately
    and which should be deferred.
20. The report is created at
    `docs/reviews/sprint-8-full-codebase-audit.md`.
21. The existing baseline tests remain unchanged.
22. `git diff --check` passes.
23. Generated-file, sensitive-path, and secret audits pass.
24. No PostgreSQL connection occurs.
25. Codex performs no Git write operation.
