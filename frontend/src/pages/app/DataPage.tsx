import { useMemo, useState } from 'react';
import { useAppData } from '../../app/AppDataContext';
import { MetricCard } from '../../components/ui/Card';
import { PageHeader, SectionHeader } from '../../components/ui/Headings';
import { TelemetryChart } from '../../features/chart/TelemetryChart';
import { DATA_METRICS, metricValues, type DataMetricKey } from '../../features/data/metrics';
import { calculateStatistics } from '../../features/data/statistics';
import { MeasurementHistoryPanel } from '../../features/history/MeasurementHistoryPanel';
import { formatDateTime } from '../../utils/dateTime';

const format = (value: number | null) => value === null ? '—' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(value);
export default function DataPage() {
  const { sessionHistory, measurementHistory } = useAppData();
  const [metricKey, setMetricKey] = useState<DataMetricKey>('pm25');
  const metric = DATA_METRICS.find(({ key }) => key === metricKey) ?? DATA_METRICS[0]!;
  const statistics = useMemo(
    () => calculateStatistics(metricValues(measurementHistory.items, metricKey)),
    [measurementHistory.items, metricKey],
  );

  return <div className="app-page">
    <PageHeader eyebrow="Серия в одной точке" title="Данные" description="Изучайте, как менялись показатели во времени внутри выбранной сессии. Таблица сохраняет точный порядок API, а график показывает копию от ранних значений к поздним." />
    <div className="data-toolbar">
      <label>Сессия
        <select value={sessionHistory.selectedSession?.id ?? ''} disabled={sessionHistory.items.length === 0} onChange={(event) => sessionHistory.selectSession(Number(event.target.value))}>
          {sessionHistory.items.map((session) => <option key={session.id} value={session.id}>Сессия №{session.id} · {formatDateTime(session.started_at)}</option>)}
        </select>
      </label>
      <label>Метрика для статистики
        <select value={metricKey} onChange={(event) => setMetricKey(event.target.value as DataMetricKey)}>
          {DATA_METRICS.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
        </select>
      </label>
    </div>
    <section className="app-section">
      <SectionHeader title={`Статистика ${metric.label}`} description="Рассчитана только по уже загруженной ограниченной выборке; отсутствующие значения исключаются." />
      <div className="statistics-grid"><MetricCard label="Количество" value={String(statistics.count)} unit="измерений" /><MetricCard label="Минимум" value={format(statistics.minimum)} unit={metric.unit} /><MetricCard label="Максимум" value={format(statistics.maximum)} unit={metric.unit} /><MetricCard label="Среднее" value={format(statistics.mean)} unit={metric.unit} /><MetricCard label="Медиана" value={format(statistics.median)} unit={metric.unit} /></div>
    </section>
    <TelemetryChart measurements={measurementHistory.items} />
    <MeasurementHistoryPanel history={measurementHistory} sessionId={sessionHistory.selectedSession?.id ?? null} />
  </div>;
}
