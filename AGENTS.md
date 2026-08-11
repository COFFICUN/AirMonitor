@'
# AirMonitor Agent Instructions

## Repository context

AirMonitor is an IoT air-quality monitoring system.

The repository contains:

- stable legacy AirMonitor v1 files at the repository root;
- AirMonitor v2 backend under backend/;
- documentation under docs/;
- Docker Compose and backend CI infrastructure.

Legacy v1 files, including the root legacy frontend, are reference material
only.

Do not modify legacy application files.

## Current branches

Integration branch:

develop

Current feature branch:

feature/frontend-v2-dashboard

## Current backend state

AirMonitor v2 backend uses:

- Python 3.13;
- FastAPI;
- PostgreSQL 18;
- async SQLAlchemy;
- Alembic;
- Pydantic;
- pytest;
- Docker;
- Docker Compose;
- GitHub Actions.

Current Alembic head:

a75caa2b44f5

Expected backend offline baseline:

- 850 passed;
- 2 skipped.

Expected OpenAPI inventory:

- OpenAPI 3.1.0;
- 11 total operations;
- 10 under /api/v1;
- 1 under /health;
- 11 unique operation IDs.

Record the actual checkout baseline before editing.

## Current macro task

Implement a complete AirMonitor frontend v2 and integrate it with the existing
FastAPI backend in one continuous macro sprint.

The new frontend must live under:

frontend/

Do not replace or edit the legacy root frontend.

The macro sprint includes:

1. frontend and API source audit;
2. React and TypeScript application bootstrap;
3. typed API client;
4. device setup and persistence;
5. backend health display;
6. geolocation handling;
7. measurement-session lifecycle controls;
8. live telemetry polling;
9. session history;
10. measurement history and charts;
11. session map;
12. loading, empty, offline, and error states;
13. responsive accessible design;
14. configurable backend CORS when required;
15. frontend unit and component tests;
16. browser end-to-end tests;
17. frontend Docker image;
18. frontend Compose service;
19. frontend CI;
20. complete clean-stack verification;
21. onboarding documentation;
22. final architecture, security, UX, and operational review.

Do not split this work into many manual phases.

Use internal RED and GREEN checkpoints, but continue automatically through the
entire approved scope.

Stop early only for a real safety, environment, or scope blocker.

## Required frontend technology

Use:

- React;
- TypeScript;
- Vite;
- modern browser Fetch API;
- Vitest;
- React Testing Library;
- Playwright for browser verification.

Use a minimal dependency set.

A focused chart or map library is allowed when it materially improves the
implementation.

Preferred map approach:

- Leaflet;
- OpenStreetMap tiles.

Preferred chart approach:

- a maintained React-compatible chart library;
- or a small custom SVG chart when that is simpler and sufficiently usable.

Do not introduce:

- Next.js;
- server-side rendering;
- Redux;
- a large UI framework;
- a commercial map service;
- paid APIs;
- unnecessary state-management libraries;
- authentication;
- Redis;
- WebSockets;
- speculative micro-frontends.

Use React state, context, hooks, and focused modules.

## Source-of-truth policy

Treat the current checkout as authoritative.

Read the actual backend routes, schemas, OpenAPI output, Docker configuration,
environment examples, tests, and documentation before designing the frontend.

Do not infer API request or response fields from historical reports when the
current code differs.

Use the generated FastAPI OpenAPI document as a contract source.

Do not redesign backend public contracts merely to simplify frontend work.

## External research

Use official primary sources when research is required:

- React documentation;
- TypeScript documentation;
- Vite documentation;
- Vitest documentation;
- Testing Library documentation;
- Playwright documentation;
- Leaflet documentation;
- Docker documentation;
- Nginx documentation;
- FastAPI CORS documentation.

Do not copy template code blindly.

Record only research that materially supports implementation decisions.

## Existing backend operations

Audit all current operations before implementation.

The frontend is expected to work with the established capabilities for:

- device registration;
- device lookup;
- device status updates;
- starting a measurement session;
- retrieving the active session;
- completing the active session;
- cancelling the active session;
- recording raw measurements;
- listing sessions;
- listing measurements;
- health status.

Do not add a new backend endpoint unless the existing API genuinely cannot
support an approved frontend requirement.

A device collection listing endpoint is not required for this MVP.

The user may select, enter, register, and persist a single active device ID in
the browser.

## Stable Telemetry Read API contract

The frontend must preserve:

- keyset pagination;
- opaque cursor handling;
- cursor/filter binding;
- timestamp DESC and id DESC ordering;
- limit range from 1 through 500;
- no OFFSET assumptions;
- mandatory device isolation;
- half-open time ranges;
- non-disclosing session filters.

The frontend must treat cursors as opaque strings.

It must not decode, construct, modify, or compare cursor contents.

## Frontend application structure

Create a maintainable structure similar to:

frontend/
  src/
    api/
    components/
    features/
    hooks/
    pages/
    types/
    utils/
    test/
  public/
  e2e/

Adapt names only when a clearer current convention exists.

Do not put the complete application into one component.

Separate at minimum:

- API transport;
- API error normalization;
- environment configuration;
- device persistence;
- geolocation handling;
- session lifecycle;
- telemetry polling;
- session pagination;
- measurement pagination;
- charts;
- map;
- shared UI states.

## Main user experience

Implement one cohesive dashboard application.

The user must be able to:

1. see whether the backend is available;
2. enter an existing device ID;
3. register a new device using the existing API;
4. persist the selected device ID in browser storage;
5. clear or change the selected device;
6. see current device state;
7. grant geolocation access when starting a session;
8. start a measurement session;
9. see whether a session is active;
10. complete the active session;
11. cancel the active session;
12. see the most recent telemetry;
13. see session history;
14. filter session history;
15. load additional session pages using the returned cursor;
16. select a session;
17. see measurements belonging to that session;
18. filter measurements by time;
19. load additional measurement pages using the returned cursor;
20. see measurement values in a chart and a compact table;
21. see session positions on a map when coordinates are present;
22. understand empty, loading, offline, permission-denied, validation, and
    server-error states.

Do not require a full page reload for normal operation.

## Device persistence

Persist only the selected non-secret device identifier and harmless UI
preferences.

Use a versioned browser-storage key.

Validate restored values before use.

Do not store:

- database credentials;
- API secrets;
- complete backend error traces;
- geolocation history beyond the application data already returned by the API;
- generated cursor internals.

Provide a visible way to clear the selected device.

## Geolocation

Use the browser Geolocation API only when needed for the approved workflow.

Requirements:

- request location when starting a session rather than on every page load;
- avoid restarting geolocation during telemetry refresh;
- preserve current UI state while polling;
- handle permission denied;
- handle timeout;
- handle unavailable location;
- use bounded timeout options;
- clearly distinguish location failure from backend failure;
- do not continuously track the user unless the current API contract requires
  it;
- do not silently fabricate coordinates.

Do not reload the page to refresh live values.

## Live telemetry polling

Implement live telemetry as application polling against the existing
measurement read endpoint.

Requirements:

- default interval approximately five seconds;
- no full page refresh;
- no geolocation restart;
- use one active polling loop;
- cancel requests when device changes or component unmounts;
- avoid overlapping requests;
- pause or reduce unnecessary polling when the document is hidden when
  practical;
- recover from temporary backend failure;
- avoid rapid unbounded retries;
- display the time of the latest successful update;
- show stale state when updates stop;
- fetch only the minimum required result, normally limit=1;
- do not infer that an empty response is a backend failure.

Display available metrics such as:

- PM1.0;
- PM2.5;
- PM10;
- temperature;
- humidity;
- measurement timestamp.

Use the actual current response-field names.

## Session history

Use:

GET /api/v1/devices/{device_id}/sessions

Support the approved filters exposed by the backend.

Requirements:

- newest-first display;
- status filtering;
- time-range filtering;
- initial page;
- cursor-based “load more” behavior;
- no page-number or OFFSET assumptions;
- no duplicate items when appending pages;
- reset accumulated items when filters change;
- clear loading and end-of-results states;
- stable selection of an active history item;
- safe rendering of timestamps.

## Measurement history

Use:

GET /api/v1/devices/{device_id}/measurements

Requirements:

- selected-session filter;
- time-range filters;
- newest-first source order;
- opaque cursor pagination;
- no duplicate rows;
- no skipped rows caused by frontend merging;
- reset pages when filters change;
- chart order appropriate for reading trends;
- keep API response order intact in the data layer;
- transform only a presentation copy when a chart requires oldest-to-newest
  ordering;
- table or details remain available for exact values.

Do not decode cursors.

## Charts

Provide a useful telemetry trend chart.

At minimum support:

- PM2.5;
- PM10;
- temperature;
- humidity.

PM1.0 may also be included.

Requirements:

- readable timestamp axis;
- understandable metric labels and units;
- no misleading interpolation;
- handle missing values;
- handle one-point datasets;
- handle empty datasets;
- responsive layout;
- accessible textual summary or table;
- no enormous unbounded dataset in memory.

Do not request all historical measurements at once.

## Map

Display session coordinates only when the actual API response includes usable
coordinates.

Requirements:

- session markers or points;
- selection synchronised with session history where practical;
- informative popup or details;
- no fabricated positions;
- clear empty state when no coordinates exist;
- map initialization and cleanup are tested;
- OpenStreetMap attribution remains visible;
- map-library CSS is loaded correctly;
- map failure must not crash the complete dashboard.

Do not send browser geolocation to third parties beyond normal map-tile
requests.

Document the OpenStreetMap tile dependency and offline limitation.

## Design requirements

The interface should look like a carefully built technical dashboard, not an
AI-generated landing page.

Use:

- restrained visual hierarchy;
- clean cards;
- readable typography;
- consistent spacing;
- accessible contrast;
- clear status indicators;
- responsive layout;
- desktop-first dashboard with usable mobile adaptation.

Avoid:

- excessive gradients;
- glassmorphism everywhere;
- decorative animations;
- fake charts;
- oversized marketing headings;
- excessive rounded panels;
- unexplained icons;
- visual noise.

Use Russian interface text unless the existing repository establishes another
frontend language convention.

Code identifiers remain in English.

## Accessibility

Provide at minimum:

- semantic headings;
- labelled form controls;
- keyboard-accessible actions;
- visible focus states;
- accessible status messages;
- appropriate buttons instead of clickable div elements;
- sufficient contrast;
- chart/table fallback;
- map not being the only source of session information;
- no colour-only status meaning.

Do not suppress browser zoom.

## API client

Create one typed API client layer.

Requirements:

- configurable base URL;
- normalized path joining;
- JSON request and response handling;
- bounded request timeout;
- AbortSignal support;
- normalized API errors;
- preservation of safe backend messages;
- no exposure of internal raw errors to the UI;
- no repeated fetch boilerplate across components;
- no hardcoded personal IP;
- no hardcoded production hostname;
- no hardcoded device ID.

Use the actual API schemas.

Do not add generated API clients unless generation is reliable, documented,
and checked into the workflow intentionally.

## API base URL

Use one canonical frontend environment variable, preferably:

VITE_API_BASE_URL

Audit existing conventions first.

Development behavior must support:

- browser frontend running locally;
- backend running through Compose;
- backend running directly from Python.

Document the distinction between:

- host-to-host URL;
- container-to-container URL;
- browser-visible URL.

Do not use the Compose service name in browser JavaScript unless a reverse
proxy makes that name browser-resolvable.

## CORS

Audit current backend CORS behavior.

If the frontend and backend run on different browser origins, add the minimum
safe configurable CORS support required for local development.

Requirements:

- allowed origins configured through environment variables;
- no unrestricted wildcard combined with credentials;
- no hardcoded personal origin;
- no unrelated middleware changes;
- exact tests for allowed and rejected origins;
- safe default;
- documentation in environment examples and README.

Do not enable credentials unless the current application requires them.

No authentication is introduced.

## Frontend testing

Add unit and component tests for at least:

- environment configuration;
- API URL construction;
- API error normalization;
- device ID persistence;
- health state;
- geolocation success;
- geolocation denial;
- live polling lifecycle;
- no overlapping polling;
- polling cancellation;
- session cursor pagination;
- filter reset;
- measurement cursor pagination;
- chart data transformation;
- empty states;
- error states;
- session lifecycle actions.

Use fake timers carefully.

Do not create tests that depend on live internet map tiles.

Mock the map boundary where needed.

## Browser end-to-end tests

Use Playwright for high-value flows.

Cover at minimum:

1. dashboard loads;
2. backend health becomes visible;
3. device ID can be selected or registered;
4. selected device persists after reload;
5. session can be started with mocked geolocation;
6. denied geolocation produces a clear state;
7. live telemetry updates without full page reload;
8. session list loads;
9. load-more uses cursor behavior;
10. session selection loads measurements;
11. chart or table displays measurements;
12. session completion works;
13. backend error displays safely;
14. narrow viewport remains usable.

Prefer deterministic API fixtures for frontend-specific browser tests.

Also add at least one Compose-backed smoke path against the real backend when
safe and practical.

Do not make the entire browser suite depend on external map tiles.

## Backend compatibility

Do not modify telemetry repositories, services, schemas, migrations, or public
contracts unless a failing integration test demonstrates a real defect.

