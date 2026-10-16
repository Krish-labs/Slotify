import { Badge } from './Badge';
import { EmptyState } from './States';
import { GRID_DAYS, type GridEntry, type GridPeriod } from './timetable-constants';

export type { GridEntry };

/*
 * Reason for the left-rule plus hatch system: practical sessions must be
 * distinguishable without color, in print, and in dark paper. Theory uses a
 * solid ink rule on plain paper, practical uses the same rule on a hatched
 * inset plus a mono LAB tag. The grid keeps period and time in mono so the
 * eye scans down the fixed left column.
 */
export function TimetableGrid({ entries, caption, periods: suppliedPeriods = [] }: { entries: GridEntry[]; caption: string; periods?: GridPeriod[] }) {
  if (!entries.length) {
    return (
      <div className="paper-panel">
        <EmptyState
          title="No sessions placed yet"
          description="Generate a timetable version first. Empty cells mean unassigned periods, not missing data."
        />
      </div>
    );
  }

  const byCell = new Map<string, GridEntry[]>();
  for (const entry of entries) {
    const key = `${entry.day_of_week}-${entry.period_number}`;
    byCell.set(key, [...(byCell.get(key) ?? []), entry]);
  }
  const periodByNumber = new Map<number, GridPeriod>();
  for (const period of suppliedPeriods) periodByNumber.set(period.period_number, period);
  for (const entry of entries) {
    if (!periodByNumber.has(entry.period_number)) {
      periodByNumber.set(entry.period_number, {
        period_number: entry.period_number,
        start_time: entry.start_time,
        end_time: entry.end_time,
      });
    }
  }
  const periods = [...periodByNumber.values()].sort((a, b) => a.period_number - b.period_number);

  return (
    <div className="paper-panel overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="tt-grid min-w-[960px]" aria-label={caption}>
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              <th scope="col" className="w-36 text-left">
                Period
              </th>
              {GRID_DAYS.map((d) => (
                <th key={d} scope="col" className="text-center">
                  {d}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {periods.map((p) => (
              <tr key={p.period_number}>
                <th scope="row" className="w-36 bg-[var(--paper-raised)] p-3 text-left align-top">
                  <span className="font-mono text-sm font-semibold text-[var(--ink)]">P{p.period_number}</span>
                  <br />
                  <span className="font-mono text-xs text-[var(--ink-muted)]">
                    {p.start_time && p.end_time ? `${p.start_time.slice(0, 5)} to ${p.end_time.slice(0, 5)}` : 'Template slot'}
                  </span>
                </th>
                {GRID_DAYS.map((day, di) => {
                    const cellEntries = byCell.get(`${di}-${p.period_number}`) ?? [];
                   if (!cellEntries.length) {
                    return (
                      <td key={day} className="p-2 align-top">
                        <span aria-hidden="true" className="block py-4 text-center text-[var(--ink-muted)]">
                          -
                        </span>
                        <span className="sr-only">Free period</span>
                      </td>
                    );
                   }
                   return (
                     <td key={day} className="p-2 align-top">
                       <div className="space-y-2">
                         {cellEntries.map((entry) => {
                           const practical = entry.session_type === 'PRACTICAL' || entry.session_type === 'P';
                           return (
                             <div key={entry.id} className={practical ? 'tt-cell-practical p-2' : 'tt-cell-lecture p-2'}>
                               <p className="text-sm font-bold leading-snug text-[var(--ink)]">{entry.subject_label}</p>
                               <p className="mt-0.5 text-xs text-[var(--ink-secondary)]">{entry.line_two}</p>
                               {entry.line_three && <p className="font-mono text-xs text-[var(--ink-muted)]">{entry.line_three}</p>}
                               <p className="mt-1 flex flex-wrap items-center gap-1">
                                 <Badge tone="lab">{practical ? 'LAB' : 'LEC'}</Badge>
                                 {entry.batch_label && <Badge tone="neutral">{entry.batch_label}</Badge>}
                               </p>
                             </div>
                           );
                         })}
                       </div>
                     </td>
                   );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
