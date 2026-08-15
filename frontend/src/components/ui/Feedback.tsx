import type { ReactNode } from 'react';
import { Button } from './Button';

export function LoadingSkeleton({ label = 'Загружаем данные…', lines = 3 }: { readonly label?: string; readonly lines?: number }) {
  return <div className="loading-skeleton" role="status" aria-label={label}>{Array.from({ length: lines }, (_, index) => <span key={index} />)}<span className="visually-hidden">{label}</span></div>;
}

export function EmptyState({ title, description, action }: { readonly title: string; readonly description: string; readonly action?: ReactNode }) {
  return <div className="empty-state"><span className="empty-state__icon" aria-hidden="true">○</span><strong>{title}</strong><p>{description}</p>{action}</div>;
}

export function ErrorState({ title = 'Не удалось загрузить данные', message, onRetry }: { readonly title?: string; readonly message: string; readonly onRetry?: () => void }) {
  return <div className="error-state" role="alert"><strong>{title}</strong><p>{message}</p>{onRetry && <Button variant="secondary" onClick={onRetry}>Повторить</Button>}</div>;
}
