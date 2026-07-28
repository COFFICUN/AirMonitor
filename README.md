# AirMonitor

AirMonitor is a portable air-quality and microclimate monitoring project built
around an M5Stack/ESP32 device, a PMSA003 particulate sensor, and an SHT30
temperature and humidity sensor.

The repository contains two deliberately separate application generations:

- **AirMonitor v1** is the stable legacy diploma implementation at the
  repository root. It uses Flask, SQLite, the original firmware, and the
  legacy browser dashboard.
- **AirMonitor v2** is the active backend under `backend/`. It uses FastAPI,
  PostgreSQL, SQLAlchemy asyncio, Alembic, Pydantic settings, and pytest.

The `main` branch is the stable legacy line. AirMonitor v2 development is based
on `develop` and uses focused feature, fix, test, and documentation branches.
Root v1 files remain reference material unless a change explicitly targets
the legacy application.

## Repository layout

```text
AirMonitor/
├── app.py                    # AirMonitor v1 Flask application
├── index.html                # AirMonitor v1 browser dashboard
├── init_db.py                # AirMonitor v1 SQLite initialization
├── schema.sql                # AirMonitor v1 SQLite schema
├── test1_final.ino           # M5Stack/ESP32 firmware
├── secrets.example.h         # Firmware credential template
├── requirements.txt          # AirMonitor v1 requirements
├── backend/
│   ├── app/                  # AirMonitor v2 FastAPI application
│   ├── alembic/              # PostgreSQL migrations
│   ├── tests/                # Offline and opt-in integration tests
│   ├── .env.example          # v2 settings template
│   ├── requirements.txt      # v2 runtime requirements
│   └── requirements-dev.txt  # v2 test requirements
└── docs/
    ├── reviews/              # Audit and verification records
    └── specs/                # Approved future contracts
```

## Hardware context

The physical monitor combines:

| Component | Role |
|---|---|
| M5Stack/ESP32 | Controller, display, and Wi-Fi communication |
| PMSA003 | PM1, PM2.5, PM10, and particle-count measurements |
| SHT30 | Temperature and relative-humidity measurements |
| Portable power source | Mobile monitoring |

AirMonitor is intended for mobile collection of air-quality and local
microclimate readings. The legacy firmware and UI remain at the repository
root. AirMonitor v2 currently provides the backend write and lifecycle
foundation; it does not yet replace every v1 dashboard or analytical feature.

## AirMonitor v2 architecture

AirMonitor v2 is a modular asynchronous API:

```text
FastAPI route
  -> request validation and dependency injection
  -> query or transactional application service
  -> repository
  -> SQLAlchemy AsyncSession
  -> PostgreSQL
```

- The FastAPI application owns its database engine and async session factory.
- Each database-backed request receives one request-scoped `AsyncSession`.
- Query services are read-only; write services own transaction boundaries.
- SQLAlchemy repositories issue parameterized statements and never own
  commits or rollbacks.
- The FastAPI lifespan disposes the application-owned async engine at
  shutdown.
- Alembic owns PostgreSQL schema evolution. The current sole head is
  `a4f9c2e7d1b6`.
- Pydantic validates request bodies and environment-backed settings.
- pytest covers schemas, services, repositories, routes, errors, migrations,
  application composition, and guarded integration behavior.

The implemented v2 domain uses four PostgreSQL tables:

- `devices`
- `device_runtime_state`
- `measurement_sessions`
- `raw_measurements`

## Current v2 capabilities

The current backend implements:

- service health;
- device creation and retrieval;
- device activation and deactivation;
- measurement-session start and active-session retrieval;
- session completion and cancellation;
- raw measurement ingestion;
- stable `ErrorResponse` envelopes for validation, domain, framework, and
  unexpected failures;
- timezone-aware timestamp normalization to UTC;
- rejection of measurements before their session start;
- rejection of terminal timestamps before the session start or latest stored
  measurement;
- rejection of non-finite PM values;
- PostgreSQL `INTEGER` boundaries for public device IDs and particle counts;
- application-owned async engine/session lifecycle.

