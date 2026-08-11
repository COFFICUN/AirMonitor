import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { MeasurementResponse } from '../../api/types';
import { TelemetryChart } from './TelemetryChart';

function point(id: number, value: number | null): MeasurementResponse {
  return {
    id,
    device_id: 42,
    session_id: 11,
    source_message_id: null,
    measured_at: `2026-08-04T06:0${id}:00Z`,
    received_at: `2026-08-04T06:0${id}:01Z`,
    temperature: value,
    humidity: value,
    pm1: null,
    pm25: value,
    pm10: value,
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
    created_at: `2026-08-04T06:0${id}:01Z`,
  };
}

describe('TelemetryChart', () => {
  it('renders four labelled metric charts and textual summaries', () => {
    render(<TelemetryChart measurements={[point(2, 7.4), point(1, 5.2)]} />);

    expect(screen.getByRole('img', { name: /PM2.5/ })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /PM10/ })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Температура/ })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Влажность/ })).toBeInTheDocument();
    expect(screen.getAllByText(/2 точки/)).toHaveLength(4);
  });

  it('renders a real point rather than a fabricated line for one sample', () => {
    const { container } = render(<TelemetryChart measurements={[point(1, 5.2)]} />);
    expect(container.querySelectorAll('circle[data-point="true"]')).toHaveLength(4);
    expect(container.querySelectorAll('polyline')).toHaveLength(0);
  });

  it('does not bridge a missing sample and handles an empty dataset', () => {
    const view = render(
      <TelemetryChart measurements={[point(3, 7), point(2, null), point(1, 5)]} />,
    );
    expect(view.container.querySelectorAll('[data-metric="pm25"] polyline')).toHaveLength(0);
    expect(view.container.querySelectorAll('[data-metric="pm25"] circle')).toHaveLength(2);

    view.rerender(<TelemetryChart measurements={[]} />);
    expect(screen.getByText('Нет данных для построения графика.')).toBeInTheDocument();
  });
});
