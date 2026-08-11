import type { MeasurementResponse } from '../../api/types';

export type DataMetricKey = 'pm1' | 'pm25' | 'pm10' | 'temperature' | 'humidity';

export interface DataMetric {
  readonly key: DataMetricKey;
  readonly label: string;
  readonly unit: string;
}

export const DATA_METRICS: readonly DataMetric[] = [
  { key: 'pm1', label: 'PM1.0', unit: 'мкг/м³' },
  { key: 'pm25', label: 'PM2.5', unit: 'мкг/м³' },
  { key: 'pm10', label: 'PM10', unit: 'мкг/м³' },
  { key: 'temperature', label: 'Температура', unit: '°C' },
  { key: 'humidity', label: 'Влажность', unit: '%' },
];

export function metricValues(
  measurements: readonly MeasurementResponse[],
  metric: DataMetricKey,
): readonly (number | null)[] {
  return measurements.map((measurement) => measurement[metric]);
}
