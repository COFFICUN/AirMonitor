import type { SessionResponse } from '../../api/types';

function coordinatesAreUsable(latitude: number | null, longitude: number | null): boolean {
  return latitude !== null && longitude !== null && Number.isFinite(latitude) && latitude >= -90 && latitude <= 90 && Number.isFinite(longitude) && longitude >= -180 && longitude <= 180;
}

export function hasUsableCoordinates(session: SessionResponse): boolean {
  return coordinatesAreUsable(session.latitude, session.longitude);
}

export function mappableSessions(
  sessions: readonly SessionResponse[],
): readonly SessionResponse[] {
  return sessions.filter(hasUsableCoordinates);
}
