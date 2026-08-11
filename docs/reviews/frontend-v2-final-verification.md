# Frontend v2 Final Verification

**Verification date:** 2026-08-04

**Inspected revision:** `8eadaae4b81c816102b6473dca54adf7a1673ff5`

**Worktree:** detached feature checkout; all changes remained unstaged

## Executive verdict

AirMonitor frontend v2 is implemented under `frontend/` and integrated with
the existing 11-operation FastAPI backend. The delivered dashboard supports
backend health, device selection and registration, device activation, one-shot
geolocated session start, active-session completion and confirmed cancellation,
live telemetry, opaque-cursor session and measurement history, exact tables,
responsive SVG trends, and a synchronized Leaflet session map.

The supported production-style path is same-origin: Vite proxies local
development requests and non-root Nginx proxies Compose requests. No backend
CORS middleware, public schema, migration, telemetry repository, service, or
business rule was changed for frontend convenience. Legacy root application
and firmware files were not modified.

All required local gates completed successfully. There is no Critical or
Required finding and no implementation blocker. The work is ready for the one
required external manual review stop.

## Delivered frontend stack

- React 19.2.8 and React DOM 19.2.8;
- TypeScript 7.0.2 and Vite 8.2.0;
- browser Fetch with a typed response-validating client;
- Vitest 4.1.10, React Testing Library, user-event, and jsdom;
- Playwright 1.62.1 with Chromium and axe-core 4.12.1;
- Leaflet 1.9.4 with OpenStreetMap tiles;
- a custom SVG chart rather than an additional chart dependency;
- Node 24.19.0 build stage and pinned-digest unprivileged Nginx runtime.

The dependency snapshot and official-source implementation constraints are in
`docs/reviews/frontend-v2-source-research.md`. The operation-by-operation
checkout mapping is in `docs/reviews/frontend-v2-api-compatibility.md`.

## Frontend architecture

```text
src/api/              typed transport, errors, contract validation
src/config/           VITE_API_BASE_URL normalization
src/storage/          versioned selected-device persistence
src/geolocation/      bounded one-shot location adapter
src/features/device/  selection, registration, activation
src/features/health/  independent backend health state
src/features/session/ active-session lifecycle and confirmation dialog
src/features/telemetry/ non-overlapping live polling and freshness UI
src/features/history/ session and measurement cursor pagination
src/features/chart/   presentation-only trend transforms and SVG charts
src/features/map/     coordinate filtering and isolated Leaflet lifecycle
src/pages/            cohesive dashboard composition
src/components/       optional-section error boundary
e2e/                  deterministic and guarded real-stack browser flows
```

The dashboard composes focused hooks and feature panels. Fetch boilerplate is
not duplicated in components, and no component owns the entire application.
React state and hooks are sufficient; there is no Redux, router, generated
client, server-side rendering, or large UI framework.

## API integration and error behavior

The client consumes every established backend capability without redesigning
the contract:

- `/health` availability metadata;
- device create, lookup, and status update;
- session start, active lookup, complete, and cancel;
- measurement ingestion only in the guarded real-stack fixture;
- session and measurement collection reads in the dashboard.

The client enforces positive bounded IDs, list limits `1..500`, a bounded
eight-second timeout, caller `AbortSignal`, JSON success/error parsing, and
runtime response-shape checks. Known safe backend messages are accepted only
from a validated public error envelope. Network, timeout, abort, invalid
response, and HTTP failures are normalized; raw exceptions and complete traces
are never rendered.

## Same-origin proxy and CORS decision

`VITE_API_BASE_URL` defaults to the browser origin. During development, Vite
proxies `/api` and `/health` to host `127.0.0.1:8000`. In Compose, Nginx serves
the browser on loopback and proxies `/api/` plus exact `/health` to container
address `api:8000`.

This makes the standard path same-origin, so no backend CORS change was
required. Nginx keeps API locations ahead of the SPA fallback; a backend 404
remains JSON and cannot become `index.html`. The direct API loopback port is
retained for backend-only workflows. The PostgreSQL service has no host port.

## Device persistence

