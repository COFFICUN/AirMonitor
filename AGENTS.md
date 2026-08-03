@'
# AirMonitor Agent Instructions

## Repository context

AirMonitor is an IoT air-quality monitoring project.

The repository contains:

- stable legacy AirMonitor v1 files at the repository root;
- AirMonitor v2 backend under backend/;
- documentation under docs/.

Legacy v1 files are reference material only.

Do not modify legacy application files unless the current task explicitly
requires legacy work.

AirMonitor v2 uses:

- Python 3.13;
- FastAPI;
- PostgreSQL;
- async SQLAlchemy;
- Alembic;
- Pydantic;
- pytest.

Current integration branch:

develop

Current feature branch:

feature/production-readiness

## Current application state

The v2 backend already contains:

- device registration and status management;
- measurement-session lifecycle operations;
- raw-measurement ingestion;
- telemetry session read API;
- telemetry measurement read API;
- strict query validation;
- opaque keyset pagination;
- PostgreSQL repositories;
- async services;
- Alembic migrations;
- composite telemetry indexes;
- OpenAPI contracts;
- guarded PostgreSQL integration tests.

Current Alembic head:

a75caa2b44f5

Current expected OpenAPI inventory:

- OpenAPI 3.1.0;
- 11 total operations;
- 10 operations under /api/v1;
- 1 operation under /health;
- 11 unique operation IDs.

Current expected offline suite baseline:

- 840 passed;
- 2 skipped.

Record the actual checkout baseline before editing.

Do not force these expected numbers when the current checkout reports
legitimate differences.

## Current macro task

Complete the backend production-readiness and developer-onboarding layer in one
continuous macro sprint.

The sprint includes:

1. repository and deployment audit;
2. backend Docker image;
3. Docker Compose development stack;
4. controlled Alembic startup migration;
5. container healthchecks;
6. environment-variable documentation;
7. GitHub Actions backend CI;
8. offline and PostgreSQL CI verification;
9. clean-clone startup verification;
10. README and deployment documentation;
11. final architecture, security, and operational review.

Do not divide this work into separate manual phases.

Use internal RED and GREEN checkpoints, but continue automatically until the
full macro task is complete.

Stop early only for a genuine safety, environment, or scope blocker.

## Out of scope

Do not implement in this macro phase:

- frontend v2;
- legacy frontend migration;
- ESP32 firmware changes;
- Redis;
- authentication;
- authorization;
- cloud deployment;
- Kubernetes;
- reverse proxy infrastructure;
- HTTPS certificate automation;
- monitoring platforms;
- background workers;
- AQI forecasting changes;
- telemetry business-logic changes;
- API contract redesign.

Do not add speculative infrastructure.

## Governing files

Read all relevant existing files before editing, including:

