# Frontend v2 Source Research

**Research date:** 2026-08-04

**Inspected revision:** `8eadaae4b81c816102b6473dca54adf7a1673ff5`

**Scope:** implementation-relevant React, TypeScript, Vite, Vitest,
Testing Library, Playwright, browser Fetch and Geolocation, Leaflet,
OpenStreetMap, Nginx, Docker, and FastAPI CORS behavior

**Source policy:** official project documentation, web standards, official npm
registry metadata, and first-party repositories only

This is an implementation input, not a verification report. The checkout had
no `frontend/package.json` at research time, so the versions below are a dated
recommendation snapshot, not installed-dependency evidence.

## 1. Version and compatibility snapshot

Official npm `latest` metadata reported the following stable versions on the
research date:

| Package | Version | Official metadata |
|---|---:|---|
| `react` | 19.2.8 | [npm registry](https://registry.npmjs.org/react/latest) |
| `react-dom` | 19.2.8 | [npm registry](https://registry.npmjs.org/react-dom/latest) |
| `vite` | 8.2.0 | [npm registry](https://registry.npmjs.org/vite/latest) |
| `@vitejs/plugin-react` | 6.0.5 | [npm registry](https://registry.npmjs.org/%40vitejs%2Fplugin-react/latest) |
| `typescript` | 7.0.2 | [npm registry](https://registry.npmjs.org/typescript/latest) |
| `leaflet` | 1.9.4 | [npm registry](https://registry.npmjs.org/leaflet/latest) |
| `vitest` | 4.1.10 | [npm registry](https://registry.npmjs.org/vitest/latest) |
| `jsdom` | 30.0.1 | [npm registry](https://registry.npmjs.org/jsdom/latest) |
| `@testing-library/react` | 16.3.2 | [npm registry](https://registry.npmjs.org/%40testing-library%2Freact/latest) |
| `@testing-library/dom` | 10.4.1 | [npm registry](https://registry.npmjs.org/%40testing-library%2Fdom/latest) |
| `@testing-library/jest-dom` | 7.0.0 | [npm registry](https://registry.npmjs.org/%40testing-library%2Fjest-dom/latest) |
| `@testing-library/user-event` | 14.6.3 | [npm registry](https://registry.npmjs.org/%40testing-library%2Fuser-event/latest) |
| `@playwright/test` | 1.62.1 | [npm registry](https://registry.npmjs.org/%40playwright%2Ftest/latest) |
| `@axe-core/playwright` | 4.12.1 | [npm registry](https://registry.npmjs.org/%40axe-core%2Fplaywright/latest) |

The matching declaration packages were `@types/react` 19.2.18,
`@types/react-dom` 19.2.4, and `@types/leaflet` 1.9.22.
([React types](https://registry.npmjs.org/%40types%2Freact/latest),
[React DOM types](https://registry.npmjs.org/%40types%2Freact-dom/latest),
[Leaflet types](https://registry.npmjs.org/%40types%2Fleaflet/latest))

Use Node.js 24.19.0 for local, image-build, Playwright, and CI consistency. It
was the current Node 24 LTS patch, and Node recommends Active or Maintenance
LTS for production applications.
([Node release policy and status](https://nodejs.org/en/about/previous-releases),
[Node 24.19.0 artifacts](https://nodejs.org/dist/latest-v24.x/))

The declared compatibility ranges intersect cleanly:

- `react-dom` 19.2.8 requires `react ^19.2.8`; keep the two packages on the
  same patch.
- `@vitejs/plugin-react` 6.0.5 requires Vite 8, while Vitest 4.1.10 accepts
  Vite 6, 7, or 8.
- Vite 8 requires Node `^20.19.0 || >=22.12.0`; Vitest accepts Node 20, 22,
  or 24+, Playwright requires Node 20+, and `jsdom` 30.0.1 requires at least
  Node 22.22.2 or 24.15.0 in the supported even-numbered lines. Node 24.19.0
  satisfies all four.
- React Testing Library 16.3.2 accepts React and React DOM 18 or 19 and
  requires DOM Testing Library 10. Jest DOM 7 requires DOM Testing Library
  10, and User Event 14.6.3 accepts it. React DOM types 19.2.4 require React
  types 19.2.x.
- `@axe-core/playwright` 4.12.1 accepts `playwright-core >=1.0.0`.

These are metadata-level compatibility checks only. The committed lockfile,
`npm ci`, `npm ls`, typecheck, tests, build, and browser runs must establish
actual compatibility after bootstrap.

## 2. React effects, polling, fetch, and geolocation

An Effect synchronizes React with an external system. React runs cleanup before
re-running an Effect with changed dependencies and after unmount; development
Strict Mode adds a setup-cleanup-setup cycle specifically to expose missing
cleanup. Every polling timer, visibility listener, in-flight request, and
Leaflet instance must therefore have symmetrical cleanup, and every reactive
dependency must be declared.
([React `useEffect`](https://react.dev/reference/react/useEffect),
[React effect synchronization](https://react.dev/learn/synchronizing-with-effects),
[React `StrictMode`](https://react.dev/reference/react/StrictMode))

React's manual-fetch example guards state updates from stale responses in its
cleanup. Fetch accepts an `AbortSignal`, and aborting rejects the fetch and
cancels readable request or response bodies. AirMonitor should combine both
ideas: pass a caller signal through the typed API client, abort on dependency
change or unmount, and prevent a superseded result from committing state.
Aborts are lifecycle events and must not become user-visible backend errors.
([React: fetching data with Effects](https://react.dev/reference/react/useEffect#fetching-data-with-effects),
[Fetch `RequestInit.signal` and abort processing](https://fetch.spec.whatwg.org/#dom-requestinit-signal))

For live telemetry, a self-scheduling timeout should start the next request
only after the current request settles. This derived design gives one active
loop and makes non-overlap explicit. Cleanup clears the pending timeout and
aborts the active request. A hidden-document listener can pause or lengthen the
cycle, but it must use the same setup/cleanup boundary.

The platform exposes one-shot `getCurrentPosition()` separately from continuous
`watchPosition()`. The approved workflow needs one-shot acquisition only, with
a finite `timeout`, and distinct handling for `PERMISSION_DENIED`,
`POSITION_UNAVAILABLE`, and `TIMEOUT`. The W3C also advises requesting location
only when necessary for the stated task.
([W3C Geolocation API, errors, timeout, and privacy](https://www.w3.org/TR/geolocation/))

## 3. Typed API client and Vite configuration

Use one transport boundary around `fetch`. It should join a validated base URL
and path, serialize JSON, enforce a bounded timeout, accept an external
`AbortSignal`, and normalize failures. Fetch rejects on network failure but
HTTP error responses remain `Response` objects, so the client must inspect
`response.ok`/status before decoding the safe backend error envelope.
([Fetch response and `ok`](https://fetch.spec.whatwg.org/#dom-response-ok),
[Fetch method](https://fetch.spec.whatwg.org/#dom-global-fetch))

`VITE_API_BASE_URL` is an appropriate canonical variable, but every `VITE_*`
value is a client-visible string statically bundled at build time. It must
never contain a secret, and changing it in a static runtime container requires
a rebuild unless an additional runtime-config mechanism is intentionally
introduced. Add an `ImportMetaEnv` declaration and validate/normalize the
value in one configuration module.
([Vite environment variables and modes](https://vite.dev/guide/env-and-mode))

Prefer relative browser API URLs by default. Vite's development server can
proxy path prefixes such as `/api` and the exact `/health` path to a backend
running on the host; matching requests are proxied instead of transformed.
The production Nginx arrangement below can expose the same browser-visible
paths, so application code does not need environment-specific Compose service
names.
([Vite `server.proxy`](https://vite.dev/config/server-options.html#server-proxy))

Vite transpiles TypeScript but does not typecheck it. Run `tsc --noEmit`
separately and enable `strict`; Vite 8 also requires `isolatedModules` for its
per-file transform. The production gate is therefore typecheck followed by
`vite build`, whose default entry is `index.html` and whose output is a static
application bundle.
([Vite TypeScript behavior](https://vite.dev/guide/features.html#typescript),
[TypeScript `strict`](https://www.typescriptlang.org/tsconfig/strict.html),
[Vite production build](https://vite.dev/guide/build))

## 4. Unit, component, browser, and accessibility tests

Vitest reads Vite configuration and `vitest run` is its non-watch command.
DOM component tests need an explicit browser-like environment such as `jsdom`
because Vitest defaults to Node. Use a TypeScript setup file that imports
`@testing-library/jest-dom/vitest`.
([Vitest getting started](https://vitest.dev/guide/),
[Vitest test environment](https://vitest.dev/config/environment.html),
[Jest DOM with Vitest](https://github.com/testing-library/jest-dom#with-vitest))

Component tests should operate on rendered DOM, prefer role-and-accessible-name
queries, use retrying `findBy*` queries for asynchronous appearance, and create
a `userEvent.setup()` instance inside each test. These choices exercise the
interface in the way a keyboard, pointer, or assistive-technology user sees it
instead of coupling tests to component internals.
([Testing Library principles](https://testing-library.com/docs/guiding-principles/),
[query priority and async behavior](https://testing-library.com/docs/queries/about/),
[User Event setup](https://testing-library.com/docs/user-event/intro/))

Fake timers are appropriate for the five-second polling interval, but scope
and restore them per test. Tests must also control pending promises so they can
prove that a second request is not launched while the first is unresolved and
that device changes/unmount abort the active request.
([Vitest timer mocking](https://vitest.dev/guide/mocking/timers))

Playwright's `page.route()` can fulfill API calls without reaching a backend.
Register routes before navigation and use deterministic fixtures for health,
registration, lifecycle actions, telemetry updates, and opaque-cursor pages.
Intercept or abort OpenStreetMap tile requests so the frontend-specific suite
does not depend on the internet. Grant a fixed geolocation and permission for
success cases. For a deterministic denial case, install a geolocation mock with
`page.addInitScript()` before navigation and invoke the error callback with the
platform permission-denied code rather than relying on a browser prompt.
([Playwright API mocking](https://playwright.dev/docs/mock),
[Playwright geolocation and permissions](https://playwright.dev/docs/emulation#geolocation),
[Playwright browser-API mocks](https://playwright.dev/docs/mock-browser-apis))

Configure Playwright `webServer` with a bounded startup timeout, a URL readiness
check, `baseURL`, and `reuseExistingServer: false` in CI. Playwright supports
multiple servers when a separate real-backend smoke path needs both frontend
and backend processes.
([Playwright `webServer`](https://playwright.dev/docs/test-webserver))

Add a focused `@axe-core/playwright` scan for automatically detectable WCAG A
and AA failures, while retaining manual keyboard, zoom, responsive, chart-table,
and map-fallback checks: Playwright explicitly warns that automated scans find
only some accessibility problems.
([Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing))

## 5. Leaflet and OpenStreetMap

Leaflet 1.9.4 requires its CSS and a map container with a defined height. In a
bundled app, import `leaflet/dist/leaflet.css` once rather than use a remote CSS
dependency. Create one map for one container, update layers without recreating
the map, call `invalidateSize()` after a dynamic layout-size change, and call
`map.remove()` in Effect cleanup; `remove()` destroys the map and clears its
listeners.
([Leaflet quick start](https://leafletjs.com/examples/quick-start/),
[Leaflet map lifecycle](https://leafletjs.com/reference.html#map-remove),
[Leaflet `invalidateSize`](https://leafletjs.com/reference.html#map-invalidatesize))

Keep the default attribution control visible and provide the required linked
OpenStreetMap credit. Use the HTTPS tile URL, preserve normal browser Referer
and cache behavior, and do not prefetch, bulk-download, or claim offline tile
support. The public tile service is an external online dependency whose access
may be withdrawn; a tile failure must leave the session list/details usable.
([OSMF tile policy](https://operations.osmfoundation.org/policies/tiles/),
[OSMF attribution guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines),
[OpenStreetMap copyright](https://www.openstreetmap.org/copyright))

Leaflet popup strings are rendered as HTML. Do not interpolate backend text
into an HTML string; use a DOM node with `textContent` or another escaped text
boundary.
([Leaflet popup warning](https://leafletjs.com/examples/quick-start/#working-with-popups))

## 6. Nginx proxy, SPA fallback, and CORS decision

Use the frontend server as the browser's same-origin gateway in Compose:

```nginx
location ^~ /api/ {
    proxy_pass http://api:8000;
}

location = /health {
    proxy_pass http://api:8000;
}

location / {
    try_files $uri $uri/ /index.html;
}
```

Nginx selects an exact location immediately and otherwise prefers the longest
prefix; `proxy_pass` without a URI preserves the request URI. `try_files`
checks static candidates and internally redirects to its final URI. Keeping
the API and health proxy locations outside the SPA location ensures backend
404/validation responses are returned as-is rather than replaced with
`index.html`.
([Nginx location matching](https://nginx.org/en/docs/http/ngx_http_core_module.html#location),
[Nginx `proxy_pass` URI behavior](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass),
[Nginx `try_files`](https://nginx.org/en/docs/http/ngx_http_core_module.html#try_files))

FastAPI defines an origin as protocol, host, and port. It describes CORS as the
case where browser frontend JavaScript calls a backend at a different origin.
Therefore, it follows that relative `/api/...` and `/health` requests served
through the frontend origin do not need a browser CORS grant even though Nginx
forwards them to the internal `api` service. The Compose service name remains
server-side and is never emitted into browser JavaScript.
([FastAPI CORS and origin definition](https://fastapi.tiangolo.com/tutorial/cors/))

Use the same relative paths with Vite's development proxy. If developers opt
instead for a direct `VITE_API_BASE_URL` such as `http://localhost:8000` from a
frontend at `http://localhost:5173`, the ports create different origins and the
backend must explicitly allow the configured frontend origin. Keep credentials
disabled, keep the default origin list empty, and test allowed and rejected
preflights. FastAPI/Starlette defaults are restrictive, and wildcard origins,
methods, or headers cannot be combined with credentialed CORS.
([FastAPI `CORSMiddleware`](https://fastapi.tiangolo.com/tutorial/cors/#use-corsmiddleware),
[Starlette CORS defaults](https://www.starlette.io/middleware/#corsmiddleware))

## 7. Frontend image

Use a multi-stage Dockerfile: a Node 24.19 build stage runs deterministic
installation, typecheck/tests as the selected build policy requires, and
`vite build`; the runtime stage receives only `dist/` and the reviewed Nginx
configuration. Multi-stage builds intentionally allow selective artifact copy
while leaving build tools and `node_modules` out of the final image.
([Docker multi-stage builds](https://docs.docker.com/build/building/multi-stage/),
[Node Official Image](https://hub.docker.com/_/node))

Use the verified-publisher `nginxinc/nginx-unprivileged` runtime on port 8080,
prefer a versioned or digest-pinned Alpine tag, and do not switch back to root.
The first-party image runs Nginx as an unprivileged user and relocates its PID
and temporary paths accordingly. Docker's `USER` instruction controls both
later build steps and the runtime `ENTRYPOINT`/`CMD`.
([NGINX unprivileged image](https://github.com/nginx/docker-nginx-unprivileged),
[verified image metadata](https://hub.docker.com/r/nginxinc/nginx-unprivileged),
[Dockerfile `USER`](https://docs.docker.com/reference/dockerfile/#user))

Probe the frontend's own static route (or a dedicated frontend-only health
location) for its container healthcheck. `/health` is deliberately proxied to
the backend for the dashboard contract and therefore must not be the sole proof
that the Nginx/static process itself is healthy.

## 8. Supported implementation decisions

1. Bootstrap React 19.2.8 with Vite 8.2.0 and strict TypeScript 7.0.2 on
   Node 24.19.0; lock exact resolved versions and verify the installed tree.
2. Keep browser API paths relative through Vite and Nginx proxies; add
   configurable explicit CORS only for the optional direct cross-origin mode.
3. Centralize timeout, abort, JSON, status, and safe-error behavior in one typed
   client; make every polling/map/listener Effect own complete cleanup.
4. Use Vitest plus jsdom and Testing Library for focused units/components, and
   Playwright route fixtures for deterministic user flows with one separate
   real-backend smoke path.
5. Integrate Leaflet directly, import its CSS, preserve attribution, avoid
   unsafe popup HTML, and keep map/tile failures non-fatal.
6. Build static assets in a Node stage and serve only the result from
   unprivileged Nginx, with API locations isolated from SPA fallback.
7. Treat all test, build, image, browser, accessibility, and clean-stack
   outcomes as later verification evidence; source research establishes none
   of those outcomes by itself.
