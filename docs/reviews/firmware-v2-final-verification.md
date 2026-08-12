# Firmware v2 final verification

Verification date: 2026-08-12

Checkout: detached `374b4beb9c7a056493a15c8b193151ff5b0574a3`

Target branch tip at start: `feature/firmware-v2`

No branch, worktree, index, commit, push, merge, reset, restore, stash or other
Git write operation was performed. All product changes remain unstaged.

## Legacy firmware findings and retained behaviour

The working root `test1_final.ino` was used as read-only hardware reference.
It established:

- M5Stack Basic v2.7 / ESP32 and the three-screen M5 LCD/button UI;
- PMSA003 through `Plantower_PMS7003` on `Serial2`, 9600 baud, RX GPIO 16,
  TX GPIO 17;
- PM1.0, PM2.5, PM10, all six particle-counter values, a five-frame PM moving
  average and a 15-second PMS timeout;
- SHT30-compatible measurement through `Adafruit_SHT31` on I2C address `0x44`;
- local two-second sensor refresh and buttons A/B/C.

Those sensor pins, libraries, readings, timeout, main visual hierarchy, three
screens and button roles were retained. The legacy moving average was removed
after hardware data showed that its variable-duration frame window stretched
short changes. The root sketch, legacy Flask, SQLite database, old certificates
and legacy frontend were not modified.

## Implemented structure

```text
firmware/
  platformio.ini
  README.md
  include/
    firmware_config.example.h
    airmonitor/
      api_client.h
      display.h
      firmware_logic.h
      sensors.h
  src/
    api_client.cpp
    display.cpp
    firmware_logic.cpp
    main.cpp
    sensors.cpp
  test/native/test_firmware_logic.cpp
  test/static/test_firmware_source.py
```

The boundaries are deliberately few: hardware sensors, display/status, HTTP
client, pure queue/retry/time/state logic, and the cooperative main loop.

## Runtime and product behaviour

Boot performs sensor/display initialization, non-blocking Wi-Fi reconnect,
UTC/NTP synchronization, API health, device identity/activity verification,
and active-session polling. Sensors remain visible locally while waiting.
Measurements begin only after the frontend-created active session is confirmed.
That ID remains the local capture context through a temporary network/API
outage; only an explicit backend no-active/rejection response or a replacement
active session changes it.

PMSA003 now uses atmospheric protocol Data 4-6, ignores the first 30 seconds
after startup, validates PM/cumulative-counter ordering and uses the latest
valid frame without clipping high coherent readings. SHT30 temperature and
humidity are obtained as one CRC-checked `readBoth()` pair. Data13 remains
ignored because the applicable PMSA003 manual reserves it even though the
PMS7003-compatible library labels that byte as an error code.

One session remains one geographic point. Firmware does not request location,
start sessions, build routes, track movement, or repeat session coordinates in
measurements.

The display retains MAIN/PARTICLES/SYSTEM views and adds Wi-Fi/API/time/device/
session state, HTTP status, session ID, delivered count, queue depth, dropped
and rejected counts and sensor error visibility. Instant PM2.5 retains its
numeric `ug/m3` presentation but no longer receives AQI/health-like labels; the
adjacent text is neutral `READING`/`LIVE`. The loop is `millis()`-scheduled with a
5 ms cooperative yield; FreeRTOS tasks were not introduced.

## FastAPI contract and backward-compatible change

Firmware uses:

- `GET /health`;
- `GET /api/v1/devices/{device_id}`;
- `GET /api/v1/devices/{device_id}/sessions/active`;
- `POST /api/v1/devices/{device_id}/measurements`.

Device acceptance requires numeric ID, matching stable UID and `is_active=true`.
No active session is the safe `404 active_session_not_found` waiting state.

Review found an unavoidable race in the original ingestion contract: a stale
queued record could be posted after the frontend replaced its session and be
atomically associated with the new geographic point. The minimal compatible
backend change adds optional positive `session_id` to
`MeasurementCreateRequest`. Existing producers may omit it. Firmware v2 always
sends it; the service compares it with the active runtime session under the
existing row lock and returns `409 active_session_mismatch` before insertion if
they differ. No persistence schema or migration changed.

