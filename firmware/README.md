# AirMonitor Firmware v2

Firmware v2 keeps the proven M5Stack Basic, PMSA003, SHT30-compatible sensor
and display logic from `test1_final.ino`, but replaces the legacy Flask network
path with the current FastAPI v2 contract.

The product model is deliberately simple:

```text
browser starts one session at one geographic point
  -> firmware detects that active session
  -> PMSA003 + SHT30 readings are queued and sent
  -> FastAPI associates each reading with the active session
  -> PostgreSQL stores it
  -> frontend reads live and historical telemetry
```

The firmware does not create sessions and does not collect, infer, or transmit
a route. Latitude and longitude belong to the session created by the browser;
measurement payloads contain `null` coordinates.

## Hardware and wiring

| Component | Connection | Firmware setting |
|---|---|---|
| M5Stack Basic v2.7 / ESP32 | Controller | PlatformIO board `m5stack-core-esp32` |
| PMSA003 VCC | 5 V | Sensor supply |
| PMSA003 GND | GND | Common ground |
| PMSA003 TX | ESP32 GPIO 16 (RX2) | `Serial2`, 9600 baud |
| PMSA003 RX | ESP32 GPIO 17 (TX2) | `Serial2`, 9600 baud |
| SHT30/SHT31 SDA | M5Stack I2C SDA | `Wire`, address `0x44` |
| SHT30/SHT31 SCL | M5Stack I2C SCL | `Wire`, address `0x44` |

The pins, UART speed, SHT address and 15-second PMS stale timeout are retained
from the working legacy sketch. Confirm the sensor module's printed pinout
before powering it; do not infer wire colours.

## Toolchain and libraries

The reproducible PlatformIO environment is in `platformio.ini`:

- Espressif32 platform 6.10.0 / Arduino-ESP32 2.0.17;
- M5Stack 0.4.6;
- Adafruit SHT31 Library 2.2.2;
- ArduinoJson 7.4.3;
- `jmstriegel/Plantower_PMS7003` pinned to commit
  `4b4c83b300b18f0f9c2c1494b1f910c4cb8cbe67`.

The established M5Stack library is intentionally retained in this pass so the
working button and display behaviour is not rewritten. Moving to M5Unified can
be evaluated separately.

## Safe configuration

Copy the tracked example and edit only the ignored real file:

```powershell
Copy-Item .\firmware\include\firmware_config.example.h `
  .\firmware\include\firmware_config.h
```

Configure:

- `AIRMONITOR_WIFI_SSID` and `AIRMONITOR_WIFI_PASSWORD`;
- the browser-created numeric `AIRMONITOR_DEVICE_ID`;
- the matching stable `AIRMONITOR_DEVICE_UID` returned by the API;
- `AIRMONITOR_API_BASE_URL`;
- an optional trusted CA certificate for HTTPS;
- measurement/session intervals and NTP servers when needed.

`firmware_config.h`, PlatformIO build state and local virtual environments are
ignored by Git. Do not put credentials into `platformio.ini`, source files, or
the tracked example.

An ESP32 cannot reach a host service through `127.0.0.1`. For a LAN or hotspot
test, bind/publish FastAPI on the computer and use that computer's Wi-Fi or
hotspot address, for example `http://192.168.1.100:8000`. Permit only the
required private-network port in the host firewall. For production, use an
`https://` URL and place the issuing root/intermediate CA in
`AIRMONITOR_API_CA_CERT`; the client never disables certificate verification.

## Build, upload, and monitor

Python 3.13 and PlatformIO 6.1.18 are the validated host tools:

```powershell
python -m venv .\firmware\.venv
& .\firmware\.venv\Scripts\python.exe -m pip install platformio==6.1.18
$env:PLATFORMIO_CORE_DIR = (Resolve-Path .\firmware).Path + "\.platformio"
& .\firmware\.venv\Scripts\pio.exe run --project-dir .\firmware
```

With the M5Stack connected, discover the port, upload, and open the monitor:

```powershell
& .\firmware\.venv\Scripts\pio.exe device list
& .\firmware\.venv\Scripts\pio.exe run --project-dir .\firmware `
  --target upload --upload-port COM5