Only the selected numeric device ID is stored, under
`airmonitor.frontend.v2.device-id` as strict version-1 JSON. Restored values
must have exactly the expected keys and a PostgreSQL-range positive integer.
Malformed or stale values are discarded. The UI can clear or replace the
selection and reports blocked browser storage without preventing current-tab
use.

No API secret, database value, error trace, cursor internals, complete
measurement history, or geolocation history is persisted.

## Geolocation and session lifecycle

Geolocation uses `getCurrentPosition` only after the user selects “Начать
сессию,” with a ten-second timeout and bounded cached-position age. The adapter
rejects non-finite/out-of-range coordinates and distinguishes permission
denial, timeout, unavailable position, and unsupported browser from backend
errors. It never uses `watchPosition`, fabricates coordinates, or restarts
location during polling.

The active-session hook aborts obsolete requests and supports lookup, start,
complete, and cancel without reload. Cancellation requires an alert dialog.
The final review added a focused RED/GREEN regression for safe initial focus,
Tab containment, Escape close, and trigger-focus restoration.

## Live polling

Live telemetry requests the minimum page (`limit=1`) approximately every five
seconds. The next timeout is scheduled only after the current request settles,
so requests cannot overlap. Device change, unmount, and hidden-document state
abort the active request; polling resumes on visibility without page reload or
geolocation access.

Empty data is not treated as backend failure. The UI records the most recent
successful update, marks data stale after 15 seconds, preserves the last good
measurement during a temporary failure, and continues with bounded retry
cadence.

## Cursor pagination

Session history supports status and half-open started-time filters, 20-row
pages, newest-first API order, stable selection, and a 100-item memory cap.
Measurement history requires the selected session, supports half-open
measured-time filters, uses 100-row pages, and has a 500-item memory cap.

Both hooks:

- forward `next_cursor` unchanged;
- never decode, construct, compare, or modify cursor contents;
- append pages with ID-based deduplication while preserving API order;
- reset pages and obsolete requests when filters or scope change;
- expose loading, retry, empty, end, and cap states;
- make no page-number, OFFSET, or N+1 assumptions.

## Chart and exact data

The custom responsive SVG shows PM2.5, PM10, temperature, and humidity. It
creates an oldest-to-newest presentation copy without mutating the descending
API data, leaves missing-value gaps unconnected, and handles empty, one-point,
and constant-value series. Each chart has an accessible metric/unit/min/max
summary. A scrollable semantic table retains exact values in source order.

## Map

The map adapter creates Leaflet once per mounted non-empty view, uses only
finite in-range coordinates returned by the API, synchronizes marker and
session-list selection, creates popup content through DOM text nodes, retains
visible OpenStreetMap attribution, invalidates size after updates, and removes
markers/listeners/map state during cleanup.

Initialization or update failure is isolated from the rest of the dashboard.
Session information remains available outside the map. Deterministic tests mock
or block tile traffic. Real tiles require internet access to
`tile.openstreetmap.org`; offline tiles are intentionally not provided.

## UX, accessibility, and responsive review

The interface uses Russian copy, semantic headings and sections, explicit form
labels, real buttons, visible focus rings, non-colour status text, safe loading
and error announcements, keyboard-accessible history rows, a chart/table
fallback, and a map-independent session list. Cancellation focus is contained
and restored. Browser zoom is not disabled.

The visual system is a restrained technical dashboard rather than a marketing
page: mineral navy shell, off-white data surfaces, cyan/amber status accents,
compact typography, limited radii, no decorative animation, and no fake data.
Wide (`1440px`) and narrow (`390px`) browser inspection found no horizontal
overflow after the device and filter-grid responsive corrections.

Automated axe verification found zero serious or critical violations in the
deterministic dashboard fixture. Automated checks supplement rather than
replace the pending external manual review.

## Frontend verification results

