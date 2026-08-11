import { useState, type FormEvent } from 'react';

import { toIsoFromLocalInput } from '../../utils/dateTime';
import { MeasurementTable } from './MeasurementTable';
import type { MeasurementHistoryState } from './useMeasurementHistory';

interface MeasurementHistoryPanelProps {
  readonly history: MeasurementHistoryState;
  readonly sessionId: number | null;
}

export function MeasurementHistoryPanel({
  history,
  sessionId,
}: MeasurementHistoryPanelProps) {
  const [measuredFrom, setMeasuredFrom] = useState('');
  const [measuredTo, setMeasuredTo] = useState('');
  const [filterError, setFilterError] = useState<string | null>(null);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fromIso = toIsoFromLocalInput(measuredFrom);
    const toIso = toIsoFromLocalInput(measuredTo);
    if (
      (measuredFrom !== '' && fromIso === undefined) ||
      (measuredTo !== '' && toIso === undefined)
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
      ...(fromIso === undefined ? {} : { measuredFrom: fromIso }),
      ...(toIso === undefined ? {} : { measuredTo: toIso }),
    });
  }

  return (
    <section className="panel panel--measurements" aria-labelledby="measurement-history-heading">
      <div className="panel__heading-row">
        <div>
          <p className="panel__eyebrow">
            {sessionId === null ? 'Сессия не выбрана' : `Сессия №${sessionId}`}
          </p>
          <h2 id="measurement-history-heading">История измерений</h2>
        </div>
        <span className="data-count">{history.items.length} / 500</span>
      </div>

      <form className="filter-grid filter-grid--measurements" onSubmit={applyFilters}>
        <label htmlFor="measurement-from">Измерено от</label>
        <input
          id="measurement-from"
          type="datetime-local"
          value={measuredFrom}
          disabled={sessionId === null}
          onChange={(event) => setMeasuredFrom(event.target.value)}
        />
        <label htmlFor="measurement-to">Измерено до</label>
        <input
          id="measurement-to"
          type="datetime-local"
          value={measuredTo}
          disabled={sessionId === null}
          onChange={(event) => setMeasuredTo(event.target.value)}
        />
        <button
          className="button button--quiet"
          type="submit"
          disabled={sessionId === null}
        >
          Применить фильтры измерений
        </button>
      </form>
      {filterError !== null && (
        <p className="form-message form-message--error" role="alert">{filterError}</p>
      )}

      {history.status === 'idle' && (
        <p className="empty-copy">Выберите сессию в истории.</p>
      )}
      {history.status === 'loading' && (
        <p className="loading-copy" role="status">Загружаем измерения…</p>
      )}
      {history.status === 'ready' && history.items.length === 0 && (
        <p className="empty-copy">В этой сессии нет измерений по заданному периоду.</p>
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
        <MeasurementTable measurements={history.items} />
      )}

      {history.nextCursor !== null && (
        <button
          className="button button--quiet load-more"
          type="button"
          disabled={history.loadingMore}
          onClick={() => void history.loadMore()}
        >
          {history.loadingMore ? 'Загружаем…' : 'Загрузить ещё измерения'}
        </button>
      )}
      {history.items.length > 0 && history.nextCursor === null && (
        <p className="end-copy">
          {history.capped
            ? 'Достигнут безопасный предел: уточните период.'
            : 'Все доступные измерения загружены.'}
        </p>
      )}
    </section>
  );
}
