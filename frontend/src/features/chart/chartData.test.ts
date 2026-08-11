import { describe, expect, it } from 'vitest';

import type { MeasurementResponse } from '../../api/types';
import { buildMetricSeries, chronologicalCopy } from './chartData';

function measurement(
  id: number,
  measuredAt: string,
  pm25: number | null,
): MeasurementResponse {
  return {
    id,
    device_id: 42,
    session_id: 11,
    source_message_id: null,
    measured_at: measuredAt,
    received_at: measuredAt,
    temperature: pm25,
    humidity: pm25,
    pm1: pm25,
    pm25,
    pm10: pm25,
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
    created_at: measuredAt,
  };
}

describe('chartData', () => {
  it('creates an oldest-first presentation copy without mutating API order', () => {
    const newestFirst = [
      measurement(3, '2026-08-04T06:02:00Z', 3),
      measurement(2, '2026-08-04T06:01:00Z', 2),
      measurement(1, '2026-08-04T06:00:00Z', 1),
    ] as const;

    expect(chronologicalCopy(newestFirst).map(({ id }) => id)).toEqual([1, 2, 3]);
    expect(newestFirst.map(({ id }) => id)).toEqual([3, 2, 1]);
  });

  it('splits lines at missing values instead of interpolating across them', () => {
    const input = [
      measurement(4, '2026-08-04T06:03:00Z', 4),
      measurement(3, '2026-08-04T06:02:00Z', null),
      measurement(2, '2026-08-04T06:01:00Z', 2),
      measurement(1, '2026-08-04T06:00:00Z', 1),
    ];

    const series = buildMetricSeries(input, 'pm25');
    expect(series.segments.map((segment) => segment.map(({ value }) => value))).toEqual([
      [1, 2],
      [4],
    ]);
    expect(series.minimum).toBe(1);
    expect(series.maximum).toBe(4);
    expect(series.valueCount).toBe(3);
  });

  it('retains equal timestamps in ascending ID order', () => {
    const input = [
      measurement(2, '2026-08-04T06:00:00Z', 2),
      measurement(1, '2026-08-04T06:00:00Z', 1),
    ];
    expect(chronologicalCopy(input).map(({ id }) => id)).toEqual([1, 2]);
  });
});
