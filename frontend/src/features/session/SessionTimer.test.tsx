import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SessionTimer } from './SessionTimer';

afterEach(() => {
  vi.useRealTimers();
});

describe('SessionTimer', () => {
  it('shows elapsed time and advances once per second', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-08-05T06:00:05Z'));

    render(<SessionTimer startedAt="2026-08-05T06:00:00Z" />);

    expect(screen.getByText('00:00:05')).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(2_000));
    expect(screen.getByText('00:00:07')).toBeInTheDocument();
  });

  it('renders a safe fallback for an invalid start time', () => {
    render(<SessionTimer startedAt="not-a-date" />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
