import { normalizeApiBaseUrl, frontendEnvironment } from '../config/environment';
import {
  parseDeviceResponse,
  parseHealthResponse,
  parseMeasurementPage,
  parseMeasurementResponse,
  parseSafeBackendError,
  parseSessionPage,
  parseSessionResponse,
} from './contracts';
import { ApiError } from './errors';
import type {
  AirMonitorApi,
  ApiRequestOptions,
  DeviceCreateRequest,
  DeviceStatusRequest,
  MeasurementCreateRequest,
  MeasurementListQuery,
  SessionCreateRequest,
  SessionListQuery,
  SessionTransitionRequest,
} from './types';

const DEFAULT_TIMEOUT_MS = 8_000;

interface CreateApiClientOptions {
  readonly baseUrl?: string;
  readonly fetchImpl?: typeof fetch;
  readonly timeoutMs?: number;
}

interface RequestDefinition<T> {
  readonly method: 'GET' | 'POST' | 'PATCH';
  readonly path: string;
  readonly body?: unknown;
  readonly parse: (value: unknown) => T;
  readonly signal?: AbortSignal;
}

function assertDeviceId(deviceId: number): void {
  if (
    !Number.isInteger(deviceId) ||
    deviceId < 1 ||
    deviceId > 2_147_483_647
  ) {
    throw new RangeError('Device ID must be a positive PostgreSQL integer.');
  }
}

function assertLimit(limit: number): void {
  if (!Number.isInteger(limit) || limit < 1 || limit > 500) {
    throw new RangeError('Telemetry limit must be between 1 and 500.');
  }
}

function assertTimeout(timeoutMs: number): void {
  if (!Number.isFinite(timeoutMs) || timeoutMs < 1 || timeoutMs > 60_000) {
    throw new RangeError('API timeout must be between 1 and 60000 milliseconds.');
  }
}

export function joinApiUrl(baseUrl: string, path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return baseUrl === '' ? normalizedPath : `${baseUrl}${normalizedPath}`;
}

function withQuery(path: string, query: object): string {
  const parameters = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') {
      parameters.append(key, String(value));
    }
  }
  const serialized = parameters.toString();
  return serialized === '' ? path : `${path}?${serialized}`;
}

function isAbortError(value: unknown): boolean {
  return value instanceof DOMException && value.name === 'AbortError';
}

