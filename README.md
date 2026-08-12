# AirMonitor

AirMonitor is a portable air-quality and microclimate monitoring project built
around an M5Stack/ESP32, a PMSA003 particulate sensor, and an SHT30 temperature
and humidity sensor.

The repository intentionally contains two application generations:

- **AirMonitor v1** is the stable legacy diploma application at the repository
  root. It uses Flask, SQLite, the original firmware, and the legacy browser UI.
- **AirMonitor v2** is the active system: firmware lives under `firmware/`, the
  backend under `backend/`, and the dashboard under `frontend/`. It uses
  PlatformIO/Arduino-ESP32, FastAPI, PostgreSQL, React, TypeScript, and Vite.

Root v1 application files are reference material. Current development targets
the v2 backend and does not silently migrate or rewrite the legacy application.

## Current v2 status

The backend currently supports:

- service health;
- device creation, retrieval, activation, and deactivation;
- measurement-session start, active lookup, completion, and cancellation;
- raw-measurement ingestion;
- session and raw-measurement history reads;
- strict query validation and opaque keyset pagination;
- guarded disposable-PostgreSQL integration testing;
- automatic Alembic migration in the container startup path;
- a Russian-language public information site and responsive participant
  application for device setup, sessions, live telemetry, cursor-paginated
  history, charts, and a real-coordinate map of measurement sessions;
- a non-root static frontend runtime with a same-origin API proxy;
- a local three-service Docker Compose stack and frontend/backend CI gates.
- session-aware M5Stack firmware with configurable Wi-Fi/API identity, UTC
  timestamps, idempotent measurement delivery, and a bounded RAM outbox.

The OpenAPI contract is version 3.1.0 with 11 operations: 10 under `/api/v1`
and one under `/health`. All 11 operation IDs are unique. The sole Alembic head
is `a75caa2b44f5`.

## Architecture

The v2 request path is deliberately layered:

```text
FastAPI route
  -> request validation and dependency injection
  -> query or transactional application service
  -> repository
  -> SQLAlchemy AsyncSession
  -> PostgreSQL
```

- The FastAPI application owns its async engine and session factory.
- Each database-backed request receives one request-scoped `AsyncSession`.
- Query services are read-only; write services own transaction boundaries.
- Repositories issue parameterized statements and do not commit or roll back.
- The FastAPI lifespan disposes the application-owned engine at shutdown.
- Alembic owns schema evolution for `devices`, `device_runtime_state`,
  `measurement_sessions`, and `raw_measurements`.
- Telemetry history uses stable descending keyset order and bounded
  `limit + 1` repository reads, never offset pagination.

The browser path keeps transport and presentation concerns separate:

```text
React feature panel
  -> focused hook
  -> typed Fetch client and response validation
  -> same-origin /api or /health request
  -> Vite development proxy or Nginx production proxy
  -> FastAPI
```

- One typed client owns URL joining, JSON parsing, request timeouts, abort
  signals, and safe error normalization.
- Browser storage contains only a versioned, validated numeric device ID and a
  separate strict record of harmless display preferences.
- Geolocation is requested once when a session starts, never on page load or
  during polling.
- Live telemetry uses one completion-scheduled five-second loop, pauses while
  the document is hidden, and never overlaps requests.
- Session and measurement cursors remain opaque. The data layer keeps API
  order; only chart presentation copies are reordered chronologically.
- Leaflet is isolated behind a small map adapter. Each session is represented
  by one geographic marker; no movement or polyline is inferred inside a
  session. Exact telemetry remains available in an accessible table and
  session details remain outside the map.
- `BrowserRouter` provides public routes (`/`, `/about`, `/participate`,
  `/methodology`, `/login`) and participant routes under `/app`; public pages,
  the participant shell, route pages, and Leaflet are loaded through focused
  lazy boundaries.

The local container path is:

```text
Docker Compose
  -> PostgreSQL 18 healthcheck
  -> API entrypoint readiness check
  -> alembic upgrade head
  -> one non-root Uvicorn process
  -> /health container healthcheck
  -> non-root Nginx frontend
  -> /frontend-health container healthcheck
```

For the current MVP, one API container owns startup migration. Do not scale the
API beyond one container until migration ownership moves to a separate one-off
job.

The physical telemetry path is:

