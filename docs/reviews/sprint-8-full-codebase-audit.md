# Sprint 8 Phase A — Full AirMonitor v2 Codebase Audit

**Audit date:** 2026-07-27

**Reviewed revision:** `c883223` on `feature/full-audit-stabilization`

**Authoritative scope:** `backend/` AirMonitor v2

**Audit mode:** read-only, offline, no PostgreSQL access

**Deliverable status:** Phase A review only; no fixes are included

## 1. Executive summary

AirMonitor v2 has a generally disciplined backend foundation: clear API/service/repository/ORM layering, service-owned transactions, one `AsyncSession` per request, consistent device-first lock ordering, a four-table PostgreSQL model, explicit response schemas, and strong static migration tests. The ORM and sole Alembic revision are in structural parity. All current lookup and foreign-key paths have usable indexes. No dynamic SQL, current N+1 query, current path conflict, tracked prohibited secret file, ORM/migration mismatch, or proven deadlock was found.

The audit confirmed **14 defects**:

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 2 |
| Medium | 8 |
| Low | 4 |
| Informational | 0 |

The two high-severity defects block further endpoint implementation:

1. `create_application(settings)` does not bind those settings to the real database engine/session dependency. A factory-created test or staging application can silently use the process-global/default database target instead.
2. PM fields accept positive infinity from valid JSON such as `1e999`. PostgreSQL accepts and commits that value, but response rendering then fails, producing a failed response after a successful write and creating a retry/duplication hazard.

The most important medium findings are missing session/measurement chronology enforcement, API integers that exceed PostgreSQL `INTEGER`, incomplete public error-envelope coverage, production configurations that allow tracebacks and SQL parameter logging, and unmanaged async-engine shutdown. The guarded integration suites also have three concrete safety/repeatability defects.

**Gate decision:** telemetry read API implementation should **not** begin yet. Phase B should first approve and order the two high fixes, the chronology and integer-boundary fixes, and their regression tests. Read-API contract and index design may proceed on paper, but code should wait until the write path and application composition are trustworthy.

### Top five findings

| Rank | ID | Severity | Summary |
|---:|---|---|---|
| 1 | AUDIT-001 | High | Factory settings do not control the database engine/session factory |
| 2 | AUDIT-002 | High | Non-finite PM values can commit before response serialization fails |
| 3 | AUDIT-003 | Medium | Measurements can exist outside their session time interval |
| 4 | AUDIT-004 | Medium | API integers can exceed PostgreSQL `INTEGER` and become unhandled 500s |
| 5 | AUDIT-006 | Medium | Production accepts traceback, SQL-parameter logging, and the development database default |

### Verification limitation

The repository-stated baseline of `246 passed, 2 skipped` could not be reproduced in the available non-project Python 3.13 installation. The available interpreter lacks declared packages including `httpx2`, `pydantic-settings`, Alembic, and `asyncpg`; use of the prohibited project `.venv` and dependency installation were intentionally avoided. The full collection stopped with nine dependency-related import errors. A partial/collectable subset produced `168 passed, 1 skipped, 1 failed`; the one failure was itself caused by absent `asyncpg` while the test attempted to patch that module.

This is an **audit-environment limitation**, not evidence that the product baseline regressed. Static source compilation, a guarded OpenAPI build, the revision graph, and all source inspections completed successfully.

## 2. Review method and selected skills

### Selected skills and exact application order

1. **`using-agent-skills`** — governed skill selection and prevented accidental use of the separately reserved architecture-refactoring skill.
2. **`source-driven-development`** — required non-obvious FastAPI, Pydantic, SQLAlchemy, and PostgreSQL conclusions to be checked against primary documentation.
3. **`code-review-and-quality`** — supplied the multi-axis, evidence-first review frame and the distinction between confirmed defects and weaker concerns.
4. **`fastapi`** — applied to application construction, dependency caching, request validation, error handling, OpenAPI, and response serialization.
5. **`api-and-interface-design`** — applied to the eight-operation public contract, compatibility impact, operation IDs, error models, and future pagination/authentication seams.
6. **`supabase-postgres-best-practices`** — applied to ORM/migration parity, constraints, locking, foreign-key indexes, current query coverage, and future keyset indexes.
7. **`security-and-hardening`** — applied to secrets, unsafe defaults, error leakage, test-database guards, trust boundaries, authentication, CORS, and logs.
8. **`performance-optimization`** — applied after correctness to query counts, lock duration, hot-path round trips, pool lifecycle, index cost, and raw-data growth.

### Listed skills intentionally not selected

| Skill | Reason |
|---|---|
| `codebase-design` | Deep-module and “deepening opportunity” analysis overlaps the explicitly deferred architecture-refactoring review. Current boundaries were still audited factually without proposing a redesign workflow. |
| `doubt-driven-development` | Its interactive adversarial review loop is disproportionate for a bounded, post-hoc read-only audit. Independent subreviews and direct source/runtime proofs supplied the needed challenge pass. |
| `documentation-and-adrs` | The user prescribed one Markdown report and explicitly said no ADR is required. |
| `improve-codebase-architecture` | Explicitly excluded by the user because its HTML/deepening workflow conflicts with this single Markdown deliverable and no-refactoring scope. It was neither selected nor invoked. |

### Multi-pass execution

The review followed the requested ten passes:

1. inventory and architecture;
2. correctness and domain invariants;
3. FastAPI and interfaces;
4. transactions and concurrency;
5. PostgreSQL and Alembic;
6. security;
7. performance;
8. test quality;
9. configuration and repository hygiene;
10. product readiness.

Three independent read-only subreviews covered core correctness/concurrency, API/security, and PostgreSQL/tests/configuration. Their conclusions were reconciled against the main review. No subreview modified files, invoked PostgreSQL, or ran Git write operations.

## 3. Reviewed scope

### Included

- all 41 runtime Python files under `backend/app`;
- all 21 Python files under `backend/tests`, including guard helpers and `__init__.py`;
- Alembic environment, template, README, and sole revision;
- backend production and development requirements;
- backend settings template and Alembic configuration;
- repository agent instructions, README, Git attributes, Git ignore rules, and legacy requirements;
- tracked-path and redacted credential-pattern checks, including the public firmware credential example and firmware include/reference context;
- read-only Git status, tracked-file, revision, and branch information;
- official FastAPI/Starlette, Pydantic, SQLAlchemy, and PostgreSQL documentation relevant to non-obvious findings.

### Excluded or restricted

- AirMonitor v1 implementation behavior was not re-audited.
- No prohibited secret, environment, certificate, key, database, SQLite, virtual-environment, or generated-cache file was opened.
- No live PostgreSQL target was contacted.
- No migration was run against a database.
- No dependency was installed or updated.
- No production code, test, migration, requirement, settings file, legacy file, environment variable, or Git index/ref/configuration state was changed.

## 4. Files inspected

### Production Python — 41 files

```text
backend/app/__init__.py
backend/app/main.py
backend/app/core/__init__.py
backend/app/core/config.py
backend/app/core/exceptions.py
backend/app/db/__init__.py
backend/app/db/base.py
backend/app/db/dependencies.py
backend/app/db/session.py
backend/app/db/models/__init__.py
backend/app/db/models/device.py
backend/app/db/models/measurement.py
backend/app/db/models/measurement_session.py
backend/app/repositories/__init__.py
backend/app/repositories/device.py
backend/app/repositories/measurement.py
backend/app/repositories/measurement_session.py
backend/app/services/__init__.py
backend/app/services/_support.py
backend/app/services/device.py
backend/app/services/measurement.py
backend/app/services/queries.py
backend/app/schemas/__init__.py
backend/app/schemas/_base.py
backend/app/schemas/devices.py
backend/app/schemas/errors.py
backend/app/schemas/measurements.py
backend/app/schemas/sessions.py
backend/app/api/__init__.py
backend/app/api/dependencies.py
backend/app/api/errors.py
backend/app/api/responses.py
backend/app/api/router.py
backend/app/api/routes/__init__.py
backend/app/api/routes/health.py
backend/app/api/v1/__init__.py
backend/app/api/v1/router.py
backend/app/api/v1/endpoints/__init__.py
backend/app/api/v1/endpoints/devices.py
backend/app/api/v1/endpoints/measurements.py
backend/app/api/v1/endpoints/sessions.py
```

### Test Python — 21 files

```text
backend/tests/__init__.py
backend/tests/api_integration_guard.py
backend/tests/persistence_guard.py
backend/tests/test_api_architecture.py
backend/tests/test_api_dependencies.py
backend/tests/test_api_errors.py
backend/tests/test_api_integration.py
backend/tests/test_api_integration_guard.py
backend/tests/test_api_openapi.py
backend/tests/test_api_routes.py
backend/tests/test_api_schemas.py
backend/tests/test_config.py
backend/tests/test_database.py
backend/tests/test_health.py
backend/tests/test_migrations.py
backend/tests/test_models.py
backend/tests/test_persistence_guard.py
backend/tests/test_persistence_integration.py
backend/tests/test_query_services.py
backend/tests/test_repositories.py
backend/tests/test_services.py
```

### Other project files — 16 files

```text
AGENTS.md
README.md
.gitignore
.gitattributes
requirements.txt
secrets.example.h                         (redacted security classification only)
test1_final.ino                           (redacted security classification only)
backend/.env.example
backend/requirements.txt
backend/requirements-dev.txt
backend/alembic.ini
backend/alembic/README
backend/alembic/script.py.mako
backend/alembic/env.py
backend/alembic/versions/.gitkeep
backend/alembic/versions/a4f9c2e7d1b6_create_initial_airmonitor_schema.py
```

