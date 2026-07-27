Sprint 8 Final Verification
Final result: the required offline baseline is reproduced, but Sprint 8 is not fully closed.
Classification	Count	Findings
FIXED	10	AUDIT-001, 002, 003, 004, 005, 007, 008, 009, 012, 013
PARTIALLY FIXED	1	AUDIT-006
OPEN	2	AUDIT-011, AUDIT-014
DEFERRED	1	AUDIT-010
NO LONGER APPLICABLE	0	—

No file or Git state was changed. PostgreSQL was not contacted. No database URL value from the environment was read or printed.
Telemetry Read API implementation should not begin yet. AUDIT-010 remains deferred, and production database hardening, API-prefix configuration, README accuracy, authorization policy, and read cursor/filter contracts need a bounded closure phase first.
Repository identity
Repository root/worktree: C:\Users\nazar\.codex\worktrees\3509\AirMonitor
Working directory: C:\Users\nazar\.codex\worktrees\3509\AirMonitor\backend
Current detached HEAD: c10c0e2d5d5d5f5fed1206a1e9838274a2d3bc3d
Base branch: feature/full-audit-stabilization
Base tip and merge base: 4c68698872d6c4a4e38d0ff0c5b304638e0df4e8
HEAD^ is the base tip; detached HEAD is one commit ahead.
The same current commit is named by review/sprint-8-final-verification in the main C:\Users\nazar\Desktop\AirMonitor worktree.
Initial and final short status: ## HEAD (no branch)
Final porcelain-v2 status contained only:
# branch.oid c10c0e2d5d5f5fed1206a1e9838274a2d3bc3d
# branch.head (detached)
Loaded governing instructions:
[AGENTS.md](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/AGENTS.md)
No other repository AGENTS.md governed this worktree.
The original audit was read completely:
[sprint-8-full-codebase-audit.md](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/docs/reviews/sprint-8-full-codebase-audit.md)
Audit history:
Original audited baseline: c883223053f8c5e271d7acd8c10db95daee8eb36
Audit-report commit: 4316e651b8f24d095ca58620ec31b9b08d675cac
Current HEAD: c10c0e2d5d5d5f5fed1206a1e9838274a2d3bc3d
From baseline to HEAD: 28 files changed, 3,296 insertions, 464 deletions. From the audit-report commit to HEAD: 26 backend application/test files changed, 1,924 insertions, 65 deletions. ORM models, Alembic migration, requirements, .env.example, and README were not changed after the audit.
Phase commits
Phase C1:
f70a536a16672d370f418d56c119e4053efbd19d — scope
53c9e833e301b8d18a76e54733f9930ee5e8037b — application-owned database state
622ba6b5f1d41c7005be6fec63b4a2adae8af574 — reject non-finite telemetry
Phase C2A:
9da497e70ad6639e66ba7ebf3d6f1e24c94db2c9 — scope
e74f3a3cc839571a717996e716becf15d7fbde52 — chronology and PostgreSQL INTEGER boundaries
Phase C2B:
f104b0850a79b073c1f4d50bceea9af33b9ec3fd — scope
237f7914d44c468b228cbd1c6af61d3b1f196857 — safe API errors
545bff2675a4ede2b3b38cf65828cd2cff640012 — production hardening
Phase C3:
d2d70d47481878e9fbb43009587cc16b90ae75c9 — scope
3e46c602b5c59f2dbca2916cbf37c1fc842dc4d3 — persistence guards
4c68698872d6c4a4e38d0ff0c5b304638e0df4e8 — fixture and health isolation
Final verification scope:
c10c0e2d5d5d5f5fed1206a1e9838274a2d3bc3d
Skills and execution order
using-agent-skills
source-driven-development
fastapi
supabase-postgres-best-practices
security-and-hardening
code-review-and-quality
doubt-driven-development
The final adversarial pass used the existing internal fresh-context audit agent. No external model or agent CLI was invoked.
Verification commands and results
All Python commands used only:
$PY = 'C:\Users\nazar\Desktop\AirMonitor\backend\.venv\Scripts\python.exe'
Before testing, existence-only checks established:
AIRMONITOR_RUN_PERSISTENCE_INTEGRATION=absent
AIRMONITOR_TEST_DATABASE_URL=absent
AIRMONITOR_API_TEST_DATABASE_URL=absent
AIRMONITOR_READ_API_TEST_DATABASE_URL=absent
AIRMONITOR_DATABASE_URL=present
backend/.env=absent
The ordinary application variable’s value was never read. Every Python verification process removed it by name before importing application code.
Runtime versions:
Python 3.13.7
FastAPI 0.139.1
Pydantic 2.13.4
pydantic-settings 2.14.2
SQLAlchemy 2.0.51
Alembic 1.18.5
asyncpg 0.31.0
pytest 8.4.2
Results:
Verification	Command	Result
Complete offline suite	$PY -B -m pytest -q -p no:cacheprovider	356 passed, 2 skipped, 6.27s
Dependency consistency	$PY -B -m pip check	No broken requirements found
Composition/lifecycle	pytest on test_application_composition.py, test_database.py, test_api_dependencies.py, test_config.py	38 passed, 1.45s
Error contract	pytest tests/test_api_errors.py	18 passed, 0.84s
Chronology/int32	Exact schema, route, service, and repository nodes covering boundaries, equality, rejection, max aggregate and lock order	46 passed, 2.01s
Persistence/fixture/health	test_persistence_guard.py, test_api_integration_guard.py, test_health.py, and the two override-restoration nodes	39 passed, 1.32s
OpenAPI	pytest tests/test_api_openapi.py	6 passed, 1.55s
ORM/Alembic parity	pytest tests/test_migrations.py	14 passed, 1.07s
Non-finite telemetry	Exact schema/API/service finite-value nodes	35 passed, 1.57s
Alembic head	$PY -B -m alembic -c alembic.ini heads --verbose	One head: a4f9c2e7d1b6
Alembic history	$PY -B -m alembic -c alembic.ini history --verbose	One root/head migration
Source compilation	In-memory compile(...) over all Python sources	65 compiled: app 41, tests 22, Alembic 2
Diff whitespace	git diff --check	Exit 0, no output
Working-tree diff	git diff --stat	No output
Final status	git status --short --branch	## HEAD (no branch)

