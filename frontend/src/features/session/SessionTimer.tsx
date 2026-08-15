import { useEffect, useState } from 'react';

import { formatDuration, sessionDurationMs } from '../../utils/duration';

export function SessionTimer({ startedAt }: { readonly startedAt: string }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <time className="session-timer" dateTime={startedAt} aria-label="Длительность активной сессии">
      {formatDuration(sessionDurationMs(startedAt, null, now))}
    </time>
  );
}