Allowed narrow backend changes may include:

- CORS configuration;
- CORS tests;
- safe configuration parsing required by frontend deployment;
- health metadata only when it does not change the approved response contract.

Do not add authentication in this phase.

Do not add frontend-specific response fields to existing API models.

## Frontend Docker image

Create a production-style frontend image.

Preferred approach:

- Node build stage;
- static runtime stage using an appropriate minimal web server.

The final frontend runtime image must:

- contain built static assets;
- not contain node_modules from development;
- not run as root when the selected runtime supports a secure non-root
  configuration;
- contain no source secrets;
- expose only the frontend HTTP port;
- provide a healthcheck or Compose healthcheck;
- support SPA route fallback;
- include required map and application assets;
- avoid copying legacy root frontend files.

Do not run the Vite development server as the production container process.

## Compose integration

Extend the existing Compose stack with a frontend service.

The complete stack must contain:

- frontend;
- api;
- db.

Requirements:

- frontend waits for API health where supported;
- API still waits for database health;
- browser reaches frontend through a loopback-bound host port;
- browser reaches API through the documented URL or reverse-proxy path;
- PostgreSQL remains unexposed publicly;
- services remain non-privileged;
- no real credential is committed;
- development data volume behavior remains intentional;
- backend migration ownership remains unchanged;
- clean startup still works;
- clean shutdown removes test resources;
- existing backend-only behavior remains supported where practical.

Prefer a same-origin reverse-proxy arrangement when it clearly reduces CORS
complexity and remains understandable.

When using a frontend web-server proxy:

- proxy only the API paths required;
- preserve `/health` behavior deliberately;
- configure SPA fallback without swallowing API 404 responses;
- document browser-visible routes.

## Frontend CI

Extend CI with frontend gates.

At minimum:

- install the approved Node version;
- use the committed lockfile;
- run dependency installation with a deterministic command;
- run TypeScript checking;
- run frontend unit tests;
- run frontend production build;
- build the frontend Docker image;
- run Playwright browser tests in a stable environment;
- preserve existing backend offline, integration, and Docker jobs.

Use minimal workflow permissions.

Use dependency caching only when correct.

Do not weaken backend CI.

Do not require secrets for normal pull-request CI.

## Documentation

Update README.md without deleting useful backend onboarding information.

Add:

- frontend architecture;
- frontend prerequisites;
- local frontend start;
- full Compose start;
- environment variables;
- browser URL;
- API URL behavior;
- device setup;
- geolocation behavior;
- live polling behavior;
- session workflow;
- test commands;
- Playwright commands;
- build commands;
- troubleshooting;
- OpenStreetMap dependency;
- current limitations.

Create:

docs/reviews/frontend-v2-final-verification.md

It must contain:

- frontend stack;
- main features;
- API integration summary;
- CORS or proxy decision;
- geolocation behavior;
- polling behavior;
- cursor pagination behavior;
- map behavior;
- chart behavior;
- frontend test results;
- Playwright results;
- Docker results;
- Compose clean-start result;
- CI changes;
- accessibility review;
- security review;
- known limitations;
- cleanup confirmation;
- any blocker without fabricated success.

A focused source-research document is allowed when it adds lasting value.

## Clean verification environment

Use unique Docker Compose project names beginning with:

airmonitor-frontend-test-

Do not reuse or modify unrelated containers, networks, images, or volumes.

Do not connect to the protected database named:

airmonitor

Use a dedicated disposable database accepted by the current guards.

Do not print passwords or complete database URLs.

Clean up every temporary project resource at the end.

## Required clean-stack verification

Run a complete clean-stack test:

1. validate Compose configuration;
2. build frontend and backend images;
3. inspect runtime users;
4. start PostgreSQL;
5. wait for database health;
6. start backend;
7. verify Alembic head;
8. wait for backend health;
9. start frontend;
10. wait for frontend health;
11. open the frontend in Playwright;
12. verify backend health display;
13. execute a minimal device workflow;
14. use mocked browser geolocation where required;
15. execute a session workflow;
16. insert or send representative measurements through approved APIs;
17. verify live display changes without reload;
18. verify session history;
19. verify measurement history;
20. verify chart/table;
21. verify map behavior when coordinates exist;
22. restart frontend;
23. verify frontend recovers;
24. restart backend;
25. verify migrations remain idempotent;
26. verify frontend reconnects;
27. inspect sanitized logs;
28. confirm no secret leakage;
29. stop the stack;
30. remove test containers, networks, volumes, and temporary image tags;
31. confirm no matching resource remains.

