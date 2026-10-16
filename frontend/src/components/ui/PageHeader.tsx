import type { ReactNode } from 'react';

interface Props {
  kicker: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}

/*
 * Reason for kicker plus serif title: every operational page gets the same
 * editorial masthead, so hierarchy is learned once and reused everywhere.
 */
export function PageHeader({ kicker, title, description, actions }: Props) {
  return (
    <div className="rule-top pt-4">
      <p className="kicker">{kicker}</p>
      <div className="mt-1 flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl">
          <h1 className="font-display text-3xl leading-tight text-[var(--ink)]">{title}</h1>
          {description && (
            <p className="mt-1 text-[0.95rem] text-[var(--ink-secondary)]">{description}</p>
          )}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
