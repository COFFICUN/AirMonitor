import { useCallback, useEffect, useRef, useState } from 'react';

import { isApiError } from '../../api/errors';
import { apiErrorMessage } from '../../api/presentation';
import type { AirMonitorApi, SessionResponse } from '../../api/types';
import {
  isGeolocationFailure,
  requestCurrentPosition,
  type Coordinates,
  type GeolocationFailureReason,
} from '../../geolocation/geolocation';

export type ActiveSessionStatus =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'working'
  | 'error';

export interface ActiveSessionState {
  readonly activeSession: SessionResponse | null;
  readonly status: ActiveSessionStatus;
  readonly error: string | null;
  readonly locationError: string | null;
  refresh(): void;
  start(): Promise<boolean>;
  complete(): Promise<boolean>;
  cancel(): Promise<boolean>;
}

interface ActiveSessionOptions {
  readonly requestLocation?: () => Promise<Coordinates>;
  readonly onSessionChanged?: () => void;
}

const LOCATION_MESSAGES: Readonly<Record<GeolocationFailureReason, string>> = {
  permission_denied:
    'Доступ к геопозиции запрещён. Разрешите его в настройках браузера.',
  timeout: 'Не удалось определить позицию за отведённое время. Повторите попытку.',
  unavailable: 'Браузер не смог определить текущую позицию.',
  unsupported: 'Этот браузер не поддерживает определение геопозиции.',
};

function activeSessionIsAbsent(error: unknown): boolean {
  return (
    isApiError(error) &&
    error.status === 404 &&
    error.code === 'active_session_not_found'
  );
}

export function useActiveSession(
  api: AirMonitorApi,
  deviceId: number | null,
  options: ActiveSessionOptions = {},
): ActiveSessionState {
  const locationRequest = options.requestLocation ?? requestCurrentPosition;
  const onSessionChanged = options.onSessionChanged;
  const [activeSession, setActiveSession] = useState<SessionResponse | null>(null);
  const [status, setStatus] = useState<ActiveSessionStatus>(
    deviceId === null ? 'idle' : 'loading',
  );
  const [error, setError] = useState<string | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);

  const beginRequest = useCallback(() => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setError(null);
    setLocationError(null);
    return controller;
  }, []);

  const finishRequest = useCallback((controller: AbortController) => {
    if (requestRef.current === controller) {
      requestRef.current = null;
    }
  }, []);

  useEffect(() => {
    requestRef.current?.abort();
    setActiveSession(null);
    setError(null);
    setLocationError(null);
    if (deviceId === null) {
      requestRef.current = null;
      setStatus('idle');
      return;
    }

    const controller = new AbortController();
    requestRef.current = controller;
    setStatus('loading');
    void api
      .getActiveSession(deviceId, { signal: controller.signal })
      .then((session) => {
        if (requestRef.current === controller) {
          setActiveSession(session);
          setStatus('ready');
        }
      })
      .catch((requestError: unknown) => {
        if (
          requestRef.current !== controller ||
          (isApiError(requestError) && requestError.kind === 'aborted')
        ) {
          return;
        }
        if (activeSessionIsAbsent(requestError)) {
          setActiveSession(null);
          setStatus('ready');
          return;
        }
        setStatus('error');
        setError(
          apiErrorMessage(requestError, 'Не удалось проверить активную сессию.'),
        );
      })
      .finally(() => finishRequest(controller));

    return () => {
      if (requestRef.current === controller) {
        controller.abort();
        requestRef.current = null;
      }
    };
  }, [api, deviceId, finishRequest, refreshVersion]);

  const start = useCallback(async (): Promise<boolean> => {
    if (deviceId === null) {
      return false;
    }
    const controller = beginRequest();
    setStatus('working');
    try {
      const coordinates = await locationRequest();
      if (requestRef.current !== controller || controller.signal.aborted) {
        return false;
      }
      const session = await api.startSession(deviceId, coordinates, {
        signal: controller.signal,
      });
      if (requestRef.current !== controller) {
        return false;
      }
      setActiveSession(session);
      setStatus('ready');
      onSessionChanged?.();
      return true;
    } catch (requestError) {
      if (
        requestRef.current !== controller ||
        (isApiError(requestError) && requestError.kind === 'aborted')
      ) {
        return false;
      }
      setStatus('ready');
      if (isGeolocationFailure(requestError)) {
        setLocationError(LOCATION_MESSAGES[requestError.reason]);
      } else {
        setError(apiErrorMessage(requestError, 'Не удалось начать сессию.'));
      }
      return false;
    } finally {
      finishRequest(controller);
    }
  }, [api, beginRequest, deviceId, finishRequest, locationRequest, onSessionChanged]);

  const transition = useCallback(
    async (kind: 'complete' | 'cancel'): Promise<boolean> => {
      if (deviceId === null || activeSession === null) {
        return false;
      }
      const controller = beginRequest();
      setStatus('working');
      try {
        const request =
          kind === 'complete'
            ? api.completeActiveSession
            : api.cancelActiveSession;
        await request.call(api, deviceId, {}, { signal: controller.signal });
        if (requestRef.current !== controller) {
          return false;
        }
        setActiveSession(null);
        setStatus('ready');
        onSessionChanged?.();
        return true;
      } catch (requestError) {
        if (
          requestRef.current !== controller ||
          (isApiError(requestError) && requestError.kind === 'aborted')
        ) {
          return false;
        }
        setStatus('ready');
        setError(
          apiErrorMessage(
            requestError,
            kind === 'complete'
              ? 'Не удалось завершить сессию.'
              : 'Не удалось отменить сессию.',
          ),
        );
        return false;
      } finally {
        finishRequest(controller);
      }
    },
    [activeSession, api, beginRequest, deviceId, finishRequest, onSessionChanged],
  );

  useEffect(
    () => () => {
      requestRef.current?.abort();
      requestRef.current = null;
    },
    [],
  );

  return {
    activeSession,
    status,
    error,
    locationError,
    refresh: () => setRefreshVersion((version) => version + 1),
    start,
    complete: () => transition('complete'),
    cancel: () => transition('cancel'),
  };
}

