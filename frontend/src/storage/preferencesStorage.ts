export const PREFERENCES_STORAGE_KEY = 'airmonitor.frontend.v2.preferences';

export type DisplayDensity = 'comfortable' | 'compact';
export type ThemePreference = 'system' | 'light' | 'dark';
export type MotionPreference = 'system' | 'full' | 'reduced';
export type TimeFormatPreference = '24h' | '12h';
export type PollingInterval = 5_000 | 10_000 | 30_000;

export interface FrontendPreferences {
  readonly density: DisplayDensity;
  readonly theme: ThemePreference;
  readonly motion: MotionPreference;
  readonly timeFormat: TimeFormatPreference;
  readonly pollingIntervalMs: PollingInterval;
  readonly mapTilesEnabled: boolean;
}

export const DEFAULT_PREFERENCES: FrontendPreferences = Object.freeze({
  density: 'comfortable',
  theme: 'system',
  motion: 'system',
  timeFormat: '24h',
  pollingIntervalMs: 5_000,
  mapTilesEnabled: true,
});

const RECORD_KEYS = ['preferences', 'version'] as const;
const PREFERENCE_KEYS = [
  'density',
  'mapTilesEnabled',
  'motion',
  'pollingIntervalMs',
  'theme',
  'timeFormat',
] as const;
const LEGACY_PREFERENCE_KEYS = PREFERENCE_KEYS.filter((key) => key !== 'theme');

function hasExactKeys(value: object, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isPreferences(value: unknown): value is FrontendPreferences {
  if (!isRecord(value) || !hasExactKeys(value, PREFERENCE_KEYS)) {
    return false;
  }
  return (
    (value.density === 'comfortable' || value.density === 'compact') &&
    (value.theme === 'system' || value.theme === 'light' || value.theme === 'dark') &&
    (value.motion === 'system' || value.motion === 'full' || value.motion === 'reduced') &&
    (value.timeFormat === '24h' || value.timeFormat === '12h') &&
    (value.pollingIntervalMs === 5_000 || value.pollingIntervalMs === 10_000 || value.pollingIntervalMs === 30_000) &&
    typeof value.mapTilesEnabled === 'boolean'
  );
}

function isLegacyPreferences(value: unknown): value is Omit<FrontendPreferences, 'theme'> {
  if (!isRecord(value) || !hasExactKeys(value, LEGACY_PREFERENCE_KEYS)) {
    return false;
  }
  return (
    (value.density === 'comfortable' || value.density === 'compact') &&
    (value.motion === 'system' || value.motion === 'full' || value.motion === 'reduced') &&
    (value.timeFormat === '24h' || value.timeFormat === '12h') &&
    (value.pollingIntervalMs === 5_000 || value.pollingIntervalMs === 10_000 || value.pollingIntervalMs === 30_000) &&
    typeof value.mapTilesEnabled === 'boolean'
  );
}

function browserStorage(storage: Storage | undefined): Storage | null {
  if (storage !== undefined) return storage;
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function readPreferences(storage?: Storage): FrontendPreferences {
  const target = browserStorage(storage);
  if (target === null) return DEFAULT_PREFERENCES;
  try {
    const raw = target.getItem(PREFERENCES_STORAGE_KEY);
    if (raw === null) return DEFAULT_PREFERENCES;
    const parsed: unknown = JSON.parse(raw);
    if (!isRecord(parsed) || !hasExactKeys(parsed, RECORD_KEYS)) {
      target.removeItem(PREFERENCES_STORAGE_KEY);
      return DEFAULT_PREFERENCES;
    }
    if (parsed.version === 2 && isPreferences(parsed.preferences)) {
      return parsed.preferences;
    }
    if (parsed.version === 1 && isLegacyPreferences(parsed.preferences)) {
      return { ...parsed.preferences, theme: 'system' };
    }
    target.removeItem(PREFERENCES_STORAGE_KEY);
    return DEFAULT_PREFERENCES;
  } catch {
    try { target.removeItem(PREFERENCES_STORAGE_KEY); } catch { /* Current-tab use remains available. */ }
    return DEFAULT_PREFERENCES;
  }
}

export function writePreferences(preferences: FrontendPreferences, storage?: Storage): boolean {
  const target = browserStorage(storage);
  if (target === null || !isPreferences(preferences)) return false;
  try {
    target.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify({ version: 2, preferences }));
    return true;
  } catch {
    return false;
  }
}

export function clearPreferences(storage?: Storage): boolean {
  const target = browserStorage(storage);
  if (target === null) return false;
  try {
    target.removeItem(PREFERENCES_STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
}