export function createApiClient(
  options: CreateApiClientOptions = {},
): AirMonitorApi {
  const baseUrl = normalizeApiBaseUrl(
    options.baseUrl ?? frontendEnvironment.apiBaseUrl,
  );
  const fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  assertTimeout(timeoutMs);

  async function request<T>(definition: RequestDefinition<T>): Promise<T> {
    if (definition.signal?.aborted === true) {
      throw new ApiError({ kind: 'aborted' });
    }

    const controller = new AbortController();
    let didTimeout = false;
    let didCallerAbort = false;
    const handleCallerAbort = () => {
      didCallerAbort = true;
      controller.abort();
    };
    definition.signal?.addEventListener('abort', handleCallerAbort, {
      once: true,
    });
    const timeout = globalThis.setTimeout(() => {
      didTimeout = true;
      controller.abort();
    }, timeoutMs);

    const headers: Record<string, string> = {
      Accept: 'application/json',
    };
    if (definition.body !== undefined) {
      headers['Content-Type'] = 'application/json';
    }

    try {
      const response = await fetchImpl(joinApiUrl(baseUrl, definition.path), {
        method: definition.method,
        headers,
        body:
          definition.body === undefined
            ? undefined
            : JSON.stringify(definition.body),
        signal: controller.signal,
      });

      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        if (!response.ok) {
          throw new ApiError({ kind: 'http', status: response.status });
        }
        throw new ApiError({ kind: 'invalid_response' });
      }

      if (!response.ok) {
        const safeError = parseSafeBackendError(payload);
        throw new ApiError({
          kind: 'http',
          status: response.status,
          code: safeError?.code,
          publicMessage: safeError?.message,
        });
      }

      try {
        return definition.parse(payload);
      } catch {
        throw new ApiError({ kind: 'invalid_response' });
      }
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      if (didTimeout) {
        throw new ApiError({ kind: 'timeout' });
      }
      if (didCallerAbort || controller.signal.aborted || isAbortError(error)) {
        throw new ApiError({ kind: 'aborted' });
      }
      throw new ApiError({ kind: 'network' });
    } finally {
      globalThis.clearTimeout(timeout);
      definition.signal?.removeEventListener('abort', handleCallerAbort);
    }
  }

  function devicePath(deviceId: number, suffix = ''): string {
    assertDeviceId(deviceId);
    return `/api/v1/devices/${deviceId}${suffix}`;
  }

  return {
    getHealth(apiOptions: ApiRequestOptions = {}) {
      return request({
        method: 'GET',
        path: '/health',
        parse: parseHealthResponse,
        signal: apiOptions.signal,
      });
    },

    createDevice(body: DeviceCreateRequest, apiOptions: ApiRequestOptions = {}) {
      return request({
        method: 'POST',
        path: '/api/v1/devices',
        body,
        parse: parseDeviceResponse,
        signal: apiOptions.signal,
      });
    },

    getDevice(deviceId: number, apiOptions: ApiRequestOptions = {}) {
      return request({
        method: 'GET',
        path: devicePath(deviceId),
        parse: parseDeviceResponse,
        signal: apiOptions.signal,
      });
    },

    setDeviceStatus(
      deviceId: number,
      body: DeviceStatusRequest,
      apiOptions: ApiRequestOptions = {},
    ) {
      return request({
        method: 'PATCH',
        path: devicePath(deviceId, '/status'),
        body,
        parse: parseDeviceResponse,
        signal: apiOptions.signal,
      });
    },

    startSession(
      deviceId: number,
      body: SessionCreateRequest,
      apiOptions: ApiRequestOptions = {},
    ) {
      return request({
        method: 'POST',
        path: devicePath(deviceId, '/sessions'),
        body,
        parse: parseSessionResponse,
        signal: apiOptions.signal,
      });
    },

    listSessions(
      deviceId: number,
      query: SessionListQuery = {},
      apiOptions: ApiRequestOptions = {},
    ) {
      if (query.limit !== undefined) {
        assertLimit(query.limit);
      }
      return request({
        method: 'GET',
        path: withQuery(devicePath(deviceId, '/sessions'), query),
        parse: parseSessionPage,
        signal: apiOptions.signal,
      });
    },

    getActiveSession(deviceId: number, apiOptions: ApiRequestOptions = {}) {
      return request({
        method: 'GET',
        path: devicePath(deviceId, '/sessions/active'),
        parse: parseSessionResponse,
        signal: apiOptions.signal,
      });
    },

    completeActiveSession(
      deviceId: number,
      body: SessionTransitionRequest = {},
      apiOptions: ApiRequestOptions = {},
    ) {
      return request({
        method: 'POST',
        path: devicePath(deviceId, '/sessions/active/complete'),
        body,
        parse: parseSessionResponse,
        signal: apiOptions.signal,
      });
    },

    cancelActiveSession(
      deviceId: number,
      body: SessionTransitionRequest = {},
      apiOptions: ApiRequestOptions = {},
    ) {
      return request({
        method: 'POST',
        path: devicePath(deviceId, '/sessions/active/cancel'),
        body,
        parse: parseSessionResponse,
        signal: apiOptions.signal,
      });
    },

    recordMeasurement(
      deviceId: number,
      body: MeasurementCreateRequest,
      apiOptions: ApiRequestOptions = {},
    ) {
      return request({
        method: 'POST',
        path: devicePath(deviceId, '/measurements'),
        body,
        parse: parseMeasurementResponse,
        signal: apiOptions.signal,
      });
    },

    listMeasurements(
      deviceId: number,
      query: MeasurementListQuery = {},
      apiOptions: ApiRequestOptions = {},
    ) {
      if (query.limit !== undefined) {
        assertLimit(query.limit);
      }
      if (query.session_id !== undefined) {
        assertDeviceId(query.session_id);
      }
      return request({
        method: 'GET',
        path: withQuery(devicePath(deviceId, '/measurements'), query),
        parse: parseMeasurementPage,
        signal: apiOptions.signal,
      });
    },
  };
}

export const apiClient = createApiClient();
