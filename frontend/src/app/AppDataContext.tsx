import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { AirMonitorApi } from '../api/types';
import { useSelectedDevice, type DeviceSelection } from '../features/device/useSelectedDevice';
import { useHealth, type HealthState } from '../features/health/useHealth';
import { useMeasurementHistory, type MeasurementHistoryState } from '../features/history/useMeasurementHistory';
import { useSessionHistory, type SessionHistoryState } from '../features/history/useSessionHistory';
import { useActiveSession, type ActiveSessionState } from '../features/session/useActiveSession';
import { useLiveTelemetry, type LiveTelemetryState } from '../features/telemetry/useLiveTelemetry';
import { usePreferences } from './PreferencesContext';

export interface AppData {
  readonly api: AirMonitorApi;
  readonly selection: DeviceSelection;
  readonly health: HealthState;
  readonly refreshHealth: () => void;
  readonly activeSession: ActiveSessionState;
  readonly liveTelemetry: LiveTelemetryState;
  readonly sessionHistory: SessionHistoryState;
  readonly measurementHistory: MeasurementHistoryState;
}

const AppDataContext = createContext<AppData | null>(null);

export function AppDataProvider({ api, children }: { readonly api: AirMonitorApi; readonly children: ReactNode }) {
  const { preferences } = usePreferences();
  const selection = useSelectedDevice(api);
  const deviceId = selection.device?.id ?? null;
  const [historyVersion, setHistoryVersion] = useState(0);
  const handleSessionChanged = useCallback(() => setHistoryVersion((version) => version + 1), []);
  const { state: health, refresh: refreshHealth } = useHealth(api);
  const activeSession = useActiveSession(api, deviceId, { onSessionChanged: handleSessionChanged });
  const liveTelemetry = useLiveTelemetry(api, deviceId, {
    intervalMs: preferences.pollingIntervalMs,
    staleAfterMs: Math.max(15_000, preferences.pollingIntervalMs * 3),
  });
  const sessionHistory = useSessionHistory(api, deviceId, historyVersion);
  const selectedSessionId = sessionHistory.selectedSession?.id ?? null;
  const measurementHistory = useMeasurementHistory(api, deviceId, selectedSessionId);
  const value = useMemo(() => ({ api, selection, health, refreshHealth, activeSession, liveTelemetry, sessionHistory, measurementHistory }), [activeSession, api, health, liveTelemetry, measurementHistory, refreshHealth, selection, sessionHistory]);
  return <AppDataContext value={value}>{children}</AppDataContext>;
}

export function useAppData(): AppData {
  const value = useContext(AppDataContext);
  if (value === null) throw new Error('useAppData must be used inside AppDataProvider.');
  return value;
}