**Project-file total inspected: 78.**

## 5. Current architecture map

```text
ASGI server
  └─ app.main:create_application
       ├─ Settings / application metadata
       ├─ exception-handler registration
       └─ router composition
            ├─ /health
            └─ /api/v1
                 ├─ FastAPI path/body validation
                 ├─ request-scoped dependency resolution
                 │    └─ one AsyncSession yielded by get_db_session
                 ├─ endpoint
                 │    ├─ query service, or
                 │    └─ transactional write service
                 ├─ repository
                 ├─ SQLAlchemy ORM / Core statement
                 ├─ PostgreSQL transaction result
                 ├─ explicit Pydantic response construction
                 └─ exception mapping / response rendering
```

### Package boundaries and dependency direction

| Layer | Current responsibility | Verdict |
|---|---|---|
| `app.main` | factory, metadata, handlers, router inclusion | Small and focused, but database ownership is not actually connected to factory settings (AUDIT-001). |
| `app.api` | DI adapters, public routes, HTTP status/response declarations | Correctly avoids repository/ORM calls in endpoints. Error coverage is incomplete (AUDIT-005). |
| `app.schemas` | closed request models and scalar response contracts | `extra="forbid"` is strong. Numeric boundary gaps remain (AUDIT-002/AUDIT-004). |
| `app.services` | domain checks, lock order, transaction ownership, exception translation | Correct transaction boundary. Chronology invariant is incomplete (AUDIT-003). |
| `app.repositories` | statements, `flush`, row locking, persistence construction | No HTTP dependency and no commit/rollback ownership. |
| `app.db.models` | relational schema, constraints, relationships | Strong constraint coverage and exact migration parity. Two invariants remain service-only risks. |
| `alembic` | deployable PostgreSQL schema | One root/head revision; static upgrade/downgrade order is symmetric. |

The dependency direction is appropriately one-way:

```text
main/api → schemas + services → repositories + domain errors/models
                                → SQLAlchemy base/models
```

No repository imports FastAPI or HTTP concerns. No service commits through a repository. No endpoint constructs SQL.

### Transaction ownership

| Operation | Transaction owner | Lock/read order | Main writes |
|---|---|---|---|
| Create device | `DeviceService` | UID lookup; no row exists to lock | device + runtime row |
| Activate/deactivate | `DeviceService` | device `FOR UPDATE` | device status |
| Start session | `MeasurementService` | device → runtime state | session insert + runtime pointer/state |
| Read device | query service/request session | unlocked device read | none |
| Read active session | query service/request session | unlocked device/status read | none |
| Complete/cancel | `MeasurementService` | device → runtime state → session | session terminal state + runtime clear |
| Record measurement | `MeasurementService` | device → runtime state → session → optional duplicate read | raw row + session count + runtime last-seen |

Repositories call `flush()` where generated IDs or immediate constraint checks are required but never call `begin`, `commit`, or `rollback`. Write services use `async with session.begin()`. `IntegrityError` translation occurs outside the context manager, after rollback, so the session is reusable.

### Domain invariant map

| Invariant | Enforcement | Verdict |
|---|---|---|
| Device UID unique | named DB unique constraint plus service translation | Enforced; precheck is advisory, DB handles races. |
| Exactly one runtime row per device | runtime primary key/FK and device-create transaction | Enforced for API-created devices. |
| Runtime active session belongs to same device | composite FK `(active_session_id, device_id)` | Enforced. |
| Raw measurement session belongs to same device | composite FK `(session_id, device_id)` | Enforced. |
| Session status and `ended_at` agree | DB checks plus service transition | Enforced. |
| `ended_at >= started_at` | service plus DB check | Enforced. |
| Measurement occurs within session interval | not enforced | Confirmed defect AUDIT-003. |
| Coordinates are paired and in range | Pydantic plus DB checks | Enforced. |
| Input timestamps are timezone-aware | Pydantic plus service normalization | Enforced. |
| PM values are finite | not enforced | Confirmed defect AUDIT-002. |
| Non-null source ID is unique per device | named DB unique constraint; null bypass is intentional | Enforced. |
| Runtime enabled/pointer/start timestamp form a consistent triad | services only | Current paths maintain it; architecture risk for future/direct writers. |
| At most one active session per device | service locks/runtime state only | Current API protects it; no DB-level partial uniqueness. |

## 6. Confirmed findings

Severity applies only to defects supported by code evidence or an offline reproduction. Coverage gaps, risks, limitations, and optional improvements are separated later.

Findings are ordered by severity: High (`AUDIT-001`–`002`), Medium (`AUDIT-003`–`010`), then Low (`AUDIT-011`–`014`). No Critical or Informational defect was confirmed.

### AUDIT-001 — Factory-supplied settings do not control the database engine

- **Severity:** High
- **Confidence:** High
- **Exact files and lines:** `backend/app/main.py:10-29`; `backend/app/db/dependencies.py:12-20`; `backend/app/db/session.py:36-45`; `backend/app/core/config.py:47-50`; masking tests at `backend/tests/test_config.py:90-120` and `backend/tests/test_api_integration.py:149-160`
- **Affected component:** application factory, settings, engine/session dependency graph
- **Evidence:** `create_application(settings)` installs a FastAPI override for `get_settings`, but `get_session_factory()` directly calls cached `get_database_engine()`, which directly calls cached `get_settings()`. FastAPI dependency overrides do not intercept an ordinary Python call. Importing `app.main` also creates the module-level app and can prime the global settings cache.
- **Reproduction/static proof:** An offline identity check constructed an app with a custom sentinel database URL. The FastAPI override returned the custom settings, while the database module’s direct `get_settings()` call returned a different object and different URL. No connection was made.
- **Real impact:** A test, staging process, or alternate in-process application can write to the ambient/default database despite being constructed with an explicitly isolated URL. In this repository the default database name is the protected local development database. Multiple app instances also share whichever global engine is initialized first.
- **Minimal recommended fix:** Make the engine and sessionmaker application-owned, construct them from the exact `application_settings`, expose that exact factory through app-scoped DI, and dispose the engine through lifespan. Remove or correctly key the no-argument global caches.
- **Required regression test:** Build two apps with distinct sentinel URLs; resolve each real request session factory with a spy engine creator; prove each app uses its own URL and that global settings are never consulted. The test must not connect.
- **API compatibility impact:** None to paths, bodies, status codes, or responses.
- **Database/migration impact:** No schema migration. Runtime connection-target behavior becomes correct.
- **Sprint 8 recommendation:** Fix immediately in Batch 1.
- **Further verification required:** Verify deployment entrypoints set intended environment before import. The code defect itself is statically proven.

### AUDIT-002 — Non-finite PM values can commit before response serialization fails

- **Severity:** High
- **Confidence:** High
- **Exact files and lines:** `backend/app/schemas/_base.py:19-28`; `backend/app/schemas/measurements.py:22-26,47-69`; `backend/app/services/measurement.py:116-244`; `backend/app/db/models/measurement.py:57-68,151-155`; `backend/app/api/v1/endpoints/measurements.py:23-42`; `backend/alembic/versions/a4f9c2e7d1b6_create_initial_airmonitor_schema.py:455-474`
- **Affected component:** ingestion validation, PostgreSQL constraints, transaction/result boundary, response serialization
- **Evidence:** Request models do not disable infinity/NaN. PM fields have only `ge=0`, so positive infinity passes. PostgreSQL `double precision` supports infinity and checks such as `pm25 >= 0` permit positive infinity. The service transaction commits before the endpoint constructs/renders the response.
- **Reproduction/static proof:** `MeasurementCreateRequest.model_validate_json()` accepted valid JSON containing `1e999` for all three PM fields and produced positive infinity. `fastapi.encoders.jsonable_encoder()` retained infinity in a `MeasurementResponse`, and Starlette `JSONResponse` raised `ValueError`. No database was used. The PostgreSQL behavior is documented by the primary source linked below.
- **Real impact:** The raw row, session sample count, and runtime last-seen update can commit while the client receives a 500. A retry with a non-null source ID becomes 409 even though the original response failed; a retry with a null source ID can add another committed row. Non-finite data would also poison later aggregation, AQI, and NowCast calculations.
- **Minimal recommended fix:** Reject non-finite external floats at the schema boundary (`allow_inf_nan=False` or finite float types) and enforce the same invariant in the service for non-HTTP callers. Add finite-value DB checks as defense in depth after an existing-data preflight.
- **Required regression test:** Send raw JSON with `1e999`, `-1e999`, and non-standard NaN spellings where the parser permits them. The API must return the stable 422 envelope and perform zero insert, sample-count, or runtime writes. A later guarded migration test must prove direct non-finite inserts fail.
- **API compatibility impact:** Pathological, non-interoperable numeric inputs change from acceptance/500 to 422; valid inputs are unchanged.
- **Database/migration impact:** API/service correction needs no migration. Database defense requires a new migration and a pre-migration scan for non-finite values.
- **Sprint 8 recommendation:** Fix immediately in Batch 1.
- **Further verification required:** Inspect existing data only through the approved disposable/development workflow before adding DB checks; never use the protected database during audit.

### AUDIT-003 — Measurements and session completion do not enforce one time interval

