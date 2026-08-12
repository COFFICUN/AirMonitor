# AirMonitor Firmware v2 API contract

This specification records the firmware-facing contract derived from the
FastAPI code and generated OpenAPI document. The baseline was detached commit
`374b4beb9c7a056493a15c8b193151ff5b0574a3`; the one backward-compatible
Firmware v2 addition is identified explicitly below.

## Product model

The frontend owns session lifecycle and captures location once when it starts a
session. One session is one geographic point and a series of measurements made
at that point. Firmware never starts sessions and never sends a route or
continuous geolocation.

## Device identity and boot verification

Firmware configuration contains both the positive PostgreSQL integer
`device_id` and the stable expected `device_uid`. It calls:

```http
GET /health
GET /api/v1/devices/{device_id}
```

The device response is accepted only when `id`, `device_uid`, and `is_active`
match the configured physical device. A missing, inactive, or mismatched device
blocks session polling and measurement delivery without stopping local sensor
display.

## Active-session detection

Firmware polls:

```http
GET /api/v1/devices/{device_id}/sessions/active
```

- `200` with `status: "active"` selects the returned numeric session `id`.
- `404` with `error.code: "active_session_not_found"` is the normal waiting
  state.
- Other failures leave API state unavailable and are retried with a bounded
  polling interval.

The most recently confirmed active ID is a local measurement context, not a
connectivity flag. Temporary Wi-Fi/API failures make the remote state stale but
do not erase that ID, so bounded offline capture continues for the confirmed
session. An explicit `active_session_not_found` response clears it. Firmware
never queues for the server before any active session has been confirmed.

The session response owns `latitude` and `longitude`. Firmware does not copy
them into individual measurements.

## Measurement ingestion

Firmware sends:

```http
POST /api/v1/devices/{device_id}/measurements
Content-Type: application/json
```

`session_id` is an optional positive integer for backward compatibility. The
backend locks the device runtime state, rejects a supplied ID that differs from
the active session, and then associates the measurement. Firmware v2 always
supplies the session ID captured with the record. This closes the race where a
session could be completed and replaced between firmware polling and delivery.

Example full payload:

```json
{
  "session_id": 31,
  "measured_at": "2026-08-11T08:15:30Z",
  "source_message_id": "am2-00000017-11223344a1b2c3d4-0000002a",
  "temperature": 24.6,
  "humidity": 41.8,
  "pm1": 5,
  "pm25": 9,
  "pm10": 14,
  "pc0_3": 824,
  "pc0_5": 173,
  "pc1_0": 48,
  "pc2_5": 7,
  "pc5_0": 1,
  "pc10": 0,
  "latitude": null,
  "longitude": null,
  "is_valid": true,
  "validation_note": null
}
```

`measured_at` is the only required request field. It must be timezone-aware;
Firmware v2 sends UTC ISO-8601 with a trailing `Z` and does not enqueue records
until NTP time is valid. All sensor fields are nullable. Firmware sends a
partial reading with invalid sensor-group values set to `null`, sets
`is_valid: false`, and supplies a short `validation_note`. It does not send a
record when both sensor groups are invalid.

The backend validates:

- temperature: `-40..85` degrees Celsius;
- humidity: `0..100` percent;
- PM values: finite and non-negative;
- particle counters: `0..2147483647`;
- latitude: `-90..90`, longitude: `-180..180`, supplied as a pair;
- `source_message_id`: at most 255 characters;
- `measured_at`: timezone-aware and not earlier than session start.

## Idempotency and delivery decisions

`source_message_id` is unique for `(device_id, source_message_id)`. Firmware
creates it once when a physical sample is captured, stores it with the queued
record, and reuses it for every retry.

- `201`: delivered; remove the FIFO head.
- `409` + `duplicate_source_message`: already delivered; remove the FIFO head.
- `409` + `active_session_mismatch`: the record's original session changed;
  reject every queued record carrying that same stale ID, but retain any records
  already captured for the newly confirmed session.
- network error, timeout, `408`, `425`, `429`, or `5xx`: retry with capped
  exponential backoff and a maximum attempt count.
- `404` + `active_session_not_found`: session ended; return to waiting and
  discard records belonging to the old session.
- all other `4xx`: permanent request/configuration error; do not tight-retry
  the record.

The backend returns safe error envelopes:

```json
{
  "error": {
    "code": "request_validation_error",
    "message": "Request validation failed.",
    "details": null
  }
}
```

Relevant error codes are `device_not_found`, `active_session_not_found`,
`active_session_mismatch`, `device_inactive`, `duplicate_source_message`,
`invalid_timestamp`,
`request_validation_error`, `internal_invariant_error`, and
`internal_server_error`.

HTTP response bodies are bounded to 2048 bytes. Firmware supports known-length,
chunked and connection-delimited unknown-length bodies. A truncated/read-timeout
body cannot safely classify a structured 409 and is therefore retried with the
same source ID; an oversized error body is rejected predictably without an
unbounded allocation.

## API compatibility conclusion

Firmware v2 adds one backward-compatible optional ingestion field,
`session_id`, plus the safe `active_session_mismatch` conflict. Existing clients
that omit the field retain the prior active-session association behaviour.
