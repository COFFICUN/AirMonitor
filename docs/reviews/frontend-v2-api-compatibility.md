# Frontend v2 API Compatibility Matrix

## Scope and source baseline

This matrix records the AirMonitor v2 contract consumed by the frontend at
detached commit `8eadaae4b81c816102b6473dca54adf7a1673ff5`. The current checkout is
authoritative. Sources inspected:

- `backend/app/api/router.py` and `backend/app/api/v1/router.py`;
- `backend/app/api/routes/health.py`;
- `backend/app/api/v1/endpoints/{devices,sessions,measurements}.py`;
- `backend/app/schemas/{devices,sessions,measurements,telemetry,errors}.py`;
- `backend/app/api/{query_validation,responses,errors}.py`;
- offline `create_application().openapi()` output;
- route, schema, OpenAPI, cursor, query-validation, repository, service, and
  guarded integration tests under `backend/tests/`.

The generated document is OpenAPI 3.1.0 with 11 operations, 10 under
`/api/v1`, one under `/health`, and 11 unique operation IDs.

## Shared public rules

- Device, session, and measurement IDs are positive PostgreSQL integers:
  `1..2147483647`.
- Request models reject unknown body fields and non-finite JSON numbers.
- Request timestamps are ISO 8601 date-times with a determinable UTC offset.
- Validation failures use HTTP 422 and the safe envelope described below.
- List upper time bounds are exclusive; lower bounds are inclusive.
- List order is timestamp descending, then ID descending.
- Cursors are opaque, unpadded, filter-bound strings of at most 2,048
  characters. The frontend may store a cursor only as transient pagination
  state and must forward it unchanged.
- List limits are `1..500`, default 100. Live telemetry uses `limit=1`.
- All list operations retain mandatory device isolation. Measurement
  `session_id` filtering is non-disclosing for another device's session.

## Stable error envelope

Every documented and framework-normalized error has this shape:

```json
{
  "error": {
    "code": "machine_readable_code",
    "message": "Safe public message.",
    "details": null
  }
}
```

Known domain codes relevant to the UI include:

| Status | Code | Safe meaning in the frontend |
|---|---|---|
| 404 | `device_not_found` | The selected device no longer exists or the ID is wrong. |
| 404 | `active_session_not_found` | Normal “no active session” state for active lookup. |
| 409 | `duplicate_device_uid` | Registration UID is already in use. |
| 409 | `device_inactive` | Activate the device before starting/recording. |
| 409 | `active_session_already_exists` | Refresh and show the existing active session. |
| 409 | `duplicate_source_message` | Ingestion-only conflict; not a normal dashboard write. |
| 409 | `invalid_session_transition` | Active session changed; refresh lifecycle state. |
| 409 | `session_device_mismatch` | Ingestion/session mismatch; do not disclose another device. |
| 409 | `invalid_timestamp` | Supplied lifecycle/measurement timestamp conflicts with session state. |
| 422 | `request_validation_error` | Highlight invalid local input without rendering backend internals. |
| 500 | `internal_server_error` / `internal_invariant_error` | Show a sanitized retryable server failure. |

Malformed or unknown envelopes never become UI copy. Network, timeout, abort,
and invalid-JSON/contract failures are normalized by the frontend boundary.

## Operation matrix

