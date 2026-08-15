import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { MeasurementResponse } from '../../api/types';
import { MeasurementHistoryPanel } from './MeasurementHistoryPanel';
import type { MeasurementHistoryState } from './useMeasurementHistory';

const newest: MeasurementResponse = {
  id: 101,
  device_id: 42,
  session_id: 11,
  source_message_id: null,
  measured_at: '2026-08-04T06:01:00Z',
  received_at: '2026-08-04T06:01:01Z',
  temperature: 23.456,
  humidity: 41.2,
  pm1: null,
  pm25: 7.4,
  pm10: 12.6,
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
  created_at: '2026-08-04T06:01:01Z',
};
const older = { ...newest, id: 100, measured_at: '2026-08-04T06:00:00Z' };

function history(
  overrides: Partial<MeasurementHistoryState> = {},
): MeasurementHistoryState {
  return {
    items: [newest, older],
    filters: {},
    status: 'ready',
    error: null,
    loadingMore: false,
    nextCursor: null,
    capped: false,
    setFilters: vi.fn(),
    loadMore: vi.fn().mockResolvedValue(true),
    retry: vi.fn(),
    ...overrides,
  };
}

describe('MeasurementHistoryPanel', () => {
  it('keeps newest-first table order and renders exact values including missing data', () => {
    render(<MeasurementHistoryPanel history={history()} sessionId={11} />);

    const rows = screen.getAllByRole('row');
    expect(within(rows[1]!).getByText('101')).toBeInTheDocument();
    expect(within(rows[2]!).getByText('100')).toBeInTheDocument();
    expect(screen.getAllByText('23,456')).toHaveLength(2);
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('applies validated half-open measurement time filters', async () => {
    const setFilters = vi.fn();
    const user = userEvent.setup();
    render(
      <MeasurementHistoryPanel
        history={history({ setFilters })}
        sessionId={11}
      />,
    );

    await user.type(screen.getByLabelText('Измерено от'), '2026-08-04T06:00');
    await user.type(screen.getByLabelText('Измерено до'), '2026-08-04T07:00');
    await user.click(screen.getByRole('button', { name: 'Применить фильтры измерений' }));

    expect(setFilters).toHaveBeenCalledWith({
      measuredFrom: new Date('2026-08-04T06:00').toISOString(),
      measuredTo: new Date('2026-08-04T07:00').toISOString(),
    });
  });

  it('explains missing selection and empty results', () => {
    const view = render(
      <MeasurementHistoryPanel history={history({ status: 'idle', items: [] })} sessionId={null} />,
    );
    expect(screen.getByText('Выберите сессию в истории.')).toBeInTheDocument();

    view.rerender(
      <MeasurementHistoryPanel history={history({ items: [] })} sessionId={11} />,
    );
    expect(screen.getByText('В этой сессии нет измерений по заданному периоду.')).toBeInTheDocument();
  });
});
