import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { SessionResponse } from '../../api/types';
import { SessionHistoryPanel } from './SessionHistoryPanel';
import type { SessionHistoryState } from './useSessionHistory';

const session: SessionResponse = {
  id: 11,
  device_id: 42,
  status: 'completed',
  started_at: '2026-08-04T06:00:00Z',
  ended_at: '2026-08-04T06:20:00Z',
  latitude: 51.128,
  longitude: 71.431,
  sample_count: 24,
  created_at: '2026-08-04T06:00:00Z',
};

function history(
  overrides: Partial<SessionHistoryState> = {},
): SessionHistoryState {
  return {
    items: [session],
    filters: {},
    status: 'ready',
    error: null,
    loadingMore: false,
    nextCursor: null,
    selectedSession: session,
    capped: false,
    setFilters: vi.fn(),
    selectSession: vi.fn(),
    loadMore: vi.fn().mockResolvedValue(true),
    retry: vi.fn(),
    ...overrides,
  };
}

describe('SessionHistoryPanel', () => {
  it('renders exact session facts and exposes selection as a button', async () => {
    const selectSession = vi.fn();
    const user = userEvent.setup();
    render(
      <SessionHistoryPanel history={history({ selectSession })} />,
    );

    expect(screen.getByText('24 измерения')).toBeInTheDocument();
    const button = screen.getByRole('button', { name: /Сессия №11/ });
    expect(button).toHaveAttribute('aria-pressed', 'true');
    await user.click(button);
    expect(selectSession).toHaveBeenCalledWith(11);
  });

  it('applies status and validated half-open local time filters', async () => {
    const setFilters = vi.fn();
    const user = userEvent.setup();
    render(
      <SessionHistoryPanel history={history({ setFilters })} />,
    );

    await user.selectOptions(screen.getByLabelText('Статус сессии'), 'active');
    await user.type(screen.getByLabelText('Начало периода'), '2026-08-01T10:00');
    await user.type(screen.getByLabelText('Конец периода'), '2026-08-02T10:00');
    await user.click(screen.getByRole('button', { name: 'Применить фильтры сессий' }));

    expect(setFilters).toHaveBeenCalledWith({
      status: 'active',
      startedFrom: new Date('2026-08-01T10:00').toISOString(),
      startedTo: new Date('2026-08-02T10:00').toISOString(),
    });
  });

  it('shows empty, failed, and load-more states explicitly', () => {
    const view = render(
      <SessionHistoryPanel
        history={history({ items: [], selectedSession: null })}
      />,
    );
    expect(screen.getByText('Сессии по этим условиям не найдены.')).toBeInTheDocument();

    view.rerender(
      <SessionHistoryPanel
        history={history({ error: 'Ошибка истории', nextCursor: 'opaque' })}
      />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Ошибка истории');
    expect(screen.getByRole('button', { name: 'Загрузить ещё сессии' })).toBeInTheDocument();
  });
});
