import type { MeasurementResponse } from '../../api/types';

export type ChartMetric = 'pm25' | 'pm10' | 'temperature' | 'humidity';

export interface MetricPoint {
  readonly id: number;
  readonly index: number;
  readonly timestamp: string;
  readonly value: number;
}

export interface MetricSeries {
  readonly segments: readonly (readonly MetricPoint[])[];
  readonly minimum: number | null;
  readonly maximum: number | null;
  readonly valueCount: number;
  readonly totalCount: number;
  readonly firstTimestamp: string | null;
  readonly lastTimestamp: string | null;
}

export function chronologicalCopy(
  measurements: readonly MeasurementResponse[],
): readonly MeasurementResponse[] {
  return [...measurements].sort((left, right) => {
    const timeDifference =
      Date.parse(left.measured_at) - Date.parse(right.measured_at);
    return timeDifference === 0 ? left.id - right.id : timeDifference;
  });
}

export function buildMetricSeries(
  measurements: readonly MeasurementResponse[],
  metric: ChartMetric,
): MetricSeries {
  const chronological = chronologicalCopy(measurements);
  const segments: MetricPoint[][] = [];
  let current: MetricPoint[] = [];
  let minimum: number | null = null;
  let maximum: number | null = null;
  let valueCount = 0;

  chronological.forEach((measurement, index) => {
    const value = measurement[metric];
    if (value === null || !Number.isFinite(value)) {
      if (current.length > 0) {
        segments.push(current);
        current = [];
      }
      return;
    }
    current.push({
      id: measurement.id,
      index,
      timestamp: measurement.measured_at,
      value,
    });
    minimum = minimum === null ? value : Math.min(minimum, value);
    maximum = maximum === null ? value : Math.max(maximum, value);
    valueCount += 1;
  });
  if (current.length > 0) {
    segments.push(current);
  }

  return {
    segments,
    minimum,
    maximum,
    valueCount,
    totalCount: chronological.length,
    firstTimestamp: chronological[0]?.measured_at ?? null,
    lastTimestamp: chronological.at(-1)?.measured_at ?? null,
  };
}