| Gate | Result |
|---|---|
| `npm ci --no-audit --no-fund` | Passed; 124 packages installed from lockfile |
| `npm ls --all` | Passed; platform-specific optional dependencies only |
| `npm run typecheck` | Passed; zero TypeScript errors |
| `npm test` | Passed; 19 files, 84 tests |
| Focused cancellation dialog test | RED as expected, then 7/7 GREEN |
| `npm run build` | Passed; 47 modules transformed |
| Built HTML | 0.71 kB, gzip 0.43 kB |
| Built CSS | 26.00 kB, gzip 9.45 kB |
| Built JavaScript | 390.50 kB, gzip 118.25 kB |
| Runtime dependency audit | Passed; 0 vulnerabilities |
| Deterministic Playwright | 6 passed, 2 guarded Compose specs skipped |
| axe in Playwright | Zero serious or critical violations |
| Compose-backed browser smoke | 1 passed; real device/session/measurement flow |
| Post-restart browser recovery | 1 passed; device and newest telemetry restored |

The six ordinary browser tests cover dashboard load and health, device lookup,
registration and persistence, mocked-geolocation session start, denial,
completion, live update without reload, session/measurement cursor pagination,
chart/table/map, safe malformed backend failure, accessibility, and narrow
layout. The guarded smoke additionally exercised the real FastAPI/PostgreSQL
path with representative coordinates and telemetry.

## Backend compatibility and PostgreSQL results

| Gate | Result |
|---|---|
| Complete offline pytest suite | 850 passed, 2 skipped in 9.69 s |
| Focused CI infrastructure contract | 10 passed |
| `pip check` | No broken requirements |
| Guarded API PostgreSQL integration | 9 passed in 2.99 s |
| Guarded persistence PostgreSQL integration | 13 passed in 1.52 s |
| OpenAPI | 3.1.0; 11 operations; 10 under `/api/v1`; 11 unique IDs |
| Alembic heads | Exactly `a75caa2b44f5 (head)` |

The live suites used a dedicated loopback-only PostgreSQL 18.4 container and
an approved `airmonitor_api_test_` database name. The target was migrated from
base, both suites performed their guarded resets, and the exact container was
removed afterward. The protected database name `airmonitor` was never used.

The CI self-test required one narrow update so its exact allow-list includes
the official `setup-node` and failure-only `upload-artifact` actions added by
the frontend job. Its official-action, pinned-major, and no-secret-echo checks
remain enforced.

## Docker and clean Compose results

The frontend image uses `node:24.19.0-alpine3.23` only for the build stage and
the pinned unprivileged Nginx 1.31.1 Alpine digest for runtime. The runtime is
configured as UID/GID `101:101`; the API remains `10001:10001`. The final
frontend filesystem contains built HTML, hashed CSS/JavaScript, favicon, and
the base image error page—not development `node_modules`, source, or legacy
root application files.

The final disposable project name began `airmonitor-frontend-test-`. Evidence:

1. Compose interpolation validated quietly.
2. Frontend and backend images built successfully.
3. PostgreSQL started healthy with no published host port.
4. API started healthy after Alembic and reported the expected head.
5. Frontend started healthy and served the CSP-protected SPA.
6. Exact `/health` proxied correctly; `/api/` 404 remained JSON; frontend
   routes used SPA fallback.
7. Playwright registered and persisted a real device, started a session with
   mocked browser geolocation, sent representative telemetry through the API,
   observed a live update without reload, completed the session, and verified
   history, exact table, chart, and map.
8. Frontend restart returned to health.
9. API restart returned to health; dependent frontend recovered.
10. Re-running `alembic upgrade head` was idempotent and `alembic current`
    remained `a75caa2b44f5 (head)`.
11. Post-restart Playwright restored the selected device and newest telemetry.
12. Logs contained no generated database credential, complete database URL,
    personal host path, or Python traceback.
13. Containers, project images, network, and named volume were removed.
14. Label-based inventory reported no matching resource afterward.

Nginx syntax was also checked in the built runtime. The frontend root, health,
security headers, same-origin proxy, asset behavior, API boundary, and SPA
fallback were exercised through HTTP rather than inferred from configuration.