- **Severity:** Medium
- **Confidence:** High
- **Exact files and lines:** `backend/app/services/measurement.py:166-234,268-303`; `backend/app/db/models/measurement.py:137-144`; `backend/app/db/models/measurement_session.py:136-145`; missing cases near `backend/tests/test_services.py:853-879,1167-1187`
- **Affected component:** measurement/session domain invariants
- **Evidence:** Ingestion normalizes `measured_at` but never compares it with the locked session’s `started_at`. Completion/cancellation checks only `ended_at >= started_at`, not whether persisted measurements are at or before `ended_at`. There is no cross-table database constraint.
- **Reproduction/static proof:** Start a session at `T1` and record an aware measurement at `T0 < T1`; it persists and increments state. Separately, record at `T2`, then complete with `T1 <= ended_at < T2`; completion succeeds and leaves a measurement outside the closed interval.
- **Real impact:** Session histories become internally contradictory. Cursor reads, summaries, AQI/NowCast, maps, and exports can assign data outside the advertised collection interval.
- **Minimal recommended fix:** Reject measurements earlier than the active session start. When ending a session, compare the proposed end with the latest measurement while holding the existing device/session locks. Define any clock-skew or out-of-order tolerance explicitly.
- **Required regression test:** Cover lower-bound rejection, end-before-latest rejection, equality acceptance, rollback/state preservation, and concurrent record-versus-complete/cancel ordering.
- **API compatibility impact:** Previously accepted contradictory timestamps should become 409 conflicts.
- **Database/migration impact:** Prevention can be service-level; a simple PostgreSQL check cannot enforce the cross-table rule. Existing-data remediation may be required.
- **Sprint 8 recommendation:** Fix before telemetry read APIs.
- **Further verification required:** Product decision only for permitted clock skew/out-of-order delivery.

### AUDIT-004 — API integers exceed PostgreSQL `INTEGER` boundaries

- **Severity:** Medium
- **Confidence:** High
- **Exact files and lines:** `backend/app/api/v1/endpoints/devices.py:21-22`; `backend/app/api/v1/endpoints/sessions.py:21-25`; `backend/app/api/v1/endpoints/measurements.py:16-20`; `backend/app/schemas/measurements.py:27-32`; `backend/app/db/models/measurement.py:118-161`; revision `backend/alembic/versions/a4f9c2e7d1b6_create_initial_airmonitor_schema.py:398-426`
- **Affected component:** API validation and PostgreSQL type contract
- **Evidence:** Path IDs use only `gt=0`. Six particle counts use only `ge=0`. Python/Pydantic integers are unbounded while PostgreSQL `INTEGER` is limited to `2,147,483,647`. Range failures are not `IntegrityError`, so the custom integrity handler does not apply.
- **Reproduction/static proof:** Offline validation accepted `2,147,483,648` for every particle field and for the shared positive path-ID annotation. An asyncpg/PostgreSQL int4 bind or insert rejects that value.
- **Real impact:** An attacker or faulty sensor can turn boundary-invalid input into an unhandled 500 rather than a deterministic 422. Particle writes roll back, but the public contract is violated and path lookups can fail before returning normal 404.
- **Minimal recommended fix:** Add `le=2_147_483_647` wherever the database column is `INTEGER`, or deliberately migrate fields that require a larger domain to `BIGINT`.
- **Required regression test:** Prove the int32 maximum reaches the service, maximum plus one returns the safe 422 envelope, and the service/database is not invoked for every affected path and particle field.
- **API compatibility impact:** Out-of-range inputs become 422; valid input is unchanged.
- **Database/migration impact:** None if API bounds are added. Widening to `BIGINT` requires a coordinated migration.
- **Sprint 8 recommendation:** Fix in Batch 2 before adding more ID-bearing endpoints.
- **Further verification required:** Confirm maximum sensor counter semantics and long-term identifier capacity.

### AUDIT-005 — The public error envelope is incomplete and OpenAPI understates it

- **Severity:** Medium
- **Confidence:** High
- **Exact files and lines:** `backend/app/api/errors.py:141-199`; `backend/app/api/responses.py:8-22`; endpoint declarations at `backend/app/api/v1/endpoints/devices.py:25-74`, `measurements.py:23-42`, and `sessions.py:28-115`; tests at `backend/tests/test_api_errors.py:46-191` and `backend/tests/test_api_openapi.py:75-114`
- **Affected component:** exception handling, error contract, OpenAPI
- **Evidence:** Installed handlers cover domain exceptions, request validation, and `IntegrityError` only. Starlette `HTTPException` and generic exceptions are not covered. Unknown routes/wrong methods therefore use FastAPI’s `{"detail": ...}` shape; `OperationalError`, `DataError`, response-validation failures, and programming errors bypass `ErrorResponse`. Device creation and status routes can encounter generic 500s but do not document 500; other 500 descriptions claim only a known invariant.
- **Reproduction/static proof:** Handler registration has exactly those three exception classes. The guarded OpenAPI build showed response sets of `201/409/422` for device creation and `200/404/422` for status, while non-integrity failures remain possible. Official FastAPI behavior for default HTTP exceptions is `detail`.
- **Real impact:** ESP32/frontend clients need multiple error parsers and cannot rely on the declared envelope. Unexpected DB failures are underdocumented. With debug enabled, the same gap can expose tracebacks.
- **Minimal recommended fix:** Add sanitized handlers for Starlette `HTTPException` and generic server errors, preserving headers such as `Allow`. Log internal detail only through a redacted logging policy. Make documented response sets/descriptions match actual behavior.
- **Required regression test:** Cover unknown route, 405, synthetic runtime failure, SQLAlchemy non-integrity failure, preserved headers, and absence of sentinel secrets/constraint names in all response bodies.
- **API compatibility impact:** Default 404/405/500 response bodies change to the project envelope; this should be versioned/documented as a contract correction.
- **Database/migration impact:** None.
- **Sprint 8 recommendation:** Fix in Batch 2.
- **Further verification required:** Approve the canonical codes/messages and whether every 500 is explicitly documented per operation.

### AUDIT-006 — Production accepts unsafe diagnostics and the development database default

- **Severity:** Medium
- **Confidence:** High
- **Exact files and lines:** `backend/app/core/config.py:14-44`; `backend/app/main.py:13-17`; `backend/app/db/session.py:15-21`; `backend/.env.example:4-9`
- **Affected component:** production configuration and sensitive logging
- **Evidence:** No cross-field validation prevents `environment="production"` with `debug=True` or `database_echo=True`. Engine construction does not set `hide_parameters=True`. Production also accepts the unchanged built-in local development database URL. The URL itself is intentionally redacted here.
- **Reproduction/static proof:** An offline settings construction accepted all three conditions simultaneously: production + debug, production + SQL echo, and production + unchanged default database. Starlette documents that debug returns tracebacks; SQLAlchemy documents that echo logs SQL parameter representations unless parameters are hidden.
- **Real impact:** A misconfigured deployment can expose paths/source context in HTTP responses, and device UID, source ID, coordinates, or validation notes in logs. It can also target the protected local development database instead of failing closed.
- **Minimal recommended fix:** Reject debug/echo in production, require an explicitly supplied non-default production database configuration, and enable parameter hiding/redaction independent of environment.
- **Required regression test:** Production settings must reject each unsafe combination; engine construction must hide parameters; a synthetic production failure must contain no sentinel in body or captured logs.
- **API compatibility impact:** None for correctly configured clients. Unsafe diagnostic configurations cease to start.
- **Database/migration impact:** None.
- **Sprint 8 recommendation:** Fix in Batch 2 before any deployment.
- **Further verification required:** Deployment owners must define accepted production configuration sources and secret injection.

### AUDIT-007 — The shared async engine has no application shutdown disposal

- **Severity:** Medium
- **Confidence:** High
- **Exact files and lines:** `backend/app/db/session.py:36-45`; `backend/app/main.py:10-29`
- **Affected component:** engine, pool, and ASGI lifespan
- **Evidence:** The async engine is globally cached. The FastAPI app defines no lifespan/shutdown path and no production call awaits `AsyncEngine.dispose()`.
- **Reproduction/static proof:** After the first database request initializes the pool, application shutdown has no code path that releases it. SQLAlchemy specifically recommends awaited disposal because async cleanup cannot be completed reliably by object finalizers.
- **Real impact:** Shutdown can leave checked-in connections unmanaged or emit event-loop-closed warnings. Repeated app lifecycles/tests can share a pool across event loops, compounding AUDIT-001.
- **Minimal recommended fix:** Make the engine/sessionmaker application-owned and dispose the initialized engine exactly once through FastAPI lifespan.
- **Required regression test:** A lifespan test proves a used engine is disposed once, unused health/OpenAPI lifecycles do not connect merely to dispose, and two app lifecycles do not share a pool.
- **API compatibility impact:** None.
- **Database/migration impact:** None.
- **Sprint 8 recommendation:** Batch 2 reliability fix, preferably together with AUDIT-001.
- **Further verification required:** None beyond offline lifecycle tests.

### AUDIT-008 — Persistence integration tests use the application database variable