Raw measurement history and session history list endpoints are **not currently
implemented**. Their approved future design is documented in
`docs/specs/telemetry-read-api.md`.

## Current v2 OpenAPI operations

The guarded offline OpenAPI schema is version `3.1.0` and currently contains
exactly nine operations: eight under `/api/v1` and one health operation.
Operation IDs are unique.

| Method | Path | Operation ID | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/devices` | `create_device` | Create a device and runtime state |
| `GET` | `/api/v1/devices/{device_id}` | `get_device` | Retrieve a device |
| `PATCH` | `/api/v1/devices/{device_id}/status` | `set_device_status` | Activate or deactivate a device |
| `POST` | `/api/v1/devices/{device_id}/sessions` | `start_measurement_session` | Start a measurement session |
| `GET` | `/api/v1/devices/{device_id}/sessions/active` | `get_active_measurement_session` | Retrieve the active session |
| `POST` | `/api/v1/devices/{device_id}/sessions/active/complete` | `complete_active_measurement_session` | Complete the active session |
| `POST` | `/api/v1/devices/{device_id}/sessions/active/cancel` | `cancel_active_measurement_session` | Cancel the active session |
| `POST` | `/api/v1/devices/{device_id}/measurements` | `record_raw_measurement` | Store one raw reading |
| `GET` | `/health` | `get_health_health_get` | Return service health |

Every current v2 path is fixed in source. There is no supported configurable
API-prefix setting.

## Supported v2 settings

`backend/app/core/config.py` defines the complete supported settings contract.
Settings use the `AIRMONITOR_` environment prefix and may be loaded from
`backend/.env`.

| Environment variable | Settings field | Type/default or policy |
|---|---|---|
| `AIRMONITOR_APP_NAME` | `app_name` | String; default `AirMonitor API` |
| `AIRMONITOR_APP_VERSION` | `app_version` | String; default `2.0.0` |
| `AIRMONITOR_SERVICE_NAME` | `service_name` | String; default `airmonitor-api` |
| `AIRMONITOR_ENVIRONMENT` | `environment` | `development`, `test`, or `production`; default `development` |
| `AIRMONITOR_DEBUG` | `debug` | Boolean; default `false`; forbidden in production |
| `AIRMONITOR_DATABASE_URL` | `database_url` | PostgreSQL with the `postgresql+asyncpg` driver; configure locally without committing it |
| `AIRMONITOR_DATABASE_ECHO` | `database_echo` | Boolean; default `false`; forbidden in production |
| `AIRMONITOR_DATABASE_POOL_PRE_PING` | `database_pool_pre_ping` | Boolean; default `true` |

Production settings must identify one explicit non-default database target and
must not use ambiguous target overrides. SQLAlchemy hides parameter values in
engine errors and logs. No additional API-prefix setting is supported.

## AirMonitor v2 setup on Windows

Run these commands from the repository root.

### 1. Create the Python environment

AirMonitor v2 supports Python 3.13. The verified development environment uses
Python 3.13.7.

```powershell
cd .\backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Use `requirements.txt` instead when only runtime dependencies are needed.
The repository currently has no machine-readable Python-version pin or
transitive lock file.

### 2. Prepare PostgreSQL

Using an administrator connection outside the application:

1. create a dedicated application role;
2. create a PostgreSQL database owned by that role;
3. grant only the privileges required by the application and migrations;
4. keep the role password and connection URL outside Git.

Do not reuse an integration-test database as an application database.

### 3. Configure the environment

```powershell
Copy-Item .\.env.example .\.env
```

Edit `.env` locally and set the eight supported variables listed above. At
minimum, replace the development database configuration with the dedicated
target prepared for this environment. Treat `.env.example` only as a template.

### 4. Apply migrations

```powershell
python -B -m alembic -c alembic.ini upgrade head
```

The expected head is `a4f9c2e7d1b6`.

### 5. Start the API

