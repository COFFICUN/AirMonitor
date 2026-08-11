import type { AirMonitorApi } from '../../api/types';
import { useHealth } from './useHealth';

interface HealthPanelProps {
  readonly api: AirMonitorApi;
}

export function HealthPanel({ api }: HealthPanelProps) {
  const { state, refresh } = useHealth(api);

  return (
    <section className="panel panel--health" aria-labelledby="health-heading">
      <div className="panel__heading-row">
        <div>
          <p className="panel__eyebrow">Подключение</p>
          <h2 id="health-heading">Связь с системой</h2>
        </div>
        <span
          className={`status-mark status-mark--${state.status}`}
          aria-hidden="true"
        />
      </div>

      {state.status === 'loading' && (
        <p className="status-copy" role="status" aria-live="polite">
          Проверяем подключение…
        </p>
      )}

      {state.status === 'available' && state.data !== null && (
        <div className="status-copy" role="status" aria-live="polite">
          <strong>Сервис доступен</strong>
          <span>
            {state.data.service} · {state.data.version}
          </span>
        </div>
      )}

      {state.status === 'unavailable' && (
        <div className="status-copy" role="alert">
          <strong>Сервис недоступен</strong>
          <span>{state.message}</span>
          <button className="button button--quiet" type="button" onClick={refresh}>
            Повторить проверку
          </button>
        </div>
      )}
    </section>
  );
}
