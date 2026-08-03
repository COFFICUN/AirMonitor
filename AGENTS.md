@'
# AirMonitor Agent Instructions

## Project structure

AirMonitor is an IoT air-quality monitoring system.

The repository contains:

- stable legacy AirMonitor v1 files at the repository root;
- AirMonitor v2 backend under backend/;
- documentation under docs/.

Legacy v1 files are reference material only.

Do not modify legacy application files unless the user explicitly requests
legacy work.

## AirMonitor v2 stack

The v2 backend uses:

- Python 3.13;
- FastAPI;
- PostgreSQL;
- async SQLAlchemy;
- Alembic;
- Pydantic;
- pytest;
- Docker;
- Docker Compose;
- GitHub Actions.

Current Alembic head:

a75caa2b44f5

## Stable backend capabilities

The backend currently supports:

- device registration and status management;
- measurement-session lifecycle management;
- raw-measurement ingestion;
- session telemetry reads;
- measurement telemetry reads;
- strict query validation;
- opaque keyset pagination;
- PostgreSQL integration testing;
- automatic container startup migrations;
- Docker Compose local development;
- backend CI.

Do not regress established API or database contracts without an explicitly
approved task.

## Branch policy

- main: stable legacy and released repository state;
- develop: current v2 integration branch;
- feature/*: isolated feature development.

Do not commit directly to main during normal v2 development.

## Development environment

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest command must include:

-B -p no:cacheprovider

Do not use a competing local Python interpreter.

## Source-of-truth policy

Treat the current checkout as authoritative.

Historical plans, previous reports, memory, and chat context are guidance only
when they agree with the current repository.

Read all relevant specifications, models, migrations, tests, configuration,
and existing conventions before editing.

## Implementation workflow

Use coherent macro sprints for substantial features instead of many tiny
manual phases.

Internally follow:

1. source audit;
2. requirements;
3. implementation plan;
4. contract-first tests;
5. incremental implementation;
6. focused verification;
7. full regression;
8. architecture and security review;
9. documentation;
10. final manual review.

Do not stop after an ordinary intermediate RED or GREEN checkpoint when the
remaining approved work can be completed safely.

Stop early only for a genuine scope, safety, or environment blocker.

## Testing policy

Before substantial work, establish the current baseline.

After changes, run:

- focused tests;
- relevant regression tests;
- the complete offline backend suite;
- applicable PostgreSQL integration tests;
- pip check;
- Alembic head verification;
- git diff --check;
- syntax and import checks;
- architecture and security scans.

Do not add skips, xfail, weakened assertions, or fallback implementations to
hide failures.

## PostgreSQL safety

Do not connect to an ambiguous, protected, remote, or production database.

Live integration verification requires a dedicated disposable local database
accepted by the repository guards.

Never print:

- passwords;
- complete database URLs;
- tokens;
- certificates;
- secret-bearing exception details.

Do not bypass database preflight or reset protections.

## Docker safety

Do not reuse or modify unrelated Docker containers, networks, or volumes.

Verification environments must use unique project names and disposable
resources.

Runtime containers must remain non-root.

Do not expose PostgreSQL publicly.

Do not retain generated credentials, temporary images, test containers, logs,
or disposable volumes after verification.

## Architecture boundaries

API routes must remain thin HTTP adapters.

Routes must not:

- import repositories;
- construct SQL;
- manage database transactions;
- perform unapproved ownership lookups;
- expose internal exceptions.

Services coordinate application behavior.

Repositories own persistence queries.

Alembic owns schema transitions.

Container entrypoints own single-container startup migration execution.

## Telemetry Read API stable contract

Completed endpoints:

GET /api/v1/devices/{device_id}/sessions

GET /api/v1/devices/{device_id}/measurements

They retain:

- strict query validation;
- filter-bound opaque keyset cursors;
- timestamp DESC, id DESC ordering;
- public limit from 1 through 500;
- SQL limit plus one;
- no OFFSET;
- mandatory device isolation;
- half-open time ranges;
- non-disclosing measurement session filters.

## Git restrictions for agents

Unless the user explicitly authorizes Git writes, do not:

- stage;
- commit;
- push;
- merge;
- reset;
- clean;
- stash;
- create or delete branches;
- modify Git configuration.

Read-only Git commands are allowed.

Keep the Git index unchanged during agent implementation and review.

## Scope discipline

Do not perform unrelated refactoring.

Do not alter public contracts without an approved specification.

Do not edit committed migrations.

Do not create agent scratch files inside the repository.

Do not retain temporary scripts, environment files, database dumps, caches, or
generated secrets.

## Definition of done

Work is complete only when:

- approved behavior is implemented;
- focused and full applicable tests pass;
- migrations remain reversible;
- OpenAPI and public contracts remain valid;
- architecture and security boundaries pass;
- deployment instructions are reproducible;
- documentation reflects verified evidence;
- no secret or temporary resource remains;
- final Git status and diff are reported for manual review.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8