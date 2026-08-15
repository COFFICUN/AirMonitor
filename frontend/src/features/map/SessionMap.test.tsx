import { act, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { SessionResponse } from '../../api/types';
import { SessionMap } from './SessionMap';

const mocks = vi.hoisted(() => ({
  createSessionMap: vi.fn(),
  update: vi.fn(),
  destroy: vi.fn(),
}));

vi.mock('./leafletAdapter', () => ({
  createSessionMap: mocks.createSessionMap,
}));

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

beforeEach(() => {
  mocks.createSessionMap.mockReset();
  mocks.update.mockReset();
  mocks.destroy.mockReset();
  mocks.createSessionMap.mockReturnValue({
    update: mocks.update,
    destroy: mocks.destroy,
  });
});

describe('SessionMap', () => {
  it('renders an empty state without initializing Leaflet', () => {
    render(
      <SessionMap sessions={[]} selectedSessionId={null} onSelect={vi.fn()} />,
    );

    expect(screen.getByText('Пока нет проведённых измерений с координатами.')).toBeInTheDocument();
    expect(mocks.createSessionMap).not.toHaveBeenCalled();
  });

  it('initializes once, updates selection, relays marker selection, and cleans up', () => {
    const onSelect = vi.fn();
    const view = render(
      <SessionMap sessions={[session]} selectedSessionId={11} onSelect={onSelect} />,
    );

    expect(mocks.createSessionMap).toHaveBeenCalledOnce();
    expect(screen.getByRole('region', { name: 'Интерактивная карта измерительных точек' })).toBeVisible();
    expect(mocks.update).toHaveBeenCalledWith([session], 11, expect.any(Function));
    const selectFromMarker = mocks.update.mock.calls[0]?.[2] as (id: number) => void;
    act(() => selectFromMarker(11));
    expect(onSelect).toHaveBeenCalledWith(11);

    view.rerender(
      <SessionMap sessions={[session]} selectedSessionId={null} onSelect={onSelect} />,
    );
    expect(mocks.createSessionMap).toHaveBeenCalledOnce();
    expect(mocks.update).toHaveBeenLastCalledWith([session], null, expect.any(Function));

    view.unmount();
    expect(mocks.destroy).toHaveBeenCalledOnce();
  });

  it('contains initialization failures and leaves the rest of the page usable', () => {
    mocks.createSessionMap.mockImplementation(() => {
      throw new Error('raw map failure');
    });
    render(
      <SessionMap sessions={[session]} selectedSessionId={11} onSelect={vi.fn()} />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Карта временно недоступна. Список сессий остаётся доступен.',
    );
    expect(screen.queryByText('raw map failure')).not.toBeInTheDocument();
  });
});