- **Severity:** Medium
- **Confidence:** High
- **Exact files and lines:** `backend/tests/test_persistence_integration.py:28-48`; `backend/tests/persistence_guard.py:12-59`; contrast `backend/tests/test_api_integration.py:28-42`
- **Affected component:** live-test target selection
- **Evidence:** The persistence suite requires an opt-in flag but then reads `AIRMONITOR_DATABASE_URL`, not the dedicated `AIRMONITOR_TEST_DATABASE_URL` named by the audit/test safety contract. Its local-host/database-prefix guard does reject the protected database, which reduces but does not remove the configuration flaw.
- **Reproduction/static proof:** Set only the dedicated persistence test URL and opt in; the suite fails for a missing URL. Set the application URL to a disposable-looking target and opt in; the test suite consumes application configuration.
- **Real impact:** Test and application targets are conflated. CI/local operators can unknowingly alter application configuration to run tests, and safety verification of the dedicated variable gives false confidence.
- **Minimal recommended fix:** Read only the dedicated persistence-test variable and keep the existing driver, host, query-override, protected-name, and prefix checks.
- **Required regression test:** Source/behavior tests prove the dedicated variable is required and the application variable is ignored; messages must not include URL text.
- **API compatibility impact:** None.
- **Database/migration impact:** None; test infrastructure only.
- **Sprint 8 recommendation:** Batch 3 test hardening.
- **Further verification required:** Offline guard tests; no live DB is needed.

### AUDIT-009 — Persistence preflight connection failures are not sanitized

- **Severity:** Medium
- **Confidence:** High
- **Exact files and lines:** `backend/tests/test_persistence_integration.py:88-154`; `backend/tests/persistence_guard.py:28-59`; safe contrast `backend/tests/api_integration_guard.py:32-50`
- **Affected component:** integration-test credential safety
- **Evidence:** Target parsing errors are sanitized, but the persistence fixture directly awaits `_preflight_disposable_database(engine)`. A connection or driver exception propagates with its cause/context. The API suite already wraps equivalent preflight in a short `raise ... from None` failure.
- **Reproduction/static proof:** Inject a preflight exception containing a sentinel URL/user/password; the persistence path retains it because there is no catch. No live database is required to prove the propagation.
- **Real impact:** CI or terminal output can expose usernames, database names, connection parameters, and potentially credential-bearing exception representations.
- **Minimal recommended fix:** Generalize/reuse the safe preflight wrapper and ensure neither exception cause nor context retains the original secret-bearing object.
- **Required regression test:** Inject a sentinel-bearing `OperationalError`; assert the sentinel, URL, user, password, driver text, cause, and context are absent.
- **API compatibility impact:** None.
- **Database/migration impact:** None.
- **Sprint 8 recommendation:** Batch 3 test hardening.
- **Further verification required:** The exact asyncpg wording need not be reproduced; an injected exception is sufficient.

### AUDIT-010 — Live integration suites leave databases dirty and cannot repeat

- **Severity:** Medium
- **Confidence:** High
- **Exact files and lines:** `backend/tests/test_persistence_integration.py:88-154,184-919`; `backend/tests/test_api_integration.py:79-146,176-375`
- **Affected component:** integration isolation, cleanup, repeatability
- **Evidence:** Both preflights require every domain table to be empty. Tests then commit domain rows. Session fixtures finally dispose only the engine; there is no delete, truncate, rollback wrapper, database drop, or per-run database provisioning.
- **Reproduction/static proof:** Run a suite successfully against an approved empty disposable database, then run it again against the same target. The second preflight fails because the first run’s committed rows remain.
- **Real impact:** Tests are not repeatable against a stable disposable target, consume manual cleanup, and can produce order/previous-run failures that obscure real regressions.
- **Minimal recommended fix:** Have an external, strongly validated harness create a unique approved disposable database per run and delete only that database after success/failure, or implement equally safe validated cleanup that preserves commit/rollback semantics. Never clean the protected `airmonitor` database.
- **Required regression test:** Run each live suite twice through the disposable harness and prove both start empty, finish cleanly, and reject protected/nonlocal targets.
- **API compatibility impact:** None.
- **Database/migration impact:** No application migration; CI/local test orchestration changes.
- **Sprint 8 recommendation:** Batch 3 test hardening.
- **Further verification required:** Must later be verified only against a disposable local PostgreSQL database.

### AUDIT-011 — `AIRMONITOR_API_PREFIX` is accepted but ignored

- **Severity:** Low
- **Confidence:** High
- **Exact files and lines:** `backend/app/core/config.py:17-27,39-44`; `backend/.env.example:6`; `backend/app/api/router.py:8-10`; `backend/tests/test_config.py:49-64`
- **Affected component:** configuration and routing
- **Evidence:** The setting is parsed and documented, while router composition hardcodes `/api/v1`; there is no production consumer of `settings.api_prefix`.
- **Reproduction/static proof:** Constructing settings with `/test/api` leaves routes and OpenAPI under `/api/v1`.
- **Real impact:** Operators can believe a reverse-proxy/base-path setting works when it has no effect.
- **Minimal recommended fix:** Because `/api/v1` is the approved stable contract, remove the ineffective setting/template entry unless configurable routing is explicitly required. If required, wire it at app construction.
- **Required regression test:** Assert either that the unsupported setting no longer exists or that supplied/default prefixes produce the intended route/OpenAPI paths.
- **API compatibility impact:** Removing the inert option preserves current paths; honoring it introduces configurable paths and needs deployment documentation.
- **Database/migration impact:** None.
- **Sprint 8 recommendation:** Low-priority cleanup after Batch 2.
- **Further verification required:** Product decision on whether route prefixes are configurable.

### AUDIT-012 — Dependency-override cleanup test is a false positive

- **Severity:** Low
- **Confidence:** High
- **Exact files and lines:** `backend/tests/test_api_routes.py:588-596`; related real fixture cleanup at `backend/tests/test_api_integration.py:149-173`
- **Affected component:** test quality
- **Evidence:** The test named `test_application_fixture_restores_dependency_overrides_after_failure` manually mutates, clears, and restores a dictionary. It never invokes the fixture teardown or creates a failure through a request.
- **Reproduction/static proof:** Break the actual fixture’s teardown; this test still passes because it reproduces restoration in the test body.
- **Real impact:** A dependency override can leak between tests while the specifically named cleanup regression remains green.
- **Minimal recommended fix:** Exercise the real yield fixture across an intentional failing path and inspect state after teardown, or use a focused fixture unit test.
- **Required regression test:** The replacement test must fail when the fixture’s `finally` restoration is removed.
- **API compatibility impact:** None.
- **Database/migration impact:** None.
- **Sprint 8 recommendation:** Batch 3.
- **Further verification required:** None.

### AUDIT-013 — Health contract test depends on ambient settings

- **Severity:** Low
- **Confidence:** High
- **Exact files and lines:** `backend/tests/test_health.py:8-23`; `backend/app/core/config.py:39-50`
- **Affected component:** test isolation and environment precedence
- **Evidence:** The test expects fixed service/version values but calls `create_application()` without explicit `_env_file=None` settings. Environment variables or a local `.env` can legally alter those values.
- **Reproduction/static proof:** Set a permitted `AIRMONITOR_SERVICE_NAME` before collection; the test’s fixed expected response no longer matches.
- **Real impact:** The offline unit suite can fail or pass differently based on developer/CI ambient configuration.
- **Minimal recommended fix:** Inject explicit isolated settings and reset any relevant settings cache in the fixture.
- **Required regression test:** Run with conflicting ambient variables and prove the isolated health contract remains deterministic.
- **API compatibility impact:** None.
- **Database/migration impact:** None.
- **Sprint 8 recommendation:** Batch 3.
- **Further verification required:** None.

### AUDIT-014 — Root documentation still presents implemented v2 as future work

- **Severity:** Low
- **Confidence:** High
- **Exact files and lines:** `README.md:7,331-344`
- **Affected component:** project documentation and portfolio readiness
- **Evidence:** The README says FastAPI/PostgreSQL/SQLAlchemy/Alembic/pytest are planned, while the reviewed backend already implements them and exposes eight versioned operations.
- **Reproduction/static proof:** Compare the cited README statements with the 41 runtime files, requirements, migration, and generated OpenAPI inventory.
- **Real impact:** Contributors, reviewers, and portfolio users receive an incorrect architecture/status picture and can overlook the authoritative backend.
- **Minimal recommended fix:** After stabilization, update the README with the v1/v2 boundary, current implemented scope, setup/testing commands, known deployment limits, and roadmap.
- **Required regression test:** No automated code test is warranted; require a documentation review checklist that validates links, commands, operation count, and status against the release.
- **API compatibility impact:** None.
- **Database/migration impact:** None.
- **Sprint 8 recommendation:** Correct after Phase C stabilization, before portfolio publication.
- **Further verification required:** Reconcile final wording with the approved post-fix state.

## 7. Test-coverage gaps

These are missing proofs, not confirmed production bugs unless tied to a finding above.

| Gap | Existing evidence | Required addition | Priority |
|---|---|---|---|
| Factory settings → real engine | metadata/health tests only; live API overrides `get_db_session` | spy factory test with two apps and no connection | Highest |
| Non-finite telemetry | no schema/service/HTTP case | raw `1e999`, infinities, parser-supported NaN; zero-write assertion | Highest |
| Session chronology | naive/missing timestamp and end-before-start only | measurement-before-start and end-before-latest | High |
| PostgreSQL int32 API bounds | nonnegative checks only | max/max+1 for paths and six counters | High |
| Framework/generic errors | domain/validation/integrity only | 404, 405, runtime, OperationalError, response error | High |
| Unsafe production settings/logging | ordinary parsing only | cross-field rejection and parameter-redaction tests | High |
| Engine lifespan | no application lifespan | initialize/dispose exactly once, no-connect OpenAPI path | High |
| Record vs complete/cancel | static lock review only | disposable-DB concurrent races with timeouts | High |
| Record/start vs deactivate | static lock review only | disposable-DB concurrent races | Medium |
| Concurrent duplicate ingestion | unique behavior tested sequentially | simultaneous same non-null ID and null IDs | Medium |
| Concurrent record/record count | no live case | exact sample-count and row-count assertion | Medium |
| Real migration lifecycle | metadata/mocked/offline DDL only | disposable upgrade, inspect, downgrade, repeat upgrade | High before next migration |
| Integration rerun/cleanup | no cleanup | two consecutive isolated suite runs | High |
| Persistence unavailable-DB sanitization | URL parser tests only | injected secret-bearing connection exception | High |
| Test-order independence | no randomized/repeated proof | targeted reverse/order run after cleanup fixes | Medium |
| Read service followed by write service on one session | not a current request path | autobegin/transaction behavior test before composing such flows | Future |