A skip-only diagnostic over the two live integration modules returned nonzero because there were no runnable tests; both modules were skipped for the intended reasons:
API integration requires a dedicated disposable database URL.
Persistence integration requires explicit opt-in.
No integration opt-in was enabled.
The guarded in-memory probe replaced asyncpg.connect, synchronous/async engine connection entry points, and MetaData.create_all with failure guards. It proved:
connection_or_schema_calls=0
openapi_version=3.1.0
operation_count=9
api_v1_operation_count=8
health_operation_count=1
operation_ids_unique=true
lifespan_body_exception_disposed_once=true
shutdown_dispose_exception_propagated=true
configured_api_prefix_applied=false
A separate production-settings probe, using only a constructed local test string and printing only its Boolean result, found:
canonical_equivalent_default_target_accepted=true
Finding matrix and evidence
AUDIT-001 — FIXED
Files/symbols: [app/main.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/main.py) create_application, application.state.database_engine, application.state.session_factory; [app/db/session.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/db/session.py) create_database_engine, create_session_factory; [app/db/dependencies.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/db/dependencies.py) get_session_factory, get_db_session.
Tests: test_create_application_uses_exact_settings_for_engine_and_session_factory, distinct-application isolation, request-factory provenance, and per-request session reuse.
Evidence: each application creates its engine and session factory from the exact supplied Settings; request dependencies resolve from request.app.state. There is no cached/global database engine.
Remaining risk: app.state is mutable, and a synchronous exception during application assembly after engine construction would occur before lifespan ownership begins. Engine creation itself opens no connection.
Next action: preserve application ownership and add an assembly-failure cleanup test if factory construction becomes more complex.
AUDIT-002 — FIXED
Files/symbols: [app/schemas/_base.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/schemas/_base.py) RequestModel.model_config with allow_inf_nan=False; [app/services/measurement.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/services/measurement.py) _validate_finite_pm_values.
Tests: schema rejection/finite acceptance, API rejection before service, and service rejection before transaction.
Evidence: NaN and positive/negative infinity are rejected both at HTTP validation and at the service boundary. This is necessary because Pydantic otherwise allows non-finite values by default, and PostgreSQL floating types support special infinity/NaN values. Pydantic configuration, PostgreSQL numeric types
Remaining risk: direct ORM writes and pre-existing database rows bypass these application boundaries; there is no database finite-value constraint.
Next action: before exposing historical reads, perform a guarded finite-data preflight and evaluate PostgreSQL-correct finite-value CHECK constraints.
AUDIT-003 — FIXED
Files/symbols: [app/services/measurement.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/services/measurement.py) record_measurement, _transition_session; [app/repositories/measurement.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/repositories/measurement.py) get_latest_measured_at.
Tests: reject terminal time before the latest measurement, allow equality, reject measurement before session start, allow equality, preserve record/terminal lock order, and bounded MAX(measured_at) aggregate.
Evidence: session lower and upper chronology is enforced. Record and terminal transitions use the same device → runtime → session locking order, and terminal transition queries the maximum measurement timestamp after acquiring those locks.
Remaining risk: concurrency evidence is mocked/static. No live PostgreSQL record-versus-complete/cancel interleaving test ran, and direct writers outside the service can bypass the locking discipline.
Next action: after AUDIT-010, add repeatable live concurrency tests for record versus complete and record versus cancel.
AUDIT-004 — FIXED
Files/symbols: [app/schemas/_base.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/schemas/_base.py) POSTGRES_INTEGER_MAX, PostgresInteger; the device, session and measurement endpoint device_id path constraints.
Tests: schema counter max/rejection, all path-ID max/rejection cases, route counter max/rejection, OpenAPI maximum inventory.
Evidence: current public identifiers and particle counters reject values above 2,147,483,647 before service execution. That is PostgreSQL INTEGER’s documented upper bound. PostgreSQL integer types
Remaining risk: future read cursors, pagination fields, and filter identifiers could omit the shared constraint.
Next action: require the shared int32 types for every new public field mapped to PostgreSQL INTEGER.
AUDIT-005 — FIXED
Files/symbols: [app/api/errors.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/api/errors.py) handle_http_exception, handle_unexpected_error, install_exception_handlers; [app/api/responses.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/api/responses.py) error_responses.
Tests: 18 error tests covering 404, 405 with Allow, generic runtime/SQLAlchemy errors, framework 500s, validation, domain errors, and integrity errors.
Evidence: with debug=False, unknown errors return the fixed 500 envelope without exception or SQL details; documented operations include a 500 response contract. SQLAlchemy engines always set hide_parameters=True. FastAPI error handling, SQLAlchemy parameter hiding
Remaining risk: Starlette intentionally substitutes traceback responses for the installed 500 handler when debug mode is enabled. Production rejects debug mode, so this is a development/test-mode caveat rather than an unresolved production finding. Starlette exceptions
Next action: document the debug-mode exception, and add sanitized server-side correlation logging when observability work begins.
AUDIT-006 — PARTIALLY FIXED
Files/symbols: [app/core/config.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/core/config.py) validate_production_settings, SettingsConfigDict; [app/db/session.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/db/session.py) hide_parameters=True.
Tests: production rejects debug, echo, and the exact unchanged default URL; safe explicit configuration is accepted; validation inputs/logs are hidden.
Evidence: debug and SQL echo are reliably rejected in production, sensitive Pydantic inputs are hidden, and SQL parameters are always hidden. However, the database check compares the raw URL to one exact literal.
Adversarial result: a canonical-equivalent default/local target with the default port omitted was accepted. Equivalent host spellings and harmless query options present the same class of bypass.
Remaining risk: production can still use the development database target and credentials while evading the literal-string comparison.
Next action: parse and compare database target components structurally, reject canonical variants of the default local target, and add omitted-port, host-alias, case, encoding, and query-option tests.
AUDIT-007 — FIXED
Files/symbols: [app/main.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/main.py) lifespan; [app/db/session.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/db/session.py) application-scoped engine construction.
Tests/evidence: application lifespan disposes its engine exactly once; independent applications dispose distinct engines; guarded factory/OpenAPI/lifespan execution made zero connection attempts. A lifespan-body exception still disposed once, while an exception raised by dispose() propagated.
Startup/shutdown review: there is no asynchronous pre-yield startup operation. Any exception during the served lifespan unwinds through finally; shutdown disposal is awaited. SQLAlchemy explicitly recommends awaiting AsyncEngine.dispose() because asynchronous cleanup cannot safely be deferred to finalization. FastAPI lifespan, SQLAlchemy asyncio disposal
Process-global review: there is one module-level FastAPI application with its owned engine, but no process-global engine/session-factory cache. Importing without entering lifespan leaves an unconnected engine object, not a connected pool.
Remaining risk: a synchronous factory failure after engine construction but before returning the application would not enter lifespan cleanup.
Next action: retain current ownership; add construction rollback only if new fallible factory steps are introduced.
AUDIT-008 — FIXED
Files/symbols: [tests/test_persistence_integration.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/tests/test_persistence_integration.py) dedicated AIRMONITOR_TEST_DATABASE_URL loading; [tests/test_persistence_guard.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/tests/test_persistence_guard.py).
Tests: dedicated variable usage, application-variable-only rejection, application-variable ignoring, and approved-target validation.
Evidence: persistence tests cannot be configured by AIRMONITOR_DATABASE_URL; explicit opt-in and a dedicated disposable target are both required.
Remaining risk: future fixture refactoring could reintroduce generic settings loading.
Next action: preserve the guard tests as a mandatory quality gate.
AUDIT-009 — FIXED
Files/symbols: [tests/persistence_guard.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/tests/persistence_guard.py) run_persistence_preflight_safely; the persistence session fixture.
Tests: preflight failure is sanitized without exception chaining or target disclosure.
Evidence: raw preflight failures are replaced with a fixed message using suppressed chaining; engine disposal remains in the fixture’s outer cleanup.
Remaining risk: a future direct preflight call could bypass the wrapper.
Next action: keep the wrapper as the sole supported execution path.
AUDIT-010 — DEFERRED
Files/symbols: [tests/test_persistence_integration.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/tests/test_persistence_integration.py) _preflight_disposable_database, session_factory; [tests/test_api_integration.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/tests/test_api_integration.py) corresponding preflight and fixture.
Evidence: both suites require all domain tables to be empty before running. Fixtures dispose engines but do not truncate, roll back all test data, or otherwise restore the database.
Remaining risk: suites are not repeatable against the same disposable target and can fail after interruption or partial completion. This also blocks credible live concurrency verification.
Next action: a bounded integration-cleanup phase should implement reliable isolation, verify cleanup after failure, and run each integration suite twice against one disposable database. Do not perform that work during this audit.
AUDIT-011 — OPEN
Files/symbols: [app/core/config.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/core/config.py) Settings.api_prefix; [app/api/router.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/app/api/router.py) hardcoded prefix="/api/v1".
Evidence: AIRMONITOR_API_PREFIX is loaded/type-validated as a string but receives no semantic path validation and is never used during router composition. The guarded probe confirmed that changing it does not change actual routes.
Remaining risk: operators can believe a supported configuration is active when it is inert.
Compatibility assessment: wiring it now would make endpoint paths and OpenAPI inventory environment-dependent and could break clients, proxies, tests, and deployments. Removing it preserves the established /api/v1 contract.
Next action: unless runtime prefix configurability is an explicit requirement, remove the field and example entry. If it is required, introduce it as a documented, validated compatibility change with route/OpenAPI tests.
AUDIT-012 — FIXED
Files/symbols: [tests/test_api_routes.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/tests/test_api_routes.py) application fixture and the normal/exception restoration tests.
Evidence: tests drive the real fixture generator and verify exact dependency-override restoration after both normal execution and exceptions.
Remaining risk: new fixtures can still implement ad hoc override cleanup.
Next action: reuse the established fixture pattern.
AUDIT-013 — FIXED
Files/symbols: [tests/test_health.py](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/backend/tests/test_health.py) test_health_returns_expected_response_with_conflicting_ambient_settings.
Evidence: the health test injects conflicting AIRMONITOR_* settings but passes explicit Settings(..., _env_file=None), proving it uses the supplied application configuration.
Remaining risk: tests that import the module-level application without explicit settings can still depend on ambient configuration by design.
Next action: use explicit application factories and _env_file=None for isolated tests.
AUDIT-014 — OPEN
File: [README.md](C:/Users/nazar/.codex/worktrees/3509/AirMonitor/README.md).
Evidence: the README still describes the active system as Flask/SQLite and presents FastAPI/PostgreSQL v2 as planned. It does not accurately document v2 architecture, setup, environment variables, database behavior, nine endpoints, pytest commands, integration safety, or the current legacy/v2 branch status.
Relevant tests: none; the unchanged file was reviewed directly against the current code and OpenAPI inventory.
Remaining risk: developers and operators can launch the wrong application, use unsafe database assumptions, miss integration safeguards, or infer incorrect feature availability.
Next action: a documentation-only phase should rewrite these sections against the verified v2 behavior.
OpenAPI inventory
OpenAPI version: 3.1.0. Nine operations, eight under /api/v1, one /health, with nine unique operation IDs.
Method	Path	Operation ID
POST	/api/v1/devices	create_device
GET	/api/v1/devices/{device_id}	get_device
PATCH	/api/v1/devices/{device_id}/status	set_device_status
POST	/api/v1/devices/{device_id}/sessions	start_measurement_session
GET	/api/v1/devices/{device_id}/sessions/active	get_active_measurement_session
POST	/api/v1/devices/{device_id}/sessions/active/cancel	cancel_active_measurement_session
POST	/api/v1/devices/{device_id}/sessions/active/complete	complete_active_measurement_session
POST	/api/v1/devices/{device_id}/measurements	record_raw_measurement
GET	/health	get_health_health_get