```powershell
python -B -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Development-only reload can be enabled with Uvicorn's `--reload` option. Do
not use reload mode as a production deployment strategy.

### 6. Verify health

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The response contains `status`, `service`, and `version`. Health is a liveness
check; it does not prove database readiness.

## Tests and verification

Run tests from `backend/`. Every pytest invocation must disable bytecode cache
effects and pytest's cache provider.

Focused offline checks:

```powershell
python -B -m pytest -q -p no:cacheprovider tests/test_health.py tests/test_api_openapi.py
```

Complete offline suite:

```powershell
python -B -m pytest -q -p no:cacheprovider
```

Dependency consistency:

```powershell
python -B -m pip check
```

The offline suite skips live PostgreSQL modules unless their dedicated opt-ins
are supplied.

### Live integration safety

Live integration is explicit opt-in only and must use dedicated, disposable
local PostgreSQL databases. Never point these suites at the protected
application or development database.

| Suite | Activation | Required database-name prefix |
|---|---|---|
| Persistence | Set `AIRMONITOR_RUN_PERSISTENCE_INTEGRATION=1` and securely provide `AIRMONITOR_TEST_DATABASE_URL` | `airmonitor_persistence_test_` |
| API | Securely provide `AIRMONITOR_API_TEST_DATABASE_URL` | `airmonitor_api_test_` |

Both guards allow only the `postgresql+asyncpg` driver and hosts `localhost`
or `127.0.0.1`. Target-changing query parameters and unapproved database names
are rejected before engine construction.

After the variables are configured through a secure local mechanism, run only
the intended module:

```powershell
python -B -m pytest -q -p no:cacheprovider tests/test_persistence_integration.py
python -B -m pytest -q -p no:cacheprovider tests/test_api_integration.py
```

Each activated suite:

1. validates the target;
2. verifies the expected schema and Alembic revision;
3. truncates all application tables before the suite;
4. uses `RESTART IDENTITY`;
5. verifies the initial application tables are empty;
6. truncates all application tables again during final cleanup;
7. disposes the engine.

The reset deliberately does not use `CASCADE`, create or drop a database, or
create or drop a schema. The completed live verification is recorded in
`docs/reviews/sprint-8-c4b-live-verification.md`.

## Error and validation contract

v2 errors use:

```json
{
  "error": {
    "code": "request_validation_error",
    "message": "Request validation failed.",
    "details": null
  }
}
```

The concrete code and message vary by failure, but the `ErrorResponse` shape
is stable. Validation failures return safe `422` responses, domain conflicts
return safe `409` responses, missing resources return safe `404` responses,
and unexpected errors return a generic `500` response when debug mode is
disabled.

All public identifiers mapped to PostgreSQL `INTEGER` must be greater than
zero and no greater than `2,147,483,647`. Particle counters are non-negative
and have the same maximum.

## Deployment and feature limitations

AirMonitor v2 currently has **no authentication or authorization**. Public
internet exposure is not approved. Use it only on a private or otherwise
trusted network until a dedicated authentication, authorization, and
rate-limiting phase is complete.

The following are not implemented v2 capabilities:

- Docker or Docker Compose deployment;
- CI/CD;
- Redis, Celery, MQTT, or WebSockets;
- v2 aggregation, AQI, NowCast, or forecast APIs;
- telemetry/session history endpoints;
- map clustering, CSV export, or retention automation;
- a v2 browser dashboard.

Some of these capabilities exist in the preserved v1 application. That does
not make them part of the v2 API contract.

## Git and secret safety

- Do not commit `.env`; use `.env.example` only as a template.
- Do not commit passwords, database URLs, database dumps, or SQLite data.
- Do not commit certificates, private keys, firmware credentials, or
  `secrets.h`.
- Keep legacy root assets unchanged unless a task explicitly targets v1.
- Do not use live integration variables in ordinary offline test runs.

## Documentation status

- `docs/reviews/sprint-8-full-codebase-audit.md` records the original audit.
- `docs/reviews/sprint-8-final-verification.md` records the pre-C4 closure
  state.
- `docs/reviews/sprint-8-c4b-live-verification.md` records the completed
  disposable PostgreSQL verification.
- `docs/specs/telemetry-read-api.md` defines the future read API contract
  without claiming it is implemented.

## License

AirMonitor is available under the MIT License. See `LICENSE`.