```text
PMSA003 + SHT30
  -> M5Stack Basic / ESP32 Firmware v2
  -> Wi-Fi HTTP(S)
  -> FastAPI active-session ingestion
  -> PostgreSQL
  -> frontend live telemetry, history, charts, table, and one-point session map
```

The browser creates and geolocates a session once. Firmware polls that active
session and sends a stationary series; it never creates a session or a route.

## API operations

| Method | Path | Operation ID |
|---|---|---|
| `GET` | `/health` | `get_health_health_get` |
| `POST` | `/api/v1/devices` | `create_device` |
| `GET` | `/api/v1/devices/{device_id}` | `get_device` |
| `PATCH` | `/api/v1/devices/{device_id}/status` | `set_device_status` |
| `POST` | `/api/v1/devices/{device_id}/sessions` | `start_measurement_session` |
| `GET` | `/api/v1/devices/{device_id}/sessions` | `list_device_sessions` |
| `GET` | `/api/v1/devices/{device_id}/sessions/active` | `get_active_measurement_session` |
| `POST` | `/api/v1/devices/{device_id}/sessions/active/complete` | `complete_active_measurement_session` |
| `POST` | `/api/v1/devices/{device_id}/sessions/active/cancel` | `cancel_active_measurement_session` |
| `POST` | `/api/v1/devices/{device_id}/measurements` | `record_raw_measurement` |
| `GET` | `/api/v1/devices/{device_id}/measurements` | `list_device_measurements` |

Telemetry read details, cursor semantics, and index guarantees are documented
in [`docs/specs/telemetry-read-api.md`](docs/specs/telemetry-read-api.md).

## Hardware

| Component | Role |
|---|---|
| M5Stack/ESP32 | Controller, display, and Wi-Fi communication |
| PMSA003 | PM1, PM2.5, PM10, and particle-count measurements |
| SHT30 | Temperature and relative-humidity measurements |
| Portable power source | Mobile monitoring |

The original working firmware remains at the repository root as read-only
reference. The maintained FastAPI-compatible firmware is under `firmware/`.

## Repository layout

```text
AirMonitor/
|-- app.py                         # v1 Flask application
|-- index.html                     # v1 browser UI
|-- init_db.py, schema.sql         # v1 SQLite setup
|-- test1_final.ino                # ESP32 firmware
|-- firmware/                      # v2 PlatformIO firmware and host tests
|-- backend/
|   |-- app/                       # v2 FastAPI application
|   |-- alembic/                   # PostgreSQL migrations
|   |-- tests/                     # offline and guarded live tests
|   |-- Dockerfile                 # canonical runtime image
|   |-- docker-entrypoint.sh       # readiness, migration, Uvicorn
|   |-- .dockerignore
|   |-- .env.example               # host-side Python template
|   |-- requirements.txt           # runtime dependencies
|   `-- requirements-dev.txt       # test dependencies
|-- frontend/
|   |-- src/                       # public site, participant app, typed API/features
|   |-- e2e/                       # deterministic and guarded browser flows
|   |-- Dockerfile, nginx.conf     # production static runtime and API proxy
|   |-- package.json
|   `-- package-lock.json
|-- compose.yaml                   # local frontend + api + db stack
|-- .env.example                   # Compose interpolation template
|-- .github/workflows/backend-ci.yml
`-- docs/
    |-- specs/
    `-- reviews/
```

## Prerequisites

Choose either the Docker path or the local Python path.

For Docker development:

- Docker Desktop or Docker Engine with `docker compose`;
- available loopback ports 8080 and 8000, or alternatives set in `.env`.

For firmware development and upload:

- Python 3.13 and PlatformIO 6.1.18;
- a data-capable USB cable and the board's USB serial driver;
- a LAN/hotspot route from the ESP32 to the computer running FastAPI.

For frontend-only development:

- Node.js 24.19.0 (the supported range is Node 24);
- npm 11 or the npm version bundled with the supported Node release;
- a backend available at `http://127.0.0.1:8000` for real API work.

For host-side development:

- Python 3.13;
- PostgreSQL 18 or another currently compatible PostgreSQL server;
- a dedicated application database and role.

## Docker Compose quick start

Run these commands from the repository root.

1. Create the ignored local Compose environment file.

   PowerShell:

   ```powershell
   Copy-Item .\.env.example .\.env
   ```

   POSIX shell:

   ```sh
   cp .env.example .env
   ```