| Operation | Request contract and validation | Success response | Safe errors | Frontend use | Existing backend coverage |
|---|---|---|---|---|---|
| `GET /health` (`get_health_health_get`) | No body or parameters. | 200 `HealthResponse`: required `status: "ok"`, `service: string`, `version: string`. | No operation-specific error schema; framework errors are still normalized globally. | Independent backend availability card and retry state. | `test_health.py`, `test_api_routes.py`, `test_api_openapi.py`, application-composition tests. |
| `POST /api/v1/devices` (`create_device`) | Required body `device_uid: string` max 255; optional `name: string|null` max 255; `is_active: boolean` default true. Extra fields forbidden. | 201 `DeviceResponse`: required `id`, `device_uid`, `name`, `is_active`, `created_at`. | 409 duplicate UID; 422 validation; sanitized 500. | Register a new device and persist returned numeric ID. | Route/schema/OpenAPI/service and PostgreSQL lifecycle tests. |
| `GET /api/v1/devices/{device_id}` (`get_device`) | Positive bounded path ID. | 200 `DeviceResponse`. | 404 missing device; 422 path validation; sanitized 500. | Validate an entered/restored ID and show current state. | Route/schema/OpenAPI/query-service tests and integration lifecycle. |
| `PATCH /api/v1/devices/{device_id}/status` (`set_device_status`) | Positive path ID; required body `{is_active: boolean}` only. | 200 `DeviceResponse`. | 404 missing device; 422 validation; sanitized 500. | Show current device state and allow explicit activation/deactivation where useful. | Route/OpenAPI/service and integration tests. |
| `POST /api/v1/devices/{device_id}/sessions` (`start_measurement_session`) | Positive path ID; required bounded `latitude: -90..90`, `longitude: -180..180`; optional aware `started_at`. | 201 `SessionResponse`: required `id`, `device_id`, status enum, `started_at`, nullable `ended_at`, coordinates, `sample_count`, `created_at`. | 404 device; 409 inactive/existing active/timestamp conflict; 422 validation; sanitized 500. | One-shot geolocation followed by session start. Do not fabricate coordinates. | Route/schema/OpenAPI/service, chronology, and PostgreSQL lifecycle tests. |
| `GET /api/v1/devices/{device_id}/sessions` (`list_device_sessions`) | Positive path ID; optional exact status `active|completed|cancelled`; aware `started_from`, `started_to`; `limit` 1..500 default 100; opaque cursor max 2048. Unknown/repeated query keys rejected. | 200 `{items: SessionResponse[], next_cursor: string|null}` in stable newest-first order. | 404 device; 422 query/cursor/filter validation; sanitized 500. | Filtered history, cursor “load more”, and selected session/map markers. | Query/cursor, route/OpenAPI, repository/service, and guarded PostgreSQL collection tests. |
| `GET /api/v1/devices/{device_id}/sessions/active` (`get_active_measurement_session`) | Positive path ID. | 200 `SessionResponse`. | 404 missing device or no active session; 422 validation; sanitized 500. | Initialize and refresh lifecycle state. Treat only `active_session_not_found` as a normal empty state. | Route/OpenAPI/query-service and integration tests. |
| `POST /api/v1/devices/{device_id}/sessions/active/complete` (`complete_active_measurement_session`) | Positive path ID; optional body `SessionTransitionRequest` with nullable aware `ended_at`; body may be omitted. | 200 terminal `SessionResponse`. | 404 missing device/session; 409 invalid transition/timestamp; 422 validation; sanitized 500. | Complete active session, then refresh active/history state. | Route/schema/OpenAPI/service chronology and integration tests. |
| `POST /api/v1/devices/{device_id}/sessions/active/cancel` (`cancel_active_measurement_session`) | Same optional transition body as complete. | 200 cancelled `SessionResponse`. | Same lifecycle classes as complete. | Confirm cancellation, cancel, then refresh active/history state. | Route/schema/OpenAPI/service and integration tests. |
| `POST /api/v1/devices/{device_id}/measurements` (`record_raw_measurement`) | Required aware `measured_at`; optional source ID max 255; temperature `-40..85`; humidity `0..100`; nonnegative PM values; particle counters `0..2147483647`; optional bounded coordinate pair supplied together; `is_valid` default true; nullable note. | 201 `MeasurementResponse` with required IDs, source ID, measured/received/created timestamps, environment, PM, particle, coordinate, validity, and note fields. | 404 device/session state; 409 inactive/duplicate/session/timestamp conflicts; 422 validation; sanitized 500. | Not a normal dashboard control; used only by the approved Compose smoke flow to create representative telemetry. | Route/schema/OpenAPI/service, non-finite/chronology, and PostgreSQL lifecycle tests. |
| `GET /api/v1/devices/{device_id}/measurements` (`list_device_measurements`) | Positive path ID; optional positive `session_id`; aware `measured_from`, `measured_to`; limit 1..500 default 100; opaque cursor max 2048. Unknown/repeated query keys rejected. | 200 `{items: MeasurementResponse[], next_cursor: string|null}` in stable newest-first order. | 404 device; 422 query/cursor/filter validation; sanitized 500. | Live `limit=1`, selected-session history, time filtering, exact table, and chart presentation copy. | Query/cursor, route/OpenAPI, repository/service, and guarded PostgreSQL collection tests. |

## CORS and deployment decision

`backend/app/main.py` installs no `CORSMiddleware`, and there are no CORS
settings or tests. Frontend v2 therefore uses same-origin proxying:

- Vite development serves the browser and proxies `/api` plus `/health` to the
  default host-side API at `127.0.0.1:8000`.
- The Nginx runtime serves built assets and proxies only `/api/` plus exact
  `/health` to the Compose `api:8000` service.
- SPA fallback applies only to frontend paths and must not convert backend 404
  responses into `index.html`.

`VITE_API_BASE_URL` remains the canonical browser-visible base. Its safe
default is the current origin. An absolute cross-origin value is not the
standard supported path unless the backend later gains an explicit-origin
CORS policy and matching tests.

## Frontend compatibility verdict

All approved MVP workflows are supported by the existing 11 operations. No
new backend endpoint, CORS middleware, response field, schema, telemetry
business-logic change, or migration is required. The only deliberate frontend
limitation is that there is no device collection listing: the user enters,
registers, and persists one active device ID as specified.