### Tests that can pass while production remains wrong

- `backend/tests/test_config.py:90-120` proves factory metadata and health settings but not database settings.
- `backend/tests/test_api_integration.py:149-173` replaces `get_db_session`, bypassing the faulty engine composition entirely.
- `backend/tests/test_api_routes.py` replaces whole services, so endpoint wiring tests cannot prove PostgreSQL type boundaries, commits, rollbacks, or post-commit response rendering.
- `backend/tests/test_api_routes.py:588-596` is the confirmed cleanup false positive.
- AST/source-policy tests at `backend/tests/test_api_architecture.py:36-103`, `test_database.py:165-184`, `test_repositories.py:343-391`, `test_services.py:1245-1286`, and `test_api_integration_guard.py:73-82` can protect selected structure while behavior changes through an unlisted helper.
- The migration suite strongly compares metadata and offline DDL, but mocked/offline execution cannot prove PostgreSQL upgrade/downgrade behavior, privileges, or existing-data compatibility.

### Positive test evidence

- Guard parsers reject non-asyncpg drivers, remote hosts, target-affecting query parameters, and protected/non-prefixed database names.
- API integration preflight deliberately removes secret-bearing exception context.
- Persistence tests cover rollback and reuse after expected uniqueness failures.
- Concurrent active-session creation has a live guarded test.
- Null and non-null source-message semantics are covered.
- Unknown fields, coordinate pairing, timezone awareness, route status codes, response models, operation IDs, and handler sanitization are exercised.
- Dependency override cleanup exists in the live API client fixture even though its separate offline test is ineffective.

## 8. Architecture risks

These concerns are real future failure surfaces but are **not confirmed current defects** on the approved write paths.

### AR-001 — Active-session uniqueness is service-only

PostgreSQL can store multiple `measurement_sessions` rows with `status='active'` for one device. Current start logic locks device/runtime state and has a guarded concurrent-start test, so no current API race was proven. A future writer, administrative import, or maintenance script could violate the assumption behind `scalar_one_or_none()`.

**Future decision:** consider a partial unique index on `measurement_sessions(device_id) WHERE status='active'` after confirming cancellation/history semantics. It would add a migration and write/check cost but make the invariant database-owned.

### AR-002 — Runtime-state triad is service-only

No DB check ties `measurement_enabled`, `active_session_id`, and `measurement_started_at` together. Current services set/clear all three atomically. Future adapters must reuse that service or add database defense.

### AR-003 — Client validity metadata has unresolved ownership

`is_valid` and `validation_note` are explicit accepted fields, so this is not generic mass assignment. Current tests treat them as public. Before aggregation/AQI trusts them, decide whether a sensor may author quality status or whether only server validation may do so.

### AR-004 — Fixed runtime location fields have no production writer

`fixed_latitude`, `fixed_longitude`, and `location_updated_at` exist in ORM/migration but current services do not populate them; session and per-reading coordinates are stored separately. This is dormant model surface, not a current defect. ESP32/frontend design must decide the authoritative location source before using it.

### AR-005 — Integer primary-key capacity is finite

`raw_measurements.id` is signed 32-bit `INTEGER`. At 100 devices sending once per second, fleet-wide exhaustion is approximately 249 days; at one sample every five seconds, approximately 3.4 years. This is not a current correctness failure, but `BIGINT` should be planned before serious fleet/high-rate deployment. Session/device IDs and `sample_count` should be reviewed in the same migration.

### AR-006 — Non-HTTP callers can bypass schema validation

Service signatures accept ordinary Python floats/integers and rely partly on API schemas plus DB checks. Firmware workers, jobs, CLI imports, or aggregation code must not call services with unchecked values. High-risk invariants should also exist at the service/DB layers.

### AR-007 — Query services rely on request cleanup for implicit transactions

SQLAlchemy reads autobegin a transaction. Query services intentionally do not commit/rollback; request session closure rolls back/releases it. This is adequate for current scalar reads. Large streaming reads or composing a read then a write on the same session will need an explicit transaction policy.

## 9. Security review

### Verdict

The current code is suitable only for controlled local/private development after the two high defects are fixed. It is **not ready for public exposure** because there is no authentication/authorization, no rate limiting/request-size policy, no production fail-closed configuration, and incomplete generic error handling. Missing authentication is treated as a deployment limitation, not mislabeled as a current implementation bug.

### Verified positives

- No tracked prohibited `.env`, secret header, private key, certificate, database, SQLite file, virtual environment, bytecode, cache, or log was found.
- The tracked public secret example contains placeholder-like values. Firmware security scanning found a reference/include context and display/status strings, not a tracked credential value. No value was printed into this report.
- `.gitignore` excludes environment files except the public example, firmware secrets, certificates/keys, databases, exports, environments, caches, coverage, logs, and archives.
- Request models use `extra="forbid"`.
- Endpoints pass declared model fields into explicit service signatures; repositories explicitly construct ORM objects. No unrestricted ORM mass assignment was found.
- Production queries use SQLAlchemy expressions and bound parameters. No dynamic SQL or string interpolation was found in `app`.
- Domain, request-validation, and integrity responses discard exception text and constraint details.
- Integration target guards restrict driver, host, database prefix, protected name, and target-changing query parameters.
- Response models expose selected scalar fields, not relationships, URLs, credentials, or internal exception objects.

### Confirmed security-relevant defects

- AUDIT-001 can select the wrong database target.
- AUDIT-002 creates a commit/failed-response retry hazard.
- AUDIT-005 leaves generic/debug error behavior outside the stable envelope.
- AUDIT-006 permits traceback and SQL-parameter disclosure modes in production.
- AUDIT-008 conflates application and persistence-test database variables.
- AUDIT-009 can retain credential-bearing connection exceptions.

### Deployment limitations

| Limitation | Current consequence | Required policy/control |
|---|---|---|
| No API authentication/authorization | Anyone with network access can enumerate devices, change status, start/end sessions, view session coordinates, and ingest data | Per-device and administrative credentials, authorization boundaries, rotation/revocation |
| No rate limiting or payload-size policy | Write/lock amplification and resource abuse are unbounded at application policy level; `validation_note` has no field-length cap and maps to `TEXT`, so one request can create an unusually large row/response | Reverse-proxy and application limits keyed by credential/device plus a domain-appropriate note limit |
| No CORS middleware | Safe same-origin default, but separately hosted frontend cannot call API | Explicit environment-specific origin allowlist; never wildcard credentials |
| Default docs/OpenAPI routes enabled | Internal contract exposed if service is public | Decide public/internal policy and protect or disable as appropriate |
| Health is liveness only | Orchestrator cannot distinguish process alive from dependency readiness | Separate authenticated or minimally revealing readiness policy |
| No trusted-host/security-header policy | Deployment depends entirely on outer proxy | Define proxy trust, forwarded headers, hosts, TLS, HSTS, and related headers |
| No structured redacted application logging | Failures cannot be investigated safely/consistently | Logging schema, request IDs, redaction, retention, access controls |

## 10. Performance review

### Current query and lock profile

Approximate SQL round trips per successful operation, excluding connection checkout and commit protocol:

| Operation | Approximate statements | Notes |
|---|---:|---|
| Get device | 1 | primary-key read |
| Get active session | 1 | `(device_id, status)` read |
| Create device | 3 | UID precheck, device insert/flush, runtime insert/flush |
| Set status | 2 | device lock, update at commit |
| Start session | 4 | device lock, runtime lock, session insert, runtime update |
| Complete/cancel | 5 | three locking reads, session update, runtime update |
| Record with null source ID | 6 | three locking reads, insert, session count update, runtime update |
| Record with non-null source ID | 7 | same plus duplicate precheck |

No current endpoint performs a list read, relationship traversal, or looped query, so no current N+1 pattern or unbounded result was found.

### Hot-path observations

- The non-null source-message precheck adds one indexed `SELECT` to every such ingestion. The unique constraint already resolves races and is translated after rollback. Removing the precheck could save a round trip but changes the fast duplicate path; measure before changing it. This is an optional optimization, not a confirmed performance defect.
- Device UID precheck is similarly redundant for correctness but occurs on a low-frequency path.
- The device → runtime → session locks serialize writes per device. This is correct and bounds race complexity, but throughput per high-rate device is intentionally limited by transaction latency.
- `pool_pre_ping` improves stale-connection behavior but costs a checkout ping when the dialect/pool requires it. No pool size, overflow, checkout timeout, statement timeout, or recycle policy is exposed for deployment.
- No production `refresh()` call or duplicate post-write reload was found.
- Engine creation and application import do not connect. Static guarded OpenAPI generation called no connection/create-schema method.
- Current responses are bounded single-resource payloads. Scalar response models avoid lazy relationship I/O; `expire_on_commit=False` makes post-commit loaded scalar access workable, and AUDIT-002 is the concrete serialization exception.

### Growth and read-path planning