2. Edit `.env` and replace `POSTGRES_PASSWORD` with a long, local-development
   password. Keep it URL-safe because Compose uses the same value in the async
   database URL. Do not commit `.env`.

3. Validate and start the stack.

   ```sh
   docker compose config --quiet
   docker compose up --build
   ```

Compose starts `db`, waits for PostgreSQL health, runs `alembic upgrade head`
inside `api`, starts Uvicorn only if migration succeeds, and then starts the
frontend after API health. Both application images run as dedicated non-root
users.

The database has no published host port. The unauthenticated API is bound only
to loopback by default:

- dashboard: <http://127.0.0.1:8080/>
- dashboard-routed backend health: <http://127.0.0.1:8080/health>
- direct backend health: <http://127.0.0.1:8000/health>
- direct OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
- direct Swagger UI: <http://127.0.0.1:8000/docs>

Browser JavaScript uses relative `/api/v1/...` and `/health` URLs. Nginx sends
those requests to the container-only `api:8000` address. Never place the
Compose service name `api` in browser configuration: it is resolvable inside
the Compose network, not on the host.

Stop containers while retaining the named development database volume:

```sh
docker compose down
```

Delete this Compose project's development data only when an intentional clean
database is required:

```sh
docker compose down --volumes
```

The second command is destructive for the Compose development volume. It does
not target an independently managed host PostgreSQL database.

## Firmware v2 quick start

Register or select one active device through the frontend first. Copy the safe
firmware example, then set its numeric ID, matching stable UID, Wi-Fi details,
and a FastAPI address reachable from the ESP32:

```powershell
Copy-Item .\firmware\include\firmware_config.example.h `
  .\firmware\include\firmware_config.h
python -m venv .\firmware\.venv
& .\firmware\.venv\Scripts\python.exe -m pip install platformio==6.1.18
$env:PLATFORMIO_CORE_DIR = (Resolve-Path .\firmware).Path + "\.platformio"
& .\firmware\.venv\Scripts\pio.exe run --project-dir .\firmware
```

For local hardware testing, `127.0.0.1` is not usable from the M5Stack. Publish
FastAPI to the trusted LAN/hotspot interface and configure that computer's LAN
address. After flashing, start a frontend session at one point; firmware will
detect it and send stationary measurements. During a short Wi-Fi/API outage it
continues bounded RAM capture for that last-confirmed session, then flushes FIFO
after server re-verification. An explicit completion/cancellation response stops
new capture; records are never rebound to a replacement point/session.

See [`firmware/README.md`](firmware/README.md) for the pin map, upload/serial
commands, exact payload, retry/outbox rules, HTTPS configuration, and hardware
smoke checklist.

## Environment configuration

### Compose interpolation

The root `.env.example` defines only local Compose inputs:

| Variable | Purpose |
|---|---|
| `POSTGRES_DB` | Development database initialized in the `db` service |
| `POSTGRES_USER` | Development database role initialized in the `db` service |
| `POSTGRES_PASSWORD` | Required placeholder; replace in ignored `.env` |
| `AIRMONITOR_API_PORT` | Loopback host port mapped to container port 8000 |
| `AIRMONITOR_FRONTEND_PORT` | Loopback host port mapped to frontend port 8080 |

Compose constructs the application URL with hostname `db`, the Compose service
name. Host-side Python must use `localhost` or another host-reachable database
address instead.

### Frontend settings and URL modes

`VITE_API_BASE_URL` is the only frontend API-base variable. Its default is an
empty string, meaning “use the current browser origin.” That default is the
recommended setup:

| Mode | Browser URL | Browser API URL | Proxy target |
|---|---|---|---|
| Local Vite + local Python | `http://127.0.0.1:5173` | relative `/api` and `/health` | host `http://127.0.0.1:8000` |
| Full Compose | `http://127.0.0.1:8080` | relative `/api` and `/health` | container `http://api:8000` |
| Direct API inspection | not a frontend mode | `http://127.0.0.1:8000` | none |

An absolute `VITE_API_BASE_URL` is accepted for deliberate deployments, but
cross-origin browser requests require an explicit backend CORS policy. The
current backend intentionally has no CORS middleware because the supported
development and Compose paths are same-origin. Vite variables are compiled
into the static bundle; do not put secrets in them.

