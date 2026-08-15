import { formatDateTime } from '../../utils/dateTime';
import type { LiveTelemetryState } from './useLiveTelemetry';

interface LiveTelemetryPanelProps {
  readonly telemetry: LiveTelemetryState;
}

const VALUE_FORMATTER = new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 1,
  minimumFractionDigits: 1,
});

function Metric({
  label,
  value,
  unit,
}: {
  readonly label: string;
  readonly value: number | null;
  readonly unit: string;
}) {
  return (
    <div className="metric-card">
      <span className="metric-card__label">{label}</span>
      <strong className="metric-card__value">
        {value === null ? '—' : VALUE_FORMATTER.format(value)}
      </strong>
      <span className="metric-card__unit">{unit}</span>
    </div>
  );
}

export function LiveTelemetryPanel({ telemetry }: LiveTelemetryPanelProps) {
  return (
    <section className="panel panel--telemetry" aria-labelledby="telemetry-heading">
      <div className="panel__heading-row">
        <div>
          <p className="panel__eyebrow">Автоматическое обновление</p>
          <h2 id="telemetry-heading">Показания датчика</h2>
        </div>
        {telemetry.isStale && (
          <span className="status-badge status-badge--warning">Данные устарели</span>
        )}
      </div>

      {telemetry.status === 'idle' && (
        <p className="empty-copy">Выберите устройство, чтобы начать обновление.</p>
      )}
      {telemetry.status === 'loading' && (
        <p className="loading-copy" role="status">Получаем последнее измерение…</p>
      )}
      {telemetry.status === 'empty' && (
        <p className="empty-copy">Измерений пока нет</p>
      )}
      {telemetry.status === 'error' && telemetry.error !== null && (
        <p className="form-message form-message--error" role="alert">
          {telemetry.error}
        </p>
      )}

      {telemetry.latest !== null && (
        <>
          <div className="metric-grid">
            <Metric label="PM1.0" value={telemetry.latest.pm1} unit="мкг/м³" />
            <Metric label="PM2.5" value={telemetry.latest.pm25} unit="мкг/м³" />
            <Metric label="PM10" value={telemetry.latest.pm10} unit="мкг/м³" />
            <Metric label="Температура" value={telemetry.latest.temperature} unit="°C" />
            <Metric label="Влажность" value={telemetry.latest.humidity} unit="%" />
          </div>
          <div className="freshness-rail">
            <span>Измерено: {formatDateTime(telemetry.latest.measured_at)}</span>
            <span>
              Последнее успешное обновление: {' '}
              {telemetry.lastSuccessfulAt === null
                ? '—'
                : formatDateTime(telemetry.lastSuccessfulAt.toISOString())}
            </span>
          </div>
        </>
      )}

      {telemetry.error !== null && telemetry.latest !== null && (
        <p className="form-message form-message--warning" role="alert">
          {telemetry.error} Показываем последнее успешное измерение.
        </p>
      )}
    </section>
  );
}
