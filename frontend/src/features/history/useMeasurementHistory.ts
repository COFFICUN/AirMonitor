import { useCallback, useEffect, useRef, useState } from 'react';

import { isApiError } from '../../api/errors';
import { apiErrorMessage } from '../../api/presentation';
import type {
  AirMonitorApi,
  MeasurementListQuery,
  MeasurementResponse,
} from '../../api/types';
import { appendUniqueById } from './pagination';

export interface MeasurementFilters {
  readonly measuredFrom?: string;
  readonly measuredTo?: string;
}

export type MeasurementHistoryStatus = 'idle' | 'loading' | 'ready' | 'error';

export interface MeasurementHistoryState {
  readonly items: readonly MeasurementResponse[];
  readonly filters: MeasurementFilters;
  readonly status: MeasurementHistoryStatus;
  readonly error: string | null;
  readonly loadingMore: boolean;
  readonly nextCursor: string | null;
  readonly capped: boolean;
  setFilters(filters: MeasurementFilters): void;
  loadMore(): Promise<boolean>;
  retry(): void;
}

const PAGE_LIMIT = 100;
const MAX_MEASUREMENTS = 500;

function makeQuery(
  sessionId: number,
  filters: MeasurementFilters,
  cursor?: string,
): MeasurementListQuery {
  return {
    session_id: sessionId,
    ...(filters.measuredFrom === undefined
      ? {}
      : { measured_from: filters.measuredFrom }),
    ...(filters.measuredTo === undefined
      ? {}
      : { measured_to: filters.measuredTo }),
    limit: PAGE_LIMIT,
    ...(cursor === undefined ? {} : { cursor }),
  };
}

export function useMeasurementHistory(
  api: AirMonitorApi,
  deviceId: number | null,
  sessionId: number | null,
): MeasurementHistoryState {
  const [items, setItems] = useState<readonly MeasurementResponse[]>([]);
  const [filters, setFilterState] = useState<MeasurementFilters>({});
  const [status, setStatus] = useState<MeasurementHistoryStatus>(
    deviceId === null || sessionId === null ? 'idle' : 'loading',
  );
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [capped, setCapped] = useState(false);
  const [retryVersion, setRetryVersion] = useState(0);
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => {
    requestRef.current?.abort();
    setItems([]);
    setNextCursor(null);
    setCapped(false);
    setLoadingMore(false);
    setError(null);
    if (deviceId === null || sessionId === null) {
      requestRef.current = null;
      setStatus('idle');
      return;
    }

    const controller = new AbortController();
    requestRef.current = controller;
    setStatus('loading');
    void api
      .listMeasurements(deviceId, makeQuery(sessionId, filters), {
        signal: controller.signal,
      })
      .then((page) => {
        if (requestRef.current !== controller) {
          return;
        }
        const firstPage = page.items.slice(0, MAX_MEASUREMENTS);
        const reachedCap = firstPage.length >= MAX_MEASUREMENTS;
        setItems(firstPage);
        setCapped(reachedCap && page.next_cursor !== null);
        setNextCursor(reachedCap ? null : page.next_cursor);
        setStatus('ready');
      })
      .catch((requestError: unknown) => {
        if (
          requestRef.current !== controller ||
          (isApiError(requestError) && requestError.kind === 'aborted')
        ) {
          return;
        }
        setStatus('error');
        setError(apiErrorMessage(requestError, 'Не удалось загрузить измерения.'));
      })
      .finally(() => {
        if (requestRef.current === controller) {
          requestRef.current = null;
        }
      });

    return () => {
      if (requestRef.current === controller) {
        controller.abort();
        requestRef.current = null;
      }
    };
  }, [
    api,
    deviceId,
    filters.measuredFrom,
    filters.measuredTo,
    retryVersion,
    sessionId,
  ]);

  const loadMore = useCallback(async (): Promise<boolean> => {
    if (
      deviceId === null ||
      sessionId === null ||
      nextCursor === null ||
      loadingMore ||
      requestRef.current !== null
    ) {
      return false;
    }
    const cursor = nextCursor;
    const controller = new AbortController();
    requestRef.current = controller;
    setLoadingMore(true);
    setError(null);
    try {
      const page = await api.listMeasurements(
        deviceId,
        makeQuery(sessionId, filters, cursor),
        { signal: controller.signal },
      );
      if (requestRef.current !== controller) {
        return false;
      }
      const merged = appendUniqueById(items, page.items, MAX_MEASUREMENTS);
      const reachedCap = merged.length >= MAX_MEASUREMENTS;
      setItems(merged);
      setCapped(reachedCap && page.next_cursor !== null);
      setNextCursor(reachedCap ? null : page.next_cursor);
      return true;
    } catch (requestError) {
      if (
        requestRef.current !== controller ||
        (isApiError(requestError) && requestError.kind === 'aborted')
      ) {
        return false;
      }
      setError(apiErrorMessage(requestError, 'Не удалось загрузить следующую страницу.'));
      return false;
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
      }
      setLoadingMore(false);
    }
  }, [api, deviceId, filters, items, loadingMore, nextCursor, sessionId]);

  const setFilters = useCallback((nextFilters: MeasurementFilters) => {
    requestRef.current?.abort();
    requestRef.current = null;
    setItems([]);
    setNextCursor(null);
    setError(null);
    setFilterState(nextFilters);
  }, []);

  useEffect(
    () => () => {
      requestRef.current?.abort();
      requestRef.current = null;
    },
    [],
  );

  return {
    items,
    filters,
    status,
    error,
    loadingMore,
    nextCursor,
    capped,
    setFilters,
    loadMore,
    retry: () => setRetryVersion((version) => version + 1),
  };
}
