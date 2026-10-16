import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Sun, Moon } from 'lucide-react';
import { WORKFLOW_STEPS } from '../components/ui/WorkflowSteps';

/*
 * Reading this as: B2B planning desk for department heads and faculty,
 * in a restrained paper ledger language, dial ENERGY 1 / RHYTHM 2 / MOTION 1.
 * Reason for the document structure: the product sells a verifiable pipeline
 * (source rows to printed timetable), so the landing reads as a contents page
 * with the workflow as the hero, not a feature grid.
 *
 * Reason for local theme state here: the landing is public and must render
 * even when no ThemeProvider wraps it (for example in tests). It mirrors the
 * persisted `theme` key used by the provider.
 */
export function Landing() {
  const [localTheme, setLocalTheme] = useState(() =>
    typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
      ? 'dark'
      : 'light',
  );
  const toggleLocalTheme = () => {
    const next = localTheme === 'light' ? 'dark' : 'light';
    setLocalTheme(next);
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(next);
    try {
      localStorage.setItem('theme', next);
    } catch {
      /* storage unavailable in some embeds */
    }
  };

  return (
    <div className="min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)]">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4">
          <div>
            <p className="kicker">Timetable Office</p>
            <p className="font-display text-2xl">Slotify</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleLocalTheme}
              aria-label={localTheme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
              className="rounded border border-[var(--rule-strong)] p-2 hover:bg-[var(--paper-inset)]"
            >
              {localTheme === 'light' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            </button>
            <Link
              to="/dashboard"
              className="inline-flex min-h-[44px] items-center rounded border border-[var(--ink)] bg-[var(--ink)] px-4 py-2 text-sm font-bold text-[var(--paper)]"
            >
              Open planner
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl space-y-10 px-4 py-10">
        <section aria-labelledby="landing-title" className="grid gap-8 md:grid-cols-12">
          <div className="md:col-span-7">
            <p className="kicker">E and TC Department, Academic Planning</p>
            <h1 id="landing-title" className="font-display mt-2 text-4xl leading-[1.05] md:text-5xl">
              Load in, validate, generate. Print a timetable the department trusts.
            </h1>
            <p className="mt-4 max-w-xl text-lg text-[var(--ink-secondary)]">
              Slotify keeps the Excel load distribution as the source of truth, maps every
              row to authoritative masters, then generates and validates the timetable before
              anyone teaches from it.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              <Link
                to="/dashboard"
                className="inline-flex min-h-[44px] items-center bg-[var(--ink)] px-5 py-2 text-sm font-bold text-[var(--paper)]"
              >
                Open the planning desk
              </Link>
              <Link
                to="/dashboard"
                className="inline-flex min-h-[44px] items-center border border-[var(--rule-strong)] px-5 py-2 text-sm font-semibold hover:bg-[var(--paper-inset)]"
              >
                Open load distribution
              </Link>
            </div>
            <dl className="mt-8 grid grid-cols-3 gap-4 border-t border-[var(--rule)] pt-4">
              {[
                ['Source first', 'Excel rows stay editable and auditable'],
                ['Mapped', 'No unmapped row reaches scheduling'],
                ['Validated', 'Conflicts read as plain clauses'],
              ].map(([term, def]) => (
                <div key={term}>
                  <dt className="font-mono text-xs uppercase tracking-widest text-[var(--ink-muted)]">{term}</dt>
                  <dd className="mt-1 text-sm text-[var(--ink-secondary)]">{def}</dd>
                </div>
              ))}
            </dl>
          </div>
          <aside aria-label="How the term moves" className="md:col-span-5">
            <div className="paper-panel p-0">
              <div className="border-b-2 border-[var(--ink)] px-4 py-3">
                <p className="kicker">Contents</p>
                <p className="font-display text-lg">One term, eight clauses</p>
              </div>
              <ol className="divide-y divide-[var(--rule)]">
                {WORKFLOW_STEPS.map((step, i) => (
                  <li key={step} className="flex items-baseline gap-3 px-4 py-2.5">
                    <span className="font-mono text-xs text-[var(--ink-muted)]">{String(i + 1).padStart(2, '0')}</span>
                    <span className={i === 3 ? 'font-bold' : ''}>{step}</span>
                    {i === 3 && (
                      <span className="ml-auto border border-[var(--ink)] bg-[var(--ink)] px-2 py-0.5 font-mono text-[0.65rem] uppercase tracking-widest text-[var(--paper)]">
                        Primary
                      </span>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          </aside>
        </section>

        <section aria-label="What you get" className="grid gap-4 md:grid-cols-3">
          {[
            {
              h: 'Spreadsheet you can defend',
              p: 'Edit Sr. No. to map rows to the right place. Invalid rows stay listed with counts and plain reasons, never silent.',
            },
            {
              h: 'Grids built for reading',
              p: 'Class, faculty, and master views share one day and time grid. Labs carry a hatch and LAB tag.',
            },
            {
              h: 'Exports are the deliverable',
              p: 'Class, faculty, master, resource, and change history exports leave as Excel for notice boards.',
            },
          ].map((c) => (
            <article key={c.h} className="paper-panel p-5">
              <h2 className="font-display text-xl">{c.h}</h2>
              <p className="mt-2 text-sm text-[var(--ink-secondary)]">{c.p}</p>
            </article>
          ))}
        </section>

        <footer className="border-t border-[var(--rule)] pt-4 text-sm text-[var(--ink-muted)]">
          <p>Faculty-first planner. Admin and HOD screens share the same paper, no separate identity.</p>
        </footer>
      </main>
    </div>
  );
}
