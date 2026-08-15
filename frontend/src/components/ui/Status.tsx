import type { ReactNode } from 'react';

export type StatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

export function StatusBadge({ tone = 'neutral', children }: { readonly tone?: StatusTone; readonly children: ReactNode }) {
  return <span className={`status-badge status-badge--${tone}`}><span aria-hidden="true" />{children}</span>;
}

export function AirQualityIndicator({ value }: { readonly value: number | null }) {
  const band = value === null ? { tone: 'neutral' as const, label: 'Нет данных' }
    : value <= 15 ? { tone: 'success' as const, label: 'Низкая концентрация' }
      : value <= 25 ? { tone: 'info' as const, label: 'Умеренная концентрация' }
        : value <= 50 ? { tone: 'warning' as const, label: 'Повышенная концентрация' }
          : { tone: 'danger' as const, label: 'Высокая концентрация' };
  return <div className="air-quality-indicator"><StatusBadge tone={band.tone}>{band.label}</StatusBadge><small>По текущей точке PM2.5; это не AQI и не заключение.</small></div>;
}
