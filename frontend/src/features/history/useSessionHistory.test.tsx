import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { SessionResponse } from '../../api/types';
import { createApiStub } from '../../test/apiStub';
import { useSessionHistory } from './useSessionHistory';

const sessionOne: SessionResponse = {
  id: 11,
  device_id: 42,
  status: 'completed',
  started_at: '2026-08-04T06:00:00Z',
  ended_at: '2026-08-04T06:20:00Z',
  latitude: 51.128,
  longitude: 71.431,
  sample_count: 24,
  created_at: '2026-08-04T06:00:00Z',
};

const sessionTwo: SessionResponse = {
  ...sessionOne,
  id: 10,
  started_at: '2026-08-03T06:00:00Z',
  ended_at: '2026-08-03T06:20:00Z',
};

describe('useSessionHistory', () => {
  it('passes the returned cursor through unchanged and deduplicates appended IDs', async () => {
    const cursor = 'opaque+/=_cursor';
    const listSessions = vi
      .fn()
      .mockResolvedValueOnce({ items: [sessionOne], next_cursor: cursor })
      .mockResolvedValueOnce({
        items: [sessionOne, sessionTwo],
        next_cursor: null,
      });
    const api = createApiStub({ listSessions });
    const { result } = renderHook(() => useSessionHistory(api, 42));

    await waitFor(() => expect(result.current.items).toEqual([sessionOne]));
    expect(result.current.selectedSession?.id).toBe(11);
    await act(async () => result.current.loadMore());

    expect(listSessions).toHaveBeenNthCalledWith(
      2,
      42,
      { limit: 20, cursor },
      expect.any(Object),
    );
    expect(result.current.items.map(({ id }) => id)).toEqual([11, 10]);
    expect(result.current.selectedSession?.id).toBe(11);
    expect(result.current.nextCursor).toBeNull();
  });

  it('resets accumulated pages and selection when filters change', async () => {
    const active = { ...sessionOne, id: 12, status: 'active' as const, ended_at: null };
    const listSessions = vi
      .fn()
      .mockResolvedValueOnce({ items: [sessionOne, sessionTwo], next_cursor: 'next' })
      .mockResolvedValueOnce({ items: [active], next_cursor: null });
    const api = createApiStub({ listSessions });
    const { result } = renderHook(() => useSessionHistory(api, 42));
    await waitFor(() => expect(result.current.items).toHaveLength(2));
    act(() => result.current.selectSession(10));
    expect(result.current.selectedSession?.id).toBe(10);

    act(() => result.current.setFilters({ status: 'active' }));
    await waitFor(() => expect(result.current.items).toEqual([active]));

    expect(listSessions).toHaveBeenNthCalledWith(
      2,
      42,
      { status: 'active', limit: 20 },
      expect.any(Object),
    );
    expect(result.current.selectedSession?.id).toBe(12);
  });

  it('uses the half-open timestamp filter names from the backend contract', async () => {
    const listSessions = vi.fn().mockResolvedValue({ items: [], next_cursor: null });
    const api = createApiStub({ listSessions });
    const { result } = renderHook(() => useSessionHistory(api, 42));
    await waitFor(() => expect(result.current.status).toBe('ready'));

    act(() =>
      result.current.setFilters({
        startedFrom: '2026-08-01T00:00:00.000Z',
        startedTo: '2026-08-02T00:00:00.000Z',
      }),
    );
    await waitFor(() => expect(listSessions).toHaveBeenCalledTimes(2));

    expect(listSessions).toHaveBeenLastCalledWith(
      42,
      {
        started_from: '2026-08-01T00:00:00.000Z',
        started_to: '2026-08-02T00:00:00.000Z',
        limit: 20,
      },
      expect.any(Object),
    );
  });

  it('aborts in-flight history when the device changes', async () => {
    let signal: AbortSignal | undefined;
    const listSessions = vi.fn((deviceId, _query, options) => {
      if (deviceId === 42) {
        signal = options?.signal;
        return new Promise<never>(() => undefined);
      }
      return Promise.resolve({ items: [], next_cursor: null });
    });
    const api = createApiStub({ listSessions });
    const { rerender } = renderHook(
      ({ deviceId }) => useSessionHistory(api, deviceId),
      { initialProps: { deviceId: 42 as number | null } },
    );

    rerender({ deviceId: 43 });
    await waitFor(() => expect(signal?.aborted).toBe(true));
  });
});
