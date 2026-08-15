const FORMATTERS = {
  '24h': new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Asia/Almaty', day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }),
  '12h': new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Asia/Almaty', day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true,
  }),
} as const;

function currentTimeFormat(): keyof typeof FORMATTERS {
  return typeof document !== 'undefined' && document.documentElement.dataset.timeFormat === '12h' ? '12h' : '24h';
}

export function formatDateTime(value: string | null): string {
  if (value === null) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Некорректная дата' : FORMATTERS[currentTimeFormat()].format(date);
}

export function toIsoFromLocalInput(value: string): string | undefined {
  if (value === '') return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}
