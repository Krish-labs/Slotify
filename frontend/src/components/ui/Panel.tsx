import type { ReactNode } from 'react';

export function Panel({
  title,
  meta,
  actions,
  children,
}: {
  title: string;
  meta?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="paper-panel" aria-label={title}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rule)] px-4 py-3">
        <div>
          <h2 className="font-display text-lg text-[var(--ink)]">{title}</h2>
          {meta && <p className="text-sm text-[var(--ink-muted)]">{meta}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}