### Backend settings

`backend/app/core/config.py` defines the application settings contract. Values
use the `AIRMONITOR_` prefix and may be loaded from `backend/.env`.

| Environment variable | Default or policy |
|---|---|
| `AIRMONITOR_APP_NAME` | `AirMonitor API` |
| `AIRMONITOR_APP_VERSION` | `2.0.0` |
| `AIRMONITOR_SERVICE_NAME` | `airmonitor-api` |
| `AIRMONITOR_ENVIRONMENT` | `development`, `test`, or `production` |
| `AIRMONITOR_DEBUG` | `false`; forbidden in production |
| `AIRMONITOR_DATABASE_URL` | Required async `postgresql+asyncpg` target for real use |
| `AIRMONITOR_DATABASE_ECHO` | `false`; forbidden in production |
| `AIRMONITOR_DATABASE_POOL_PRE_PING` | `true` |

Uvicorn receives `UVICORN_HOST` and `UVICORN_PORT` from the real container
environment. They are server-process settings, not duplicate application
settings.

For local Python development, copy `backend/.env.example` to
`backend/.env` and replace all database placeholders. Never commit the real
file.

## Local Python development

The commands below begin at the repository root and use PowerShell.

Create the environment and install development dependencies:

```powershell
py -3.13 -m venv .\backend\.venv
& .\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-dev.txt
Copy-Item .\backend\.env.example .\backend\.env
```

Edit `backend/.env` and replace the database placeholders. Then migrate and
start the API from the backend working directory:

```powershell
Push-Location .\backend
& .\.venv\Scripts\python.exe -B -m alembic upgrade head
& .\.venv\Scripts\python.exe -B -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Stop Uvicorn with Ctrl+C, then return to the repository root:

```powershell
Pop-Location
```

Reload mode is for local development only:

```powershell
Push-Location .\backend
& .\.venv\Scripts\python.exe -B -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Stop Uvicorn with Ctrl+C and run `Pop-Location` when finished.

## Local frontend development

Install the pinned dependency graph and start Vite from the repository root:

```powershell
Push-Location .\frontend
npm ci --no-audit --no-fund
npm run dev
```

Open <http://127.0.0.1:5173>. With the default configuration, Vite proxies
relative `/api` and `/health` requests to a backend running on
`http://127.0.0.1:8000`. Stop Vite with Ctrl+C and run `Pop-Location`.

The public start page is `/`. It explains the real project, methodology,
participation and privacy boundaries without mounting participant API state.
`/login` is deliberately explanatory: the current backend has no account,
credential or token contract, so the disabled preview form sends and stores
nothing.

The participant workflow begins at `/app`:

1. confirm that the system status reads “Система доступна”;
2. open “Моё устройство”, enter an existing numeric device ID or register a
   device UID and optional name;
3. activate the selected device if necessary;
4. start a session and answer the browser's one-time geolocation prompt;
5. observe live telemetry without reloading the page;
6. complete or explicitly confirm cancellation of the session;
7. select a historical session, filter or load more with cursor pagination,
   and inspect its chart, exact-value table, and map position.

The selected device ID is restored from the versioned
`airmonitor.frontend.v2.device-id` browser-storage record. Use “Очистить выбор”
to remove it. No credential, cursor content, backend trace, or geolocation
history is stored by the frontend.

Local display preferences use the separate
`airmonitor.frontend.v2.preferences` record. Settings cover system/light/dark
theme, display density, motion, 12/24-hour time, a bounded 5/10/30-second
polling interval and OSM tile loading. Valid version 1 records migrate to the
system theme; unknown or corrupt records reset to safe defaults. “Сбросить
настройки отображения” removes the record.

Geolocation errors are intentionally separate from backend errors. Permission
denial, timeout, unavailable location, and unsupported-browser states are shown
without fabricating coordinates. The dashboard uses one position only for the
session-start request and does not continuously track the browser.

One session always represents one stationary geographic point. Keep the sensor
in place while it collects a series of values. To study another place, finish
the current session, move the device, and start a new session.

Live telemetry requests only the newest measurement (`limit=1`) about every
five seconds. An empty result is a valid state. The last successful result
remains visible during a temporary failure and becomes visibly stale when
updates stop. Polling pauses while the page is hidden and resumes without a
full reload or a new geolocation request.