- Raw measurements will dominate table and index size. Each additional index increases insert WAL, page writes, vacuum work, storage, and cache pressure.
- Prefer keyset cursors over offset pagination. Stable ordering requires `(timestamp, id)`, not timestamp alone.
- Do not partition by default. Establish retention, ingest rate, query latency, vacuum behavior, and table-size thresholds first. Partitioning becomes reasonable when operational evidence shows very large tables or retention/drop requirements.
- Plan `BIGINT` before the projected fleet-wide integer horizon described in AR-005.
- Avoid count-on-every-page and unrestricted response payloads. Use bounded limits and optional approximate/separate totals.

### Performance verdict

Current write/query structure is appropriate for the implemented eight operations. The one avoidable hot-path duplicate lookup is not yet proven material. The major near-term performance work is lifecycle correctness, workload measurement, deterministic read indexes, bounded keyset endpoints, and raw-ID capacity—not micro-optimization.

## 11. PostgreSQL schema and index inventory

### Table/column inventory

All timestamp columns below are `timestamp with time zone`; all `Float` mappings become PostgreSQL double precision.

| Table | Columns |
|---|---|
| `devices` | `id INTEGER` PK/autoincrement; `device_uid VARCHAR(255)` non-null; `name VARCHAR(255)` null; `is_active BOOLEAN` non-null server default true; `created_at`, `updated_at` non-null server default now |
| `device_runtime_state` | `device_id INTEGER` PK; `measurement_enabled BOOLEAN` non-null default false; `active_session_id INTEGER` null; fixed latitude/longitude float null; measurement-started/location-updated/last-seen timestamps null; `updated_at` non-null default now |
| `measurement_sessions` | `id INTEGER` PK/autoincrement; `device_id INTEGER` non-null; `status VARCHAR(20)` non-null default active; `started_at` non-null default now; `ended_at` null; latitude/longitude float non-null; `sample_count INTEGER` non-null default 0; nullable average/min/max floats; nullable `aqi_pm25 INTEGER`; nullable `aqi_category VARCHAR(50)`; created/updated timestamps non-null default now |
| `raw_measurements` | `id INTEGER` PK/autoincrement; device/session IDs non-null; source ID `VARCHAR(255)` null; measured timestamp non-null; received timestamp non-null default now; nullable temperature/humidity/PM floats; six nullable particle `INTEGER`s; paired nullable coordinates; `is_valid BOOLEAN` non-null default true; validation note text null; created timestamp non-null default now |

ORM `default`/`onupdate` values that are client-side behaviors are not expected as database DDL; corresponding server defaults and structural properties match the revision.

### Constraint inventory

| Table | PK | Named unique | Foreign keys | Check constraints |
|---|---:|---:|---:|---:|
| `devices` | 1 | 1 (`device_uid`) | 0 | 0 |
| `device_runtime_state` | 1 | 1 (`active_session_id`) | 2, including composite active-session/device | 3 |
| `measurement_sessions` | 1 | 1 (`id, device_id`) | 1 | 15 |
| `raw_measurements` | 1 | 1 (`device_id, source_message_id`) | 2, including composite session/device | 14 |
| **Total** | **4** | **4** | **5** | **32** |

Delete actions:

- runtime → device: `CASCADE`;
- session → device: `RESTRICT`;
- raw measurement → device: `RESTRICT`;
- runtime active session/device → session: `RESTRICT`;
- raw session/device → session: `RESTRICT`.

The composite session unique constraint is not accidental redundancy: PostgreSQL needs a unique referenced column set for the composite device-consistency foreign keys.

### Index inventory

#### Explicit indexes — 4

1. `ix_measurement_sessions_device_id_started_at (device_id, started_at)`
2. `ix_measurement_sessions_device_id_status (device_id, status)`
3. `ix_raw_measurements_device_id_measured_at (device_id, measured_at)`
4. `ix_raw_measurements_session_id_measured_at (session_id, measured_at)`

#### Constraint-backed unique indexes — 8

- four primary-key indexes;
- `devices(device_uid)`;
- `device_runtime_state(active_session_id)`;
- `measurement_sessions(id, device_id)`;
- `raw_measurements(device_id, source_message_id)`.

PostgreSQL automatically creates unique indexes for primary keys and unique constraints. All current child-side FK lookup columns have a useful leading index:

- runtime `device_id`: primary key;
- runtime `(active_session_id, device_id)`: unique `active_session_id` narrows to at most one row;
- session `device_id`: both explicit session indexes;
- raw `device_id`: device/time and device/source indexes;
- raw `(session_id, device_id)`: session/time index starts with `session_id`.

### Current and future query coverage

| Query | Current coverage | Verdict |
|---|---|---|
| Device by ID | device PK | Complete |
| Device by UID | UID unique index | Complete |
| Runtime by device ID | runtime PK | Complete |
| Active session by device ID | `(device_id, status)` | Complete |
| Session by ID | session PK | Complete |
| Duplicate source message | `(device_id, source_message_id)` unique | Complete |
| Measurement insertion | all integrity indexes present | Correct; each index adds expected write cost |
| Future session history ordered by `started_at, id` | `(device_id, started_at)` lacks deterministic tie-break column | Add/replace with `(device_id, started_at, id)` when contract is approved |
| Future session measurements ordered by `measured_at, id` | `(session_id, measured_at)` lacks tie-break column | Add/replace with `(session_id, measured_at, id)` |
| Future latest/device measurements | `(device_id, measured_at)` lacks tie-break column | Add/replace with `(device_id, measured_at, id)` |

### Index verdict and trade-offs

**Current verdict:** no confirmed missing-index correctness or current-query defect.

**Future read verdict:** three composite keyset indexes are recommended—and required for the intended bounded-at-scale read contract—once ordering/filter contracts are fixed. Existing two-column indexes remain usable, but adding `id` covers the deterministic cursor tie-break and avoids extra sorting/work at scale. The cost is larger raw/session indexes, extra WAL/write latency, vacuum work, and migration build time.

Potential future refinements:

- A partial unique active-session index would database-enforce AR-001 and may replace the full `(device_id, status)` index. It adds a migration and conflict-handling implications.
- The source-message unique constraint indexes null rows even though null IDs may repeat. At high raw volume, a partial unique index for non-null IDs could be smaller and cheaper, but replacing the named constraint changes error translation and requires migration/test work.
- New indexes should be measured with real `EXPLAIN (ANALYZE, BUFFERS)` only on approved disposable/development data, never during this audit.

## 12. ORM-to-migration parity review

### Verdict

**Pass — exact structural parity found.**

The ORM and `a4f9c2e7d1b6` agree on:

- all four table names;
- all columns and order-independent membership;
- PostgreSQL-relevant types;
- string lengths;
- nullability;
- primary-key/autoincrement intent;
- server defaults;
- four named unique constraints;
- 32 named checks;
- five named foreign keys, including both composite FKs;
- all delete actions;
- all four explicit indexes.

No extra migration column, missing ORM column, mismatched check expression, mismatched FK target, or index-name drift was found.

### Revision graph and symmetry

- Revision count: 1
- Root: `a4f9c2e7d1b6`
- Sole head: `a4f9c2e7d1b6`
- `down_revision`: `None`
- Upgrade order: devices → sessions → runtime/raw dependents → indexes
- Downgrade order: indexes/dependents → sessions → devices

Static create/drop order is dependency-safe and symmetric. The installed non-project Python environment had no Alembic distribution, so the Alembic CLI `heads/history` commands could not run. An AST-only graph check independently produced one root/head and history `a4f9c2e7d1b6`.

### What remains unproven

- PostgreSQL execution of upgrade/downgrade/repeated upgrade;
- actual constraint/index introspection after migration;
- role ownership and least-privilege grants;
- existing-data compatibility of any future finite-value or `BIGINT` migration.

Those require the separately authorized disposable-database workflow, not Phase A.

## 13. API and OpenAPI review

### Generated operation inventory

The guarded offline OpenAPI build produced OpenAPI `3.1.0`, nine total operations, eight under `/api/v1`, and unique operation IDs. Connection/create-schema guards were not called.

| Method | Path | Operation ID | Documented responses |
|---|---|---|---|
| POST | `/api/v1/devices` | `create_device` | 201, 409, 422 |
| GET | `/api/v1/devices/{device_id}` | `get_device` | 200, 404, 422 |
| PATCH | `/api/v1/devices/{device_id}/status` | `set_device_status` | 200, 404, 422 |
| POST | `/api/v1/devices/{device_id}/sessions` | `start_measurement_session` | 201, 404, 409, 422, 500 |
| GET | `/api/v1/devices/{device_id}/sessions/active` | `get_active_measurement_session` | 200, 404, 422 |
| POST | `/api/v1/devices/{device_id}/sessions/active/complete` | `complete_active_measurement_session` | 200, 404, 409, 422, 500 |
| POST | `/api/v1/devices/{device_id}/sessions/active/cancel` | `cancel_active_measurement_session` | 200, 404, 409, 422, 500 |
| POST | `/api/v1/devices/{device_id}/measurements` | `record_raw_measurement` | 201, 404, 409, 422, 500 |
| GET | `/health` | generated health ID | 200 |

### Verified positives

- Router composition has no current static/dynamic path conflict.
- All eight versioned operations have explicit unique IDs.
- Create operations return 201; reads/status/transitions return 200.
- Request and response models are explicit.
- Unknown body fields are forbidden.
- Positive path IDs, timezone awareness, coordinate pairing, value ranges, and status literals are represented in schemas.
- Each service dependency converges on the same `get_db_session`; FastAPI’s per-request dependency cache provides one session per request.
- Query services and write services are separate.
- Endpoint responses access scalar attributes only.
- Application import/factory/OpenAPI construction does not statically request a session or connect.

