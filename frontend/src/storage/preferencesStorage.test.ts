import { describe, expect, it, vi } from 'vitest';

import {
  DEFAULT_PREFERENCES,
  PREFERENCES_STORAGE_KEY,
  readPreferences,
  writePreferences,
} from './preferencesStorage';

describe('preferences storage', () => {
  it('returns strict defaults when no record exists', () => {
    const storage = { getItem: vi.fn(() => null) } as unknown as Storage;
    expect(readPreferences(storage)).toEqual(DEFAULT_PREFERENCES);
    expect(DEFAULT_PREFERENCES.theme).toBe('system');
  });

  it('restores a valid versioned record', () => {
    const storage = {
      getItem: vi.fn(() => JSON.stringify({
        version: 2,
        preferences: {
          density: 'compact',
          theme: 'dark',
          motion: 'reduced',
          timeFormat: '12h',
          pollingIntervalMs: 10_000,
          mapTilesEnabled: false,
        },
      })),
    } as unknown as Storage;

    expect(readPreferences(storage)).toEqual({
      density: 'compact',
      theme: 'dark',
      motion: 'reduced',
      timeFormat: '12h',
      pollingIntervalMs: 10_000,
      mapTilesEnabled: false,
    });
  });

  it('migrates a valid version 1 record to the system theme', () => {
    const storage = {
      getItem: vi.fn(() => JSON.stringify({
        version: 1,
        preferences: {
          density: 'compact',
          motion: 'reduced',
          timeFormat: '24h',
          pollingIntervalMs: 5_000,
          mapTilesEnabled: true,
        },
      })),
    } as unknown as Storage;

    expect(readPreferences(storage)).toEqual({
      ...DEFAULT_PREFERENCES,
      density: 'compact',
      motion: 'reduced',
    });
  });

  it('removes corrupt, unknown-key, and invalid records', () => {
    const removeItem = vi.fn();
    const storage = {
      getItem: vi.fn(() => JSON.stringify({
        version: 1,
        preferences: {
          ...DEFAULT_PREFERENCES,
          pollingIntervalMs: 1,
          email: 'must-not-be-stored@example.test',
        },
      })),
      removeItem,
    } as unknown as Storage;

    expect(readPreferences(storage)).toEqual(DEFAULT_PREFERENCES);
    expect(removeItem).toHaveBeenCalledWith(PREFERENCES_STORAGE_KEY);
  });

  it('writes only the supported preferences envelope', () => {
    const setItem = vi.fn();
    const storage = { setItem } as unknown as Storage;

    expect(writePreferences(DEFAULT_PREFERENCES, storage)).toBe(true);
    expect(JSON.parse(setItem.mock.calls[0]![1])).toEqual({
      version: 2,
      preferences: DEFAULT_PREFERENCES,
    });
  });
});
