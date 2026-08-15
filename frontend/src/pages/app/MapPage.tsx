import { Link } from 'react-router';

import { useAppData } from '../../app/AppDataContext';
import { usePreferences } from '../../app/PreferencesContext';
import { EmptyState, LoadingSkeleton } from '../../components/ui/Feedback';
import { PageHeader } from '../../components/ui/Headings';
import { StatusBadge } from '../../components/ui/Status';
import { SessionMap } from '../../features/map/SessionMap';
import { mappableSessions } from '../../features/map/mapData';
import { formatDateTime } from '../../utils/dateTime';

const STATUS_LABELS = {
  active: 'Активна',
  completed: 'Завершена',
  cancelled: 'Отменена',
} as const;

function measurementCountLabel(count: number): string {
  const lastTwo = count % 100;
  const last = count % 10;
  if (lastTwo >= 11 && lastTwo <= 14) return `${count} измерений`;
  if (last === 1) return `${count} измерение`;
  if (last >= 2 && last <= 4) return `${count} измерения`;
  return `${count} измерений`;
}

function pointCountLabel(count: number): string {
  const lastTwo = count % 100;
  const last = count % 10;
  if (lastTwo >= 11 && lastTwo <= 14) return 'точек на карте';
  if (last === 1) return 'точка на карте';
  if (last >= 2 && last <= 4) return 'точки на карте';
  return 'точек на карте';
}

export default function MapPage() {
  const { sessionHistory } = useAppData();
  const { preferences, update } = usePreferences();
  const selected = sessionHistory.selectedSession;
  const points = mappableSessions(sessionHistory.items);

  return (
    <div className="app-page map-page">
      <PageHeader
        eyebrow="География наблюдений"
        title="Карта точек"
        description="Каждая отметка — одна измерительная сессия в одном месте. Линии между точками не строятся."
        actions={(
          <button
            className="button button--secondary"
            type="button"
            onClick={() => update({ mapTilesEnabled: !preferences.mapTilesEnabled })}
          >
            {preferences.mapTilesEnabled ? 'Отключить подложку' : 'Включить подложку'}
          </button>
        )}
      />
      <div className="map-toolbar">
        <label>
          Выбранная сессия
          <select
            value={selected?.id ?? ''}
            disabled={sessionHistory.items.length === 0}
            onChange={(event) => sessionHistory.selectSession(Number(event.target.value))}
          >
            {sessionHistory.items.map((session) => (
              <option key={session.id} value={session.id}>
                Сессия №{session.id} · {formatDateTime(session.started_at)}
              </option>
            ))}
          </select>
        </label>
        <div className="map-toolbar__summary" aria-live="polite">
          <strong>{points.length}</strong>
          <span>{pointCountLabel(points.length)}</span>
        </div>
      </div>
      <div className="point-map-layout">
        {sessionHistory.status === 'loading' ? (
          <div className="panel"><LoadingSkeleton label="Загружаем точки…" lines={4} /></div>
        ) : preferences.mapTilesEnabled ? (
          <SessionMap
            sessions={sessionHistory.items}
            selectedSessionId={selected?.id ?? null}
            onSelect={sessionHistory.selectSession}
          />
        ) : (
          <EmptyState
            title="Подложка карты отключена"
            description="Координаты не отправляются в OpenStreetMap. Список сессий и данные остаются доступны."
          />
        )}
        <aside className="card map-session-card" aria-live="polite">
          {selected ? (
            <>
              <div className="map-session-card__heading">
                <div><small>Выбранное место</small><h2>Точка сессии №{selected.id}</h2></div>
                <StatusBadge tone={selected.status === 'completed' ? 'success' : selected.status === 'active' ? 'info' : 'neutral'}>
                  {STATUS_LABELS[selected.status]}
                </StatusBadge>
              </div>
              <dl>
                <div><dt>Начало</dt><dd>{formatDateTime(selected.started_at)}</dd></div>
                <div><dt>Измерения</dt><dd>{measurementCountLabel(selected.sample_count)}</dd></div>
                <div><dt>Широта</dt><dd>{selected.latitude.toFixed(5)}</dd></div>
                <div><dt>Долгота</dt><dd>{selected.longitude.toFixed(5)}</dd></div>
              </dl>
              <p>Все показания этой сессии относятся к указанной географической точке.</p>
              <div className="button-row">
                <Link className="button button--primary" to="/app/data">Открыть данные</Link>
                <Link className="button button--secondary" to="/app/sessions">Все сессии</Link>
              </div>
            </>
          ) : (
            <EmptyState
              title="Точка не выбрана"
              description="Подключите устройство и проведите первое измерение — координаты появятся здесь."
              action={<Link className="button button--secondary" to="/app/measurement">Новое измерение</Link>}
            />
          )}
        </aside>
      </div>
      <p className="map-disclaimer">
        OpenStreetMap получает только обычные запросы тайлов. Браузерная геопозиция
        запрашивается приложением один раз — при старте новой сессии.
      </p>
    </div>
  );
}
