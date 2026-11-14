import type { ReactNode } from 'react';

interface PanelProps {
  title: string;
  /** Optional controls rendered on the right of the title (e.g. toggles, buttons). */
  actions?: ReactNode;
  className?: string;
  id?: string;
  children?: ReactNode;
}

export function Panel({ title, actions, className, id, children }: PanelProps) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <section className={`panel ${className ?? ''}`} id={id} aria-labelledby={headingId}>
      <header className="panel__head">
        <h2 id={headingId}>{title}</h2>
        {actions && <div className="panel__actions">{actions}</div>}
      </header>
      {children}
    </section>
  );
}
