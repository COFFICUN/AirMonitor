@'
# AirMonitor Agent Instructions

## Project structure

AirMonitor v1 at the repository root is stable legacy reference material.

Do not modify legacy v1 files unless the user explicitly requests legacy work.

AirMonitor v2 lives under backend/ and uses:

- FastAPI;
- PostgreSQL;
- async SQLAlchemy;
- Alembic;
- Pydantic;
- pytest.

## Branch policy

- main: stable legacy and released repository state;
- develop: current v2 integration branch;
- feature/*: isolated feature implementation.

Do not commit directly to main during normal v2 development.

## Development environment

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest command must include:

-B -p no:cacheprovider

Do not use another Python interpreter.

## Source-of-truth policy

Treat the current checkout as authoritative.

Historical plans, prior reports, memory, and chat context are guidance only
when they agree with the current repository.

Read relevant specifications, plans, tests, models, migrations, and existing
conventions completely before editing.

## Implementation workflow

For substantial work, use one coherent macro sprint rather than many tiny
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
remaining work is already approved and safely executable.

Stop early only for a genuine safety, scope, or environment blocker.

## Testing policy

Before significant changes, establish the current baseline.

After changes, run:

- focused tests;
- relevant regression tests;
- full offline backend suite;
- pip check;
- git diff --check;
- syntax and import checks;
- architecture and security scans.

Do not add skips, xfail, fallback implementations, or weakened assertions to
hide failures.

## PostgreSQL safety

Do not connect to an ambiguous, remote, protected, or production database.

Live integration and migration verification require a dedicated disposable
local database whose name matches the project test guards.

Never print:

- passwords;
- full database URLs;
- tokens;
- certificates;
- secret-bearing exception details.

Do not bypass database preflight or reset protections.

## Architecture boundaries

API routes must remain thin HTTP adapters.

Routes must not:

- import repositories;
- construct SQL;
- import SQLAlchemy statement builders;
- manage transactions;
- perform ownership lookups outside approved services;
- expose internal exceptions.

Services coordinate domain behavior but do not own HTTP concerns.

Repositories own SQL and persistence access.

Alembic owns schema transitions.

## Telemetry Read API stable contract

The completed read endpoints are:

GET /api/v1/devices/{device_id}/sessions

GET /api/v1/devices/{device_id}/measurements

They use:

- strict query validation;
- filter-bound opaque keyset cursors;
- stable timestamp DESC, id DESC ordering;
- public limit 1..500;
- SQL limit + 1;
- no OFFSET;
- mandatory device isolation;
- half-open time ranges;
- non-disclosing measurement session filters.

The current Alembic head is:

a75caa2b44f5

Do not regress these contracts without an explicitly approved new task.

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

Do not modify tests merely to accommodate an incorrect implementation.

Do not create agent scratch files inside the repository unless the repository
already tracks that exact convention.

Remove temporary containers, files, scripts, logs, and generated secrets after
verification.

## Definition of done

Work is complete only when:

- approved behavior is implemented;
- focused and full applicable tests pass;
- migrations are reversible where applicable;
- OpenAPI and public contracts remain valid;
- architecture and security boundaries pass;
- documentation reflects only verified evidence;
- no secret or temporary artifact remains;
- final Git status and diff are reported for manual review.
