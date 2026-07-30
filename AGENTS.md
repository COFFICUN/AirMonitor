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
- backend/app/schemas/telemetry.py
- backend/app/api/query_validation.py
- backend/tests/test_telemetry_read_repositories.py
- backend/tests/test_telemetry_read_services.py
- current repository and query-service implementations
- current DeviceNotFoundError usage

The two C1 test files are approved and must not be weakened.

## Current task

Telemetry Read API — Phase C2.

Implement only:

- bounded read methods in the two existing telemetry repositories;
- immutable telemetry page values;
- session and measurement telemetry query services.

Do not implement routes, response schemas, router registration, ORM changes,
indexes, migrations, integration tests, authentication, aggregation, AQI, or
frontend work.

## Allowed production changes

Modify:

- backend/app/repositories/measurement_session.py
- backend/app/repositories/measurement.py

Create:

- backend/app/services/telemetry.py

Do not modify the C1 tests.

Do not modify other production or test files.

## Approved repository interfaces

MeasurementSessionRepository:

async def list_for_device(
    self,
    *,
    device_id: int,
    status: str | None,
    started_from: datetime | None,
    started_to: datetime | None,
    position: CursorPosition | None,
    limit: int,
) -> list[MeasurementSession]:
    ...

RawMeasurementRepository:

async def list_for_device(
    self,
    *,
    device_id: int,
    session_id: int | None,
    measured_from: datetime | None,
    measured_to: datetime | None,
    position: CursorPosition | None,
    limit: int,
) -> list[RawMeasurement]:
    ...

## Repository dependency direction

Repository modules must not import app.services.telemetry_cursor at runtime.

Because CursorPosition belongs to the current approved contract, use:

- from __future__ import annotations;
- TYPE_CHECKING;
- a type-only CursorPosition import;

or an equivalent approach that creates no runtime repository-to-service
dependency.

Do not move CursorPosition in this phase.

## Session repository SQL contract

Start with:

MeasurementSession.device_id == device_id

Optional predicates:

- status equality;
- started_at >= started_from;
- started_at < started_to;
- exclusive cursor:

  started_at < position.timestamp
  OR (
      started_at == position.timestamp
      AND id < position.identifier
  )

Ordering:

- started_at DESC;
- id DESC.

SQL limit:

- limit + 1.

Do not use OFFSET.

Return:

result.scalars().all()

Preserve database/result ordering and entity identity.

## Measurement repository SQL contract

Always include:

RawMeasurement.device_id == device_id

When session_id is supplied, retain both:

- device_id equality;
- session_id equality.

Optional predicates:

- measured_at >= measured_from;
- measured_at < measured_to;
- exclusive cursor:

  measured_at < position.timestamp
  OR (
      measured_at == position.timestamp
      AND id < position.identifier
  )

Ordering:

- measured_at DESC;
- id DESC.

SQL limit:

- limit + 1.

Do not use OFFSET.

Return:

result.scalars().all()

## Repository transaction boundary

Repositories must not:

- begin;
- commit;
- rollback;
- flush;
- delete;
- mutate entities;
- use SELECT FOR UPDATE.

They perform one read-only session.execute() call.

## Approved service module

Create:

backend/app/services/telemetry.py

## Approved page type

PageItem = TypeVar("PageItem")

@dataclass(frozen=True)
class TelemetryPage(Generic[PageItem]):
    items: tuple[PageItem, ...]
    next_cursor: str | None

Do not replace tuple with list.

## Approved service interfaces

class SessionTelemetryQueryService:
    def __init__(self, session: AsyncSession) -> None:
        ...

    async def list_sessions(
        self,
        *,
        read_request: SessionReadRequest,
    ) -> TelemetryPage[MeasurementSession]:
        ...

class MeasurementTelemetryQueryService:
    def __init__(self, session: AsyncSession) -> None:
        ...

    async def list_measurements(
        self,
        *,
        read_request: MeasurementReadRequest,
    ) -> TelemetryPage[RawMeasurement]:
        ...

## Required repository attributes

Follow current query-service conventions and expose:

SessionTelemetryQueryService:

- device_repository
- session_repository

MeasurementTelemetryQueryService:

- device_repository
- measurement_repository

Construct all repositories from the same AsyncSession supplied to the service
constructor.

Do not add constructor dependency-injection parameters.

## Device existence behavior

For every service call:

1. call device_repository.get_by_id(device_id);
2. if it returns None, raise the existing DeviceNotFoundError using the
   established constructor convention;
3. only then consider empty-range or telemetry-list behavior.

Do not query telemetry rows for an unknown device.

## Equal-range behavior

For:

from == to

after device existence succeeds:

- return TelemetryPage(items=(), next_cursor=None);
- do not call the telemetry repository.

This applies independently to:

- started_from == started_to;
- measured_from == measured_to.

## Normal read behavior

Forward the exact normalized read request values to the repository:

Sessions:

- device_id;
- status;
- started_from;
- started_to;
- position;
- public limit.

Measurements:

- device_id;
- session_id;
- measured_from;
- measured_to;
- position;
- public limit.

The repository, not the service, applies SQL limit + 1.

## Page construction

Let public_limit = read_request.limit.

For repository rows of length 0 through public_limit:

- return all rows as a tuple;
- preserve order and identity;
- next_cursor is None.

For repository rows of length public_limit + 1:

- return tuple(rows[:public_limit]);
- do not return the extra row;
- use rows[public_limit - 1] as the cursor source;
- never use rows[public_limit].

Session cursor position:

CursorPosition(
    final_returned_session.started_at,
    final_returned_session.id,
)

Measurement cursor position:

CursorPosition(
    final_returned_measurement.measured_at,
    final_returned_measurement.id,
)

Generate next_cursor with production encode_cursor and the original
read_request.filters.

Do not duplicate cursor encoding.

## Error behavior

Do not broadly catch repository or cursor exceptions.

Repository failures must propagate.

CursorValidationError from next-cursor generation must propagate.

Do not convert failures into an empty page or fake success.

## Service transaction boundary

Services in this phase must not:

- begin;
- commit;
- rollback;
- flush;
- mutate Device;
- mutate MeasurementSession;
- mutate RawMeasurement;
- import FastAPI;
- construct HTTP Response objects;
- contain SQL.

## Scope exclusions

Do not modify:

- API routes;
- response schemas;
- query validation;
- cursor code;
- ORM models;
- Alembic;
- indexes;
- settings;
- dependencies;
- README;
- legacy files;
- approved C1 tests.

## Verification environment

Use only:

C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe

Every pytest command must include:

-B -p no:cacheprovider

Do not connect to PostgreSQL.

Do not activate live integration tests.

## Required incremental verification

1. run the approved C1 tests and record initial RED;
2. implement repository methods only;
3. run repository C1 tests;
4. implement telemetry service only;
5. run service C1 tests;
6. run both C1 files;
7. run telemetry cursor and query-validation tests;
8. run existing repository/query-service/service tests;
9. run the full offline backend suite;
10. run OpenAPI tests;
11. run pip check;
12. run git diff --check;
13. run scope/import/secret/local-path scans.

Expected final results:

- C1 focused: 51 passed;
- full offline suite: 781 passed, 2 skipped;
- OpenAPI 3.1.0;
- nine operations;
- eight /api/v1 operations;
- one /health operation;
- nine unique operation IDs;
- Alembic head remains a4f9c2e7d1b6.

## Architecture checks

Verify:

- repository modules do not import FastAPI;
- repository modules have no runtime import from app.services;
- app.services.telemetry contains no SQLAlchemy select/where/order building;
- no commit, rollback, flush, begin, delete, or entity assignment was added;
- no broad exception handler was added;
- no database URL, credential, environment read, or local user path was added.

## Git restrictions

Do not stage, commit, push, reset, clean, stash, create branches, or modify Git
configuration.

Read-only Git commands are allowed.

## Definition of done

Phase C2 is complete only when:

- exactly three approved production files changed;
- approved C1 tests remain unchanged;
- repository tests pass;
- service tests pass;
- full offline suite passes;
- OpenAPI remains unchanged;
- no PostgreSQL access occurs;
- no transaction or mutation behavior is introduced;
- Git index remains unchanged;
- work stops for manual external review.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8