## Alembic migrations

Run migration commands from `backend/` so application imports resolve using the
same convention as container startup:

```powershell
Push-Location .\backend
& .\.venv\Scripts\python.exe -B -m alembic heads
& .\.venv\Scripts\python.exe -B -m alembic upgrade head
Pop-Location
```

The expected single head is `a75caa2b44f5`. Container startup owns migration
for the one-container MVP. A migration failure terminates the entrypoint, so the
API never starts and never becomes healthy.

Do not downgrade, truncate, drop, or recreate a real application database as a
test. Downgrade verification belongs only on a disposable target or in offline
SQL generation.

## Tests

Every pytest command must disable bytecode creation and pytest's cache provider.
Run from the repository root:

```powershell
Push-Location .\backend
& .\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider
Pop-Location
```

Focused health, OpenAPI, and infrastructure contracts:

```powershell
Push-Location .\backend
& .\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_health.py tests/test_api_openapi.py tests/test_production_readiness_infrastructure.py
Pop-Location
```

Frontend type, unit, build, and browser gates:

```powershell
Push-Location .\frontend
npm ci --no-audit --no-fund
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
Pop-Location
```

Firmware host-logic and M5Stack build gates:

```powershell
g++ -std=c++17 -Wall -Wextra -Werror -I .\firmware\include `
  .\firmware\src\firmware_logic.cpp `
  .\firmware\test\native\test_firmware_logic.cpp `
  -o .\firmware\test\native\firmware_logic_tests.exe
& .\firmware\test\native\firmware_logic_tests.exe
python -B -m unittest firmware.test.static.test_firmware_source -v

$env:PLATFORMIO_CORE_DIR = (Resolve-Path .\firmware).Path + "\.platformio"
& .\firmware\.venv\Scripts\pio.exe run --project-dir .\firmware
```

The ordinary Playwright suite uses deterministic route fixtures, mocked
geolocation, and deterministic map tiles. It covers all public and participant
routes, honest no-op login, health, device selection and registration, storage
restore, session start/denial/completion, live updates without reload, opaque
cursor load-more, statistics/chart/table/map rendering, safe server errors,
mobile navigation, narrow layout, modal keyboard behavior, and axe scans of
representative public, app, table, and dialog states. Separate specs are
guarded for screenshot capture, disposable Compose smoke, and restart recovery;
they do not run against an arbitrary local database.

Build or inspect the frontend image independently:

```powershell
docker build --file .\frontend\Dockerfile --tag airmonitor-frontend:local .\frontend
docker image inspect --format '{{.Config.User}}' airmonitor-frontend:local
```

Dependency consistency:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m pip check
```

Ordinary offline runs must leave all live integration variables unset. The two
live modules then skip by design.

### Guarded PostgreSQL integration tests

Live suites are destructive to their dedicated disposable test database: they
verify the expected schema/head and truncate all four application tables before
and after the suite. Never point them at an application or development target.

Accepted targets use the asyncpg driver, `localhost` or `127.0.0.1`, and an
approved database-name prefix:

| Suite | Variable | Required database-name prefix |
|---|---|---|
| API | `AIRMONITOR_API_TEST_DATABASE_URL` | `airmonitor_api_test_` |
| Persistence | `AIRMONITOR_TEST_DATABASE_URL` plus `AIRMONITOR_RUN_PERSISTENCE_INTEGRATION=1` | `airmonitor_persistence_test_` or `airmonitor_api_test_` |

After securely providing a migrated disposable target, run:

```powershell
if ([string]::IsNullOrWhiteSpace($env:AIRMONITOR_API_TEST_DATABASE_URL)) {
    throw "Set the dedicated API integration database URL first."
}
if ([string]::IsNullOrWhiteSpace($env:AIRMONITOR_TEST_DATABASE_URL)) {
    throw "Set the dedicated persistence integration database URL first."
}

Push-Location .\backend
try {
    & .\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_api_integration.py
    if ($LASTEXITCODE -ne 0) {
        throw "API integration tests failed."
    }

    $env:AIRMONITOR_RUN_PERSISTENCE_INTEGRATION = "1"
    & .\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider tests/test_persistence_integration.py
    if ($LASTEXITCODE -ne 0) {
        throw "Persistence integration tests failed."
    }
} finally {
    Remove-Item Env:AIRMONITOR_RUN_PERSISTENCE_INTEGRATION -ErrorAction SilentlyContinue
    Pop-Location
}
```