Two discarded verifier attempts are recorded for transparency. A PowerShell
wrapper rebound Compose `-d` to the common `-Debug` switch, and a later SQL
probe used API name `uid` instead of schema column `device_uid`. Neither was a
product failure. Both attempts ran under the unique disposable project, both
were cleaned with label-based zero-resource confirmation, and the corrected
fresh run above completed uninterrupted.

## CI changes

The existing workflow retains minimal `contents: read` permission, concurrency
cancellation, the complete offline backend job, guarded PostgreSQL job, and
backend image job. A frontend job now performs:

- Node 24.19.0 setup with npm lockfile caching;
- deterministic `npm ci`;
- TypeScript, Vitest, and production build gates;
- pinned Chromium installation and deterministic Playwright;
- seven-day test diagnostics upload only on failure;
- frontend image build and non-root configured-user inspection.

Normal pull-request CI needs no repository secret and does not rely on live map
tiles. GitHub-hosted execution itself was not available locally; every command
and image gate was reproduced locally.

## Security review

- No authentication was invented; loopback-only exposure remains the approved
  boundary for this unauthenticated MVP.
- PostgreSQL remains unpublished in Compose.
- No real `.env`, credential, complete database URL, personal IP, hostname,
  device ID, token, or host path was committed.
- API and frontend runtime users are non-root with `no-new-privileges`; the
  frontend root filesystem is read-only with a small `noexec` tmpfs.
- CSP restricts scripts, connections, frames, objects, forms, and image hosts.
  Leaflet's inline positioning requires the documented `style-src
  'unsafe-inline'` exception.
- The app contains no `dangerouslySetInnerHTML`, application `innerHTML`,
  `eval`, continuous location tracking, or cursor decoding.
- Map popup values use `textContent`; UI backend errors pass through safe
  envelope validation.
- External map attribution remains visible. No application code sends browser
  geolocation to OpenStreetMap.

## Performance review

- One polling loop requests one row and schedules only after settlement.
- History is paginated and capped at 100 sessions and 500 measurements.
- Live updates do not refetch all history or reinitialize geolocation.
- The map is initialized once for a non-empty view and cleaned on teardown.
- Chart transforms are bounded presentation copies; API arrays retain order.
- There is no frontend N+1 loop, OFFSET pagination, unbounded retry, or
  thousands-row unvirtualized table.
- The production bundle remains one modest application chunk; speculative
  memoization and route splitting were not added.

## Known limitations

- Authentication, authorization, rate limiting, HTTPS termination, and public
  internet deployment remain out of scope.
- The MVP has no device collection endpoint; users enter or register one
  active device ID.
- Browser UI reads measurements but does not expose a manual production
  measurement-ingestion form.
- OpenStreetMap tiles require internet and are subject to the public tile
  service policy/availability. List and table workflows remain usable offline.
- The custom chart intentionally provides trends and exact table fallback, not
  zooming, forecasting, or unlimited datasets.
- Automated accessibility tests and visual inspection passed, but the required
  external manual accessibility/UX review is still the final human gate.

## Cleanup and external-review stop

All temporary Vite/browser processes used by verification were stopped. All
disposable Docker containers, Compose images, networks, volumes, and the
standalone PostgreSQL integration container were removed. Reproducible
`node_modules`, `dist`, and Playwright failure output were removed after the
last successful run; no test report, coverage directory, or Python cache
remains in the worktree.

The final status contains seven modified tracked files and 77 untracked source,
test, configuration, planning, and documentation files. The tracked diff is
327 insertions and 27 deletions across seven files. All 84 changed/created text
files passed explicit trailing-whitespace, NUL, and final-newline checks.
`git diff --check`, BaseLoader YAML parsing, credential, database-URL,
personal-path, forbidden-scope, and temporary-artifact scans passed.

No Git write was performed: nothing was staged, committed, pushed, stashed,
merged, reset, cleaned, or configured. The Git index remained 34,776 bytes,
with SHA-256
`9367e9269345066497b095613becf8c527df5a0aa188f9d12e23934b156e4ca6`
and an empty cached diff. The handoff response carries the final per-file line
and SHA-256 manifest so this report's own final hash is included without a
self-referential checksum.
