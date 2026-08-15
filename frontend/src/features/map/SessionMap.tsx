import { useEffect, useMemo, useRef, useState } from 'react';

import type { SessionResponse } from '../../api/types';
import { createSessionMap, type SessionMapController } from './leafletAdapter';
import { mappableSessions } from './mapData';

interface SessionMapProps {
  readonly sessions: readonly SessionResponse[];
  readonly selectedSessionId: number | null;
  readonly onSelect: (sessionId: number) => void;
}

export function SessionMap({
  sessions,
  selectedSessionId,
  onSelect,
}: SessionMapProps) {
  const elementRef = useRef<HTMLDivElement | null>(null);
  const controllerRef = useRef<SessionMapController | null>(null);
  const [failed, setFailed] = useState(false);
  const points = useMemo(() => mappableSessions(sessions), [sessions]);
  const hasPoints = points.length > 0;

  useEffect(() => {
    if (!hasPoints || elementRef.current === null) {
      return;
    }
    try {
      setFailed(false);
      controllerRef.current = createSessionMap(elementRef.current);
    } catch {
      controllerRef.current = null;
      setFailed(true);
    }
    return () => {
      try {
        controllerRef.current?.destroy();
      } finally {
        controllerRef.current = null;
      }
    };
  }, [hasPoints]);

  useEffect(() => {
    if (controllerRef.current === null) {
      return;
    }
    try {
      controllerRef.current.update(points, selectedSessionId, onSelect);
    } catch {
      try {
        controllerRef.current.destroy();
      } finally {
        controllerRef.current = null;
        setFailed(true);
      }
    }
  }, [onSelect, points, selectedSessionId]);

  return (
    <section className="panel panel--map" aria-labelledby="session-map-heading">
      <div className="panel__heading-row">
        <div>
          <p className="panel__eyebrow">Реальные координаты</p>
          <h2 id="session-map-heading">Карта измерительных точек</h2>
        </div>
      </div>
      {!hasPoints && (
        <p className="empty-copy">Пока нет проведённых измерений с координатами.</p>
      )}
      {hasPoints && !failed && (
        <div
          ref={elementRef}
          className="session-map"
          role="region"
          aria-label="Интерактивная карта измерительных точек"
        />
      )}
      {failed && (
        <p className="form-message form-message--error" role="alert">
          Карта временно недоступна. Список сессий остаётся доступен.
        </p>
      )}
      <p className="panel__supporting">
        Каждая отметка соответствует одной сессии в одном месте. Для подложки нужны интернет-запросы к OpenStreetMap.
      </p>
    </section>
  );
}
