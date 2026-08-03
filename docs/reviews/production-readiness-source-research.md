# Production-Readiness Source Research

**Research date:** 2026-08-03

**Scope:** implementation-relevant Docker, Compose, PostgreSQL, Uvicorn,
Alembic, and GitHub Actions behavior

**Source policy:** official project documentation, official image metadata, and
first-party action repositories only

This is an implementation input, not a verification report. It records only
external facts that materially constrain the AirMonitor production-readiness
work.

## 1. Checkout facts that constrain the design

The inspected revision was `d19238abf2d0d7a327a58a14ff51a4a8cea76c58`.
The approved local interpreter reported Python 3.13.7, and the migration graph
reported one head, `a75caa2b44f5`.

The declared backend stack is:

| Component | Declared version |
|---|---:|
| FastAPI | 0.139.1 |
| pydantic-settings | 2.14.2 |
| Uvicorn | 0.51.0 |
| SQLAlchemy asyncio | 2.0.51 |
| asyncpg | 0.31.0 |
| Alembic | 1.18.5 |
| httpx2, development only | 2.7.0 |
| pytest, development only | 8.4.2 |

Repository consequences:

- `backend/requirements.txt` is the runtime dependency boundary.
  `backend/requirements-dev.txt` includes it and then adds test dependencies,
  so a runtime image must install only the former.
- `backend/app/core/config.py` accepts the existing `AIRMONITOR_*` settings and
  requires an async `postgresql+asyncpg` application URL. Container host and
  port settings should therefore use Uvicorn's own variables rather than add a
  second application-settings contract.
- Online Alembic execution obtains the same application database setting in
  `backend/alembic/env.py`; the entrypoint does not need a competing migration
  URL variable.
- `/health` is intentionally a process liveness endpoint and does not query
  PostgreSQL. Because the entrypoint runs migrations synchronously before it
  starts Uvicorn, the endpoint cannot become reachable after a migration
  failure.
- The integration guards accept only `localhost` or `127.0.0.1`. API database
  names must start with `airmonitor_api_test_`; the persistence guard accepts
  that prefix as well as `airmonitor_persistence_test_`. A runner-hosted CI job
  can therefore use one disposable API-prefixed database for both suites,
  sequentially, without weakening either guard.

## 2. Backend image and process model

### Base image