ORM and Alembic consistency
Static/offline parity passed for:
Four tables: devices, device runtime state, measurement sessions, raw measurements.
All columns, types, nullability, primary keys, autoincrement behavior and server defaults.
Four primary keys, four named unique constraints, five foreign keys with delete behavior, 32 CHECK constraints, and four explicit indexes.
Dependency-safe creation and reverse-order drop behavior.
PostgreSQL DDL compilation and approved-object inventory.
No runtime settings, database connections, or live migrations during generation.
Alembic has exactly one root/head revision: a4f9c2e7d1b6. ScriptDirectory.get_heads() is the authoritative static head inventory API used by the verification. Alembic ScriptDirectory
This proves source-level ORM/migration parity, not the condition of any deployed database.
No-connection evidence
All live integration opt-ins were absent.
The ordinary application database variable was removed by name before every Python verification subprocess.
Import, application factory, OpenAPI and lifespan probes ran with connection and schema-creation entry points replaced by failure guards.
Guard counters remained zero.
Alembic inspection was limited to source/history/offline DDL.
No migration, preflight SQL, database creation/drop, or PostgreSQL client command was executed.
Security and compatibility assessment
The backend is materially safer for controlled development and private deployment:
Non-finite telemetry and int32 overflow are rejected before persistence.
Chronology conflicts have safe 409 responses.
Unknown failures are sanitized when debug is disabled.
Production rejects debug and SQL echo.
SQLAlchemy parameters are hidden.
Integration suites require dedicated local disposable targets.
No sensitive/generated paths were introduced.
It is not yet ready for an untrusted public deployment. Authentication/authorization, request/rate limits, production observability, and the canonical-equivalent database-target bypass remain outside or incomplete in this sprint. pip check verifies dependency consistency, not vulnerability status.
Compatibility remains stable for valid clients: operation IDs, success contracts, routes and status codes remain intact. Corrected invalid inputs now return 422/409. Removing inert api_prefix would preserve this stability; wiring it would require an explicit compatibility decision.
Bounded adversarial review
False-positive coverage: most lifecycle, transaction and concurrency evidence is mocked or static; live integration suites did not run.
Exception leakage: safe with debug=False; debug-mode traceback behavior remains intentional framework behavior.
Unsafe production bypass: canonical-equivalent default/local database targets bypass literal equality.
Chronology race assumptions: lock order is consistent, but no live record-versus-terminal interleaving test exists.
Int32 gaps: all current API fields are covered; future cursors, filters and pagination are not automatically protected.
Engine disposal: runtime lifespan disposal is correct; only pre-lifespan synchronous factory failure and import-without-lifespan remain low-risk edges.
Ambient environment: health and composition tests are isolated, but module-level app construction intentionally loads environment and .env settings.
Accidental database targeting: dedicated variables and target validators are effective; cleanup/repeatability remains deferred.
Migration drift: static parity is strong, but no deployed schema was inspected.
Stale documentation: README remains materially inaccurate.
Scope creep: none observed; no fix, refactor, file edit, integration activation or Git mutation occurred.
Remaining technical debt and next phase
Recommended bounded closure phase:
Fix AUDIT-006 with structural database-target validation.
Resolve AUDIT-011, preferably by removing the inert prefix setting unless configurability is explicitly required.
Implement AUDIT-010 integration isolation and prove two consecutive runs.
Add live chronology interleaving tests after cleanup exists.
Audit existing telemetry for non-finite data and decide on database constraints.
Rewrite README v2 architecture, setup, configuration, endpoints and test-safety sections.
Define Telemetry Read API authorization, stable ordering, cursor and filter contracts.
Repeat this offline audit and obtain manual external approval.
Final repository checks:
git diff --check: exit 0
git diff --stat: empty
tracked backend paths: 81
tracked sensitive/generated matches: 0
backend paths changed since audited baseline: 26
changed sensitive/generated matches: 0
filesystem generated-artifact matches: 0
backend/.env exists: false
final status: ## HEAD (no branch)
Telemetry Read API decision: NO-GO for endpoint implementation now. Preparatory paper design may proceed, but implementation should wait for the bounded closure phase and manual external review.
Stopped for manual external review.