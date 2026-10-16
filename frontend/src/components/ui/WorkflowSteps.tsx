/*
 * Core product workflow, shown on Dashboard and Load Distribution so the
 * sequence is learned once: source rows move left to right toward export.
 * Reason for numbered ledger style: the workflow is a document pipeline,
 * not a marketing funnel, so it reads as numbered clauses.
 */

export const WORKFLOW_STEPS = [
  'Load Distribution',
  'Validate and Map',
  'Approve',
  'Generate Optimized Timetable',
  'Validate',
  'View Timetable',
  'Repair and Reoptimize',
  'Export',
] as const;

export function WorkflowSteps({ current = 0 }: { current?: number }) {
  return (
    <nav aria-label="Timetable workflow" className="paper-panel px-4 py-3">
      <p className="kicker">Workflow</p>
      <ol className="mt-2 flex flex-wrap gap-x-4 gap-y-2">
        {WORKFLOW_STEPS.map((step, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <li key={step} className="flex items-center gap-2 text-sm">
              <span
                aria-hidden="true"
                className={`flex h-6 w-6 items-center justify-center rounded-full border font-mono text-xs ${
                  active
                    ? 'border-[var(--ink)] bg-[var(--ink)] text-[var(--paper)]'
                    : done
                      ? 'border-[var(--ink)] text-[var(--ink)]'
                      : 'border-[var(--rule-strong)] text-[var(--ink-muted)]'
                }`}
              >
                {i + 1}
              </span>
              <span
                aria-current={active ? 'step' : undefined}
                className={active ? 'font-bold text-[var(--ink)]' : 'text-[var(--ink-secondary)]'}
              >
                {step}
              </span>
              {i < WORKFLOW_STEPS.length - 1 && (
                <span aria-hidden="true" className="text-[var(--ink-muted)]">
                  /
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
