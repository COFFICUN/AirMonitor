import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { isApiError } from '../../api/errors';
import { apiErrorMessage } from '../../api/presentation';
import type {
  AirMonitorApi,
  SessionListQuery,
  SessionResponse,
  SessionStatus,
} from '../../api/types';
import { appendUniqueById } from './pagination';

export interface SessionFilters {
  readonly status?: SessionStatus;
  readonly startedFrom?: string;
  readonly startedTo?: string;
}

export type SessionHistoryStatus = 'idle' | 'loading' | 'ready' | 'error';

export interface SessionHistoryState {
  readonly items: readonly SessionResponse[];
  readonly filters: SessionFilters;
  readonly status: SessionHistoryStatus;
  readonly error: string | null;
  readonly loadingMore: boolean;
  readonly nextCursor: string | null;
  readonly selectedSession: SessionResponse | null;
  readonly capped: boolean;
  setFilters(filters: SessionFilters): void;
  selectSession(sessionId: number): void;
  loadMore(): Promise<boolean>;
  retry(): void;
}

const PAGE_LIMIT = 20;
const MAX_SESSIONS = 100;

function makeQuery(filters: SessionFilters, cursor?: string): SessionListQuery {
  return {
    ...(filters.status === undefined ? {} : { status: filters.status }),
    ...(filters.startedFrom === undefined
      ? {}
      : { started_from: filters.startedFrom }),
    ...(filters.startedTo === undefined ? {} : { started_to: filters.startedTo }),
    limit: PAGE_LIMIT,
    ...(cursor === undefined ? {} : { cursor }),
  };
}

export function useSessionHistory(
  api: AirMonitorApi,
  deviceId: number | null,
  refreshVersion = 0,
): SessionHistoryState {
  const [items, setItems] = useState<readonly SessionResponse[]>([]);
  const [filters, setFilterState] = useState<SessionFilters>({});
  const [status, setStatus] = useState<SessionHistoryStatus>(
    deviceId === null ? 'idle' : 'loading',
  );
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [capped, setCapped] = useState(false);
  const [retryVersion, setRetryVersion] = useState(0);
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => {
    requestRef.current?.abort();
    setItems([]);
    setSelectedSessionId(null);
    setNextCursor(null);
    setCapped(false);
    setLoadingMore(false);
    setError(null);
    if (deviceId === null) {
      requestRef.current = null;
      setStatus('idle');
      return;
    }

    const controller = new AbortController();
    requestRef.current = controller;
    setStatus('loading');
    void api
      .listSessions(deviceId, makeQuery(filters), { signal: controller.signal })
      .then((page) => {
        if (requestRef.current !== controller) {
          return;
        }
        const firstPage = page.items.slice(0, MAX_SESSIONS);
        setItems(firstPage);
        setSelectedSessionId(firstPage[0]?.id ?? null);
        const reachedCap = firstPage.length >= MAX_SESSIONS;
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
        setError(apiErrorMessage(requestError, 'Не удалось загрузить сессии.'));
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
    filters.startedFrom,
    filters.startedTo,
    filters.status,
    refreshVersion,
    retryVersion,
  ]);

  const loadMore = useCallback(async (): Promise<boolean> => {
    if (
      deviceId === null ||
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
      const page = await api.listSessions(
        deviceId,
        makeQuery(filters, cursor),
        { signal: controller.signal },
      );
      if (requestRef.current !== controller) {
        return false;
      }
      const merged = appendUniqueById(items, page.items, MAX_SESSIONS);
      const reachedCap = merged.length >= MAX_SESSIONS;
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
  }, [api, deviceId, filters, items, loadingMore, nextCursor]);

  const selectedSession = useMemo(
    () => items.find(({ id }) => id === selectedSessionId) ?? null,
    [items, selectedSessionId],
  );

  const setFilters = useCallback((nextFilters: SessionFilters) => {
    requestRef.current?.abort();
    requestRef.current = null;
    setItems([]);
    setSelectedSessionId(null);
    setNextCursor(null);
    setError(null);
    setFilterState(nextFilters);
  }, []);

  const selectSession = useCallback(
    (sessionId: number) => {
      if (items.some(({ id }) => id === sessionId)) {
        setSelectedSessionId(sessionId);
      }
    },
    [items],
  );

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
    selectedSession,
    capped,
    setFilters,
    selectSession,
    loadMore,
    retry: () => setRetryVersion((version) => version + 1),
  };
}