`python:3.13-slim` is a current supported Docker Official Image tag; on the
research date the official tag inventory also listed the patch-specific
`3.13.14-slim` variants. The moving major/minor tag matches AirMonitor's Python
3.13 contract while receiving later 3.13 patch-image updates. The official
image documentation warns that `slim` contains only the minimal Debian
packages needed to run Python, so `pip install` can fail when a dependency has
no suitable wheel and requires native compilation. The Docker build is the
required proof that the pinned AirMonitor dependency set needs no compiler in
the final image. [Python Official Image](https://hub.docker.com/_/python)

### Non-root runtime and deterministic metadata

Create a dedicated user and place `USER` after all root-only install/copy
steps. Docker specifies that `USER` controls subsequent build steps and the
runtime `ENTRYPOINT` and `CMD`. Set an explicit `WORKDIR`; Docker recommends
this to avoid operating in an inherited or unknown directory.
[Dockerfile `USER` and `WORKDIR`](https://docs.docker.com/reference/dockerfile/#user)

`EXPOSE 8000` documents the listener but does not publish it to the host;
publication remains a Compose/runtime choice.
[Dockerfile `EXPOSE`](https://docs.docker.com/reference/dockerfile/#expose)

### Entrypoint and signals

Use exec-form Docker metadata, for example an exec-form entrypoint plus an
exec-form default command. Docker's exec form avoids an implicit shell, and an
entrypoint script must finish with `exec "$@"` so Uvicorn replaces the shell
as PID 1 and receives termination signals.
[Dockerfile shell and exec forms](https://docs.docker.com/reference/dockerfile/#shell-and-exec-form),
[entrypoint signal handling](https://docs.docker.com/reference/dockerfile/#exec-form-entrypoint-example)

The startup sequence should be:

1. enable fail-fast shell behavior;
2. run `python -m alembic -c alembic.ini upgrade head`;
3. only on success, `exec` the supplied Uvicorn command.

Alembic 1.18.5 defines `upgrade(..., "head")` as upgrading to the later target
revision. AirMonitor already has exactly one script head, so `head` is
unambiguous. A non-zero migration command must terminate the entrypoint before
the API starts.
[Alembic 1.18.5 upgrade command](https://alembic.sqlalchemy.org/en/latest/api/commands.html#alembic.command.upgrade)

### One server process and migration ownership

Run one Uvicorn process and no reload mode or multi-worker process manager.
FastAPI and Uvicorn both recommend a single process per container when the
container/orchestrator owns replication. FastAPI also documents that a simple
single-container deployment may perform prerequisite steps immediately before
starting the app. This makes one API container a valid migration owner for the
current MVP, but it is an explicit no-scaling limitation: migration ownership
must move to a separate one-off job before multiple API replicas are started.
[FastAPI: one process per container](https://fastapi.tiangolo.com/deployment/docker/#one-process-per-container),
[FastAPI: previous steps before startup](https://fastapi.tiangolo.com/deployment/docker/#previous-steps-before-starting-and-containers),
[Uvicorn Docker guidance](https://www.uvicorn.org/deployment/docker/)

Uvicorn recognizes `UVICORN_HOST` and `UVICORN_PORT` from the real process
environment. Its defaults are `127.0.0.1` and `8000`, so a container must set
the host to `0.0.0.0`. CLI options override environment variables, and
`UVICORN_*` variables are not loaded from a file passed through Uvicorn's
`--env-file`; Compose must inject them as container environment values (or the
command must pass explicit CLI flags).
[Uvicorn configuration methods and socket binding](https://www.uvicorn.org/settings/#configuration-methods)

## 3. Compose and PostgreSQL 18

### Startup dependency and health

Use long-form `depends_on` with `condition: service_healthy`. Compose creates
dependencies in order but waits for readiness only when the dependency is
marked `service_healthy`. The official Docker example for PostgreSQL 18 uses a
bounded `pg_isready` healthcheck for exactly this purpose.
[Docker Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/)

The database healthcheck should use the configured user and database. Escape
container-side variables as `$${...}` so Compose does not substitute them on
the host. PostgreSQL 18 documents `pg_isready` exit code 0 as accepting
connections, 1 as rejecting connections during startup, 2 as no response, and
3 as no attempt. Correct credentials are not required merely to detect server
status, but invalid names cause noisy failed-connection log entries.
[Compose interpolation](https://docs.docker.com/reference/compose-file/interpolation/),
[PostgreSQL 18 `pg_isready`](https://www.postgresql.org/docs/18/app-pg-isready.html)

The API healthcheck should request the existing `/health` endpoint. A Python
standard-library probe avoids adding `curl` solely for health checking to the
minimal Python image. Compose healthchecks use Docker `HEALTHCHECK` semantics:
exit 0 is healthy, exit 1 is unhealthy, and interval, timeout, start period,
and retry count are bounded controls.
[Compose service healthcheck](https://docs.docker.com/reference/compose-file/services/#healthcheck),
[Dockerfile `HEALTHCHECK`](https://docs.docker.com/reference/dockerfile/#healthcheck)

Compose health gating is sufficient for the development stack, so an extra
entrypoint retry loop is unnecessary. A standalone API container remains
usable when its database is already ready and otherwise fails promptly at the
migration step instead of retrying forever.

### Networking and published ports

Compose gives services a default network and stable DNS names. The API must
connect to `db:5432`, not `localhost`; service-to-service traffic uses the
container port. Host port publication is only needed for traffic originating
outside the Compose network. Therefore:

- publish no database port;
- publish only the API port, preferably bound to `127.0.0.1` for this
  unauthenticated local-development service;
- do not add custom networks or legacy links.

[Docker Compose networking](https://docs.docker.com/compose/how-tos/networking/),
[Compose port `host_ip`](https://docs.docker.com/reference/compose-file/services/#ports)

### Interpolation and environment boundary

Use `${VAR:?message}` for a required, externally supplied local-development
credential; Compose exits with an error when the variable is absent or empty.
Defaults are appropriate only for non-sensitive settings. A Compose `.env`
file supplies interpolation values but does not automatically place every
value in the container; the service `environment` mapping must explicitly pass
the supported values.
[Compose interpolation forms](https://docs.docker.com/reference/compose-file/interpolation/),
[setting container environment values](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/)

The official Docker guidance prefers secrets over environment variables for
sensitive production data. This repository's requested stack is explicitly a
local development stack and forbids secret mounts, so external interpolation
with no committed real value is a scoped development compromise, not a cloud
or production secret-management recommendation.

`POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` belong to the official
database image and do not duplicate AirMonitor's application setting. Pass the
application only its existing `AIRMONITOR_DATABASE_URL` plus its other existing
`AIRMONITOR_*` settings and Uvicorn's host/port variables.

### PostgreSQL 18 image and data volume

`postgres:18` is a supported Docker Official Image tag (the current
patch-specific tag on the research date was 18.4). The image requires a
non-empty `POSTGRES_PASSWORD` unless `POSTGRES_HOST_AUTH_METHOD=trust` is used;
the official image explicitly advises against `trust`. `POSTGRES_USER` and
`POSTGRES_DB` are optional initialization controls. These variables apply only
when the data directory is empty, so changing them does not rewrite an
existing named volume.
[PostgreSQL Official Image tags and environment variables](https://hub.docker.com/_/postgres)

PostgreSQL 18 changed the official image layout: `PGDATA` is
`/var/lib/postgresql/18/docker`, and the declared volume target is now
`/var/lib/postgresql`. Mount the Compose named volume at
`/var/lib/postgresql`, not the pre-18 `/var/lib/postgresql/data` path. Compose
creates a declared named volume on `up` and reuses it until explicitly
removed.
[PostgreSQL 18 `PGDATA` change](https://hub.docker.com/_/postgres),
[Compose named volumes](https://docs.docker.com/reference/compose-file/volumes/)

## 4. GitHub Actions backend CI

### Current official action majors

As of 2026-08-03, the official first-party repositories document:

| Action | Current stable release | Workflow major tag |
|---|---:|---:|
| `actions/checkout` | 7.0.1 | `actions/checkout@v7` |
| `actions/setup-python` | 7.0.0 | `actions/setup-python@v7` |

The setup-python v7 README uses both v7 actions and explicitly sets
`python-version: '3.13'`; it warns that relying on the runner's PATH can change
unexpectedly. Use the explicit 3.13 input in every Python job.
[checkout repository and usage](https://github.com/actions/checkout),
[checkout releases](https://github.com/actions/checkout/releases),
[setup-python repository and usage](https://github.com/actions/setup-python),
[setup-python releases](https://github.com/actions/setup-python/releases)

Major tags are the official readable usage. GitHub's stronger supply-chain
guidance says a full-length commit SHA is the only immutable action reference.
If the repository adopts SHA pinning, resolve each current v7 release to its
verified upstream commit and retain the major/version in a comment; do not
invent or copy an unverified SHA.
[GitHub secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use)

### PostgreSQL service job shape

Run integration tests directly on `ubuntu-latest`, not inside a job container.
GitHub documents that runner-hosted jobs access a service through `localhost`
only after mapping the service port; container jobs instead use the service
label as hostname. The runner-hosted form is required by AirMonitor's existing
localhost-only guards. Map the disposable service's 5432 port, use the
accepted API-test database prefix, and apply Alembic before the guarded suites.

GitHub's PostgreSQL service example uses Docker health options
`--health-cmd`, `--health-interval`, `--health-timeout`, and
`--health-retries`, so no arbitrary sleep is needed. The example's literal
test credential demonstrates service mechanics only; AirMonitor must not copy
it as a real credential, expose a connection value, or echo either guarded
database variable.
[GitHub PostgreSQL service containers](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers)

### Permissions and cancellation

Set workflow-level `permissions: contents: read`. GitHub documents that once
specific permissions are declared, unspecified permissions become `none`, and
both checkout and setup-python recommend `contents: read`.
[GitHub workflow permissions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions),
[checkout recommended permissions](https://github.com/actions/checkout#recommended-permissions),
[setup-python recommended permissions](https://github.com/actions/setup-python#recommended-permissions)

Use a workflow-scoped concurrency group such as the workflow name plus Git
reference, with `cancel-in-progress: true`, so a newer run supersedes an older
run only for the same workflow/ref and does not cancel unrelated workflows.
[GitHub Actions concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)

## 5. Implementation decisions supported by the sources

1. Build the backend from `python:3.13-slim`, install only
   `backend/requirements.txt`, and prove the slim image is sufficient by
   building it.
2. Run as a dedicated non-root user with an explicit working directory and
   exec-form process metadata.
3. Let one API container run `alembic upgrade head`, then `exec` one Uvicorn
   process bound to `0.0.0.0:8000`; do not enable reload or workers.
4. Use Compose `api` and `db` services, database `service_healthy` gating,
   bounded healthchecks, no database host-port publication, and only a
   loopback-bound API host port.
5. Use `postgres:18` and mount its named volume at
   `/var/lib/postgresql`.
6. Require the local-development database credential through Compose
   interpolation, commit placeholders only, and explicitly pass the existing
   AirMonitor settings into the API container.
7. Use `actions/checkout@v7`, `actions/setup-python@v7`, Python 3.13,
   `permissions: contents: read`, ref-scoped cancellation, and a runner-hosted
   PostgreSQL 18 service with health options and a localhost port mapping.
8. Treat clean Compose startup, restart, image-user inspection, migrations,
   `/health`, OpenAPI, and guarded PostgreSQL suites as verification evidence;
   none of those outcomes is established by source research alone.
