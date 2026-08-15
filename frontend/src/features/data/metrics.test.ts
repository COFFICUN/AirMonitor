import { describe, expect, it } from 'vitest';

import type { MeasurementResponse } from '../../api/types';
import { DATA_METRICS, metricValues } from './metrics';

const measurement = {
  pm1: 4,
  pm25: 8,
  pm10: 12,
  temperature: 21.5,
  humidity: null,
} as MeasurementResponse;

describe('data metrics', () => {
  it('offers every metric required by the participant data view', () => {
    expect(DATA_METRICS.map(({ key }) => key)).toEqual([
      'pm1',
      'pm25',
      'pm10',
      'temperature',
      'humidity',
    ]);
  });

  it('reads the selected metric without replacing missing values', () => {
    expect(metricValues([measurement], 'temperature')).toEqual([21.5]);
    expect(metricValues([measurement], 'humidity')).toEqual([null]);
  });
});
