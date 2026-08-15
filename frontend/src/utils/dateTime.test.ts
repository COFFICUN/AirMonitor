import { afterEach, describe, expect, it } from 'vitest';
import { formatDateTime } from './dateTime';

afterEach(() => { delete document.documentElement.dataset.timeFormat; });

describe('Almaty date and time presentation', () => {
  it('formats an instant in the Asia/Almaty product timezone', () => {
    expect(formatDateTime('2026-08-05T00:00:00Z')).toContain('05:00:00');
  });

  it('uses the selected 12-hour presentation and handles invalid values safely', () => {
    document.documentElement.dataset.timeFormat = '12h';
    expect(formatDateTime('2026-08-05T12:00:00Z')).toMatch(/05:00:00/);
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateTime('not-a-date')).toBe('Некорректная дата');
  });
});