& .\firmware\.venv\Scripts\pio.exe device monitor `
  --project-dir .\firmware --port COM5 --baud 115200
```

Replace `COM5` with the discovered port. If upload cannot enter the bootloader,
hold the M5Stack reset/power control only as required by the installed USB
driver and board revision.

## Runtime state model

Boot initializes the display and sensors and starts Wi-Fi connection attempts.
After Wi-Fi connects, NTP synchronization and the `/health` -> device -> active
session checks progress independently. API availability is therefore not
blocked by NTP, while capture and measurement submission still require a valid
UTC clock. Until that clock is valid, the state resolver shows `SYNC TIME`; it
does not show `API ERROR` merely because the API has not yet been checked. All
scheduling uses `millis()`; the main loop contains only a 5 ms cooperative yield
and at most one bounded HTTP request per iteration.

The display states are:

- `WIFI`: reconnecting every 10 seconds;
- `TIME`: waiting for a valid UTC clock;
- `API`: health unavailable, retrying with a bounded interval;
- `DEVICE`: unknown, inactive, UID mismatch, or otherwise rejected;
- `WAIT SESSION`: device ready but the frontend has not started a session;
- `MEASURING`: active session confirmed and records may be captured;
- `PAUSED`: local capture pause selected with button C.

Sensors continue updating the local display outside an active session. Button
A changes screens, button B requests an immediate capture when a last-confirmed
session context and valid clock exist (including a temporary network outage),
and button C toggles the local pause. The three legacy screens and prominent
PM/temperature/humidity readings remain; connection state, last-confirmed
session ID, HTTP status, delivered count, queue depth, total dropped count and
rejected count were added.

## Sensor acquisition and validation

PMSA003 runs in its default active serial mode at 9600 baud. Firmware drains
the UART continuously and uses the newest checksum-valid frame rather than
sampling the UART only at the server measurement interval. For ambient air it
maps protocol Data 4-6 through the library's `getPM_*_atmos()` accessors:

- PM1.0, PM2.5 and PM10 are atmospheric mass concentrations in `ug/m3`;
- particle counters are cumulative counts above each diameter threshold in
  `0.1 L` of air, not mass concentrations and not an air-quality index;
- the first 30 seconds after sensor startup are warm-up time and are neither
  displayed as valid PM nor queued for delivery;
- non-monotonic PM values, non-monotonic cumulative particle counters, or 15
  seconds without a frame makes PMS data unavailable;
- high but internally consistent readings are preserved; firmware does not
  cap or fabricate pollution values.

The legacy five-frame arithmetic mean was removed. PMSA003 varies its active
output interval with concentration, so a fixed number of frames represented a
variable time window and visually stretched short changes. The device now
uses the latest validated atmospheric frame. Server records remain governed
by `AIRMONITOR_MEASUREMENT_INTERVAL_MS`.

SHT30 is read every two seconds in single-shot mode. `readBoth()` obtains the
temperature and relative-humidity pair from one sensor command with the
library's CRC validation, instead of issuing two separate physical
measurements. Non-finite or out-of-range pairs are rejected.

SHT30 reports the local conditions at the sensor. It must be exposed to room
air and thermally separated from the ESP32, display regulator and other heat
sources; firmware does not apply an arbitrary temperature offset. A heated
sensor also reports lower relative humidity than the room air.

PMSA003 protocol Data13 is reserved in the applicable data manual. Although
the compatible PMS7003 library names its low byte `error_code`, firmware does
not reject PMSA003 data based on that undocumented interpretation.

The main display labels PM values as `ug/m3`. The particle screen labels values
as `PARTICLE COUNT / 0.1L` and uses `>0.3um` through `>10um` thresholds. The
main screen shows the instantaneous PM2.5 number with neutral `READING`/`LIVE`
text. It deliberately does not classify one raw sample as `GOOD`, `UNHEALTHY`
or another official-looking AQI/health category. A defensible AQI/NowCast
calculation, averaging window, jurisdiction and product wording require a
separate product feature. The system screen distinguishes `WARMUP`, `FRAME ERR`
and `NO DATA`.
The serial monitor prints one compact sensor diagnostic every five seconds.

## FastAPI interaction

Firmware uses exactly these operations:

| Purpose | Operation |
|---|---|
| API availability | `GET /health` |
| identity and activity | `GET /api/v1/devices/{device_id}` |
| active-session detection | `GET /api/v1/devices/{device_id}/sessions/active` |
| ingestion | `POST /api/v1/devices/{device_id}/measurements` |

The expected identity is both the configured numeric ID and matching
`device_uid`, and `is_active` must be true. Active-session `404` with code
`active_session_not_found` is the normal waiting state.

Response JSON is capped at 2048 bytes. Known `Content-Length`, chunked transfer,
and connection-delimited unknown-length responses are read into one fixed-size
buffer. HTTPClient's existing timeout plus an absolute bounded read deadline
prevent an endless response wait. An oversized body is rejected without an
unbounded `String` allocation; a truncated/timeout body is treated as a
temporary read failure when its error code is needed for a delivery decision.

Each full firmware payload has this shape (values are illustrative):

```json
{
  "session_id": 31,
  "measured_at": "2026-08-11T12:34:56Z",
  "source_message_id": "am2-00000001-11223344a1b2c3d4-0000002a",
  "temperature": 23.5,
  "humidity": 41.2,
  "pm1": 4.0,
  "pm25": 7.0,
  "pm10": 11.0,
  "pc0_3": 120,
  "pc0_5": 96,
  "pc1_0": 48,
  "pc2_5": 9,
  "pc5_0": 2,
  "pc10": 1,
  "latitude": null,
  "longitude": null,
  "is_valid": true,
  "validation_note": null
}
```

`measured_at` is UTC ISO-8601 and is never fabricated before NTP succeeds.
`session_id` identifies the session observed at capture. The backend verifies
it against the active session inside the same transaction, preventing a stale
queued record from entering a replacement session. If one sensor group is
temporarily unavailable after PMS warm-up, its fields are `null`, `is_valid`
is false, and the note names the failed group. No record is created during PMS
warm-up or when both sensor groups are invalid.

The complete code-derived contract, nullable fields, limits, error codes and
idempotency rules are in
[`../docs/specs/firmware-v2-api.md`](../docs/specs/firmware-v2-api.md).

## Retry and pending queue

After `GET .../sessions/active` confirms session X, firmware stores X as the
last-confirmed measurement context separately from current Wi-Fi/API state. A
temporary Wi-Fi, API or HTTP outage invalidates only remote freshness: sensors
keep producing timestamped records for X and the bounded queue grows. Before the
first confirmed active session, an outage never creates server-bound records.
An explicit active-session 404 clears the context and stops capture.

Each physical capture receives one `source_message_id` built from device ID, a
64-bit per-boot random nonce and a monotonic boot-local sequence; its session ID,
timestamp and source ID never change on retry. After reconnection firmware
re-verifies health, device and active session, then flushes FIFO. HTTP 201 and
backend 409 `duplicate_source_message` both finish the logical delivery.
Network/read errors, timeouts, 408, 425, 429 and 5xx receive at most six total
delivery attempts with 2, 4, 8, 16, 30 second capped backoff. Other 4xx responses
are permanent and are not retried blindly.

If X ended while offline and Y is now active, queued X records are not rewritten
to Y. The first X POST still carries X and the backend atomically returns 409
`active_session_mismatch`; firmware then rejects all remaining X records only,
logs the session/count/reason to Serial, increments both total dropped and
rejected counters, and leaves any Y records in FIFO. A 404
`active_session_not_found` rejects the queue because the backend explicitly
confirmed that no measurement session exists. Neither response creates an
infinite retry loop.

The RAM outbox is bounded (24 records by default), FIFO, and uses an explicit
drop-oldest overflow policy so recent short-outage samples can continue to be
captured. Capacity never grows. Each overflow logs the dropped session/source
ID and capacity to Serial and increments the visible total dropped count. The
system screen uses `d` for total drops (overflow plus rejection) and `r` for the
rejected subset; queue depth is also visible.

The queue is intentionally volatile: reset or power loss can lose pending
records. A crash-safe flash outbox remains a possible follow-up if field tests
show that short outages and power interruptions make it necessary.

## Host logic tests

Pure queue, retry, timestamp, message-ID, state and PMS validation logic is
independent of Arduino. With a host C++17 compiler:

```powershell
g++ -std=c++17 -Wall -Wextra -Werror -I .\firmware\include `
  .\firmware\src\firmware_logic.cpp `
  .\firmware\test\native\test_firmware_logic.cpp `
  -o .\firmware\test\native\firmware_logic_tests.exe
& .\firmware\test\native\firmware_logic_tests.exe
python -B -m unittest firmware.test.static.test_firmware_source -v
```

The generated executable is not a repository artifact and should be removed
after a local run. CI runs the same test before compiling the ESP32 image.

## Manual hardware smoke checklist

1. Inspect wiring, common ground and PMSA003 5 V supply before USB power.
2. Confirm both configured device ID and UID match `GET /api/v1/devices/{id}`.
3. Boot and confirm SHT, PMS, Wi-Fi, NTP, health and device serial messages;
   wait for the 30-second PMS `WARMUP` state to become `OK`.
4. Confirm all three screens, buttons and live values update without long UI
   freezes.
5. With no active session, confirm `WAIT SESSION` and no measurement POSTs.
6. In the frontend, start a session and allow one browser geolocation request.
7. Confirm the firmware shows the new session ID and sends a real reading.
8. Confirm the value appears in frontend live telemetry and PostgreSQL-backed
   history; confirm the session map has one point only.
9. While session X is confirmed, disconnect Wi-Fi for longer than one
   measurement interval. Confirm `NO WIFI`, continued sensor updates and a
   growing `Q` count. Reconnect and confirm X records flush FIFO with their
   original source IDs and no duplicate history rows.
10. Repeat by stopping only the API while Wi-Fi remains connected. Confirm
    `API ERROR`, a growing queue and recovery after API restart.
11. With X records queued, complete X and start Y at a different point before
    reconnecting the device. Confirm Serial logs
    `active_session_mismatch`, rejected `r` grows, X records never appear in Y,
    and later Y measurements send normally.
12. Boot with API unavailable and no previously confirmed session; confirm live
    sensor display but a zero server queue.
13. For an overflow check, temporarily configure a small queue/short interval;
    confirm depth never exceeds capacity and Serial logs `overflow
    dropped_oldest` for every overflow.
14. Test SHT and PMS disconnection separately and confirm invalid data is not
    presented or posted as a fully valid sample.
15. For production HTTPS, confirm an untrusted certificate fails and the
    configured trusted CA succeeds.
16. For a stability check, leave the device stationary for two minutes with
    unobstructed, separated PMS inlet/outlet and no breath, mist, spray, smoke
    or disturbed dust near the inlet. Compare PM `ug/m3` separately from the
    particle counts per `0.1 L`.

## Current limitations

- There is no persistent offline outbox; queued data is lost on reset.
- Wi-Fi/device provisioning and credential rotation are compile-time config in
  an ignored file, not yet an end-user provisioning workflow.
- NTP must be reachable (a LAN NTP host is supported) before server delivery.
- OTA, MQTT, accounts and device ownership are intentionally outside this
  firmware pass.
- A regulatory/health AQI or NowCast interpretation is not implemented; the LCD
  intentionally displays raw instantaneous PM mass concentration only.
- Physical sensor accuracy, airflow placement and long-duration stability need
  verification on the target M5Stack/PMSA003/SHT30 assembly.

## Primary hardware/library references

- [PlatformIO M5Stack Core ESP32 board definition](https://docs.platformio.org/en/latest/boards/espressif32/m5stack-core-esp32.html)
- [M5Stack legacy Arduino library](https://github.com/m5stack/M5Stack)
- [Adafruit SHT31 Arduino library](https://github.com/adafruit/Adafruit_SHT31)
- [Plantower PMS7003/PMSA003-compatible parser](https://github.com/jmstriegel/Plantower_PMS7003)
- [Plantower PMSA003 data manual](https://www.gotronic.fr/pj2-pmsa003-series-data-manua-english-v2-5-2083.pdf)
- [Sensirion SHT3x-DIS datasheet](https://sensirion.com/media/documents/213E6A3B/63A5A569/Datasheet_SHT3x_DIS.pdf)
- [Sensirion humidity/temperature sensor design guide](https://sensirion.com/resource/user_guide/sht/design_in)