### Contract defects

- AUDIT-001 breaks factory/dependency correctness.
- AUDIT-002 breaks commit/result atomicity from the client’s perspective.
- AUDIT-004 exposes DB range errors as 500.
- AUDIT-005 makes the error body inconsistent and OpenAPI incomplete.
- AUDIT-011 advertises an inert prefix.

### OpenAPI verification caveat

Because the available Python 3.13 environment lacked `pydantic-settings`, the build used an in-memory compatibility shim for settings construction and patched connection/create-schema methods to fail if called. It used the installed FastAPI `0.139.1` and repository schemas/routes. This proves route/schema generation and no connection call but is not a substitute for rerunning `test_api_openapi.py` in the exact declared environment.

## 14. Test-quality review

### Inventory and balance

The 21 Python files contain:

- schema and settings unit tests;
- ORM metadata/model tests;
- repository/service tests with async mocks;
- API route/error/OpenAPI tests;
- source/AST architecture tests;
- migration metadata/offline SQL tests;
- pure integration-target guard tests;
- opt-in PostgreSQL persistence and HTTP integration suites.

This is broader than a mock-only suite. The guarded live tests are valuable, but their gating and cleanup defects currently reduce confidence.

### Behavioral confidence

Strongest areas:

- service transaction ownership and expected rollback;
- duplicate device/source behavior;
- null source-ID repeatability;
- inactive-device handling;
- session transitions;
- API schema/response/status basics;
- ORM/migration metadata parity;
- target URL rejection rules.

Weakest areas:

- app factory to real engine composition;
- post-commit serialization failures;
- numeric DB boundaries;
- chronology;
- unexpected exception contract;
- most concurrency interleavings;
- real migration execution;
- integration repeatability and unavailable-DB sanitization.

### Concurrency verdict

No conflicting lock order was found:

```text
device → runtime state → session
```

This same prefix/order is used by start, record, complete, cancel, and device-status operations. Therefore:

- record vs complete/cancel serializes on the device lock;
- deactivate vs record/start serializes on the device lock;
- concurrent start is protected by device/runtime locks and has live coverage;
- expected duplicate uniqueness races fall back to the DB constraint.

The absence of live tests for the other races is a coverage gap, not proof of a bug.

### Baseline execution

Before running tests, existence-only checks confirmed:

- `AIRMONITOR_TEST_DATABASE_URL`: absent;
- `AIRMONITOR_API_TEST_DATABASE_URL`: absent;
- `AIRMONITOR_READ_API_TEST_DATABASE_URL`: absent;
- persistence opt-in: disabled;
- repository `.env`: absent.

No live integration path could activate.

Results:

1. `python -B -m pytest -q -p no:cacheprovider`
   - collection stopped with nine import errors;
   - missing declared packages included `httpx2`, `pydantic-settings`, Alembic, and `asyncpg`;
   - one integration module skipped before collection;
   - no product pass/fail baseline can be claimed.
2. Dependency-independent subset:
   - `168 passed, 1 skipped, 1 failed`;
   - the single failure was `test_application_import_does_not_connect_or_create_schema`, because the test tried to patch absent `asyncpg`;
   - it did not demonstrate an application connection attempt.
3. The user-provided prior baseline remains `246 passed, 2 skipped`, but is **not independently verified by this run**.

The system interpreter was Python `3.13.7`. Installed relevant versions included FastAPI `0.139.1`, Pydantic `2.13.4`, SQLAlchemy `2.0.47`, and pytest `8.4.2`; this differs from the declared complete dependency set. `pip check` reported no broken relationships among installed packages, but that does not mean the project requirements are installed.

## 15. Configuration, dependency, and Git hygiene review

### Configuration

- Settings are centralized and environment-prefixed.
- Database driver validation correctly requires `postgresql+asyncpg`.
- Unknown settings are ignored, which eases mixed environments but can hide misspellings; no confirmed incident was found.
- AUDIT-006 shows production does not fail closed.
- AUDIT-011 shows the API prefix is inert.
- The example database URL contains predictable local-development placeholders and targets the protected local database. It is not evidence of a live secret, but production must require explicit replacement.
- Alembic’s INI URL is a generic placeholder. `env.py:59-66` replaces it from runtime settings in online mode, while `env.py:24-35` intentionally uses the INI URL for offline SQL generation. No credential was treated as live.

### Dependencies and reproducibility

Backend direct packages are version-pinned:

- FastAPI `0.139.1`
- pydantic-settings `2.14.2`
- Uvicorn `0.51.0`
- SQLAlchemy `2.0.51`
- asyncpg `0.31.0`
- Alembic `1.18.5`
- httpx2 `2.7.0`
- pytest `8.4.2`

Gaps:

- no transitive lock/constraints file;
- no `pyproject.toml`, package metadata, or `.python-version`;
- Pydantic is directly imported but not declared directly;
- tests rely on AnyIO’s pytest plugin through a transitive dependency rather than a direct declaration;
- runtime/dev separation exists, but reproducibility depends on transitive resolver state;
- no installed-environment check in CI because no CI configuration exists.

No declared direct dependency was proven unused: Uvicorn is the server entrypoint, asyncpg is loaded through the SQLAlchemy URL, Alembic is a CLI/runtime tool, and the remaining packages are imported directly. Exact declared-version compatibility remains unverified because the available interpreter did not contain the declared environment. These are deployment/readiness gaps, not current runtime defects.

### Git and generated-file hygiene

- Initial worktree status was clean.
- Tracked prohibited sensitive/generated path count was zero.
- Credential-pattern path scan returned only an integration-guard test and legacy firmware status/reference context; redacted classification found no tracked actual credential.
- `.gitignore` is substantively complete for the project.
- `.gitignore:61-64` duplicates earlier environment/cache patterns; harmless cleanup only.
- No tracked CI workflow, Dockerfile, Compose file, project lock, or constraints file exists.
- `alembic/versions/.gitkeep` is obsolete if present outside the tracked revision inventory; no functional impact.
- README status drift is confirmed as AUDIT-014.

## 16. Product-readiness gaps

No item in this section was implemented.

| Capability | Exact prerequisites before implementation/deployment |
|---|---|
| Telemetry read API | Fix AUDIT-001/002/003/004; define filters, visibility, timestamp semantics, limits, response DTOs, not-found/empty behavior, authorization, and composite indexes; add service/repository/API/integration tests |
| Keyset cursor pagination | Stable unique order `(timestamp, id)`; opaque/versioned cursor; direction and inclusive/exclusive rules; max/default limit; filter binding; malformed/stale cursor errors; three composite indexes; no offset fallback for large tables |
| API-key authentication | Threat model; separate device/admin permissions; secure generated keys; hashed-at-rest storage; key prefix/lookup; rotation, revocation, expiry; per-device binding; constant-time verification; audit events; rate limiting; migration and bootstrap process |
| ESP32 ingestion | Authenticate by stable device UID/key rather than database ID; map firmware payload to v2 schema; idempotency/source ID; retry/backoff semantics for commit/failed-response cases; UTC clock/skew policy; server-vs-device location and validity ownership; TLS validation; size limits; device provisioning |
| Frontend v2 | Read endpoints and pagination; authentication/session handling; stable error client; CORS; generated/typed client or contract tests; loading/empty/error states; map/chart data limits; no reuse of legacy v1 endpoints as replacements |
| CORS | Known frontend origins per environment; least methods/headers; explicit credential policy; preflight tests; no wildcard with credentials |
| Docker | Reproducible Python 3.13 image; non-root user; health/readiness; runtime secret injection; no secrets in layers; migration entrypoint policy; graceful shutdown; resource limits; Compose only for local disposable/development PostgreSQL |
| CI | Python 3.13; locked install; offline suite; lint/type/secret/generated checks; disposable PostgreSQL service with approved names; migration upgrade/inspect/downgrade/re-upgrade; integration cleanup; `git diff --check`; artifact/log sanitization |
| Application logging | Structured events; request/correlation ID; operation/device identifiers under privacy policy; no URL/password/payload/coordinates by default; exception classification; retention/access controls |
| Observability | Request/DB latency, status/error rate, ingest throughput/lag, duplicate/conflict rate, pool usage/waits, transaction/deadlock metrics, tracing, dashboards, alerts, SLOs, readiness |
| Minute aggregation | Source-of-truth and late-arrival policy; UTC buckets; idempotent/rebuildable job; raw retention; schema/index design; completeness/validity rules; backfill and correction tests |
| AQI and NowCast | Authoritative formula/version; units and rounding; required history/completeness; missing/invalid sample policy; timezone boundaries; cap/category mapping; reproducible fixtures; provenance/version fields; clear non-regulatory disclaimer |

## 17. Optional improvements

These are worthwhile cleanups or optimizations, not confirmed defects and not prerequisites for the Batch 1 fixes:

- Remove the device-UID and non-null source-message prechecks only if measurement shows the saved round trip outweighs the clearer early conflict path.
- Expose pool size/overflow/checkout/statement timeouts only after deployment concurrency and latency are known.
- Evaluate a partial unique active-session index and a partial non-null source-message index only after their invariant/error-contract implications are approved.
- Consolidate duplicate `.gitignore` entries and remove the now-redundant Alembic revision `.gitkeep`.
- Add a direct Pydantic declaration and a transitive lock/constraints strategy as part of packaging/CI work.
- Add project metadata and a machine-readable Python 3.13 declaration.
- Decide whether generated clients/schema-diff checks add enough value once the public read/auth contracts exist.

