# Frontend User Redesign Final Verification

Date: 2026-08-11

## Outcome

The accepted AirMonitor field-laboratory redesign remains the visual
foundation. This pass polished it instead of replacing it and corrected the
product model everywhere: one measurement session represents one stationary
geographic point. The device may be moved between sessions, but the frontend
does not imply movement, a track, or multiple places inside one session.

All changes remain unstaged and uncommitted. Legacy root v1 files, backend
business logic, migrations, and public API contracts were not changed.

## Pages and presentation completed

- `/`, `/about`, `/participate`, and `/methodology` now explain selecting a
  place, taking a series of measurements there, and starting a new session for
  another place. `/login` remains an honest disabled future-account surface.
- `/app` keeps a compact system indicator and prioritizes device, session,
  current readings, the next action, trends, point map, and recent sessions.
- `/app/measurement` now has balanced lifecycle/live-data columns and a full
  width stationary-measurement instruction panel with one-shot geolocation
  guidance.
- `/app/sessions` describes separate researched points and retains strict
  newest-first opaque-cursor pagination and filters.
- `/app/map` is now a session-point map. It renders one marker per finite
  session coordinate, no polyline, and no per-measurement location chain. A
  synchronized detail card shows status, start time, sample count, latitude,
  and longitude.
- `/app/data` describes a time series at one stationary place while preserving
  the exact-value table and presentation-only chronological chart copy.
- `/app/settings` adds real system/light/dark theme selection, keeps density,
  motion, time, polling, tile, and reset controls, and shows the actual locally
  selected preferred device without inventing account state.
- Light, dark, comfortable, compact, reduced-motion, tile-disabled, loading,
  empty, offline, validation, permission-denied, and safe server-error states
  remain supported.

## Visual system and original character

- Palette: petrol navy, mineral off-white, chartreuse signal, teal data, and
  explicit semantic state colours. The dark theme uses dedicated surface,
  border, focus, map, table, and navigation tokens.
- Onest is bundled locally as variable WOFF2 Cyrillic, Cyrillic Extended, and
  Latin subsets under the SIL Open Font License. It now carries body,
  navigation, control, and display typography; compact technical labels keep a
  deliberate mono stack. No remote font request is required at runtime.
- The landing signature is a constellation of independent observation points,
  not a connected path. Desktop and mobile compositions retain clear type,
  restrained cards, stable spacing, and the original field-lab identity.
- `frontend/public/airi-field-robot.webp` is the original generated Айри
  character: a portable air-sampling robot with an e-ink face, chest turbine,
  utility pack, sensor cage, and protected leaf. It is 1,024 × 1,536 and 89,510
  bytes, locally served, and not copied from an existing game character.

## State, map, and compatibility

- Preferences use strict version 2 storage. Valid version 1 records migrate to
  `theme: "system"`; unknown keys, values, and corrupt JSON reset safely.
- Geolocation remains a single bounded browser request when a session starts.
  Polling does not request it again and never fabricates coordinates.
- Live telemetry remains one abortable, visibility-aware, non-overlapping loop
  with `limit=1`; histories remain bounded and cursor-based.
- Leaflet remains lazy and isolated. OpenStreetMap attribution is visible;
  disabling tiles keeps session details, history, charts, and tables usable.
- OpenAPI stayed at 3.1.0 with 11 operations, 10 under `/api/v1`, one under
  `/health`, and 11 unique operation IDs. Alembic has one head,
  `a75caa2b44f5`.

## Verification results

| Gate | Final result |
|---|---|
| TypeScript | passed, zero errors |
| Vitest | 27 files, 115 passed, zero failures |
| production build | passed, 139 modules transformed |
| main browser bundle | 236.48 kB, 76.02 kB gzip |
| lazy Leaflet bundle | 152.45 kB, 45.11 kB gzip |
| deterministic Playwright | 21 passed; 3 intentionally guarded Compose/visual specs skipped |
| axe/keyboard | 4 passed across all public and participant routes in explicit light/dark themes plus the dialog; zero serious/critical findings |
| responsive browser checks | no horizontal overflow at 360×800, 390×844, 768×1024, 1280×800, 1440×900, and 1920×1080 |
| visual capture | 1 passed; 20 reviewed desktop/mobile/light/dark screenshots |
| backend offline suite | 850 passed, 2 guarded skips, zero failures |
| backend OpenAPI tests | 12 passed |
| backend `pip check` | no broken requirements |
| Compose config and images | valid; frontend and API images built |
| runtime users | frontend `101:101`; API `10001:10001` |
| clean stack | PostgreSQL, API, and frontend all reached healthy; PostgreSQL had no published host port |
| real backend browser smoke | passed device registration, persistence, geolocation, session, telemetry, completion, history, chart/table, and point map |
| route boundaries | `/health` 200 JSON; `/app/settings` 200 SPA HTML; unknown `/api/v1/*` 404 JSON; Айри 200 WebP |
| restart recovery | frontend and API recovered; selected device and latest telemetry restored |
| migration idempotency | `a75caa2b44f5 (head)` after API restart |
| sanitized logs | zero traceback, error, credential, token, secret, or database-URL findings |
| Docker cleanup | zero matching containers, networks, volumes, or temporary project images |

The guarded Compose tests were executed separately and passed 1/1 each. The
visual spec was also executed separately and passed 1/1.

## Accessibility findings resolved

The expanded dark-theme axe pass found the destructive reset button at 2.21:1
contrast. A dedicated destructive-action token now keeps white text above the
WCAG AA threshold without weakening readable pale-red status text. The full
axe set then passed with no excluded rules.

The follow-up public-theme regression reproduced headings at 1.02:1,
navigation at 1.5:1, and the primary button at 1.69:1 when a stored dark
preference was applied outside `/app`. Hard-coded public light surfaces were
replaced with semantic theme surfaces, the hero point card was moved onto a
theme-aware surface, and primary buttons received paired foreground/background
tokens. The final route matrix passed in both explicit themes.

Semantic landmarks, labelled controls, visible focus, keyboard-safe dialogs,
status text that does not depend only on colour, chart/table alternatives, and
session details outside the map remain intact. Mobile navigation is a true
mobile composition rather than a scaled desktop sidebar.

## Clean-stack evidence

The disposable project was
`airmonitor-frontend-test-ee08-point-polish`, using a dedicated non-protected
database and loopback-only frontend/API ports. The workflow built both images,
checked runtime users, started the stack, ran the real browser flow, restarted
frontend and API, confirmed Alembic head and recovery, scanned logs, and ran
`down -v --remove-orphans --rmi local`. Final matching resource counts were:
containers 0, networks 0, volumes 0, images 0.

## Known limitations

- AirMonitor is an engineering and research tool, not official monitoring,
  AQI, medical advice, exposure estimation, or an account system.
- WHO guidance uses averaging periods; one instantaneous value or one short
  session is not a health conclusion.
- OpenStreetMap tiles require internet and expose ordinary tile-request
  metadata. The local tile setting provides an explicit opt-out.
- Axe and this manual visual pass do not replace testing with multiple screen
  readers and external users of assistive technology.

## Handoff

No Git write operation was performed. The Git index remains unchanged and the
cached diff is empty. The frontend is ready for external manual review before
the project moves on to firmware work.
