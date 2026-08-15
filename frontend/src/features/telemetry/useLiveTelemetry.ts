import { useEffect, useRef, useState } from 'react';

import { isApiError } from '../../api/errors';
import { apiErrorMessage } from '../../api/presentation';
import type { AirMonitorApi, MeasurementResponse } from '../../api/types';

export type LiveTelemetryStatus =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'empty'
  | 'error';

export interface LiveTelemetryState {
  readonly latest: MeasurementResponse | null;
  readonly status: LiveTelemetryStatus;
  readonly error: string | null;
  readonly lastSuccessfulAt: Date | null;
  readonly isStale: boolean;
}

interface LiveTelemetryOptions {
  readonly intervalMs?: number;
  readonly staleAfterMs?: number;
}

const DEFAULT_INTERVAL_MS = 5_000;
const DEFAULT_STALE_AFTER_MS = 15_000;

function assertTiming(value: number, name: string): void {
  if (!Number.isFinite(value) || value < 1 || value > 3_600_000) {
    throw new RangeError(`${name} must be between 1 and 3600000 milliseconds.`);
  }
}

function pageIsVisible(): boolean {
  return typeof document === 'undefined' || document.visibilityState !== 'hidden';
}

export function useLiveTelemetry(
  api: AirMonitorApi,
  deviceId: number | null,
  options: LiveTelemetryOptions = {},
): LiveTelemetryState {
  const intervalMs = options.intervalMs ?? DEFAULT_INTERVAL_MS;
  const staleAfterMs = options.staleAfterMs ?? DEFAULT_STALE_AFTER_MS;
  assertTiming(intervalMs, 'Polling interval');
  assertTiming(staleAfterMs, 'Stale threshold');

  const [latest, setLatest] = useState<MeasurementResponse | null>(null);
  const [status, setStatus] = useState<LiveTelemetryStatus>(
    deviceId === null ? 'idle' : 'loading',
  );
  const [error, setError] = useState<string | null>(null);
  const [lastSuccessfulAt, setLastSuccessfulAt] = useState<Date | null>(null);
  const [isStale, setIsStale] = useState(false);
  const latestRef = useRef<MeasurementResponse | null>(null);

  useEffect(() => {
    let stopped = false;
    let running = false;
    let runWhenSettled = false;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;
    let staleTimer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;

    latestRef.current = null;
    setLatest(null);
    setError(null);
    setLastSuccessfulAt(null);
    setIsStale(false);

    const clearPollTimer = () => {
      if (pollTimer !== null) {
        clearTimeout(pollTimer);
        pollTimer = null;
      }
    };
    const clearStaleTimer = () => {
      if (staleTimer !== null) {
        clearTimeout(staleTimer);
        staleTimer = null;
      }
    };

    if (deviceId === null) {
      setStatus('idle');
      return;
    }
    setStatus('loading');

    const schedule = () => {
      clearPollTimer();
      if (!stopped && pageIsVisible()) {
        pollTimer = setTimeout(() => void run(), intervalMs);
      }
    };

    const run = async () => {
      if (stopped || !pageIsVisible()) {
        return;
      }
      if (running) {
        runWhenSettled = true;
        return;
      }
      running = true;
      clearPollTimer();
      controller = new AbortController();
      try {
        const page = await api.listMeasurements(
          deviceId,
          { limit: 1 },
          { signal: controller.signal },
        );
        if (stopped || controller.signal.aborted) {
          return;
        }
        const newest = page.items[0] ?? null;
        latestRef.current = newest;
        setLatest(newest);
        setError(null);
        setStatus(newest === null ? 'empty' : 'ready');
        setLastSuccessfulAt(new Date(Date.now()));
        setIsStale(false);
        clearStaleTimer();
        if (newest !== null) {
          staleTimer = setTimeout(() => {
            if (!stopped) {
              setIsStale(true);
            }
          }, staleAfterMs);
        }
      } catch (requestError) {
        if (
          stopped ||
          (isApiError(requestError) && requestError.kind === 'aborted')
        ) {
          return;
        }
        setError(apiErrorMessage(requestError));
        setStatus(latestRef.current === null ? 'error' : 'ready');
      } finally {
        running = false;
        controller = null;
        if (stopped) {
          return;
        }
        if (runWhenSettled && pageIsVisible()) {
          runWhenSettled = false;
          void run();
        } else {
          schedule();
        }
      }
    };

    const handleVisibilityChange = () => {
      if (!pageIsVisible()) {
        clearPollTimer();
        controller?.abort();
        return;
      }
      if (running) {
        runWhenSettled = true;
      } else {
        void run();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    void run();

    return () => {
      stopped = true;
      clearPollTimer();
      clearStaleTimer();
      controller?.abort();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [api, deviceId, intervalMs, staleAfterMs]);

  return { latest, status, error, lastSuccessfulAt, isStale };
}
