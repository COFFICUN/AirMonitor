import { describe, expect, it } from 'vitest';

import { calculateStatistics } from './statistics';

describe('calculateStatistics', () => {
  it('calculates count, minimum, maximum, mean, and median without mutating input', () => {
    const values = [9, 1, 4, 2] as const;
    expect(calculateStatistics(values)).toEqual({
      count: 4,
      minimum: 1,
      maximum: 9,
      mean: 4,
      median: 3,
    });
    expect(values).toEqual([9, 1, 4, 2]);
  });

  it('ignores null and non-finite values', () => {
    expect(calculateStatistics([null, Number.NaN, 8, Number.POSITIVE_INFINITY])).toEqual({
      count: 1,
      minimum: 8,
      maximum: 8,
      mean: 8,
      median: 8,
    });
  });

  it('returns an explicit empty result', () => {
    expect(calculateStatistics([])).toEqual({
      count: 0,
      minimum: null,
      maximum: null,
      mean: null,
      median: null,
    });
  });
});
