import { describe, expect, it } from 'vitest';
import { formatDuration, sessionDurationMs } from './duration';

describe('session duration presentation', () => {
  it('calculates a reliable completed duration', () => {
    expect(sessionDurationMs('2026-08-05T05:00:00Z', '2026-08-05T06:02:03Z')).toBe(3_723_000);
    expect(formatDuration(3_723_000)).toBe('01:02:03');
  });

  it('rejects invalid and reversed timestamps', () => {
    expect(sessionDurationMs('invalid', null)).toBeNull();
    expect(sessionDurationMs('2026-08-05T06:00:00Z', '2026-08-05T05:00:00Z')).toBeNull();
    expect(formatDuration(null)).toBe('—');
  });
});