## 18. Rejected concerns and false positives

The following were investigated and **not** reported as confirmed defects:

- **ORM/migration drift:** none found.
- **Current missing FK/query index:** none found.
- **Duplicate null source IDs:** intentional; PostgreSQL unique semantics allow repeats and code bypasses lookup.
- **Concurrent active-session race:** current device/runtime locks serialize starts; live coverage exists.
- **Inconsistent lock ordering/deadlock:** no reverse order found.
- **Completion/cancellation/ingestion partial writes:** service transaction contexts are atomic for reviewed failures.
- **Session reuse after expected `IntegrityError`:** catch occurs after context rollback; persistence tests exercise reuse.
- **Stale locked identity-map objects:** locked reloads use `populate_existing=True`.
- **Deactivation must cancel a session:** current tests explicitly preserve an active session while disabling new ingestion/start; this is current product behavior, not a proven defect.
- **Lazy-loading/MissingGreenlet in current responses:** scalar-only response models, no relationship access, and `expire_on_commit=False` avoid it.
- **Repository transaction leakage:** repositories flush but do not begin/commit/rollback.
- **Generic mass assignment:** extras are forbidden and service/repository parameters are explicit. Ownership of `is_valid` remains AR-003.
- **SQL injection:** no dynamic SQL/string construction in application persistence.
- **CORS absence as a vulnerability:** same-origin default is safe; CORS is a frontend deployment prerequisite.
- **Missing authentication as a code regression:** it is a deployment blocker/unfinished feature, not a claim that the current private development API enforces auth.
- **Import/OpenAPI database access:** guarded build invoked no connection or schema creation.
- **Current N+1/unbounded list query:** no list endpoint exists.
- **Tracked secret match:** no actual tracked credential was established; values were not displayed.

## 19. Prioritized stabilization backlog

### Batch 1 — critical and high correctness/security fixes

1. AUDIT-001: make settings, engine, session factory, and lifespan application-owned.
2. AUDIT-002: reject non-finite telemetry before any write; add service defense and plan DB checks.

No endpoint implementation belongs in this batch.

### Batch 2 — approved medium reliability fixes

1. AUDIT-003: enforce session/measurement chronology after clock-skew decision.
2. AUDIT-004: align API integer bounds with PostgreSQL or approve a widening migration.
3. AUDIT-005: complete and document the error envelope.
4. AUDIT-006: make production settings fail closed and hide SQL parameters.
5. AUDIT-007: dispose the async engine through lifespan.
6. Resolve AUDIT-011 after deciding whether prefix configurability is real.

### Batch 3 — test hardening

1. AUDIT-008: dedicated persistence URL.
2. AUDIT-009: sanitized persistence preflight.
3. AUDIT-010: repeatable disposable integration databases.
4. AUDIT-012: replace the false-positive override cleanup test.
5. AUDIT-013: isolate health settings.
6. Add missing high-value correctness, error, lifecycle, concurrency, and migration tests from Section 7.

### Deferred architecture work

- database enforcement for one active session per device;
- runtime-state triad constraint/design;
- trust ownership of validity/location fields;
- `BIGINT` capacity migration;
- pool/timeout tuning after workload measurements;
- partial source-message index evaluation;
- package/project metadata and transitive dependency locking;
- README correction after stabilized behavior is approved.

### Future feature work

- telemetry reads and cursors;
- authentication/authorization;
- ESP32 v2 contract;
- frontend v2/CORS;
- Docker and CI;
- structured logging/observability;
- aggregation, AQI, and NowCast.

## 20. Proposed Phase B triage

1. Accept/reject each confirmed finding and lock stable IDs.
2. Reproduce AUDIT-001/002/004/005 with new offline failing tests only.
3. Decide timestamp skew/out-of-order behavior for AUDIT-003.
4. Decide whether finite-value DB checks ship with the API fix or a later migration; define existing-data preflight.
5. Decide int32 bounds versus `BIGINT`.
6. Approve canonical framework/generic error codes and compatibility notes.
7. Approve production configuration source, secret injection, and diagnostic policy.
8. Approve a disposable integration provisioning/cleanup workflow.
9. Re-run the exact declared environment and reconcile `246 passed, 2 skipped` before code changes.
10. Keep read API implementation out of triage/fix branches.

## 21. Proposed Phase C bug-fix batches

### Phase C1 — application composition and finite telemetry

- Write failing tests for AUDIT-001 and AUDIT-002.
- Implement application-owned settings/engine/session/lifespan.
- Implement finite schema/service validation.
- Add DB checks only through the required migration safety workflow.
- Re-run offline suite and guarded disposable PostgreSQL tests.

### Phase C2 — domain/API reliability

- Add chronology tests and fix AUDIT-003.
- Add int-boundary tests and fix AUDIT-004.
- Add error-contract tests and fix AUDIT-005.
- Add production-settings/log-redaction tests and fix AUDIT-006.
- Verify response/status/OpenAPI compatibility remains limited to documented corrections.

### Phase C3 — test infrastructure

- Fix AUDIT-008 through AUDIT-010 before relying on live suites as a release gate.
- Replace/isolate AUDIT-012 and AUDIT-013.
- Add missing concurrency races with bounded timeouts and deadlock diagnostics.
- Execute migration upgrade/inspect/downgrade/re-upgrade only against an approved disposable local database.

### Phase C4 — documentation and deferred decisions

- Resolve the API-prefix contract.
- Update README after the stabilized API/database state is known.
- Record separate future decisions for authentication, active-session DB enforcement, `BIGINT`, read indexes, and data-quality ownership.

## 22. Telemetry read API gate

**Recommendation: do not begin implementation yet.**

Minimum gate to open read-API implementation:

1. AUDIT-001 fixed and proven with the real session dependency.
2. AUDIT-002 fixed with zero-write non-finite regressions.
3. AUDIT-003 and AUDIT-004 behavior approved and fixed, so reads do not expose newly accepted inconsistent/out-of-range data.
4. Exact baseline rerun in the declared environment.
5. Stable read authorization decision, even if implementation is scheduled in the read feature.
6. Cursor order/filter contract approved before creating the three composite indexes.
7. Integration target/cleanup safety sufficient to test the new repositories and endpoints repeatedly.

Read API **specification and query/index prototyping on paper** may begin during triage. Production endpoint code should wait for the gate.

## 23. Offline verification record

| Check | Result |
|---|---|
| Required integration variables | all three absent by existence-only check |
| Persistence live-test opt-in | disabled |
| Repository `.env` | absent by existence-only check; not opened |
| PostgreSQL access | none |
| Python | system Python 3.13.7 |
| Full pytest | not runnable to baseline; nine missing-package collection errors |
| Partial/collectable subset | 168 passed, 1 skipped, 1 environment-caused failure |
| `pip check` | no broken requirements among installed packages; project dependency set incomplete |
| Source compilation | 43 app/Alembic Python files and 21 test Python files compiled in memory; no bytecode writes |
| Alembic graph | one root/head `a4f9c2e7d1b6`; CLI unavailable because Alembic distribution absent |
| OpenAPI | 3.1.0; 9 total operations; 8 `/api/v1`; unique IDs; connection guards untouched |
| ORM/migration parity | pass, static field-by-field comparison |
| Current index coverage | pass |
| Tracked prohibited paths | zero |
| Tracked credential review | no actual credential established; values redacted/not printed |
| Final sensitive/generated-path audit | pass; zero prohibited or generated tracked paths |
| Initial Git status | clean |
| Final `git diff --check`/report whitespace check | pass; the requested report is untracked and has no trailing-whitespace errors |
| File modifications during review | only this audit report |
| Git write operations | none |

## 24. Authoritative references

Primary documentation used for non-obvious framework/database conclusions:

- [Pydantic `allow_inf_nan` configuration](https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict.allow_inf_nan)
- [PostgreSQL numeric types and special floating-point values](https://www.postgresql.org/docs/current/datatype-numeric.html)
- [FastAPI error handling and overriding default handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [Starlette exception behavior, including debug tracebacks](https://www.starlette.io/exceptions/)
- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [SQLAlchemy asyncio and explicit engine disposal](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [SQLAlchemy session transaction/rollback behavior](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [SQLAlchemy engine echo and `hide_parameters`](https://docs.sqlalchemy.org/en/20/core/engines.html)
- [PostgreSQL unique indexes and constraint-backed indexes](https://www.postgresql.org/docs/current/indexes-unique.html)
- [PostgreSQL multicolumn index leading-column behavior](https://www.postgresql.org/docs/current/indexes-multicolumn.html)
- [PostgreSQL partial indexes](https://www.postgresql.org/docs/current/indexes-partial.html)
- [PostgreSQL index benefits and write overhead](https://www.postgresql.org/docs/current/indexes.html)

## 25. Final Phase A verdict

AirMonitor v2 has a credible, test-conscious foundation and an exact initial schema, but the application factory/database boundary and non-finite telemetry path are unsafe enough to stop feature expansion. Stabilize those first, then the chronology/type/error/lifecycle issues, then repair the live-test harness. Current index coverage is sufficient; future read indexes should follow the approved keyset contract rather than precede it. Public deployment remains blocked on authentication and production hardening.

Phase A made no production, test, migration, configuration, environment, database, legacy, or Git index/ref/configuration change. The only intended filesystem change is this untracked report.
