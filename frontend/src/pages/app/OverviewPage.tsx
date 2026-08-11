import { lazy, Suspense } from 'react';
import { Link } from 'react-router';
import { useAppData } from '../../app/AppDataContext';
import { usePreferences } from '../../app/PreferencesContext';
import { AppErrorBoundary } from '../../components/AppErrorBoundary';
import { Card, MetricCard } from '../../components/ui/Card';
import { EmptyState, ErrorState, LoadingSkeleton } from '../../components/ui/Feedback';
import { PageHeader, SectionHeader } from '../../components/ui/Headings';
import { AirQualityIndicator, StatusBadge } from '../../components/ui/Status';
import { TelemetryChart } from '../../features/chart/TelemetryChart';
import { formatDateTime } from '../../utils/dateTime';

const SessionMap = lazy(() => import('../../features/map/SessionMap').then((module) => ({ default: module.SessionMap })));
const number = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const value = (input: number | null) => input === null ? '—' : number.format(input);

export default function OverviewPage() {
  const { selection, health, refreshHealth, activeSession, liveTelemetry, sessionHistory, measurementHistory } = useAppData();
  const { preferences } = usePreferences();
  const latest = liveTelemetry.latest;
  return <div className="app-page overview-page">
    <PageHeader eyebrow="Личный обзор" title="Добрый день!" description="Здесь собраны устройство, текущая сессия и последние реальные измерения." actions={<Link className="button button--signal" to="/app/measurement">{activeSession.activeSession ? 'Продолжить измерение' : 'Начать измерение'}</Link>} />
    <div className="overview-status-grid">
      <Card className="overview-status-card"><span>Система</span>{health.status === 'loading' ? <LoadingSkeleton lines={1} /> : health.status === 'available' ? <><StatusBadge tone="success">Доступна</StatusBadge><small>{health.data?.version}</small></> : <ErrorState message={health.message ?? 'Нет связи.'} onRetry={refreshHealth} />}</Card>
      <Card className="overview-status-card"><span>Устройство</span>{selection.status === 'loading' ? <LoadingSkeleton lines={1} /> : selection.device ? <><strong>{selection.device.name ?? selection.device.device_uid}</strong><StatusBadge tone={selection.device.is_active ? 'success' : 'warning'}>{selection.device.is_active ? 'Активно' : 'Неактивно'}</StatusBadge></> : <><strong>Не выбрано</strong><Link className="text-link" to="/app/device">Подключить</Link></>}</Card>
      <Card className="overview-status-card"><span>Сессия</span>{activeSession.activeSession ? <><strong>№{activeSession.activeSession.id}</strong><StatusBadge tone="info">Идёт измерение</StatusBadge></> : <><strong>Нет активной</strong><span>Можно измерить новую точку</span></>}</Card>
    </div>

    <section className="app-section" aria-labelledby="latest-heading"><SectionHeader title="Последние показания" description={latest ? `Измерено ${formatDateTime(latest.measured_at)}` : 'Обновляются автоматически после выбора устройства.'} aside={<AirQualityIndicator value={latest?.pm25 ?? null} />} />
      {liveTelemetry.status === 'loading' && <LoadingSkeleton lines={3} />}
      {liveTelemetry.status === 'error' && latest === null && <ErrorState message={liveTelemetry.error ?? 'Не удалось получить измерение.'} />}
      {(liveTelemetry.status === 'idle' || liveTelemetry.status === 'empty') && latest === null && <EmptyState title="Показаний пока нет" description={selection.device ? 'Дождитесь первой записи от датчика.' : 'Сначала подключите устройство.'} action={<Link className="button button--secondary" to="/app/device">Моё устройство</Link>} />}
      {latest && <><div className="metric-grid"><MetricCard label="PM1.0" value={value(latest.pm1)} unit="мкг/м³" /><MetricCard label="PM2.5" value={value(latest.pm25)} unit="мкг/м³" /><MetricCard label="PM10" value={value(latest.pm10)} unit="мкг/м³" /><MetricCard label="Температура" value={value(latest.temperature)} unit="°C" /><MetricCard label="Влажность" value={value(latest.humidity)} unit="%" /></div><p className={`freshness-note${liveTelemetry.isStale ? ' freshness-note--stale' : ''}`}>{liveTelemetry.isStale ? 'Обновления задерживаются — показано последнее успешное значение.' : `Последнее обновление: ${liveTelemetry.lastSuccessfulAt ? formatDateTime(liveTelemetry.lastSuccessfulAt.toISOString()) : '—'}`}</p></>}
    </section>

    <div className="overview-content-grid"><AppErrorBoundary label="График последних измерений"><TelemetryChart measurements={measurementHistory.items} /></AppErrorBoundary><AppErrorBoundary label="Карта последних сессий">{preferences.mapTilesEnabled ? <Suspense fallback={<LoadingSkeleton label="Загружаем карту…" lines={3} />}><SessionMap sessions={sessionHistory.items} selectedSessionId={sessionHistory.selectedSession?.id ?? null} onSelect={sessionHistory.selectSession} /></Suspense> : <EmptyState title="Подложка карты отключена" description="Её можно включить в настройках. Данные сессий при этом остаются доступны." action={<Link className="button button--secondary" to="/app/settings">Открыть настройки</Link>} />}</AppErrorBoundary></div>
    <section className="app-section" aria-labelledby="recent-heading"><SectionHeader title="Недавние сессии" description="Каждая сессия относится к отдельной географической точке." aside={<Link className="text-link text-link--arrow" to="/app/sessions">Все сессии</Link>} />{sessionHistory.status === 'loading' ? <LoadingSkeleton /> : sessionHistory.items.length === 0 ? <EmptyState title="История ещё пуста" description="Завершите первое измерение, и сессия появится здесь." /> : <div className="recent-session-list">{sessionHistory.items.slice(0, 3).map((session) => <Link key={session.id} to="/app/sessions"><span><strong>Сессия №{session.id}</strong><small>{formatDateTime(session.started_at)}</small></span><StatusBadge tone={session.status === 'completed' ? 'success' : session.status === 'active' ? 'info' : 'neutral'}>{session.status === 'completed' ? 'Завершена' : session.status === 'active' ? 'Активна' : 'Отменена'}</StatusBadge></Link>)}</div>}</section>
  </div>;
}
