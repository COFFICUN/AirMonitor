import { describe, expect, it, vi } from 'vitest';

import {
  GeolocationFailure,
  requestCurrentPosition,
} from './geolocation';

function geolocationWithResult(
  result:
    | { readonly latitude: number; readonly longitude: number }
    | { readonly code: number; readonly message?: string },
): Geolocation {
  return {
    getCurrentPosition: vi.fn((success, failure, options) => {
      expect(options).toEqual({
        enableHighAccuracy: true,
        maximumAge: 60_000,
        timeout: 10_000,
      });
      if ('latitude' in result) {
        success({
          coords: {
            accuracy: 12,
            altitude: null,
            altitudeAccuracy: null,
            heading: null,
            latitude: result.latitude,
            longitude: result.longitude,
            speed: null,
            toJSON: () => ({}),
          },
          timestamp: 1,
          toJSON: () => ({}),
        });
      } else {
        failure?.({
          code: result.code,
          message: result.message ?? '',
          PERMISSION_DENIED: 1,
          POSITION_UNAVAILABLE: 2,
          TIMEOUT: 3,
        });
      }
    }),
    watchPosition: vi.fn(),
    clearWatch: vi.fn(),
  };
}

describe('requestCurrentPosition', () => {
  it('returns only the one-shot coordinates needed to start a session', async () => {
    const geolocation = geolocationWithResult({
      latitude: 51.128,
      longitude: 71.431,
    });

    await expect(requestCurrentPosition(geolocation)).resolves.toEqual({
      latitude: 51.128,
      longitude: 71.431,
    });
    expect(geolocation.getCurrentPosition).toHaveBeenCalledOnce();
    expect(geolocation.watchPosition).not.toHaveBeenCalled();
  });

  it.each([
    [1, 'permission_denied'],
    [2, 'unavailable'],
    [3, 'timeout'],
  ] as const)('maps browser error %s without exposing its raw message', async (code, reason) => {
    const promise = requestCurrentPosition(
      geolocationWithResult({ code, message: 'raw browser detail' }),
    );

    await expect(promise).rejects.toMatchObject({
      name: 'GeolocationFailure',
      reason,
    });
  });

  it('reports an unsupported browser distinctly', async () => {
    await expect(requestCurrentPosition(null)).rejects.toEqual(
      new GeolocationFailure('unsupported'),
    );
  });

  it('rejects non-finite or out-of-range coordinates', async () => {
    await expect(
      requestCurrentPosition(
        geolocationWithResult({ latitude: 91, longitude: Number.NaN }),
      ),
    ).rejects.toMatchObject({ reason: 'unavailable' });
  });
});
