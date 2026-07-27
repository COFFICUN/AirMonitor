@'
# AirMonitor Agent Instructions

## Repository context

AirMonitor v1 is the stable legacy implementation.

The following legacy assets are read-only reference material and must not be
modified:

- root app.py;
- root sensor_data.db;
- legacy HTML, CSS, and JavaScript;
- firmware and Arduino files;
- certificates, keys, secrets, and environment files;
- legacy Flask and SQLite implementation files.

AirMonitor v2 lives under backend/ and uses FastAPI, SQLAlchemy, Alembic,
PostgreSQL, Pydantic, and pytest.

## Current active task

Sprint 8 Final Verification.

This is a read-only audit and verification phase.

Do not modify production code, tests, documentation, configuration, migrations,
requirements, Agent Skills, legacy files, or Git state.

Read completely:

docs/reviews/sprint-8-full-codebase-audit.md

Review all changes made after the original audit and determine the final status
of every finding.

## Findings to verify

Verify the final status of:

- AUDIT-001: application settings and database composition;
- AUDIT-002: non-finite telemetry;
- AUDIT-003: session and measurement chronology;
- AUDIT-004: PostgreSQL INTEGER API boundaries;
- AUDIT-005: safe API error contract;
- AUDIT-006: production configuration hardening;
- AUDIT-007: engine disposal and lifespan cleanup;
- AUDIT-008: persistence test database variable;
- AUDIT-009: persistence preflight sanitization;
- AUDIT-010: integration database cleanup;
- AUDIT-011: inert API prefix configuration;
- AUDIT-012: dependency override cleanup test;
- AUDIT-013: health-test environment isolation;
- AUDIT-014: README accuracy.

AUDIT-010 was explicitly deferred. Do not implement it.

Do not silently treat AUDIT-007, AUDIT-011, or AUDIT-014 as fixed. Inspect and
report their actual status with evidence.

## Required classification

Classify each finding as exactly one of:

- FIXED;
- PARTIALLY FIXED;
- OPEN;
- DEFERRED;
- NO LONGER APPLICABLE.

For every finding provide:

- current classification;
- relevant files and symbols;
- supporting test coverage;
- remaining risk;
- recommended next action.

## Required verification

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

All pytest commands must use:

- -B;
- -p no:cacheprovider;
- no live integration opt-ins;
- no PostgreSQL connection.

At minimum perform:

1. read-only Git status and history inspection;
2. comparison between the original audited baseline and current HEAD;
3. complete offline backend suite;
4. pip check;
5. OpenAPI generation and inventory validation;
6. unique operation ID validation;
7. import, application factory, lifespan, and engine no-connection guards;
8. engine creation and disposal review;
9. settings and environment isolation review;
10. ORM and Alembic head consistency review;
11. migration and ORM schema parity review using offline/static methods only;
12. API error-envelope review;
13. chronology and integer-boundary review;
14. persistence guard and test-fixture review;
15. README and configuration-field accuracy review;
16. in-memory source compilation;
17. sensitive/generated-path inspection;
18. git diff --check;
19. final adversarial review.

Expected current offline baseline:

- 356 passed;
- 2 skipped.

Expected public API inventory:

- nine total operations;
- eight under /api/v1;
- one /health;
- unique operation IDs.

## Database restrictions

Do not:

- connect to PostgreSQL;
- inspect a live database;
- create or drop a database;
- run migrations against a database;
- read or print database environment variable values;
- activate integration suites;
- execute preflight SQL;
- modify database contents.

Use static SQLAlchemy metadata, Alembic source files, mocks, and existing
offline tests only.

## Git restrictions

Do not:

- stage files;
- commit;
- push;
- create branches;
- create tags;
- create pull requests;
- reset, checkout, restore, clean, stash, merge, or rebase;
- modify Git refs or worktree registration.

Read-only Git commands are allowed.

## Scope restrictions

Do not implement fixes during this review.

Do not modify:

- backend/app;
- backend/tests;
- Alembic files;
- README;
- AGENTS.md;
- requirements;
- legacy files;
- environment files;
- Agent Skills.

When a remaining issue is found, report it and propose a bounded next phase.

## Required final report

The final report must include:

1. repository root, worktree, detached HEAD, and base branch;
2. exact current Git status;
3. exact verification commands and results;
4. full finding matrix for AUDIT-001 through AUDIT-014;
5. evidence for every classification;
6. OpenAPI inventory;
7. migration and ORM consistency result;
8. no-connection evidence;
9. security and compatibility assessment;
10. remaining technical debt;
11. recommended next phase;
12. whether development of Telemetry Read API should begin now;
13. final diff and Git status.

Stop for manual external review.

Do not make any file or Git change.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8