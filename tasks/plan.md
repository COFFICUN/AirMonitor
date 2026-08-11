# AirMonitor User Frontend Redesign Plan

## Objective

Replace the rejected single-screen technical dashboard with a cohesive Russian
public site and participant application in the existing `frontend/` directory.
Keep the proven typed API, storage, geolocation, polling, pagination, chart,
Leaflet, same-origin proxy, Docker, and CI boundaries. Backend contracts and
legacy root files remain read-only.

## Verified pre-edit baseline (2026-08-05)

- Checkout: detached `8eadaae4b81c816102b6473dca54adf7a1673ff5`.
- Git index: clean; SHA-256
  `9367e9269345066497b095613becf8c527df5a0aa188f9d12e23934b156e4ca6`.
- Frontend: typecheck passed; 19 Vitest files and 84 tests passed; production
  build passed; deterministic Playwright 6 passed and 2 guarded tests skipped.
- Backend: 850 passed and 2 skipped; `pip check` passed; one Alembic head
  `a75caa2b44f5`.
- OpenAPI: 3.1.0; 11 operations total; 10 under `/api/v1`; 11 unique IDs.

## Source-led decisions

- Use `react-router@8.3.0`, not the legacy browser-package recommendation.
  Current official declarative documentation installs `react-router` and uses
  `BrowserRouter`; its MIT package requires React/React DOM >=19.2.7 and Node
  >=22.22.0, compatible with this checkout.
- Route modules use `React.lazy` and `Suspense`. Leaflet and history-heavy
  routes are not part of the initial landing-page chunk.
- Confirmation dialogs preserve focus containment, Escape close, safe initial
  focus, and trigger focus restoration.
- PM2.5 colour bands are presentation aids, never AQI or a health conclusion.
  WHO values are averaging-period guidelines; a single sensor point is not a
  24-hour average.
- Keep same-origin Vite/Nginx proxying. API paths remain outside SPA fallback.

## Implementation slices

### 1. Contract and specification

- Create the redesign spec, endpoint/feature audit, and future-auth boundary.
- Record exact baseline and prohibited fabricated capabilities.
- Gate: documentation review and unchanged OpenAPI inventory.

### 2. Navigation and visual foundation

- Add router and lazy route configuration.
- Add design tokens, shared controls/states, original SVG/CSS mascot “Айри”,
  public header/footer, app sidebar/header/mobile navigation, 404, and route
  error handling.
- Build `/`, `/about`, `/participate`, `/methodology`, and `/login` without any
  authentication request or credential storage.
- Gate: RED/GREEN routing, public page, mascot, keyboard, and reduced-motion
  tests; typecheck and build.

### 3. Local preferences and core participant workflow

- Add versioned local settings with strict validation, migration-safe reset,
  and no personal or secret values.
- Compose existing device, health, active-session, and live-polling hooks in a
  shared app context mounted only under `/app`.
- Rebuild `/app`, `/app/measurement`, `/app/device`, and `/app/settings`.
- Gate: storage-corruption, device, geolocation, session, polling-overlap,
  cancellation, empty/error/retry, and preference tests.

### 4. Sessions, data, charts, and map

- Rebuild `/app/sessions` with opaque cursor pagination and real filters.
- Build `/app/data` with pure min/max/mean/median/count functions and explicit
  “loaded sample” scope.
- Build `/app/map` from real session coordinates, with one marker per
  stationary session, synchronized details, OSM attribution, tile opt-out,
  and defensive cleanup. Never infer movement or draw a polyline.
- Gate: pagination, statistics, chart transform, coordinate, selection,
  cleanup, empty, and failure tests.

### 5. Browser flows and responsive accessibility

- Replace deterministic fixtures with Almaty-domain data while preserving exact
  API shapes and cursor pass-through assertions.
- Cover public routes, persistence, start/deny/complete/cancel, live polling,
  sessions, data, map, login no-op, keyboard, reduced motion, and widths
  360/390/768/1280/1440.
- Capture required screenshots under test output, copy final reviewed evidence
  to the documented screenshot directory, then remove ephemeral reports.
- Gate: required Playwright tests and zero serious/critical axe findings.

### 6. Runtime and repository verification

- Verify TypeScript, all Vitest tests, production build, dependency tree/audit,
  deterministic Playwright, static files, links, YAML, secrets, personal paths,
  whitespace, final newlines, API image, frontend image, Compose config, clean
  stack, restarts, migrations, live backend smoke, logs, non-root users, and
  resource cleanup.
- Re-run backend offline and guarded PostgreSQL suites without accessing the
  protected `airmonitor` database.

### 7. Review and handoff

- Review correctness, readability, architecture, compatibility, accessibility,
  UX, security, performance, browser reliability, containers, CI, docs, and
  cleanliness. Resolve all Critical and Required findings.
- Update README and the redesign accessibility/final verification reports.
- Re-run exact Git status/stat/cached-stat and index hash checks. Leave every
  change unstaged and stop once for external manual review.

### 8. Final point-based product polish (2026-08-10)

- Preserve the accepted field-laboratory visual system and original Айри
  mascot; this is a cleanup pass, not another redesign.
- Correct public and participant terminology to the product invariant: one
  session equals one stationary geographic point.
- Replace the former connected per-measurement visualization with session
  markers and a selected-point detail panel.
- Balance the measurement layout, add a real system/light/dark theme with
  versioned preference migration, and show the actual preferred device in
  settings.
- Re-run responsive, accessibility, deterministic browser, real-backend,
  Docker/Compose, documentation, and Git-index verification.

## Dependency order

```text
contract audit
  -> router + design system + layouts
  -> public pages
  -> app context + preferences
  -> core participant workflow
  -> histories + statistics + chart + map
  -> browser/accessibility coverage
  -> Docker/Compose/backend regression
  -> review, docs, cleanup, manual-review stop
```

## Scope controls

- No Git writes, backend changes, public-schema changes, auth simulation,
  device listing, notifications, profile/research entities, manual browser
  measurement ingestion, reverse geocoding, third-party user-location sharing,
  fake statistics, AQI, battery/Wi-Fi/firmware data, or unbounded history.
- No remote font, image, animation, chart, or UI-framework dependency.
- New dependencies require exact pinning, compatible license/runtime, lockfile
  update, `npm audit`, typecheck, tests, and build evidence.
