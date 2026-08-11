import type { HTMLAttributes, ReactNode } from 'react';

export function Card({ className = '', children, ...props }: HTMLAttributes<HTMLElement> & { readonly children: ReactNode }) {
  return <section className={`card${className ? ` ${className}` : ''}`} {...props}>{children}</section>;
}

export function MetricCard({ label, value, unit, hint }: { readonly label: string; readonly value: string; readonly unit: string; readonly hint?: string }) {
  return <article className="metric-card"><span className="metric-card__label">{label}</span><div><strong className="metric-card__value">{value}</strong><span className="metric-card__unit">{unit}</span></div>{hint && <small>{hint}</small>}</article>;
}
