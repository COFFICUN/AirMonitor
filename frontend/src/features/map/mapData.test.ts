import { describe, expect, it } from 'vitest';

import type { SessionResponse } from '../../api/types';
import { mappableSessions } from './mapData';

function session(id: number, latitude: number, longitude: number): SessionResponse {
  return {
    id,
    device_id: 42,
    status: 'completed',
    started_at: '2026-08-04T06:00:00Z',
    ended_at: '2026-08-04T06:20:00Z',
    latitude,
    longitude,
    sample_count: 20,
    created_at: '2026-08-04T06:00:00Z',
  };
}

describe('mappableSessions', () => {
  it('keeps only real finite in-range backend coordinates', () => {
    expect(
      mappableSessions([
        session(1, 51.128, 71.431),
        session(2, 91, 71),
        session(3, 51, 181),
        session(4, Number.NaN, 71),
      ]).map(({ id }) => id),
    ).toEqual([1]);
  });
});
