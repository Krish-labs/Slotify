import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';

interface Props {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  labelledBy?: string;
}

/*
 * Reason for custom dialog: native dialog styling fights the paper system,
 * but behavior follows the accessible pattern (Escape closes, focus moves in,
 * labelled heading, modal role).
 */
export function Dialog({ title, subtitle, onClose, children, labelledBy = 'dialog-title' }: Props) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    panelRef.current?.querySelector<HTMLElement>('button, input, select, textarea, a[href]')?.focus();
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="presentation" onClick={onClose}>
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto border border-[var(--rule-strong)] bg-[var(--paper-raised)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b-2 border-[var(--ink)] px-5 py-4">
          <div>
            <h2 id={labelledBy} className="font-display text-xl text-[var(--ink)]">
              {title}
            </h2>
            {subtitle && <p className="mt-1 text-sm text-[var(--ink-secondary)]">{subtitle}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="rounded border border-[var(--rule-strong)] p-2 text-[var(--ink)] hover:bg-[var(--paper-inset)]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}
