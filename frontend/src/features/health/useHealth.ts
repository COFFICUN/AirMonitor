import { useCallback, useEffect, useRef, useState } from 'react';

import { isApiError } from '../../api/errors';
import { apiErrorMessage } from '../../api/presentation';
import type { AirMonitorApi, HealthResponse } from '../../api/types';

export type HealthStatus = 'loading' | 'available' | 'unavailable';

export interface HealthState {
  readonly status: HealthStatus;
  readonly data: HealthResponse | null;
  readonly message: string | null;
}

export function useHealth(api: AirMonitorApi) {
  const [state, setState] = useState<HealthState>({
    status: 'loading',
    data: null,
    message: null,
  });
  const requestRef = useRef<AbortController | null>(null);

  const refresh = useCallback(() => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setState({ status: 'loading', data: null, message: null });

    void api
      .getHealth({ signal: controller.signal })
      .then((data) => {
        if (requestRef.current === controller) {
          setState({ status: 'available', data, message: null });
        }
      })
      .catch((error: unknown) => {
        if (
          requestRef.current !== controller ||
          (isApiError(error) && error.kind === 'aborted')
        ) {
          return;
        }
        setState({
          status: 'unavailable',
          data: null,
          message: apiErrorMessage(error, 'Сервис временно недоступен.'),
        });
      })
      .finally(() => {
        if (requestRef.current === controller) {
          requestRef.current = null;
        }
      });
  }, [api]);

  useEffect(() => {
    refresh();
    return () => {
      requestRef.current?.abort();
      requestRef.current = null;
    };
  }, [refresh]);

  return { state, refresh } as const;
}
