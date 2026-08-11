import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { MeasurementResponse } from '../../api/types';
import { LiveTelemetryPanel } from './LiveTelemetryPanel';
import type { LiveTelemetryState } from './useLiveTelemetry';

const latest: MeasurementResponse = {
  id: 101,
  device_id: 42,
  session_id: 7,
  source_message_id: null,
  measured_at: '2026-08-04T06:00:00Z',
  received_at: '2026-08-04T06:00:01Z',
  temperature: 23.4,
  humidity: 41.2,
  pm1: 3.1,
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
  created_at: '2026-08-04T06:00:01Z',
};

function state(overrides: Partial<LiveTelemetryState> = {}): LiveTelemetryState {
  return {
    latest: null,
    status: 'empty',
    error: null,
    lastSuccessfulAt: new Date('2026-08-04T06:01:00Z'),
    isStale: false,
    ...overrides,
  };
}

describe('LiveTelemetryPanel', () => {
  it('renders current metrics with understandable units', () => {
    render(
      <LiveTelemetryPanel
        telemetry={state({ latest, status: 'ready' })}
      />,
    );

    expect(screen.getByText('7,4')).toBeInTheDocument();
    expect(screen.getAllByText('мкг/м³')).toHaveLength(3);
    expect(screen.getByText('23,4')).toBeInTheDocument();
    expect(screen.getByText('°C')).toBeInTheDocument();
    expect(screen.getByText('41,2')).toBeInTheDocument();
    expect(screen.getByText('%')).toBeInTheDocument();
    expect(screen.getByText(/Последнее успешное обновление/)).toBeInTheDocument();
  });

  it('distinguishes an empty result from an unavailable backend', () => {
    const view = render(<LiveTelemetryPanel telemetry={state()} />);
    expect(screen.getByText('Измерений пока нет')).toBeInTheDocument();

    view.rerender(
      <LiveTelemetryPanel
        telemetry={state({
          status: 'error',
          error: 'Не удалось связаться с сервером.',
          lastSuccessfulAt: null,
        })}
      />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Не удалось связаться с сервером.',
    );
  });

  it('keeps old values visible and labels them stale after a failure', () => {
    render(
      <LiveTelemetryPanel
        telemetry={state({
          latest,
          status: 'ready',
          isStale: true,
          error: 'Не удалось связаться с сервером.',
        })}
      />,
    );

    expect(screen.getByText('Данные устарели')).toBeInTheDocument();
    expect(screen.getByText('7,4')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Показываем последнее успешное измерение.',
    );
  });
});
