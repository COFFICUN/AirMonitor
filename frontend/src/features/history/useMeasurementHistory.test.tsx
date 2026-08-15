import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { MeasurementResponse } from '../../api/types';
import { createApiStub } from '../../test/apiStub';
import { useMeasurementHistory } from './useMeasurementHistory';

const newest: MeasurementResponse = {
  id: 101,
  device_id: 42,
  session_id: 11,
  source_message_id: null,
  measured_at: '2026-08-04T06:01:00Z',
  received_at: '2026-08-04T06:01:01Z',
  temperature: 23.4,
  humidity: 41.2,
  pm1: 3.1,
  pm25: 7.4,
  pm10: 12.6,
  pc0_3: null,
  pc0_5: null,
  pc1_0: null,
  pc2_5: null,
  pc5_0: null,
  pc10: null,
  latitude: null,
  longitude: null,
  is_valid: true,
  validation_note: null,
  created_at: '2026-08-04T06:01:01Z',
};

const older: MeasurementResponse = {
  ...newest,
  id: 100,
  measured_at: '2026-08-04T06:00:00Z',
};

describe('useMeasurementHistory', () => {
  it('keeps API order while appending an opaque cursor page without duplicates', async () => {
    const cursor = 'opaque.measurement+/=';
    const listMeasurements = vi
      .fn()
      .mockResolvedValueOnce({ items: [newest], next_cursor: cursor })
      .mockResolvedValueOnce({ items: [newest, older], next_cursor: null });
    const api = createApiStub({ listMeasurements });
    const { result } = renderHook(() =>
      useMeasurementHistory(api, 42, 11),
    );

    await waitFor(() => expect(result.current.items).toEqual([newest]));
    await act(async () => result.current.loadMore());

    expect(listMeasurements).toHaveBeenNthCalledWith(
      2,
      42,
      { session_id: 11, limit: 100, cursor },
      expect.any(Object),
    );
    expect(result.current.items.map(({ id }) => id)).toEqual([101, 100]);
  });

  it('resets pages when time filters change and uses measured contract names', async () => {
    const listMeasurements = vi
      .fn()
      .mockResolvedValueOnce({ items: [newest, older], next_cursor: 'next' })
      .mockResolvedValueOnce({ items: [older], next_cursor: null });
    const api = createApiStub({ listMeasurements });
    const { result } = renderHook(() => useMeasurementHistory(api, 42, 11));
    await waitFor(() => expect(result.current.items).toHaveLength(2));

    act(() =>
      result.current.setFilters({
        measuredFrom: '2026-08-04T06:00:00.000Z',
        measuredTo: '2026-08-04T06:01:00.000Z',
      }),
    );
    await waitFor(() => expect(result.current.items).toEqual([older]));

    expect(listMeasurements).toHaveBeenLastCalledWith(
      42,
      {
        session_id: 11,
        measured_from: '2026-08-04T06:00:00.000Z',
        measured_to: '2026-08-04T06:01:00.000Z',
        limit: 100,
      },
      expect.any(Object),
    );
  });

  it('does not request measurements until both device and session are selected', () => {
    const listMeasurements = vi.fn();
    const api = createApiStub({ listMeasurements });
    const { result } = renderHook(() =>
      useMeasurementHistory(api, 42, null),
    );

    expect(result.current.status).toBe('idle');
    expect(listMeasurements).not.toHaveBeenCalled();
  });

  it('aborts an old request when session selection changes', async () => {
    let oldSignal: AbortSignal | undefined;
    const listMeasurements = vi.fn((_deviceId, query, options) => {
      if (query?.session_id === 11) {
        oldSignal = options?.signal;
        return new Promise<never>(() => undefined);
      }
      return Promise.resolve({ items: [], next_cursor: null });
    });
    const api = createApiStub({ listMeasurements });
    const { rerender } = renderHook(
      ({ sessionId }) => useMeasurementHistory(api, 42, sessionId),
      { initialProps: { sessionId: 11 as number | null } },
    );

    rerender({ sessionId: 12 });
    await waitFor(() => expect(oldSignal?.aborted).toBe(true));
    expect(listMeasurements).toHaveBeenCalledWith(
      42,
      { session_id: 12, limit: 100 },
      expect.any(Object),
    );
  });
});
