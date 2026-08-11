import { beforeEach, describe, expect, it } from 'vitest';

import {
  DEVICE_STORAGE_KEY,
  clearSelectedDeviceId,
  readSelectedDeviceId,
  writeSelectedDeviceId,
} from './deviceStorage';

beforeEach(() => {
  localStorage.clear();
});

describe('device storage', () => {
  it('restores one valid versioned positive device ID', () => {
    localStorage.setItem(
      DEVICE_STORAGE_KEY,
      JSON.stringify({ version: 1, deviceId: 47 }),
    );

    expect(readSelectedDeviceId()).toBe(47);
  });

  it.each([
    'not-json',
    JSON.stringify({ version: 2, deviceId: 47 }),
    JSON.stringify({ version: 1, deviceId: 0 }),
    JSON.stringify({ version: 1, deviceId: 2_147_483_648 }),
    JSON.stringify({ version: 1, deviceId: '47' }),
    JSON.stringify({ version: 1, deviceId: 47, cursor: 'must-not-be-stored' }),
  ])('rejects and removes a malformed restored record: %s', (record) => {
    localStorage.setItem(DEVICE_STORAGE_KEY, record);

    expect(readSelectedDeviceId()).toBeNull();
    expect(localStorage.getItem(DEVICE_STORAGE_KEY)).toBeNull();
  });

  it('writes only the version and validated device ID', () => {
    expect(writeSelectedDeviceId(91)).toBe(true);
    expect(localStorage.getItem(DEVICE_STORAGE_KEY)).toBe(
      JSON.stringify({ version: 1, deviceId: 91 }),
    );
  });

  it('rejects an invalid ID before writing', () => {
    expect(() => writeSelectedDeviceId(Number.NaN)).toThrow('device ID');
    expect(localStorage.getItem(DEVICE_STORAGE_KEY)).toBeNull();
  });

  it('clears the selected identifier without touching other storage', () => {
    localStorage.setItem(DEVICE_STORAGE_KEY, '{}');
    localStorage.setItem('unrelated', 'keep');

    expect(clearSelectedDeviceId()).toBe(true);
    expect(localStorage.getItem(DEVICE_STORAGE_KEY)).toBeNull();
    expect(localStorage.getItem('unrelated')).toBe('keep');
  });

  it('degrades safely when storage access is unavailable', () => {
    const unavailableStorage: Storage = {
      get length(): number {
        throw new DOMException('blocked', 'SecurityError');
      },
      clear() {
        throw new DOMException('blocked', 'SecurityError');
      },
      getItem() {
        throw new DOMException('blocked', 'SecurityError');
      },
      key() {
        throw new DOMException('blocked', 'SecurityError');
      },
      removeItem() {
        throw new DOMException('blocked', 'SecurityError');
      },
      setItem() {
        throw new DOMException('blocked', 'SecurityError');
      },
    };

    expect(readSelectedDeviceId(unavailableStorage)).toBeNull();
    expect(writeSelectedDeviceId(7, unavailableStorage)).toBe(false);
    expect(clearSelectedDeviceId(unavailableStorage)).toBe(false);
  });
});