- AGENTS.md;
- README.md;
- .gitignore;
- .env.example files;
- backend/requirements.txt;
- backend/requirements-dev.txt;
- backend/alembic.ini;
- backend/alembic/env.py;
- backend/app/main.py;
- backend/app/core configuration modules;
- backend/app/db configuration and dependencies;
- backend/app/api routes;
- backend/tests integration guards;
- backend/tests integration runtime helpers;
- backend/tests PostgreSQL integration suites;
- backend/alembic/versions/*.py;
- docs/specs/telemetry-read-api.md;
- docs/reviews/telemetry-read-api-final-verification.md;
- existing Docker, Compose, CI, and deployment files if present.

The current checkout is the source of truth.

Do not rely on an earlier report when it conflicts with the repository.

## Required source research

When external research is necessary, use official primary documentation only.

Examples:

- Docker documentation;
- Docker Compose specification;
- Python official images;
- PostgreSQL official images;
- FastAPI deployment documentation;
- Uvicorn documentation;
- GitHub Actions documentation;
- Alembic documentation.

Record only findings that materially affect implementation.

Do not add a large generic research document unless it provides lasting value.

## Development environment

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest invocation must include:

-B -p no:cacheprovider

Do not use another local interpreter.

Docker commands may use the installed Docker Desktop environment.

## Git restrictions

Do not perform Git writes.

Do not:

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

Keep the Git index unchanged.

## Stage 1 — current-state audit

Before editing, inspect and report:

1. worktree path;
2. detached HEAD;
3. current Git status;
4. Git index state;
5. applicable instruction files;
6. selected installed skills;
7. current project tree relevant to deployment;
8. existing Docker-related files;
9. existing Compose-related files;
10. existing CI workflows;
11. current configuration-loading behavior;
12. current database URL handling;
13. current Alembic startup assumptions;
14. current README startup instructions;
15. current offline test baseline;
16. current OpenAPI inventory;
17. current Alembic head;
18. safe local Docker availability;
19. expected files to modify or create;
20. internal implementation plan.

Do not wait for approval after reporting.

Continue automatically.

## Stage 2 — contract-first infrastructure tests

Before implementing deployment files, add focused tests or static contract
checks for the repository requirements below.

Prefer testing behavior and parsed structure over fragile whole-file snapshots.

Test or verify at minimum:

- the Docker image uses the approved Python major/minor version;
- the image installs runtime dependencies;
- the image does not install development dependencies in the runtime layer;
- the image runs as a non-root user;
- the image exposes the API port;
- the image contains a healthcheck or the Compose service defines one;
- the startup process applies Alembic migrations before starting the API;
- shell scripts use LF line endings;
- shell scripts fail safely;
- Compose defines API and PostgreSQL services;
- Compose uses PostgreSQL health status before API startup;
- Compose does not contain a committed real password;
- Compose does not expose PostgreSQL publicly by default;
- Compose persists development PostgreSQL data intentionally;
- the API service receives configuration through environment variables;
- the API healthcheck targets the existing /health endpoint;
- CI runs offline tests without live database activation;
- CI runs PostgreSQL integration tests against a dedicated test database;
- CI checks Alembic head consistency;
- CI builds the Docker image;
- workflow permissions are minimal;
- no workflow exposes secret values;
- example environment files contain placeholders only;
- README commands correspond to actual files and service names.

Record the intentional RED boundary.

Do not stop after RED.

## Stage 3 — backend Docker image

Create or update the canonical backend Dockerfile.

Expected location:

backend/Dockerfile

Follow current repository conventions where they already exist.

The final runtime image must:

- use an official Python 3.13 slim image or another justified official
  Python 3.13 runtime image;
- avoid unnecessary build tools in the final layer;
- install only runtime dependencies;
- copy only required application and Alembic files;
- run as a dedicated non-root user;
- set a deterministic working directory;
- disable Python bytecode generation;
- enable unbuffered output;
- expose the configured API port;
- use exec-form process execution;
- support the project startup script;
- contain no credentials;
- contain no copied local virtual environment;
- contain no tests unless they are intentionally required by the final image;
- contain no legacy v1 files;
- contain no local certificates or database files.

Use a multi-stage build only when it provides real value.

Do not add complexity solely to advertise a multi-stage build.

Add an appropriate:

backend/.dockerignore

It must exclude at minimum:

- .venv;
- __pycache__;
- pytest caches;
- coverage output;
- local environment files;
- SQLite databases;
- certificates;
- secrets;
- Git metadata;
- editor files;
- build artifacts.

Do not exclude files required by Alembic or application startup.

## Stage 4 — controlled container startup

Create one canonical startup script, preferably:

backend/docker-entrypoint.sh

The script must:

1. use a safe shell mode;
2. avoid printing secrets;
3. optionally wait for PostgreSQL readiness when necessary;
4. run `alembic upgrade head`;
5. start the API only after successful migration;
6. use `exec` for the final process;
7. propagate termination signals correctly;
8. fail when migration fails;
9. avoid infinite unbounded retry loops;
10. remain usable in Docker Compose and a standalone container.

Use LF line endings.

Do not run migrations concurrently in multiple worker processes.

For the current single-container MVP, one API container may own startup
migration execution.

Document this limitation.

The application command should run Uvicorn in a production-appropriate form
for the current MVP.

Do not add multiple workers until migration ownership and deployment behavior
are designed for them.

## Stage 5 — Docker Compose development stack

Create or update the canonical root Compose file.

Preferred name:

compose.yaml

Use the repository convention when an existing canonical Compose filename is
already established.

The development stack must contain at minimum:

- api;
- db.

### Database service

Use an official PostgreSQL 18 image when supported.

Requirements:

- database data stored in one named development volume;
- database port not published to all host interfaces by default;
- preferably no host PostgreSQL port at all unless required for documented
  development workflows;
- healthcheck based on `pg_isready`;
- credentials supplied from environment-variable substitution;
- no real credentials committed;
- explicit development database name;
- restart policy appropriate for local development;
- no connection to the user's existing protected database.

### API service

Requirements:

- built from backend/Dockerfile;
- depends on PostgreSQL health;
- receives an async SQLAlchemy/asyncpg URL;
- receives host, port, and environment settings;
- exposes only the API port required by the developer;
- has a healthcheck using `/health`;
- runs the migration-aware startup process;
- does not mount the host virtual environment;
- does not mount secrets;
- does not use privileged mode;
- does not run as root;
- does not depend on legacy v1 files.

Compose must support:

docker compose up --build

from the repository root.

The resulting API must become healthy without requiring manual Alembic
commands.

## Stage 6 — environment configuration

Audit all current configuration keys before adding anything.

Reuse existing environment-variable names wherever possible.

Do not create competing aliases for the same configuration.

Update or create safe example configuration only where needed.

Expected example values must:

- contain no real password;
- contain no personal path;
- contain no local IP tied to one machine;
- use placeholders or safe development defaults;
- explain which values are for host execution and which are for Compose;
- explain that the Compose database hostname is the service name, not
  localhost;
- avoid committing an actual `.env`.

Ensure `.gitignore` excludes real environment files while retaining example
files.

Do not print or expose existing secret values during the audit.

## Stage 7 — GitHub Actions backend CI

Create or update the canonical backend CI workflow under:

.github/workflows/

Use one workflow with logically separated jobs unless current repository
conventions strongly favor another structure.

The workflow must trigger on relevant:

- pull requests;
- pushes to develop;
- optionally pushes to main where appropriate.

Use minimal permissions:

contents: read

Add concurrency cancellation for superseded runs when appropriate.

The CI must contain at least these logical jobs.

### Offline job

The offline job must:

1. check out the repository;
2. install the approved Python version;
3. install runtime and development dependencies;
4. run `pip check`;
5. run Alembic head verification;
6. run the complete offline backend suite;
7. ensure live integration variables are not enabled;
8. run static repository checks required by existing tests.

Every pytest invocation still uses:

-B -p no:cacheprovider

### PostgreSQL integration job

The integration job must:

1. start a disposable PostgreSQL service;
2. use a dedicated test database accepted by repository guards;
3. avoid printing the database password;
4. install dependencies;
5. apply Alembic migrations;
6. run API PostgreSQL integration tests;
7. run persistence PostgreSQL integration tests;
8. verify reset and preflight behavior;
9. avoid the protected database name `airmonitor`;
10. leave no external persistent resource.

Use repository guard variables exactly as currently required.

Do not weaken database guards for CI convenience.

### Docker build job

The Docker job must:

1. build the backend image from the canonical Dockerfile;
2. fail on an invalid Dockerfile;
3. optionally inspect the configured non-root user;
4. avoid pushing an image;
5. avoid requiring registry credentials.

A Compose smoke job may be added when it remains stable and provides real
coverage.

Do not create an unreliable CI job that depends on arbitrary sleep delays.

## Stage 8 — local clean-start verification

Use a unique Docker Compose project name beginning with:

airmonitor-v2-test-

Do not reuse or modify unrelated containers.

Do not connect to the protected local `airmonitor` database.

Before starting:

- confirm the Compose configuration;
- inspect sanitized service names and published ports;
- confirm no secret is printed;
- confirm the project owns its own development database volume.

Run a complete clean-start verification:

1. `docker compose config`;
2. build the API image without using an old project container;
3. start the database;
4. wait for the database healthcheck;
5. start the API;
6. confirm Alembic reaches `a75caa2b44f5`;
7. confirm the API healthcheck becomes healthy;
8. request `/health`;
9. request `/openapi.json`;
10. confirm OpenAPI remains 3.1.0 with exactly 11 operations;
11. perform one minimal safe API write/read smoke sequence using disposable
    data when current API contracts make this practical;
12. restart the API container;
13. confirm migrations remain idempotent;
14. confirm the API becomes healthy again;
15. inspect API logs for credential leakage and startup failures;
16. stop the project;
17. remove its containers, networks, and test volume;
18. confirm no matching test container remains.

Use bounded health polling rather than arbitrary long sleep commands.

Do not leave test containers or volumes running.

## Stage 9 — README and deployment documentation

Update the root README.md as the primary onboarding document.

Preserve useful existing project information.

The README must contain:

- project purpose;
- v1 versus v2 distinction;
- current architecture summary;
- current implemented API scope;
- hardware summary;
- repository structure;
- prerequisites;
- Docker Compose quick start;
- local Python development start;
- environment setup;
- Alembic migration commands;
- offline test commands;
- PostgreSQL integration-test commands;
- OpenAPI and health URLs;
- common troubleshooting;
- security and secret-handling notes;
- current limitations;
- roadmap;
- portfolio-oriented technical highlights.

Commands must be directly usable from the repository root unless clearly
marked otherwise.

Do not claim cloud deployment or frontend v2 completion.

Create a focused deployment document only when README would otherwise become
unreasonably large.

Preferred optional document:

docs/guides/backend-local-development.md

Do not duplicate the entire README.

## Stage 10 — production-readiness report

Create:

docs/reviews/production-readiness-final-verification.md

The report must include:

- exact Docker files;
- final image base;
- runtime user;
- startup process;
- migration ownership;
- Compose services;
- healthchecks;
- environment-variable inventory;
- CI workflow inventory;
- clean-start verification result;
- restart and migration-idempotency result;
- offline test result;
- PostgreSQL integration result;
- Docker build result;
- OpenAPI inventory;
- Alembic head;
- dependency check;
- security review;
- limitations;
- cleanup confirmation;
- any blocker without invented success.

Do not include credentials or full database URLs.

## Stage 11 — final verification

After implementation, run all applicable checks.

At minimum:

1. infrastructure contract tests;
2. configuration tests;
3. migration/model tests;
4. integration guard/reset tests;
5. telemetry cursor tests;
6. telemetry query-validation tests;
7. repository tests;
8. service tests;
9. API schema tests;
10. API dependency tests;
11. API route tests;
12. OpenAPI tests;
13. API architecture tests;
14. complete offline backend suite;
15. guarded PostgreSQL API integration suite;
16. guarded PostgreSQL persistence integration suite;
17. pip check;
18. Alembic heads;
19. offline upgrade SQL;
20. offline downgrade SQL;
21. Dockerfile build;
22. Compose configuration validation;
23. clean Compose startup;
24. API health smoke test;
25. OpenAPI smoke test;
26. restart/idempotency test;
27. shell syntax validation where available;
28. YAML parsing or workflow static validation;
29. git diff --check;
30. final-newline checks;
31. secret scans;
32. database URL scans;
33. local absolute-path scans;
34. temporary-artifact scans;
35. Git index verification.

The offline suite must retain:

- zero failures;
- no unexpected additional skips;
- at least the previous 840 passing cases.

Report actual counts.

OpenAPI must remain:

- 3.1.0;
- 11 operations;
- 10 under /api/v1;
- 1 under /health;
- 11 unique operation IDs.

Alembic must retain one head:

a75caa2b44f5

## Security requirements

The final diff must not contain:

- real passwords;
- real database URLs;
- tokens;
- private certificates;
- local database files;
- personal absolute paths;
- credentials in Compose;
- secrets in workflow YAML;
- secrets in README examples;
- generated Docker test credentials;
- protected database names used as test reset targets.

The runtime container must not run as root.

The Compose API must not use privileged mode.

The PostgreSQL development service must not be exposed publicly.

Database guards must remain intact.

## Operational requirements

The API must not start when Alembic migration fails.

The API must become healthy only after startup is complete.

Container restart must not create a second migration head or duplicate schema
objects.

The Compose stack must start from a clean repository clone using documented
commands.

The project must cleanly stop without orphaned containers.

## Allowed changes

Expected changes may include:

- backend/Dockerfile;
- backend/.dockerignore;
- backend/docker-entrypoint.sh;
- compose.yaml;
- safe example environment files;
- .gitignore;
- .github/workflows/backend-ci.yml;
- README.md;
- focused infrastructure tests;
- focused configuration tests;
- docs/guides/backend-local-development.md;
- docs/reviews/production-readiness-final-verification.md.

Narrow application configuration changes are allowed only when required to
support environment-driven container startup.

Do not modify telemetry business logic or public API contracts.

Do not modify existing migrations.

Do not modify legacy v1 application files.

## Scope cleanliness

Do not create or retain:

- tasks scratch files;
- temporary Docker Compose files;
- generated passwords;
- actual .env files;
- database dumps;
- container logs;
- copied virtual environments;
- coverage output;
- test caches;
- temporary shell scripts;
- local certificate files;
- editor metadata.

Remove all temporary Docker resources created by verification.

Do not use `git clean`.

## Final review axes

Review the completed diff for:

1. correctness;
2. readability;
3. architecture;
4. security;
5. operational safety;
6. container correctness;
7. CI reliability;
8. migration safety;
9. documentation accuracy;
10. repository cleanliness.

Resolve all Critical and Required findings before stopping.

## Definition of done

The macro phase is complete only when:

- the backend image builds;
- the image runs as non-root;
- Compose starts API and PostgreSQL from a clean state;
- Alembic migrations run automatically and successfully;
- the API becomes healthy;
- restart remains healthy and migration-safe;
- offline tests pass;
- live PostgreSQL integration tests pass;
- OpenAPI remains unchanged;
- CI workflow covers offline, integration, and Docker build gates;
- README contains reproducible setup instructions;
- no secret or temporary resource remains;
- documentation records actual verification;
- Git index remains unchanged;
- work stops once for external manual review.

Do not stop after Dockerfile completion.

Do not stop after Compose becomes healthy.

Do not stop after CI YAML creation.

Complete the entire approved macro sprint.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8