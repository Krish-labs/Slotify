import type { ReactNode } from 'react';

type Tone = 'neutral' | 'valid' | 'invalid' | 'pending' | 'lab';

/*
 * Reason for monochrome badges: status must be readable without color.
 * Tone changes border weight and label, never hue alone. Icons and text
 * always accompany the badge.
 */
export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  const styles: Record<Tone, string> = {
    neutral:
      'border-[var(--rule-strong)] text-[var(--ink-secondary)] bg-[var(--paper-raised)]',
    valid: 'border-[var(--ink)] text-[var(--ink)] bg-[var(--paper-raised)]',
    invalid: 'border-[var(--ink)] bg-[var(--ink)] text-[var(--paper)]',
    pending:
      'border-dashed border-[var(--ink-muted)] text-[var(--ink-secondary)] bg-[var(--paper-raised)]',
    lab: 'border-[var(--ink)] text-[var(--ink)] bg-[var(--paper-inset)] font-mono',
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-semibold whitespace-nowrap ${styles[tone]}`}
    >
      {children}
    </span>
  );
}
