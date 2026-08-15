import type { AirMonitorApi } from '../api/types';

function unexpectedCall(): never {
  throw new Error('Unexpected API call in test.');
}

export function createApiStub(
  overrides: Partial<AirMonitorApi> = {},
): AirMonitorApi {
  return {
    getHealth: async () => unexpectedCall(),
    createDevice: async () => unexpectedCall(),
    getDevice: async () => unexpectedCall(),
    setDeviceStatus: async () => unexpectedCall(),
    startSession: async () => unexpectedCall(),
    listSessions: async () => unexpectedCall(),
    getActiveSession: async () => unexpectedCall(),
    completeActiveSession: async () => unexpectedCall(),
    cancelActiveSession: async () => unexpectedCall(),
    recordMeasurement: async () => unexpectedCall(),
    listMeasurements: async () => unexpectedCall(),
    ...overrides,
  };
}
