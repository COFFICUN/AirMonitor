export const DEVICE_STORAGE_KEY = 'airmonitor.frontend.v2.device-id';

const STORAGE_VERSION = 1;
const POSTGRES_INTEGER_MAX = 2_147_483_647;

function isValidDeviceId(value: unknown): value is number {
  return (
    typeof value === 'number' &&
    Number.isInteger(value) &&
    value >= 1 &&
    value <= POSTGRES_INTEGER_MAX
  );
}

function resolveStorage(storage: Storage | undefined): Storage | null {
  if (storage !== undefined) {
    return storage;
  }
  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
}

function removeInvalidRecord(storage: Storage): void {
  try {
    storage.removeItem(DEVICE_STORAGE_KEY);
  } catch {
    // Storage is optional; a blocked cleanup must not prevent app startup.
  }
}

export function readSelectedDeviceId(storage?: Storage): number | null {
  const target = resolveStorage(storage);
  if (target === null) {
    return null;
  }

  let serialized: string | null;
  try {
    serialized = target.getItem(DEVICE_STORAGE_KEY);
  } catch {
    return null;
  }
  if (serialized === null) {
    return null;
  }

  try {
    const value: unknown = JSON.parse(serialized);
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
      throw new Error('Invalid storage record.');
    }
    const record = value as Record<string, unknown>;
    const keys = Object.keys(record).sort();
    if (
      keys.length !== 2 ||
      keys[0] !== 'deviceId' ||
      keys[1] !== 'version' ||
      record.version !== STORAGE_VERSION ||
      !isValidDeviceId(record.deviceId)
    ) {
      throw new Error('Invalid storage record.');
    }
    return record.deviceId;
  } catch {
    removeInvalidRecord(target);
    return null;
  }
}

export function writeSelectedDeviceId(
  deviceId: number,
  storage?: Storage,
): boolean {
  if (!isValidDeviceId(deviceId)) {
    throw new RangeError('Selected device ID must be a positive PostgreSQL integer.');
  }
  const target = resolveStorage(storage);
  if (target === null) {
    return false;
  }
  try {
    target.setItem(
      DEVICE_STORAGE_KEY,
      JSON.stringify({ version: STORAGE_VERSION, deviceId }),
    );
    return true;
  } catch {
    return false;
  }
}

export function clearSelectedDeviceId(storage?: Storage): boolean {
  const target = resolveStorage(storage);
  if (target === null) {
    return false;
  }
  try {
    target.removeItem(DEVICE_STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
}
