import { useEffect, useRef, useState } from 'react';

import { formatDateTime } from '../../utils/dateTime';
import { SessionTimer } from './SessionTimer';
import type { ActiveSessionState } from './useActiveSession';

interface SessionPanelProps {
  readonly session: ActiveSessionState;
  readonly deviceActive: boolean;
}

export function SessionPanel({ session, deviceActive }: SessionPanelProps) {
  const [confirmCancel, setConfirmCancel] = useState(false);
  const cancelTriggerRef = useRef<HTMLButtonElement | null>(null);
  const confirmButtonRef = useRef<HTMLButtonElement | null>(null);
  const returnButtonRef = useRef<HTMLButtonElement | null>(null);
  const busy = session.status === 'loading' || session.status === 'working';

  useEffect(() => {
    if (!confirmCancel) {
      return;
    }
    const trigger = cancelTriggerRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    returnButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setConfirmCancel(false);
        return;
      }
      if (event.key !== 'Tab') {
        return;
      }
      if (
        event.shiftKey &&
        document.activeElement === confirmButtonRef.current
      ) {
        event.preventDefault();
        returnButtonRef.current?.focus();
      } else if (
        !event.shiftKey &&
        document.activeElement === returnButtonRef.current
      ) {
        event.preventDefault();
        confirmButtonRef.current?.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = previousOverflow;
      trigger?.focus();
    };
  }, [confirmCancel]);

  async function handleConfirmedCancel() {
    await session.cancel();
    setConfirmCancel(false);
  }

  return (
    <section className="panel panel--session" aria-labelledby="session-heading">
      <div className="panel__heading-row">
        <div>
          <p className="panel__eyebrow">Полевое измерение</p>
          <h2 id="session-heading">Активная сессия</h2>
        </div>
        {session.activeSession !== null && (
          <span className="status-badge status-badge--active">Идёт сбор</span>
        )}
      </div>

      <div aria-busy={busy}>
        {session.status === 'idle' && (
          <p className="empty-copy">Выберите устройство для управления сессией.</p>
        )}
        {session.status === 'loading' && (
          <p className="loading-copy" role="status">Проверяем активную сессию…</p>
        )}
        {session.status !== 'idle' && session.status !== 'loading' && (
          session.activeSession === null ? (
            <div className="session-empty">
              <p className="session-title">Нет активной сессии</p>
              <p className="panel__supporting">
                Координаты будут запрошены только после запуска.
              </p>
              {!deviceActive && (
                <p className="form-message">Сначала активируйте устройство.</p>
              )}
              <button
                className="button"
                type="button"
                disabled={busy || !deviceActive}
                onClick={() => void session.start()}
              >
                Начать сессию
              </button>
            </div>
          ) : (
            <div className="session-summary">
              <p className="session-title">
                Сессия №{session.activeSession.id} активна
              </p>
              <dl className="compact-facts">
                <div>
                  <dt>Начало</dt>
                  <dd>{formatDateTime(session.activeSession.started_at)}</dd>
                </div>
                <div>
                  <dt>Длительность</dt>
                  <dd><SessionTimer startedAt={session.activeSession.started_at} /></dd>
                </div>
                <div>
                  <dt>Координаты</dt>
                  <dd>
                    {session.activeSession.latitude.toFixed(5)}, {' '}
                    {session.activeSession.longitude.toFixed(5)}
                  </dd>
                </div>
              </dl>
              <div className="button-row">
                <button
                  className="button"
                  type="button"
                  disabled={busy}
                  onClick={() => void session.complete()}
                >
                  Завершить
                </button>
                <button
                  ref={cancelTriggerRef}
                  className="button button--danger"
                  type="button"
                  disabled={busy}
                  onClick={() => setConfirmCancel(true)}
                >
                  Отменить
                </button>
              </div>
            </div>
          )
        )}
      </div>

      {session.locationError !== null && (
        <p className="form-message form-message--error" role="alert">
          {session.locationError}
        </p>
      )}
      {session.error !== null && (
        <div className="form-message form-message--error" role="alert">
          <p>{session.error}</p>
          <button className="button button--text" type="button" onClick={session.refresh}>
            Повторить
          </button>
        </div>
      )}

      {confirmCancel && (
        <div className="dialog-backdrop">
          <div
            className="confirm-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="cancel-session-title"
            aria-describedby="cancel-session-description"
          >
            <h3 id="cancel-session-title">Отменить активную сессию?</h3>
            <p id="cancel-session-description">Отмена сохранит сессию со статусом «Отменена».</p>
            <div className="button-row">
              <button
                ref={confirmButtonRef}
                className="button button--danger"
                type="button"
                onClick={() => void handleConfirmedCancel()}
              >
                Подтвердить отмену
              </button>
              <button
                ref={returnButtonRef}
                className="button button--quiet"
                type="button"
                onClick={() => setConfirmCancel(false)}
              >
                Вернуться
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
