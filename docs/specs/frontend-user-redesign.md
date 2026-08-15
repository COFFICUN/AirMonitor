# AirMonitor User Frontend Redesign Specification

## Product intent

AirMonitor helps participants explore particulate measurements at selected
places in Almaty with a portable sensor. The experience combines a calm public
explanation with a practical measurement workspace. It presents observed data
honestly: no fabricated city totals, research enrolment, health diagnosis,
official AQI, or unsupported account behavior.

Interface language is Russian; code identifiers stay English. Date/time
presentation uses the browser with the `Asia/Almaty` product context called out
in copy and documentation.

## Information architecture

Public routes:

- `/` — landing page with “Измеряем воздух Алматы — точка за точкой”, the
  stationary-session process, metrics, privacy, participation, FAQ, and Айри;
- `/about` — goals, system composition, current engineering/research status,
  and limitations;
- `/participate` — real device/place/session/review workflow;
- `/methodology` — measured fields, placement conditions, averaging caveat,
  uncertainty, and non-official status;
- `/login` — future-account explanation with no auth side effect.

Application routes:

- `/app` — overview, health/device/session state, primary action, latest real
  metrics, freshness, trend, coordinates, and recent sessions;
- `/app/measurement` — start, active timer, finish, confirmed cancel,
  geolocation explanation, live data, and errors;
- `/app/sessions` — real filtered cursor history and stable selection;
- `/app/map` — one real geographic marker per measurement session;
- `/app/data` — bounded loaded sample, filters, statistics, chart, and table;
- `/app/device` — select/register/activate/clear one device;
- `/app/settings` — local-only validated preferences and reset.

Unknown paths render a helpful 404 with routes back to the public home and app.

## Layouts and navigation

`PublicLayout` provides a skip link, compact brand/header, public navigation,
main landmark, and truthful footer. `AppLayout` mounts shared participant state,
desktop sidebar with collapse, compact header with health/device state, main
landmark, and mobile bottom navigation. The app navigation labels are exactly:
Обзор, Новое измерение, Мои сессии, Карта, Данные, Моё устройство, Настройки.

Direct URLs and browser back/forward must work. Nginx serves frontend routes
through SPA fallback without swallowing `/api/*` or `/health` responses.

## Design system

CSS custom properties define:

- mineral off-white surfaces, petrol-navy structure, chartreuse signal
  actions, teal data accents, and explicit green/yellow/orange/red states;
- spacing, radii, shadows, typography, control heights, content/sidebar widths,
  motion durations, and z-index layers;
- focus, hover, active, disabled, loading, selected, error, and success states.

The result is a field-laboratory product rather than a generic SaaS template.
Its visual signature is a constellation of separate observation points, with
restrained cut-corner cards, disciplined shadows, thin borders, a locally
bundled Cyrillic-capable UI font with system fallbacks, and original icons.

## Айри mascot

Айри is an original generated field robot stored as a locally served WebP. The
portable air-sampling design uses an e-ink face, chest turbine, utility pack,
sensor cage, and protected leaf with a unique silhouette. Explicit width and
height prevent layout shift, and responsive `object-fit` crops keep the image
stable. The mascot is decorative unless nearby text supplies an accessible
label. No remote artwork request is made at runtime.

## State and data architecture

`PreferencesProvider` applies local display choices. `AppDataProvider`, mounted
only under `/app`, composes the existing selected-device, active-session, live
telemetry, session-history, and measurement-history hooks. Route pages consume
typed state; API transport remains outside components.

Preferences use one strict versioned JSON record. Allowed values are
system/light/dark theme, display density, motion preference, time format, safe
polling interval (5/10/30 s), and whether OSM tiles may load. Version 1 records
migrate to the system theme; invalid, unknown, or corrupt records reset to safe
defaults. No email, secret, token, coordinate, cursor, measurement history, or
backend error is stored.

## Air data presentation

Metric cards show only actual PM1.0, PM2.5, PM10, temperature, humidity, and
timestamps. Empty values stay empty. Concentration labels are descriptive
presentation aids, not AQI, diagnosis, exposure estimates, or regulatory
conclusions. The methodology page states that WHO guidelines use averaging
periods and cannot classify a single instant sample by themselves.

Statistics are pure functions over the currently loaded finite values and show
count, minimum, maximum, arithmetic mean, and median. Every statistics surface
states: “Статистика рассчитана по загруженной выборке”. API order remains
newest-first; only chart presentation copies reverse chronologically.

## Map behavior

The map loads only on the pages/components that need it and only when local
tile loading is enabled. It uses Leaflet and OpenStreetMap with visible
attribution. Each finite session coordinate returned by the API becomes one
marker. Measurements inside a session do not become separate places and no
polyline is drawn between sessions or samples. Selection synchronizes the map
and session details. Initialization, tile, or update failure cannot crash the
rest of the app. No reverse geocoding, clusters, fabricated coordinates, or
browser-location transmission to OSM is added.

## Accessibility and responsive acceptance

- semantic header/nav/main/footer landmarks, one logical page H1, skip links,
  labelled controls, visible focus, real buttons, live status messages, and
  non-colour labels;
- native or fully conforming modal behavior with safe focus, Tab containment,
  Escape, cancel action, and restoration;
- chart/table and map/list alternatives; tooltips never contain essential-only
  information;
- all decorative movement removed for reduced motion;
- no body horizontal overflow at 360×800, 390×844, 768×1024, 1280×800,
  1440×900, or wider; tables scroll internally; touch targets remain usable;
- zero serious or critical axe findings in representative public/app/dialog
  states, followed by documented manual review.

## Performance and security acceptance

Route pages are lazy. Leaflet is excluded from the public initial route. Lists
remain cursor-paginated and capped; polling remains one abortable loop; no
request N+1, unbounded retry, continuous geolocation, or retained listener is
introduced. SVG dimensions are stable; there is no canvas, WebGL, video, or
remote artwork.

The UI never renders raw exceptions or unsafe HTML, never stores secrets, never
hardcodes a personal address or device, and never issues an authentication
request. Existing CSP, same-origin proxy, OSM attribution, non-root runtime,
loopback exposure, and private PostgreSQL topology remain intact.

## Verification acceptance

Required evidence includes frontend typecheck/tests/build/audit, deterministic
Playwright across public/app workflows and target sizes, screenshots,
accessibility results, frontend/API images, Compose route boundaries, clean
stack and restart recovery, Alembic idempotency, backend offline/integration
tests, stable OpenAPI inventory, sanitized logs, resource cleanup, whitespace
and secret scans, unchanged Git index, and an empty cached diff.
