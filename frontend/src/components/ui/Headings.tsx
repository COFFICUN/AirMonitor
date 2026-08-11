import type { ReactNode } from 'react';

export function PageHeader({ eyebrow, title, description, actions }: { readonly eyebrow?: string; readonly title: string; readonly description?: string; readonly actions?: ReactNode }) {
  return <header className="page-header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description && <p>{description}</p>}</div>{actions && <div className="page-header__actions">{actions}</div>}</header>;
}

export function SectionHeader({ title, description, aside }: { readonly title: string; readonly description?: string; readonly aside?: ReactNode }) {
  return <div className="section-header"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{aside}</div>;
}
