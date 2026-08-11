import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from './errors';
import { createApiClient, joinApiUrl } from './client';

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

const emptySessionPage = {
  items: [],
  next_cursor: null,
};

const emptyMeasurementPage = {
  items: [],
  next_cursor: null,
};

afterEach(() => {
  vi.useRealTimers();
});

describe('joinApiUrl', () => {
  it('joins same-origin, path-prefix, and absolute bases predictably', () => {
    expect(joinApiUrl('', '/health')).toBe('/health');
    expect(joinApiUrl('/gateway', '/api/v1/devices')).toBe(
      '/gateway/api/v1/devices',
    );
    expect(joinApiUrl('https://api.example.test/base', '/health')).toBe(
      'https://api.example.test/base/health',
    );
  });
});

describe('AirMonitor API client', () => {
  it('parses the exact health contract', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({ status: 'ok', service: 'airmonitor-api', version: '2.0.0' }),
    );
    const client = createApiClient({ fetchImpl });

    await expect(client.getHealth()).resolves.toEqual({
      status: 'ok',
      service: 'airmonitor-api',
      version: '2.0.0',
    });
    expect(fetchImpl).toHaveBeenCalledWith(
      '/health',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('preserves only a validated safe backend error message', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'device_not_found',
            message: 'Device was not found.',
            details: null,
          },
        },
        { status: 404 },
      ),
    );
    const client = createApiClient({ fetchImpl });

    const failure = await client.getDevice(42).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({
      kind: 'http',
      status: 404,
      code: 'device_not_found',
      publicMessage: 'Device was not found.',
    });
  });

  it('does not expose malformed backend data or response text', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'internal_server_error',
            message: { stack: 'sensitive-internal-value' },
          },
        },
        { status: 500 },
      ),
    );
    const client = createApiClient({ fetchImpl });

    const failure = await client.getHealth().catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({
      kind: 'http',
      status: 500,
      code: undefined,
      publicMessage: undefined,
    });
    expect(String(failure)).not.toContain('sensitive-internal-value');
  });

  it('rejects a successful response that violates the declared contract', async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ status: 'ok', service: 7, version: '2' }));
    const client = createApiClient({ fetchImpl });

    const failure = await client.getHealth().catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ kind: 'invalid_response' });
    expect(String(failure)).not.toContain('service');
  });

  it('turns its bounded timeout into a distinct safe error', async () => {
    vi.useFakeTimers();
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation((_, init) => {
      return new Promise<Response>((_, reject) => {
        init?.signal?.addEventListener(
          'abort',
          () => reject(new DOMException('aborted', 'AbortError')),
          { once: true },
        );
      });
    });
    const client = createApiClient({ fetchImpl, timeoutMs: 1_000 });

    const pending = client.getHealth();
    const observedFailure = pending.catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(1_000);

    await expect(observedFailure).resolves.toMatchObject({ kind: 'timeout' });
  });

  it('distinguishes caller cancellation from a timeout', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation((_, init) => {
      return new Promise<Response>((_, reject) => {
        init?.signal?.addEventListener(
          'abort',
          () => reject(new DOMException('aborted', 'AbortError')),
          { once: true },
        );
      });
    });
    const client = createApiClient({ fetchImpl });
    const controller = new AbortController();

    const pending = client.getHealth({ signal: controller.signal });
    controller.abort();

    await expect(pending).rejects.toMatchObject({ kind: 'aborted' });
  });

  it('registers a device with the exact JSON body and no credentials mode', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          id: 17,
          device_uid: 'sensor-17',
          name: 'Лаборатория',
          is_active: true,
          created_at: '2026-08-04T06:00:00Z',
        },
        { status: 201 },
      ),
    );
    const client = createApiClient({ fetchImpl });

    await client.createDevice({
      device_uid: 'sensor-17',
      name: 'Лаборатория',
      is_active: true,
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      '/api/v1/devices',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          device_uid: 'sensor-17',
          name: 'Лаборатория',
          is_active: true,
        }),
      }),
    );
    expect(fetchImpl.mock.calls[0]?.[1]).not.toHaveProperty('credentials');
  });

  it('forwards a session cursor unchanged with all declared filters', async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(emptySessionPage));
    const client = createApiClient({ fetchImpl });
    const cursor = 'opaque-_cursor.VALUE';

    await client.listSessions(7, {
      status: 'completed',
      started_from: '2026-08-01T00:00:00Z',
      started_to: '2026-08-04T00:00:00Z',
      limit: 25,
      cursor,
    });

    const requestUrl = String(fetchImpl.mock.calls[0]?.[0]);
    const parameters = new URL(requestUrl, 'https://frontend.test').searchParams;
    expect(parameters.get('cursor')).toBe(cursor);
    expect(parameters.get('status')).toBe('completed');
    expect(parameters.get('started_from')).toBe('2026-08-01T00:00:00Z');
    expect(parameters.get('started_to')).toBe('2026-08-04T00:00:00Z');
    expect(parameters.get('limit')).toBe('25');
  });

  it('forwards a measurement cursor unchanged with selected-session filters', async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(emptyMeasurementPage));
    const client = createApiClient({ fetchImpl });
    const cursor = 'still-opaque_123';

    await client.listMeasurements(7, {
      session_id: 91,
      measured_from: '2026-08-02T00:00:00Z',
      measured_to: '2026-08-03T00:00:00Z',
      limit: 100,
      cursor,
    });

    const requestUrl = String(fetchImpl.mock.calls[0]?.[0]);
    const parameters = new URL(requestUrl, 'https://frontend.test').searchParams;
    expect(parameters.get('cursor')).toBe(cursor);
    expect(parameters.get('session_id')).toBe('91');
    expect(parameters.get('measured_from')).toBe('2026-08-02T00:00:00Z');
    expect(parameters.get('measured_to')).toBe('2026-08-03T00:00:00Z');
  });
});
