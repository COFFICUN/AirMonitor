import type { MeasurementResponse } from '../../api/types';
import { formatDateTime } from '../../utils/dateTime';
import { buildMetricSeries, type ChartMetric, type MetricPoint } from './chartData';

interface TelemetryChartProps {
  readonly measurements: readonly MeasurementResponse[];
}

interface MetricDefinition {
  readonly key: ChartMetric;
  readonly label: string;
  readonly unit: string;
  readonly color: string;
}

const METRICS: readonly MetricDefinition[] = [
  { key: 'pm25', label: 'PM2.5', unit: 'мкг/м³', color: '#00a9b8' },
  { key: 'pm10', label: 'PM10', unit: 'мкг/м³', color: '#526ea6' },
  { key: 'temperature', label: 'Температура', unit: '°C', color: '#d17b35' },
  { key: 'humidity', label: 'Влажность', unit: '%', color: '#5a8b69' },
];

const WIDTH = 360;
const HEIGHT = 150;
const PADDING_X = 22;
const PADDING_TOP = 14;
const PADDING_BOTTOM = 28;

function coordinate(
  point: MetricPoint,
  totalCount: number,
  minimum: number,
  maximum: number,
): readonly [number, number] {
  const usableWidth = WIDTH - PADDING_X * 2;
  const usableHeight = HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const x =
    totalCount <= 1
      ? WIDTH / 2
      : PADDING_X + (point.index / (totalCount - 1)) * usableWidth;
  const y =
    minimum === maximum
      ? PADDING_TOP + usableHeight / 2
      : PADDING_TOP + ((maximum - point.value) / (maximum - minimum)) * usableHeight;
  return [x, y];
}

function valueLabel(value: number | null): string {
  return value === null ? '—' : String(value).replace('.', ',');
}

function pointCountLabel(count: number): string {
  const suffix = count === 1 ? 'точка' : count >= 2 && count <= 4 ? 'точки' : 'точек';
  return `${count} ${suffix}`;
}

function MetricChart({
  definition,
  measurements,
}: {
  readonly definition: MetricDefinition;
  readonly measurements: readonly MeasurementResponse[];
}) {
  const series = buildMetricSeries(measurements, definition.key);
  const minimum = series.minimum ?? 0;
  const maximum = series.maximum ?? 0;

  return (
    <figure className="trend-card" data-metric={definition.key}>
      <figcaption>
        <strong>{definition.label}</strong>
        <span>{definition.unit}</span>
      </figcaption>
      <svg
        role="img"
        aria-label={`${definition.label}: ${pointCountLabel(series.valueCount)}, минимум ${valueLabel(series.minimum)}, максимум ${valueLabel(series.maximum)} ${definition.unit}`}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
      >
        <line
          className="chart-axis"
          x1={PADDING_X}
          x2={WIDTH - PADDING_X}
          y1={HEIGHT - PADDING_BOTTOM}
          y2={HEIGHT - PADDING_BOTTOM}
        />
        {series.segments.map((segment) => {
          if (segment.length === 1) {
            const point = segment[0]!;
            const [cx, cy] = coordinate(
              point,
              series.totalCount,
              minimum,
              maximum,
            );
            return (
              <circle
                key={point.id}
                data-point="true"
                cx={cx}
                cy={cy}
                r="4"
                fill={definition.color}
              />
            );
          }
          const coordinates = segment
            .map((point) =>
              coordinate(
                point,
                series.totalCount,
                minimum,
                maximum,
              ).join(','),
            )
            .join(' ');
          return (
            <polyline
              key={`${segment[0]!.id}-${segment.at(-1)!.id}`}
              points={coordinates}
              fill="none"
              stroke={definition.color}
              strokeWidth="3"
              vectorEffect="non-scaling-stroke"
            />
          );
        })}
        {series.firstTimestamp !== null && (
          <text x={PADDING_X} y={HEIGHT - 8} textAnchor="start">
            {formatDateTime(series.firstTimestamp).slice(0, 10)}
          </text>
        )}
        {series.lastTimestamp !== null && (
          <text x={WIDTH - PADDING_X} y={HEIGHT - 8} textAnchor="end">
            {formatDateTime(series.lastTimestamp).slice(0, 10)}
          </text>
        )}
      </svg>
      <p className="chart-summary">
        {pointCountLabel(series.valueCount)} · мин. {valueLabel(series.minimum)} · макс. {' '}
        {valueLabel(series.maximum)} {definition.unit}
      </p>
    </figure>
  );
}

export function TelemetryChart({ measurements }: TelemetryChartProps) {
  return (
    <section className="panel panel--chart" aria-labelledby="chart-heading">
      <div className="panel__heading-row">
        <div>
          <p className="panel__eyebrow">Хронология для чтения тренда</p>
          <h2 id="chart-heading">Графики измерений</h2>
        </div>
      </div>
      {measurements.length === 0 ? (
        <p className="empty-copy">Нет данных для построения графика.</p>
      ) : (
        <div className="trend-grid">
          {METRICS.map((definition) => (
            <MetricChart
              key={definition.key}
              definition={definition}
              measurements={measurements}
            />
          ))}
        </div>
      )}
      <p className="panel__supporting">
        Пропуски не соединяются линией. Точные значения доступны в таблице ниже.
      </p>
    </section>
  );
}