Use bounded polling rather than arbitrary sleep commands.

## Baseline preservation

Backend must retain:

- zero offline failures;
- no unexpected new skips;
- at least the current 850 passing tests;
- OpenAPI 3.1.0;
- 11 operations;
- 11 unique operation IDs;
- one Alembic head: a75caa2b44f5.

Report actual final counts.

Frontend must have:

- zero TypeScript errors;
- zero unit-test failures;
- zero production-build failures;
- zero required Playwright failures.

## Security requirements

Do not add:

- real credentials;
- real database URLs;
- personal paths;
- hardcoded local IP addresses;
- public PostgreSQL exposure;
- privileged containers;
- root runtime where avoidable;
- unsafe HTML injection;
- unvalidated external URLs;
- silent geolocation tracking;
- token storage;
- complete backend exception rendering;
- source maps containing secrets;
- wildcard CORS with credentials.

External links opened in a new tab must use safe rel attributes.

Map attribution must remain intact.

## Performance requirements

Do not:

- poll faster than required;
- create overlapping polling requests;
- load unlimited historical data;
- render thousands of unvirtualized rows;
- refetch all history after every live update;
- initialize multiple maps for one view;
- retain stale event listeners;
- retain aborted fetch errors as user-visible failures;
- decode backend cursors;
- create frontend N+1 request loops.

Use memoization only where measurable or clearly necessary.

Do not over-optimise before correctness.

## Git restrictions

Do not perform Git writes.

Do not:

- stage;
- commit;
- push;
- merge;
- reset;
- clean;
- stash;
- create or delete branches;
- modify Git configuration.

Read-only Git commands are allowed.

Keep the Git index unchanged.

## Expected changed or created files

Expected scope may include:

- frontend/**;
- compose.yaml;
- safe environment examples;
- .gitignore;
- .gitattributes;
- .github/workflows/backend-ci.yml or a clearly named frontend workflow;
- narrowly scoped backend CORS configuration and tests;
- README.md;
- docs/reviews/frontend-v2-final-verification.md;
- optional focused frontend source research.

Do not modify:

- legacy root application files;
- committed Alembic revisions;
- telemetry business logic;
- established response schemas;
- firmware files.

## Final verification

Run at minimum:

1. backend focused tests for any changed configuration;
2. full backend offline suite;
3. applicable PostgreSQL integration tests;
4. pip check;
5. Alembic heads;
6. OpenAPI inventory;
7. frontend dependency installation;
8. TypeScript check;
9. frontend unit tests;
10. frontend production build;
11. frontend lint when configured;
12. Playwright tests;
13. backend Docker build;
14. frontend Docker build;
15. Compose config validation;
16. clean full-stack startup;
17. browser smoke flow;
18. restart recovery;
19. migration idempotency;
20. accessibility checks available in the test stack;
21. git diff --check;
22. shell and YAML syntax checks;
23. final-newline checks;
24. secret scans;
25. database URL scans;
26. personal-path scans;
27. temporary-artifact scans;
28. Docker cleanup verification;
29. Git index verification.

## Final review axes

Review the completed diff for:

1. correctness;
2. readability;
3. frontend architecture;
4. backend compatibility;
5. accessibility;
6. UX;
7. security;
8. performance;
9. browser reliability;
10. container correctness;
11. CI reliability;
12. documentation accuracy;
13. repository cleanliness.

Resolve every Critical and Required finding before stopping.

## Definition of done

The macro phase is complete only when:

- frontend v2 exists under frontend/;
- legacy frontend is unchanged;
- device selection and registration work;
- selected device persists safely;
- backend health is displayed;
- geolocation is requested only for approved actions;
- session start, complete, and cancel work;
- live measurements update without page reload;
- geolocation does not restart during polling;
- session history works with opaque cursor pagination;
- measurement history works with opaque cursor pagination;
- chart and table work;
- map works when coordinates exist;
- loading, empty, offline, permission, validation, and server states exist;
- responsive and accessibility checks pass;
- frontend unit tests pass;
- Playwright tests pass;
- frontend Docker image builds;
- full Compose stack starts cleanly;
- restart recovery works;
- backend contracts remain stable;
- CI covers frontend and existing backend gates;
- documentation is reproducible;
- no secret or temporary Docker resource remains;
- Git index remains unchanged;
- work stops once for external manual review.
'@ | Set-Content -Path ".\AGENTS.md" -Encoding UTF8