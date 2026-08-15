import { useState, type FormEvent } from 'react';

import type { SessionStatus } from '../../api/types';
import { formatDateTime, toIsoFromLocalInput } from '../../utils/dateTime';
import { formatDuration, sessionDurationMs } from '../../utils/duration';
import type { SessionHistoryState } from './useSessionHistory';

interface SessionHistoryPanelProps {
  readonly history: SessionHistoryState;
}

const STATUS_LABELS: Readonly<Record<SessionStatus, string>> = {
  active: 'Активна',
  completed: 'Завершена',
  cancelled: 'Отменена',
};

function measurementCountLabel(count: number): string {
  const lastTwo = count % 100;
  const last = count % 10;
  const suffix =
    lastTwo >= 11 && lastTwo <= 14
      ? 'измерений'
      : last === 1
        ? 'измерение'
        : last >= 2 && last <= 4
          ? 'измерения'
          : 'измерений';
  return `${count} ${suffix}`;
}

export function SessionHistoryPanel({ history }: SessionHistoryPanelProps) {
  const [status, setStatus] = useState<SessionStatus | ''>('');
  const [startedFrom, setStartedFrom] = useState('');
  const [startedTo, setStartedTo] = useState('');
  const [filterError, setFilterError] = useState<string | null>(null);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fromIso = toIsoFromLocalInput(startedFrom);
    const toIso = toIsoFromLocalInput(startedTo);
    if (
      (startedFrom !== '' && fromIso === undefined) ||
      (startedTo !== '' && toIso === undefined)
    ) {
      setFilterError('Проверьте даты периода.');
      return;
    }
    if (fromIso !== undefined && toIso !== undefined && fromIso >= toIso) {
      setFilterError('Конец периода должен быть позже начала.');
      return;
    }
    setFilterError(null);
    history.setFilters({
      ...(status === '' ? {} : { status }),
      ...(fromIso === undefined ? {} : { startedFrom: fromIso }),
      ...(toIso === undefined ? {} : { startedTo: toIso }),
    });
  }

  return (
    <section className="panel panel--history" aria-labelledby="session-history-heading">
      <div className="panel__heading-row">
        <div>
          <p className="panel__eyebrow">Новейшие первыми</p>
          <h2 id="session-history-heading">История сессий</h2>
        </div>
        <span className="data-count">{history.items.length} / 100</span>
      </div>

      <form className="filter-grid" onSubmit={applyFilters}>
        <label htmlFor="session-status-filter">Статус сессии</label>
        <select
          id="session-status-filter"
          value={status}
          onChange={(event) => setStatus(event.target.value as SessionStatus | '')}
        >
          <option value="">Все</option>
          <option value="active">Активные</option>
          <option value="completed">Завершённые</option>
          <option value="cancelled">Отменённые</option>
        </select>
        <label htmlFor="session-started-from">Начало периода</label>
        <input
          id="session-started-from"
          type="datetime-local"
          value={startedFrom}
          onChange={(event) => setStartedFrom(event.target.value)}
        />
        <label htmlFor="session-started-to">Конец периода</label>
        <input
          id="session-started-to"
          type="datetime-local"
          value={startedTo}
          onChange={(event) => setStartedTo(event.target.value)}
        />
        <button className="button button--quiet" type="submit">
          Применить фильтры сессий
        </button>
      </form>
      {filterError !== null && (
        <p className="form-message form-message--error" role="alert">{filterError}</p>
      )}

      {history.status === 'idle' && (
        <p className="empty-copy">Выберите устройство для просмотра истории.</p>
      )}
      {history.status === 'loading' && (
        <p className="loading-copy" role="status">Загружаем сессии…</p>
      )}
      {history.status === 'ready' && history.items.length === 0 && (
        <p className="empty-copy">Сессии по этим условиям не найдены.</p>
      )}
      {history.error !== null && (
        <div className="form-message form-message--error" role="alert">
          <p>{history.error}</p>
          {history.status === 'error' && (
            <button className="button button--text" type="button" onClick={history.retry}>
              Повторить загрузку
            </button>
          )}
        </div>
      )}

      {history.items.length > 0 && (
        <ol className="session-list">
          {history.items.map((session) => {
            const selected = history.selectedSession?.id === session.id;
            return (
              <li key={session.id}>
                <button
                  className={`session-row${selected ? ' session-row--selected' : ''}`}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => history.selectSession(session.id)}
                >
                  <span>
                    <strong>Сессия №{session.id}</strong>
                    <span>{STATUS_LABELS[session.status]}</span>
                  </span>
                  <span>
                    <time dateTime={session.started_at}>
                      {formatDateTime(session.started_at)}
                    </time>
                    <span>Длительность: {formatDuration(sessionDurationMs(session.started_at, session.ended_at))}</span>
                    <span>{measurementCountLabel(session.sample_count)}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}

      {history.nextCursor !== null && (
        <button
          className="button button--quiet load-more"
          type="button"
          disabled={history.loadingMore}
          onClick={() => void history.loadMore()}
        >
          {history.loadingMore ? 'Загружаем…' : 'Загрузить ещё сессии'}
        </button>
      )}
      {history.items.length > 0 && history.nextCursor === null && (
        <p className="end-copy">
          {history.capped
            ? 'Достигнут безопасный предел: уточните фильтры.'
            : 'Все доступные сессии загружены.'}
        </p>
      )}
    </section>
  );
}
