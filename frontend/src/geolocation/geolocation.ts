export type GeolocationFailureReason =
  | 'permission_denied'
  | 'unavailable'
  | 'timeout'
  | 'unsupported';

export interface Coordinates {
  readonly latitude: number;
  readonly longitude: number;
}

export class GeolocationFailure extends Error {
  readonly reason: GeolocationFailureReason;

  constructor(reason: GeolocationFailureReason) {
    super(`Geolocation failed: ${reason}`);
    this.name = 'GeolocationFailure';
    this.reason = reason;
  }
}

function browserGeolocation(): Geolocation | null {
  return typeof navigator === 'undefined'
    ? null
    : (navigator.geolocation ?? null);
}

function failureReason(code: number): GeolocationFailureReason {
  switch (code) {
    case 1:
      return 'permission_denied';
    case 3:
      return 'timeout';
    default:
      return 'unavailable';
  }
}

function coordinatesAreValid(coordinates: Coordinates): boolean {
  return (
    Number.isFinite(coordinates.latitude) &&
    coordinates.latitude >= -90 &&
    coordinates.latitude <= 90 &&
    Number.isFinite(coordinates.longitude) &&
    coordinates.longitude >= -180 &&
    coordinates.longitude <= 180
  );
}

export function requestCurrentPosition(
  geolocation: Geolocation | null = browserGeolocation(),
): Promise<Coordinates> {
  if (geolocation === null) {
    return Promise.reject(new GeolocationFailure('unsupported'));
  }

  return new Promise((resolve, reject) => {
    geolocation.getCurrentPosition(
      (position) => {
        const coordinates = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        };
        if (!coordinatesAreValid(coordinates)) {
          reject(new GeolocationFailure('unavailable'));
          return;
        }
        resolve(coordinates);
      },
      (error) => reject(new GeolocationFailure(failureReason(error.code))),
      {
        enableHighAccuracy: true,
        maximumAge: 60_000,
        timeout: 10_000,
      },
    );
  });
}

export function isGeolocationFailure(
  value: unknown,
): value is GeolocationFailure {
  return value instanceof GeolocationFailure;
}
