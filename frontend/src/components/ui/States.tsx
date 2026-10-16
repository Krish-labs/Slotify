import type { ReactNode } from 'react';

/* Required states per antislop R-27: every data view gets empty, loading, error. */

export function LoadingState({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="paper-inset p-8 text-center" role="status" aria-live="polite">
      <p className="font-mono text-xs uppercase tracking-widest text-[var(--ink-muted)]">{label}</p>
      <p className="mt-2 font-display text-lg text-[var(--ink)]">Setting the type…</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="p-8 text-center">
      <p className="kicker">Empty</p>
      <p className="mt-2 font-display text-xl text-[var(--ink)]">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-[var(--ink-secondary)]">{description}</p>
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function ErrorState({ title, description, retry, action }: { title: string; description: string; retry?: ReactNode; action?: ReactNode }) {
  return (
    <div className="p-8 text-center" role="alert">
      <p className="kicker">Error</p>
      <p className="mt-2 font-display text-xl text-[var(--ink)]">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-[var(--ink-secondary)]">{description}</p>
      {retry && <div className="mt-4 flex justify-center">{retry}</div>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}