The exact full payload is:

```json
{
  "session_id": 31,
  "measured_at": "2026-08-11T08:15:30Z",
  "source_message_id": "am2-00000017-11223344a1b2c3d4-0000002a",
  "temperature": 24.6,
  "humidity": 41.8,
  "pm1": 5.0,
  "pm25": 9.0,
  "pm10": 14.0,
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

`measured_at` is UTC ISO-8601 and is not created until NTP is valid. A partial
sensor reading after PMS warm-up has the failed group set to null,
`is_valid=false`, and a short note. PMS warm-up or both groups invalid means no
record. The first capture waits one full measurement interval after session
detection, avoiding second-precision time rounding immediately before the
backend session start.

## Idempotency, retries and queue

Each capture stores one source message ID with a 64-bit random boot nonce and
boot-local sequence; retries reuse it. HTTP 201 and 409
`duplicate_source_message` are delivered. Network/timeout, 408, 425, 429 and
5xx retry with 2/4/8/16/30/30-second backoff and at most six attempts. Session
404 rejects the queue after the backend explicitly reports no active session.
`active_session_mismatch` rejects only records carrying the stale session ID;
records for a newly confirmed session remain queued. Other 4xx errors are
permanent. Device-not-found/inactive returns to device verification.

The RAM outbox is bounded FIFO, default capacity 24. Last-confirmed session X
continues to capture while remote state is temporarily unavailable. Overflow
drops the oldest record, logs its identity and increments the visible total-drop
count. Permanent/session rejection logs the reason and increments the rejected
subset. Every record stores its captured session ID and source ID; these are
never rewritten to a replacement session. The queue is intentionally volatile
and is lost on reset/power loss.

HTTP response parsing is now bounded for known Content-Length, chunked and
unknown connection-delimited bodies. A 2048-byte fixed buffer replaces the
previous `getSize() >= 0`/`getString()` gate, and the HTTP timeout plus absolute
read deadline bound unknown-length waits.

## Correction-pass defect verification

The review findings were checked against the current source before edits:

- offline capture was genuinely broken because Wi-Fi invalidation zeroed the
  active session and `capture_measurement()` required remote `MEASURING` state;
- a replacement-session poll also discarded old records locally before the
  backend could return `active_session_mismatch`;
- `resolve_run_state()` selected `API ERROR` before `SYNC TIME`, although HTTP
  service was still gated by time and had not checked the API;
- `ApiClient::request()` read response JSON only for non-negative
  `Content-Length`, so `getSize() == -1` left chunked/unknown bodies empty;
- instantaneous PM2.5 was mapped to official-looking health/AQI labels without
  an AQI/NowCast algorithm;
- the reported humidity `print("%%")` defect was not present in this checkout:
  the actual source already used `print("%")`. A static regression now protects
  that exact one-character unit.

The correction separates `SessionState`'s last-confirmed capture context from
remote freshness, moves TIME ahead of untested API state, allows API checks
before NTP, gates capture/submission on valid time, and keeps every queued
session/source identity immutable. Queue overflow and every permanent rejection
are observable in Serial and counters.

## Build and automated verification

- PlatformIO 6.1.18, environment `m5stack-core-esp32`: **SUCCESS**.
- Safe-example and restored-real-config builds both passed; the ignored real
  header was restored byte-for-byte by SHA-256 comparison.
- Final restored-config size: RAM 53,952/327,680 bytes (16.5%); flash
  1,050,413/1,310,720 bytes (80.1%).
- Host C++17 queue/retry/time/message-ID/state/PMS tests: **passed** with
  warnings treated as errors.
- Static humidity/AQI source regressions: **2 passed**.
- Focused backend schema/service/error/route/OpenAPI tests: **273 passed**.
- Complete backend offline suite: **853 passed, 2 skipped** in 10.30 seconds.
- `pip check`: **No broken requirements found**.
- Alembic: one head, `a75caa2b44f5`.
- OpenAPI: 3.1.0, 11 operations, 10 under `/api/v1`, 11 unique operation IDs.

OpenAPI operation inventory and response status inventory are unchanged. The
only request-schema addition is nullable/optional positive PostgreSQL-bounded
`MeasurementCreateRequest.session_id`; 409 already existed on the ingestion
operation. The new stable error code is `active_session_mismatch`.

## PostgreSQL and Compose integration

A disposable PostgreSQL 18.4 database named with the approved
`airmonitor_api_test_` prefix was migrated from base through
`a75caa2b44f5`. The full guarded API integration module passed: **10 passed**.
The firmware case verified waiting 404, session creation, exact payload,
duplicate 409, ORM persistence, session coordinates/sample count, read API,
completion, and stale-session rejection.

The correction pass built a clean three-service stack under project
`airmonitor-frontend-test-firmware-correction`, with a dedicated disposable DB
and loopback ports. The flow created a device and point session, posted three
firmware-shaped X records, verified duplicate handling, completed X, opened Y,
proved stale X returned `409 active_session_mismatch`, verified Y remained empty,
then posted one valid Y record. Both histories were read through the frontend
Nginx proxy. PostgreSQL showed:

- old session: completed, three records, coordinate 51.1694/71.4491;
- replacement session: one record, coordinate 43.2389/76.8897;
- raw measurements: exactly four; stale X created no Y record.

The development stack was also restored healthy after controlled API outages.
All correction-test containers, networks, volumes and test-only local Compose
images were removed; the user's development `api/db/frontend` stack remains
healthy for the flashed device.

## Hardware verification status

M5Stack was detected as CH9102 `COM3`. The final correction image was uploaded
successfully with esptool and its flash hash verified. Controlled serial tests
confirmed:

- booted Firmware v2 with device ID 3 and valid API configuration;
- SHT30 initialized and returned stable CRC-checked pairs;
- PMS remained `warmup` with no valid PM for the first 30 seconds;
- PMS then changed to `ok` and reported coherent atmospheric readings around
  PM1 8-13, PM2.5 10-17, PM10 12-17 ug/m3 and PC>0.3 1389-2031 per 0.1 L;
- Wi-Fi/NTP, matching device identity, active-session detection and HTTP 201
  measurement creation worked;
- during a controlled 20-second API outage, six new session-8 records were
  captured as `remote=offline`, FIFO depth grew to six, and all six original
  source IDs flushed successfully after health/device/session re-verification;
- in the physical X=10 -> Y=11 replacement test, five X records queued offline;
  reconnect confirmed Y, the first old POST received
  `409 active_session_mismatch`, Serial logged one rejection of exactly five X
  records, PostgreSQL X stayed 13 -> 13, and four new Y records then succeeded;
- completing Y caused the one in-flight record to receive
  `active_session_not_found`, log its rejection and stop subsequent capture.

The physical LCD pixels and buttons were not visible/operable to Codex, so the
single-percent glyph, neutral `READING`/`LIVE` copy, queue/rejected counters and
button interaction still require the documented visual/manual check. Their
source and build/static regressions passed.

## Security and operational review

- Real Wi-Fi credentials, private URLs and device identity are absent from
  tracked config; the actual header is ignored.
- API base URL is configurable and the example uses a generic LAN address.
- HTTPS requires a configured CA; firmware never calls `setInsecure()`.
- HTTP timeouts, response size, retry count, backoff and queue size are bounded.
- No MQTT, Redis, OTA, provisioning service, GPS route, accounts or ownership
  subsystem was added.
- Firmware has no dependency on Flask, SQLite or legacy certificates.

## Remaining risks

1. Long-duration accuracy and enclosure airflow still require the documented
   soak test. SHT30 reported about 33 C during USB testing; compare it with a
   room reference and thermally separate it from M5Stack heat before considering
   a calibrated offset.
2. Flash use is 80%; future library/features need a size budget review.
3. The outbox is RAM-only and loses pending samples on power loss.
4. Compile-time local configuration is safe for development but is not a
   commercial end-user provisioning/rotation workflow.
5. NTP must be reachable; isolated hotspots should provide a LAN NTP server.
6. The retained M5Stack library is deprecated upstream; a future M5Unified
   migration should be isolated and hardware-regression-tested rather than
   mixed into this network-contract pass.
7. Official AQI/NowCast calculation and product wording remain a separate
   product feature; this firmware reports raw instantaneous mass concentration.
