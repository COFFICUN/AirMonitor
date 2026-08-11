import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/errors';
import type { MeasurementResponse } from '../../api/types';
import { createApiStub } from '../../test/apiStub';
import { useLiveTelemetry } from './useLiveTelemetry';

const measurement: MeasurementResponse = {
  id: 101,
  device_id: 42,
  session_id: 7,
  source_message_id: null,
  measured_at: '2026-08-04T06:00:00Z',
  received_at: '2026-08-04T06:00:01Z',
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
  latitude: 51.128,
  longitude: 71.431,
  is_valid: true,
  validation_note: null,
  created_at: '2026-08-04T06:00:01Z',
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function setVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    value: state,
  });
  document.dispatchEvent(new Event('visibilitychange'));
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-08-04T06:01:00Z'));
  setVisibility('visible');
});

afterEach(() => {
  vi.useRealTimers();
  setVisibility('visible');
});

describe('useLiveTelemetry', () => {
  it('loads only the newest item and polls every five seconds', async () => {
    const listMeasurements = vi.fn().mockResolvedValue({
      items: [measurement],
      next_cursor: 'opaque-not-used-for-live',
    });
    const api = createApiStub({ listMeasurements });
    const { result } = renderHook(() => useLiveTelemetry(api, 42));

    await act(async () => undefined);
    expect(result.current.latest).toEqual(measurement);
    expect(result.current.lastSuccessfulAt?.toISOString()).toBe(
      '2026-08-04T06:01:00.000Z',
    );
    expect(listMeasurements).toHaveBeenLastCalledWith(
      42,
      { limit: 1 },
      expect.any(Object),
    );

    await act(async () => vi.advanceTimersByTimeAsync(5_000));
    expect(listMeasurements).toHaveBeenCalledTimes(2);
  });

  it('never overlaps requests even when a response is slow', async () => {
    const first = deferred<{
      readonly items: readonly MeasurementResponse[];
      readonly next_cursor: string | null;
    }>();
    const listMeasurements = vi
      .fn()
      .mockReturnValueOnce(first.promise)
      .mockResolvedValue({ items: [measurement], next_cursor: null });
    const api = createApiStub({ listMeasurements });
    renderHook(() => useLiveTelemetry(api, 42));

    await act(async () => vi.advanceTimersByTimeAsync(30_000));
    expect(listMeasurements).toHaveBeenCalledOnce();

    await act(async () => first.resolve({ items: [measurement], next_cursor: null }));
    await act(async () => vi.advanceTimersByTimeAsync(4_999));
    expect(listMeasurements).toHaveBeenCalledOnce();
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(listMeasurements).toHaveBeenCalledTimes(2);
  });

  it('aborts the old request and clears old-device data on device change', async () => {
    let firstSignal: AbortSignal | undefined;
    const first = deferred<{
      readonly items: readonly MeasurementResponse[];
      readonly next_cursor: string | null;
    }>();
    const listMeasurements = vi.fn((deviceId, _query, options) => {
      if (deviceId === 42) {
        firstSignal = options?.signal;
        return first.promise;
      }
      return Promise.resolve({ items: [], next_cursor: null });
    });
    const api = createApiStub({ listMeasurements });
    const { result, rerender } = renderHook(
      ({ deviceId }) => useLiveTelemetry(api, deviceId),
      { initialProps: { deviceId: 42 as number | null } },
    );

    rerender({ deviceId: 43 });
    await act(async () => undefined);

    expect(firstSignal?.aborted).toBe(true);
    expect(result.current.latest).toBeNull();
    expect(listMeasurements).toHaveBeenCalledWith(
      43,
      { limit: 1 },
      expect.any(Object),
    );
  });

  it('pauses while hidden and resumes after visibility returns', async () => {
    const listMeasurements = vi.fn().mockResolvedValue({
      items: [measurement],
      next_cursor: null,
    });
    const api = createApiStub({ listMeasurements });
    renderHook(() => useLiveTelemetry(api, 42));
    await act(async () => undefined);
    expect(listMeasurements).toHaveBeenCalledOnce();

    act(() => setVisibility('hidden'));
    await act(async () => vi.advanceTimersByTimeAsync(20_000));
    expect(listMeasurements).toHaveBeenCalledOnce();

    act(() => setVisibility('visible'));
    await act(async () => undefined);
    expect(listMeasurements).toHaveBeenCalledTimes(2);
  });

  it('keeps the last success visible through a failure and marks it stale', async () => {
    const listMeasurements = vi
      .fn()
      .mockResolvedValueOnce({ items: [measurement], next_cursor: null })
      .mockRejectedValue(new ApiError({ kind: 'network' }));
    const api = createApiStub({ listMeasurements });
    const { result } = renderHook(() =>
      useLiveTelemetry(api, 42, { staleAfterMs: 10_000 }),
    );
    await act(async () => undefined);

    await act(async () => vi.advanceTimersByTimeAsync(5_000));
    expect(result.current.latest).toEqual(measurement);
    expect(result.current.error).toBe('Не удалось связаться с сервером.');
    expect(result.current.isStale).toBe(false);

    await act(async () => vi.advanceTimersByTimeAsync(5_000));
    expect(result.current.latest).toEqual(measurement);
    expect(result.current.isStale).toBe(true);
  });

  it('treats an empty page as a successful empty state', async () => {
    const api = createApiStub({
      listMeasurements: vi.fn().mockResolvedValue({
        items: [],
        next_cursor: null,
      }),
    });
    const { result } = renderHook(() => useLiveTelemetry(api, 42));

    await act(async () => undefined);
    expect(result.current.status).toBe('empty');
    expect(result.current.error).toBeNull();
  });
});