The repository guards reject remote hosts, the protected database name,
unapproved prefixes, target-changing query parameters, and unavailable targets
without exposing connection details.

## Continuous integration

`.github/workflows/backend-ci.yml` runs on relevant pull requests and pushes to
`develop`, with workflow-level `contents: read` permission and superseded-run
cancellation.

Its independent jobs are:

- **Frontend gates:** Node 24.19.0, deterministic `npm ci`, TypeScript,
  Vitest, production build, pinned Chromium, deterministic Playwright, failure
  diagnostics, frontend image build, and non-root runtime-user inspection.
- **Offline backend tests:** Python 3.13, runtime/development dependencies,
  `pip check`, exact Alembic-head validation, and the complete offline suite
  with live variables explicitly empty.
- **Guarded PostgreSQL integration:** disposable PostgreSQL 18.4 with a health
  gate, Alembic migration, guard/reset checks, API integration, and persistence
  integration against one approved API-prefixed test database.
- **Backend image build:** builds `backend/Dockerfile`, does not push it, and
  inspects the configured runtime user to reject root execution.
- **Firmware gates:** compiles and runs pure C++17 state/queue/retry tests, then
  builds the pinned M5Stack PlatformIO environment from the safe example config.

GitHub-hosted CI cannot be executed locally. The same dependency, type, test,
browser, migration, and Docker build commands are reproducible locally. The
full three-service Compose smoke/restart workflow is recorded separately in
the frontend final-verification report.

## Troubleshooting

### Compose reports a missing variable

Copy the root `.env.example` to `.env` and replace the password placeholder.
Compose intentionally refuses to invent database credentials.

### The API cannot reach PostgreSQL

- In Compose, the database hostname is `db`, not `localhost`.
- From host-side Python, use a host-reachable address such as `localhost`, not
  the Compose-only service name.
- Check `docker compose ps` and sanitized API/database logs.

### Credentials changed but the database still uses old values

PostgreSQL initialization variables apply only to an empty data directory. If
the Compose data is disposable, stop the stack and intentionally run
`docker compose down --volumes`, then start again. Do not use
that cleanup pattern on independently managed databases.

### The API container exits before serving requests

Inspect `docker compose logs api`. A bounded database-readiness
failure or Alembic failure intentionally prevents Uvicorn from starting. Fix
the target or migration problem; do not bypass the entrypoint.

### Port 8000 is already in use

Set `AIRMONITOR_API_PORT` in the root `.env` to another unused host port. The
container still listens on port 8000.

### Port 8080 is already in use

Set `AIRMONITOR_FRONTEND_PORT` in the root `.env` to another unused loopback
port and open that port in the browser. The frontend container still listens
on port 8080.

### The dashboard loads but reports that the backend is unavailable

- With Vite, verify the host backend at <http://127.0.0.1:8000/health> and do
  not set `VITE_API_BASE_URL` to the Compose service name.
- With Compose, verify `docker compose ps`; frontend health depends on API
  health, and the API depends on database health and successful migrations.
- A cross-origin absolute API base is not the default path and will require
  explicit backend CORS configuration.

### Geolocation is denied or times out

Geolocation is requested only after “Начать сессию.” Allow location access for
the current loopback origin in browser site settings and retry. A location
failure does not imply that the backend is unavailable, and the application
does not substitute synthetic coordinates.

### The map has no tiles

The session list and coordinates remain usable, but the Leaflet basemap needs
internet access to `tile.openstreetmap.org`. Ad blockers, offline operation, or
tile-service availability can prevent tiles from loading. OpenStreetMap
attribution must remain visible; do not remove it when changing map styling.

## Security and operational boundaries

- AirMonitor v2 has no authentication, authorization, or rate limiting.
  Public internet exposure is not approved.
- The Compose API port is loopback-bound and PostgreSQL is not published.
- The API container runs as UID/GID 10001; the frontend runs as UID/GID 101.
  Both enable `no-new-privileges`, and the frontend filesystem is read-only
  except for a small `noexec` `/tmp` tmpfs.
