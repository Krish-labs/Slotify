import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

/*
 * Reason for ink-filled primary: on a grayscale paper system the strongest
 * hierarchy signal is solid ink, reserved for the one action per screen that
 * moves the workflow forward (for example Generate Optimized Timetable).
 */
export function Button({ variant = 'secondary', className = '', type, ...rest }: Props) {
  const base =
    'inline-flex items-center justify-center gap-2 rounded px-4 py-2 text-sm font-semibold transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-50';
  const styles: Record<Variant, string> = {
    primary: 'bg-[var(--ink)] text-[var(--paper)] border border-[var(--ink)] hover:opacity-90',
    secondary:
      'bg-[var(--paper-raised)] text-[var(--ink)] border border-[var(--rule-strong)] hover:bg-[var(--paper-inset)]',
    ghost: 'bg-transparent text-[var(--ink)] border border-transparent hover:bg-[var(--paper-inset)] underline underline-offset-4',
    danger:
      'bg-transparent text-[var(--ink)] border border-[var(--ink)] hover:bg-[var(--ink)] hover:text-[var(--paper)]',
  };
  return (
    <button type={type ?? 'button'} className={`${base} ${styles[variant]} ${className}`} {...rest} />
  );
}
