@'
# AirMonitor Agent Instructions

## Repository context

AirMonitor v1 at the repository root is stable legacy reference material and
must not be modified.

AirMonitor v2 lives under backend/ and uses FastAPI, PostgreSQL, async
SQLAlchemy, Alembic, Pydantic, and pytest.

Current feature branch:

feature/telemetry-read-api

## Governing contracts

Read completely:

- docs/specs/telemetry-read-api.md
- docs/reviews/telemetry-read-api-source-audit.md
- docs/plans/telemetry-read-api-implementation-plan.md
- backend/app/services/telemetry_cursor.py
- backend/app/services/telemetry.py
- backend/app/schemas/telemetry.py
- backend/app/schemas/sessions.py
- backend/app/schemas/measurements.py
- backend/app/api/dependencies.py
- backend/app/db/dependencies.py
- backend/tests/test_api_schemas.py
- backend/tests/test_api_dependencies.py
- backend/tests/test_api_routes.py
- backend/tests/test_api_openapi.py
- backend/tests/test_api_architecture.py

The approved Phase D1 tests must not be weakened.

## Current task

Telemetry Read API — Phase D2.

Implement only:

- public telemetry list response schemas;
- request-scoped telemetry query-service providers.

Do not implement GET routes in this phase.

Do not change OpenAPI indirectly through route registration.

Do not implement indexes, migrations, integration tests, authentication,
frontend work, aggregation, AQI, or documentation.

## Allowed production changes

Modify only:

- backend/app/schemas/telemetry.py
- backend/app/api/dependencies.py

Do not modify tests.

Do not modify any other production file.

## Response schema contract

Add to backend/app/schemas/telemetry.py:

- SessionListResponse
- MeasurementListResponse

SessionListResponse exact fields:

- items: list[SessionResponse]
- next_cursor: str | None

MeasurementListResponse exact fields:

- items: list[MeasurementResponse]
- next_cursor: str | None

Both fields are required.

Do not assign defaults.

Valid construction requires both:

items=...
next_cursor=...

Reuse:

- app.schemas.sessions.SessionResponse
- app.schemas.measurements.MeasurementResponse

The envelopes must contain no other fields.

Do not add:

- total
- count
- page
- offset
- has_more
- metadata

Follow the current response-model base convention used by existing ORM response
schemas where applicable.

The schemas must serialize ORM items using the existing SessionResponse and
MeasurementResponse contracts.

Export both public symbols according to the current module export convention.

## Dependency provider contract

Add to backend/app/api/dependencies.py:

- get_session_telemetry_query_service
- get_measurement_telemetry_query_service

Exact behavior:

def get_session_telemetry_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> SessionTelemetryQueryService:
    return SessionTelemetryQueryService(session)

def get_measurement_telemetry_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> MeasurementTelemetryQueryService:
    return MeasurementTelemetryQueryService(session)

Follow the existing provider annotation and Depends conventions exactly.

Each provider must:

- use the existing request-scoped get_db_session dependency;
- pass the exact supplied AsyncSession object;
- construct exactly one service;
- create no database engine or second session;
- perform no query;
- perform no execute;
- perform no begin, commit, rollback or flush;
- contain no error translation.

Export both symbols according to current module convention.

## Scope exclusions

Do not modify or create:

- sessions endpoint GET route;
- measurements endpoint GET route;
- routers;
- main application;
- response helpers;
- error handlers;
- query validation;
- cursor implementation;
- repositories;
- services;
- ORM models;
- migrations;
- settings;
- tests.

## Expected checkpoint

After implementation:

Schema telemetry cases:

- 6 passed.

Dependency telemetry cases:

- 2 passed.

Existing schema and dependency assertions remain green.

Route telemetry cases remain intentionally RED because GET routes do not yet
exist.

OpenAPI telemetry cases remain intentionally RED because GET operations do not
yet exist.

Architecture telemetry route case remains intentionally RED because route
functions do not yet exist.

Expected focused D1 partition:

- 8 formerly RED cases become GREEN;
- approximately 40 intentional RED cases remain;
- no new failure category is allowed.

Exact counts must be reported from the actual run rather than assumed.

## Verification environment

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest command must include:

-B -p no:cacheprovider

Do not connect to PostgreSQL.

Do not activate integration suites.

## Required verification

Before editing:

- run the five D1 files and record the 48-failure RED baseline;
- run schema tests;
- run dependency tests;
- run pip check;
- run git diff --check.

After schema implementation:

- run the six telemetry schema cases;
- run the complete schema file.

After provider implementation:

- run the two telemetry dependency cases;
- run the complete dependency file.

Then:

- run all five D1 files;
- classify remaining failures;
- prove route/OpenAPI/architecture RED boundaries remain intentional;
- run the full offline suite excluding only intentionally RED D1 telemetry
  route/OpenAPI/architecture assertions where technically necessary;
- run pip check;
- run git diff --check;
- run syntax and import checks;
- run scope, secret, database URL, environment-read and local-path scans.

## Architecture requirements

Verify:

- schemas import no FastAPI or SQLAlchemy;
- providers build no SQL;
- providers do not call execute, begin, commit, rollback or flush;
- providers do not instantiate AsyncSession;
- providers use get_db_session;
- no broad exception handler is added;
- no environment or settings read is added;
- application import and OpenAPI generation remain connection-free.

## Git restrictions

Do not:

- stage;
- commit;
- push;
- reset;
- clean;
- stash;
- create or delete branches;
- modify Git configuration.

Read-only Git commands are allowed.

## Definition of done

Phase D2 is complete only when:

- exactly two approved production files changed;
- no test changed;
- both response schemas satisfy exact required-field contracts;
- both providers reuse the supplied request-scoped session;
- schema and dependency telemetry tests pass;
- remaining RED failures concern only absent GET routes and OpenAPI operations;
- existing contracts remain green;
- no PostgreSQL or Git write occurs;
- Git index remains unchanged;
- work stops for manual external review.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8