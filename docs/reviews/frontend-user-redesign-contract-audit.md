# Frontend User Redesign Contract Audit

**Audit date:** 2026-08-05
**Inspected revision:** `8eadaae4b81c816102b6473dca54adf7a1673ff5`
**Scope:** current checkout only; no backend or Git write

## Verified baseline

The offline backend suite passed with 850 tests and 2 guarded skips. OpenAPI is
3.1.0 with 11 operations, 10 under `/api/v1`, and 11 unique operation IDs. The
sole Alembic head is `a75caa2b44f5`. Frontend typecheck, 84 Vitest tests,
production build, and six deterministic Playwright tests passed; two guarded
Compose tests skipped by design.

## Public API to user capability matrix

| Operation | Current request and response | Permitted user capability | Not inferred |
|---|---|---|---|
| `GET /health` | Exact health envelope | Show service availability and retry | Uptime history, infrastructure internals |
| `POST /api/v1/devices` | `device_uid`, optional `name`, optional `is_active`; returns one device | Register and select one sensor | Account registration, device catalogue |
| `GET /api/v1/devices/{device_id}` | Positive device ID; returns one device | Connect a known device ID and restore selection | Search or list devices |
| `PATCH /api/v1/devices/{device_id}/status` | `is_active`; returns updated device | Activate/deactivate selected sensor | Battery, Wi-Fi, firmware, MQTT status |
| `POST /api/v1/devices/{device_id}/sessions` | One real latitude/longitude pair; returns active session | Start one geolocated measurement session | Background tracking, fabricated coordinates |
| `GET /api/v1/devices/{device_id}/sessions/active` | Device-scoped; active session or safe 404 | Restore current workflow | Multiple active sessions |
| `POST .../sessions/active/complete` | Optional `ended_at`; returns completed session | Finish the current session | Undo or server-side editing |
| `POST .../sessions/active/cancel` | Optional `ended_at`; returns cancelled session | Cancel after confirmation | Deletion of session history |
| `POST /api/v1/devices/{device_id}/measurements` | Raw telemetry creation schema | Used only by approved device/backend smoke fixtures | Manual browser ingestion UI |
| `GET /api/v1/devices/{device_id}/sessions` | Status and half-open time filters, limit 1..500, opaque cursor | Newest-first history and “load more” | Page numbers, OFFSET, districts, distance |
| `GET /api/v1/devices/{device_id}/measurements` | Session and half-open time filters, limit 1..500, opaque cursor | Live `limit=1`, selected-session history, chart/table/map | Cursor decoding, forecast, wind, official AQI |

Every request remains device-scoped. Collection responses retain newest-first
API order and return `next_cursor` as an opaque string or null. The frontend
may forward a cursor only with the same resource and filters; it must never
decode, construct, compare, or display cursor contents.

## Reusable frontend boundaries

The existing implementation already provides and must retain:

- one typed Fetch client with normalized base URL/path joining, bounded timeout,
  caller AbortSignal, runtime response validation, and sanitized errors;
- strict versioned selected-device persistence;
- one-shot bounded geolocation requested only by session start;
- abortable active-session transitions;
- visibility-aware, non-overlapping live polling with `limit=1`;
- bounded opaque-cursor session and measurement pagination;
- presentation-only chart ordering and exact-value table fallback;
- isolated Leaflet creation/update/cleanup with OSM attribution;
- Vite and Nginx same-origin `/api` and exact `/health` proxy boundaries.

The redesign changes composition, routes, content, presentation, and tests. It
does not rewrite those contracts merely to fit a new visual structure.

## Unsupported capabilities that must remain honest

The backend has no users, credentials, tokens, roles, logout, password reset,
device listing, profiles, notifications, research enrolment, participant
records, community statistics, server settings, reverse geocoding, or route
sharing. UI must not issue requests for these capabilities or imply successful
server persistence. `/login` is an explanatory future-facing page only.

## Deployment boundary

The supported browser path remains same-origin:

- local Vite proxies `/api` and `/health` to host API;
- production Nginx proxies `/api/` and exact `/health` to Compose `api:8000`;
- frontend paths use SPA fallback, but API failures remain API responses;
- PostgreSQL remains unpublished; no CORS change is needed.

## Audit verdict

All requested real participant workflows are supported by the current 11
operations. No endpoint, schema, backend module, migration, or CORS middleware
change is justified for this redesign. Authentication and account UX require a
separate backend contract sprint.
