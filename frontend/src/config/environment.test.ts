import { describe, expect, it } from 'vitest';

import { normalizeApiBaseUrl, readFrontendEnvironment } from './environment';

describe('normalizeApiBaseUrl', () => {
  it('uses the current browser origin for an omitted value', () => {
    expect(normalizeApiBaseUrl(undefined)).toBe('');
  });

  it('removes trailing slashes without changing a configured path prefix', () => {
    expect(normalizeApiBaseUrl('/gateway///')).toBe('/gateway');
  });

  it('accepts an absolute HTTP origin and removes its trailing slash', () => {
    expect(normalizeApiBaseUrl('https://api.example.test/')).toBe(
      'https://api.example.test',
    );
  });

  it('rejects credentials and non-HTTP schemes', () => {
    expect(() => normalizeApiBaseUrl('https://user:secret@example.test')).toThrow(
      'VITE_API_BASE_URL',
    );
    expect(() => normalizeApiBaseUrl('javascript:alert(1)')).toThrow(
      'VITE_API_BASE_URL',
    );
  });
});

describe('readFrontendEnvironment', () => {
  it('returns one immutable canonical API base URL', () => {
    const environment = readFrontendEnvironment({
      VITE_API_BASE_URL: '/airmonitor/',
    });

    expect(environment).toEqual({ apiBaseUrl: '/airmonitor' });
    expect(Object.isFrozen(environment)).toBe(true);
  });
});
