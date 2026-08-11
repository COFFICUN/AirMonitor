import { Link } from 'react-router';
import { useAppData } from '../../app/AppDataContext';
import { Card } from '../../components/ui/Card';
import { PageHeader } from '../../components/ui/Headings';
import { SessionHistoryPanel } from '../../features/history/SessionHistoryPanel';
import { formatDateTime } from '../../utils/dateTime';

export default function SessionsPage() {
  const { sessionHistory } = useAppData();
  const selected = sessionHistory.selectedSession;
  return <div className="app-page">
    <PageHeader eyebrow="История измерений" title="Мои сессии" description="Каждая сессия — отдельная точка исследования. Фильтры и последовательная загрузка помогают работать с историей без нумерации страниц." />
    {selected && <Card className="selected-session-actions"><div><small>Выбрана сессия</small><strong>№{selected.id} · {formatDateTime(selected.started_at)}</strong></div><div className="button-row"><Link className="button button--secondary" to="/app/map">Открыть на карте</Link><Link className="button button--primary" to="/app/data">Открыть данные</Link></div></Card>}
    <SessionHistoryPanel history={sessionHistory} />
  </div>;
}
