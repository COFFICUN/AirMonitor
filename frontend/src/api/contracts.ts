import type {
  CursorPage,
  DeviceResponse,
  HealthResponse,
  MeasurementResponse,
  SessionResponse,
  SessionStatus,
} from './types';

interface SafeBackendError {
  readonly code: string;
  readonly message: string;
}

const ERROR_CODE_PATTERN = /^[a-z][a-z0-9_]{0,63}$/;
const CONTROL_CHARACTER_PATTERN = /[\u0000-\u001f\u007f]/;
const AWARE_DATETIME_PATTERN = /(?:Z|[+-]\d{2}:\d{2})$/i;
const SESSION_STATUSES = new Set<SessionStatus>([
  'active',
  'completed',
  'cancelled',
]);

function invalidResponse(): never {
  throw new Error('Invalid API response.');
}

function asRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return invalidResponse();
  }
  return value as Record<string, unknown>;
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : invalidResponse();
}

function asNullableString(value: unknown): string | null {
  return value === null ? null : asString(value);
}

function asBoolean(value: unknown): boolean {
  return typeof value === 'boolean' ? value : invalidResponse();
}

function asFiniteNumber(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value)
    ? value
    : invalidResponse();
}

function asNullableFiniteNumber(value: unknown): number | null {
  return value === null ? null : asFiniteNumber(value);
}

function asInteger(value: unknown, minimum = 1): number {
  const number = asFiniteNumber(value);
  return Number.isInteger(number) && number >= minimum && number <= 2_147_483_647
    ? number
    : invalidResponse();
}

function asNullableInteger(value: unknown, minimum = 0): number | null {
  return value === null ? null : asInteger(value, minimum);
}

function asAwareDateTime(value: unknown): string {
  const dateTime = asString(value);
  if (
    !AWARE_DATETIME_PATTERN.test(dateTime) ||
    !Number.isFinite(Date.parse(dateTime))
  ) {
    return invalidResponse();
  }
  return dateTime;
}

function asNullableAwareDateTime(value: unknown): string | null {
  return value === null ? null : asAwareDateTime(value);
}

function asBoundedNumber(
  value: unknown,
  minimum: number,
  maximum: number,
): number {
  const number = asFiniteNumber(value);
  return number >= minimum && number <= maximum ? number : invalidResponse();
}

export function parseSafeBackendError(value: unknown): SafeBackendError | null {
  try {
    const envelope = asRecord(value);
    const detail = asRecord(envelope.error);
    const code = asString(detail.code);
    const message = asString(detail.message).trim();
    if (
      !ERROR_CODE_PATTERN.test(code) ||
      message === '' ||
      message.length > 512 ||
      CONTROL_CHARACTER_PATTERN.test(message) ||
      (detail.details !== undefined && detail.details !== null)
    ) {
      return null;
    }
    return { code, message };
  } catch {
    return null;
  }
}

export function parseHealthResponse(value: unknown): HealthResponse {
  const response = asRecord(value);
  if (response.status !== 'ok') {
    return invalidResponse();
  }
  return {
    status: 'ok',
    service: asString(response.service),
    version: asString(response.version),
  };
}

export function parseDeviceResponse(value: unknown): DeviceResponse {
  const response = asRecord(value);
  return {
    id: asInteger(response.id),
    device_uid: asString(response.device_uid),
    name: asNullableString(response.name),
    is_active: asBoolean(response.is_active),
    created_at: asAwareDateTime(response.created_at),
  };
}

export function parseSessionResponse(value: unknown): SessionResponse {
  const response = asRecord(value);
  const status = asString(response.status);
  if (!SESSION_STATUSES.has(status as SessionStatus)) {
    return invalidResponse();
  }
  return {
    id: asInteger(response.id),
    device_id: asInteger(response.device_id),
    status: status as SessionStatus,
    started_at: asAwareDateTime(response.started_at),
    ended_at: asNullableAwareDateTime(response.ended_at),
    latitude: asBoundedNumber(response.latitude, -90, 90),
    longitude: asBoundedNumber(response.longitude, -180, 180),
    sample_count: asInteger(response.sample_count, 0),
    created_at: asAwareDateTime(response.created_at),
  };
}

export function parseMeasurementResponse(value: unknown): MeasurementResponse {
  const response = asRecord(value);
  const latitude = asNullableFiniteNumber(response.latitude);
  const longitude = asNullableFiniteNumber(response.longitude);
  if ((latitude === null) !== (longitude === null)) {
    return invalidResponse();
  }
  if (
    (latitude !== null && (latitude < -90 || latitude > 90)) ||
    (longitude !== null && (longitude < -180 || longitude > 180))
  ) {
    return invalidResponse();
  }

  return {
    id: asInteger(response.id),
    device_id: asInteger(response.device_id),
    session_id: asInteger(response.session_id),
    source_message_id: asNullableString(response.source_message_id),
    measured_at: asAwareDateTime(response.measured_at),
    received_at: asAwareDateTime(response.received_at),
    temperature: asNullableFiniteNumber(response.temperature),
    humidity: asNullableFiniteNumber(response.humidity),
    pm1: asNullableFiniteNumber(response.pm1),
    pm25: asNullableFiniteNumber(response.pm25),
    pm10: asNullableFiniteNumber(response.pm10),
    pc0_3: asNullableInteger(response.pc0_3),
    pc0_5: asNullableInteger(response.pc0_5),
    pc1_0: asNullableInteger(response.pc1_0),
    pc2_5: asNullableInteger(response.pc2_5),
    pc5_0: asNullableInteger(response.pc5_0),
    pc10: asNullableInteger(response.pc10),
    latitude,
    longitude,
    is_valid: asBoolean(response.is_valid),
    validation_note: asNullableString(response.validation_note),
    created_at: asAwareDateTime(response.created_at),
  };
}

function parseCursorPage<T>(
  value: unknown,
  parseItem: (item: unknown) => T,
): CursorPage<T> {
  const response = asRecord(value);
  if (!Array.isArray(response.items)) {
    return invalidResponse();
  }
  return {
    items: response.items.map(parseItem),
    next_cursor: asNullableString(response.next_cursor),
  };
}

export function parseSessionPage(value: unknown): CursorPage<SessionResponse> {
  return parseCursorPage(value, parseSessionResponse);
}

export function parseMeasurementPage(
  value: unknown,
): CursorPage<MeasurementResponse> {
  return parseCursorPage(value, parseMeasurementResponse);
}