- Nginx applies a restrictive content-security policy and proxies only `/api/`
  plus exact `/health`; API failures cannot fall through to the SPA shell.
- Browser responses are contract-validated, complete backend exceptions are
  never rendered, and the UI uses no unsafe HTML injection.
- The only third-party browser traffic is the documented OpenStreetMap tile
  request when the map is visible. Browser geolocation is not sent to the tile
  service by application code.
- Real `.env` files, credentials, certificates, database files, logs, caches,
  and local virtual environments are excluded from Git and/or Docker context.
- Database values are passed through environment variables for this local
  development stack. A production deployment must use its platform's secret
  manager and a separately designed migration owner.
- `/health` is process liveness. Container startup proves migrations completed,
  but the endpoint does not continuously query PostgreSQL.

## Current limitations and roadmap

Not implemented in v2:

- authentication, authorization, and rate limiting;
- HTTPS termination or an internet-facing gateway;
- cloud deployment, Kubernetes, or multi-replica migration coordination;
- monitoring-platform integration and background workers;
- Redis, MQTT, WebSockets, retention automation, CSV export, or forecasting
  changes;
- a device collection browser—the MVP selects or registers one device ID;
- offline map tiles—the dashboard's list/table functions remain available
  when OpenStreetMap tiles cannot load;
- browser-side measurement ingestion—the dashboard reads telemetry, while the
  existing ingestion API remains available to approved producers.

- Persistent firmware outbox and end-user Wi-Fi provisioning are not included;
  current firmware uses a bounded RAM queue and ignored compile-time config.
- Official AQI/NowCast interpretation is not included; the M5Stack reports raw
  instantaneous PM mass concentration without health-category wording.

Next production-facing work should design identity/access control first, then
external secret management, separated migration ownership, HTTPS gateway
deployment, and observability.

## Technical highlights

- Typed environment configuration with production-only safety validation.
- Async request-scoped persistence with explicit service transaction ownership.
- Composite same-device foreign keys and reversible Alembic migrations.
- Opaque filter-bound keyset cursors and PostgreSQL-backed index-plan evidence.
- Typed, abortable frontend transport; one-shot geolocation; non-overlapping
  visibility-aware polling; bounded cursor history; accessible SVG charts; and
  an isolated Leaflet map.
- Guarded integration suites that reject unsafe database targets before engine
  construction and sanitize unavailable-target failures.
- Two non-root application images, health-gated three-service Compose startup,
  automatic migration, restart-safe schema handling, deterministic browser
  tests, and preserved backend CI gates.
- Session-aware M5Stack ingestion with verified device identity, UTC timestamps,
  stable per-capture IDs, last-confirmed-session offline capture, bounded
  backoff, and backend-enforced cross-session isolation.

## Documentation

- [`firmware/README.md`](firmware/README.md) — firmware wiring, configuration,
  build/upload, runtime states, failure behaviour, and hardware checklist.
- [`docs/specs/firmware-v2-api.md`](docs/specs/firmware-v2-api.md) — exact
  code-derived FastAPI contract used by the device.

- [`docs/specs/telemetry-read-api.md`](docs/specs/telemetry-read-api.md) —
  implemented telemetry-read contract.
- [`docs/reviews/telemetry-read-api-final-verification.md`](docs/reviews/telemetry-read-api-final-verification.md)
  — telemetry implementation and PostgreSQL evidence.
- [`docs/reviews/production-readiness-source-research.md`](docs/reviews/production-readiness-source-research.md)
  — official-source implementation constraints.
- [`docs/reviews/production-readiness-final-verification.md`](docs/reviews/production-readiness-final-verification.md)
  — checkout-specific production-readiness results.
- [`docs/reviews/frontend-v2-source-research.md`](docs/reviews/frontend-v2-source-research.md)
  — official-source frontend implementation constraints and pinned versions.
- [`docs/reviews/frontend-v2-api-compatibility.md`](docs/reviews/frontend-v2-api-compatibility.md)
  — checkout-derived mapping of all 11 operations to frontend workflows.
- [`docs/reviews/frontend-v2-final-verification.md`](docs/reviews/frontend-v2-final-verification.md)
  — frontend architecture, UX, security, browser, Docker, Compose, restart,
  and cleanup evidence.

## License

AirMonitor is available under the MIT License. See `LICENSE`.
