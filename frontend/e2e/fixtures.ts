import type { Page, Route } from '@playwright/test';

export const SESSION_CURSOR = 'session-opaque+/=_cursor';
export const MEASUREMENT_CURSOR = 'measurement-opaque+/=_cursor';

export interface MockBackendState {
  readonly seenSessionCursors: string[];
  readonly seenMeasurementCursors: string[];
  readonly sessionStartBodies: unknown[];
  liveReadCount: number;
  activeSession: Record<string, unknown> | null;
}

interface MockBackendOptions {
  readonly malformedDeviceId?: number;
  readonly healthFailure?: boolean;
}

const device = {
  id: 42,
  device_uid: 'sensor-42',
  name: 'Лаборатория',
  is_active: true,
  created_at: '2026-08-04T06:00:00Z',
};

const sessions = [
  {
    id: 11,
    device_id: 42,
    status: 'completed',
    started_at: '2026-08-04T06:00:00Z',
    ended_at: '2026-08-04T06:20:00Z',
    latitude: 43.238,
    longitude: 76.945,
    sample_count: 2,
    created_at: '2026-08-04T06:00:00Z',
  },
  {
    id: 10,
    device_id: 42,
    status: 'cancelled',
    started_at: '2026-08-03T06:00:00Z',
    ended_at: '2026-08-03T06:05:00Z',
    latitude: 43.251,
    longitude: 76.921,
    sample_count: 1,
    created_at: '2026-08-03T06:00:00Z',
  },
] as const;

function measurement(id: number, sessionId: number, pm25: number) {
  const minute = String(id % 60).padStart(2, '0');
  return {
    id,
    device_id: 42,
    session_id: sessionId,
    source_message_id: null,
    measured_at: `2026-08-04T06:${minute}:00Z`,
    received_at: `2026-08-04T06:${minute}:01Z`,
    temperature: 23.4,
    humidity: 41.2,
    pm1: 3.1,
    pm25,
    pm10: 12.6,
    pc0_3: null,
    pc0_5: null,
    pc1_0: null,
    pc2_5: null,
    pc5_0: null,
    pc10: null,
    latitude: 43.238 + (id % 3) * 0.004,
    longitude: 76.945 - (id % 3) * 0.004,
    is_valid: true,
    validation_note: null,
    created_at: `2026-08-04T06:${minute}:01Z`,
  };
}

function errorBody(code: string, message: string, details: unknown = null) {
  return { error: { code, message, details } };
}

async function fulfillJson(route: Route, status: number, json: unknown) {
  await route.fulfill({ status, json });
}

export async function installMockBackend(
  page: Page,
  options: MockBackendOptions = {},
): Promise<MockBackendState> {
  const state: MockBackendState = {
    seenSessionCursors: [],
    seenMeasurementCursors: [],
    sessionStartBodies: [],
    liveReadCount: 0,
    activeSession: null,
  };

  await page.route('https://tile.openstreetmap.org/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#e5eef3"/><path d="M0 64H256M0 128H256M0 192H256M64 0V256M128 0V256M192 0V256" stroke="#cbdce5" stroke-width="2"/></svg>',
    });
  });

  await page.route('**/health', async (route) => {
    if (options.healthFailure) {
      await fulfillJson(
        route,
        503,
        errorBody('service_unavailable', 'Service is unavailable.'),
      );
      return;
    }
    await fulfillJson(route, 200, {
      status: 'ok',
      service: 'airmonitor-api',
      version: '2.0.0',
    });
  });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path === '/api/v1/devices' && method === 'POST') {
      const body = request.postDataJSON() as { device_uid: string; name?: string | null };
      await fulfillJson(route, 201, {
        ...device,
        device_uid: body.device_uid,
        name: body.name ?? null,
      });
      return;
    }

    const deviceMatch = /^\/api\/v1\/devices\/(\d+)$/.exec(path);
    if (deviceMatch !== null && method === 'GET') {
      const id = Number(deviceMatch[1]);
      if (id === options.malformedDeviceId) {
        await fulfillJson(route, 500, {
          error: {
            code: 'internal_server_error',
            message: { trace: 'sensitive-stack-value' },
            details: 'sensitive-stack-value',
          },
        });
        return;
      }
      if (id !== 42) {
        await fulfillJson(route, 404, errorBody('device_not_found', 'Device was not found.'));
        return;
      }
      await fulfillJson(route, 200, device);
      return;
    }

    if (path === '/api/v1/devices/42/status' && method === 'PATCH') {
      const body = request.postDataJSON() as { is_active: boolean };
      await fulfillJson(route, 200, { ...device, is_active: body.is_active });
      return;
    }

    if (path === '/api/v1/devices/42/sessions/active' && method === 'GET') {
      if (state.activeSession === null) {
        await fulfillJson(
          route,
          404,
          errorBody('active_session_not_found', 'Active session was not found.'),
        );
      } else {
        await fulfillJson(route, 200, state.activeSession);
      }
      return;
    }

    if (path === '/api/v1/devices/42/sessions' && method === 'POST') {
      const body = request.postDataJSON() as {
        latitude: number;
        longitude: number;
      };
      state.sessionStartBodies.push(body);
      state.activeSession = {
        id: 12,
        device_id: 42,
        status: 'active',
        started_at: new Date().toISOString(),
        ended_at: null,
        latitude: body.latitude,
        longitude: body.longitude,
        sample_count: 0,
        created_at: new Date().toISOString(),
      };
      await fulfillJson(route, 201, state.activeSession);
      return;
    }

    if (
      path === '/api/v1/devices/42/sessions/active/complete' &&
      method === 'POST'
    ) {
      const completed = {
        ...state.activeSession,
        status: 'completed',
        ended_at: new Date().toISOString(),
      };
      state.activeSession = null;
      await fulfillJson(route, 200, completed);
      return;
    }

    if (
      path === '/api/v1/devices/42/sessions/active/cancel' &&
      method === 'POST'
    ) {
      const cancelled = {
        ...state.activeSession,
        status: 'cancelled',
        ended_at: new Date().toISOString(),
      };
      state.activeSession = null;
      await fulfillJson(route, 200, cancelled);
      return;
    }

    if (path === '/api/v1/devices/42/sessions' && method === 'GET') {
      const cursor = url.searchParams.get('cursor');
      if (cursor !== null) {
        state.seenSessionCursors.push(cursor);
      }
      await fulfillJson(
        route,
        200,
        cursor === null
          ? { items: [sessions[0]], next_cursor: SESSION_CURSOR }
          : { items: [sessions[1]], next_cursor: null },
      );
      return;
    }

    if (path === '/api/v1/devices/42/measurements' && method === 'GET') {
      const limit = url.searchParams.get('limit');
      if (limit === '1') {
        state.liveReadCount += 1;
        await fulfillJson(route, 200, {
          items: [measurement(101, 11, state.liveReadCount === 1 ? 7.4 : 8.8)],
          next_cursor: null,
        });
        return;
      }
      const sessionId = Number(url.searchParams.get('session_id'));
      const cursor = url.searchParams.get('cursor');
      if (cursor !== null) {
        state.seenMeasurementCursors.push(cursor);
      }
      await fulfillJson(
        route,
        200,
        cursor === null
          ? {
              items: [measurement(sessionId === 10 ? 201 : 101, sessionId, 7.4)],
              next_cursor: MEASUREMENT_CURSOR,
            }
          : {
              items: [measurement(sessionId === 10 ? 200 : 100, sessionId, 6.1)],
              next_cursor: null,
            },
      );
      return;
    }

    await fulfillJson(route, 404, errorBody('route_not_found', 'Route was not found.'));
  });

  return state;
}
