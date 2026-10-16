import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { academicTermApi, leaveApi, loadApi, timetableApi } from '../api';
import { PageHeader } from '../components/ui/PageHeader';
import { Panel } from '../components/ui/Panel';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States';
import { latestReadableVersion } from '../utils/timetable';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

const SESSION_SEGMENTS = [
  { key: 'theory_hours', label: 'Theory', bar: 'bg-[var(--ink)]' },
  { key: 'practical_hours', label: 'Practical', bar: 'bg-amber-500' },
  { key: 'tutorial_hours', label: 'Tutorial', bar: 'bg-[var(--ink-muted)]' },
  { key: 'project_hours', label: 'Project', bar: 'bg-amber-200' },
] as const;

/*
 * Reason for this composition: analytics here is a reading of the ledger,
 * not a separate BI product. Every figure is a counted row with its target
 * in text beside it (bullet-chart discipline: number + target, color only
 * as supplement), and every bar chart is followed by its data table so a
 * screen reader or a printed circular gets the same facts. Motion stays at
 * hover/focus per DESIGN.md MOTION 1.
 */
export function Analytics() {
  const [timetableId, setTimetableId] = useState('');

  const termsQuery = useQuery({
    queryKey: ['academicTerms', { page_size: 100 }],
    queryFn: () => academicTermApi.list({ page_size: 100 }),
  });
  const terms = termsQuery.data;
  const currentTerm =
    terms?.items.find((t) => t.is_current) ?? terms?.items[0];

  const timetablesQuery = useQuery({
    queryKey: ['timetables'],
    queryFn: () => timetableApi.list(),
  });
  const timetables = useMemo(
    () => timetablesQuery.data?.timetables ?? [],
    [timetablesQuery.data],
  );
  const effectiveTimetableId = timetableId || timetables[0]?.id || '';

  const loadSummaryQuery = useQuery({
    queryKey: ['loadSummary', currentTerm?.id],
    queryFn: () => loadApi.getLoadSummary(currentTerm!.id),
    enabled: !!currentTerm?.id,
  });

  const versionQuery = useQuery({
    queryKey: ['analyticsVersion', effectiveTimetableId],
    queryFn: async () => {
      if (!effectiveTimetableId) return null;
      const versions = await timetableApi.listVersions(effectiveTimetableId);
       const latest = latestReadableVersion(versions.versions ?? []);
      if (!latest) return null;
      const full = await timetableApi.getVersion(effectiveTimetableId, latest.id);
      return { latest, entries: full?.entries ?? [] };
    },
    enabled: !!effectiveTimetableId,
  });

  const leavesQuery = useQuery({
    queryKey: ['leaves', 'pending'],
    queryFn: () => leaveApi.list({ status: 'PENDING' }),
  });

  const loadSummary = loadSummaryQuery.data;
  const entries = useMemo(
    () => versionQuery.data?.entries ?? [],
    [versionQuery.data],
  );

  const sessionTypeTotals = useMemo(() => {
    const totals: Record<string, number> = {
      theory_hours: 0,
      practical_hours: 0,
      tutorial_hours: 0,
      project_hours: 0,
    };
    for (const f of loadSummary?.faculty_summary ?? []) {
      totals.theory_hours += f.theory_hours;
      totals.practical_hours += f.practical_hours;
      totals.tutorial_hours += f.tutorial_hours;
      totals.project_hours += f.project_hours;
    }
    return totals;
  }, [loadSummary]);
  const totalLoadHours = Object.values(sessionTypeTotals).reduce((a, b) => a + b, 0);

  const perDay = useMemo(() => {
    const counts = [0, 0, 0, 0, 0, 0];
    for (const e of entries) {
      if (e.day_of_week >= 0 && e.day_of_week <= 5) counts[e.day_of_week] += 1;
    }
    return counts;
  }, [entries]);
  const maxDay = Math.max(1, ...perDay);

  const topFaculty = useMemo(
    () =>
      [...(loadSummary?.faculty_summary ?? [])]
        .sort((a, b) => b.total_hours - a.total_hours)
        .slice(0, 8),
    [loadSummary],
  );
  const maxFacultyHours = Math.max(1, ...topFaculty.map((f) => f.total_hours));

  if (termsQuery.isLoading || timetablesQuery.isLoading || loadSummaryQuery.isLoading || versionQuery.isLoading || leavesQuery.isLoading) {
    return <LoadingState label="Loading analytics" />;
  }
  if (termsQuery.error || timetablesQuery.error || loadSummaryQuery.error || versionQuery.error || leavesQuery.error) {
    return (
      <ErrorState
        title="Analytics did not load"
        description="Timetable or load summary data failed. Retry, then check Load Distribution for the source of truth."
        retry={
          <Button
            onClick={() =>
              Promise.all([
                 termsQuery.refetch(),
                 timetablesQuery.refetch(),
                loadSummaryQuery.refetch(),
                versionQuery.refetch(),
                leavesQuery.refetch(),
              ])
            }
          >
            Retry loading analytics
          </Button>
        }
      />
    );
  }

  if (!currentTerm) {
    return <EmptyState title="No academic term is available" description="Set a current academic term before loading planning analytics." />;
  }

  const facultyCount = loadSummary?.faculty_summary.length ?? 0;
  const subjectCount = loadSummary?.subject_summary.length ?? 0;
  const pendingLeaves = leavesQuery.data?.leaves?.length ?? 0;

  return (
    <div className="space-y-5">
      <PageHeader
        kicker={
          currentTerm
            ? `${currentTerm.academic_year} / Semester ${currentTerm.semester}`
            : 'Term'
        }
        title="Analytics"
        description="Counted rows from the current term: sessions filed, load by type, and who carries it."
        actions={
          timetables.length > 0 ? (
            <label className="inline-flex min-h-[44px] items-center gap-2 text-sm">
              <span className="field-label sr-only">Timetable under analysis</span>
              <select
                value={effectiveTimetableId}
                onChange={(e) => setTimetableId(e.target.value)}
                className="field-select"
                aria-label="Timetable under analysis"
              >
                {timetables.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.academic_year} Sem {t.semester})
                  </option>
                ))}
              </select>
            </label>
          ) : undefined
        }
      />

      <div className="grid gap-4 md:grid-cols-4">
        {[
          ['Sessions filed', String(entries.length), versionQuery.data ? `Version ${versionQuery.data.latest.version_number} · ${versionQuery.data.latest.status}` : 'No version filed'],
          ['Faculty on load', String(facultyCount), `${totalLoadHours} hours across ${subjectCount} subjects`],
          ['Load hours', String(totalLoadHours), 'Theory + practical + tutorial + project'],
          ['Leaves pending', String(pendingLeaves), 'Need a decision'],
        ].map(([label, value, sub]) => (
          <div key={label} className="paper-panel border-t-2 border-t-[var(--ink)] p-4">
            <p className="font-mono text-xs uppercase tracking-widest text-[var(--ink-muted)]">{label}</p>
            <p className="font-display mt-1 text-4xl">{value}</p>
            <p className="mt-1 text-sm text-[var(--ink-secondary)]">{sub}</p>
          </div>
        ))}
      </div>

      {timetables.length === 0 && (
        <EmptyState
          title="No timetable versions yet"
          description="Analytics of sessions needs a filed version. Approve load rows, then generate a timetable."
        />
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel
          title="Sessions per day"
          meta={
            versionQuery.data
              ? `Version ${versionQuery.data.latest.version_number}, ${entries.length} sessions`
              : 'Select a timetable with a filed version'
          }
        >
          {entries.length === 0 ? (
            <EmptyState title="No sessions to count" description="File a timetable version to see the weekly spread." />
          ) : (
            <>
              <div
                role="img"
                aria-label={`Sessions per day: ${DAYS.map((d, i) => `${d} ${perDay[i]}`).join(', ')}`}
                className="space-y-2"
              >
                {DAYS.map((day, i) => (
                  <div key={day} className="flex items-center gap-3">
                    <span className="w-24 shrink-0 text-sm">{day}</span>
                    <div className="h-5 flex-1 bg-[var(--paper-inset)]">
                      <div
                        className="h-5 bg-[var(--ink)] transition-[width]"
                        style={{ width: `${(perDay[i] / maxDay) * 100}%` }}
                      />
                    </div>
                    <span className="w-12 shrink-0 text-right font-mono text-sm">{perDay[i]}</span>
                  </div>
                ))}
              </div>
              <table className="mt-4 w-full text-sm">
                <caption className="sr-only">Sessions per weekday with counts</caption>
                <tbody className="divide-y divide-[var(--rule)]">
                  {DAYS.map((day, i) => (
                    <tr key={day}>
                      <th scope="row" className="py-1 text-left font-normal">{day}</th>
                      <td className="py-1 text-right font-mono">{perDay[i]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </Panel>

        <Panel
          title="Load hours by session type"
          meta={`${totalLoadHours} hours across ${facultyCount} faculty`}
          actions={totalLoadHours > 0 ? <Badge tone="neutral">{subjectCount} subjects</Badge> : undefined}
        >
          {totalLoadHours === 0 ? (
            <EmptyState title="No load hours recorded" description="Import and approve load rows to see the mix." />
          ) : (
            <>
              <div
                role="img"
                aria-label={`Load mix: ${SESSION_SEGMENTS.map((s) => `${s.label} ${sessionTypeTotals[s.key]} hours`).join(', ')}`}
                className="flex h-8 w-full overflow-hidden border border-[var(--rule)]"
              >
                {SESSION_SEGMENTS.map((s) => {
                  const hours = sessionTypeTotals[s.key];
                  if (hours <= 0) return null;
                  return (
                    <div
                      key={s.key}
                      className={`h-full ${s.bar}`}
                      style={{ width: `${(hours / totalLoadHours) * 100}%` }}
                      title={`${s.label}: ${hours} hours`}
                    />
                  );
                })}
              </div>
              <ul className="mt-3 grid grid-cols-2 gap-2 text-sm">
                {SESSION_SEGMENTS.map((s) => (
                  <li key={s.key} className="flex items-center justify-between border border-[var(--rule)] px-3 py-2">
                    <span>
                      <span className={`mr-2 inline-block h-3 w-3 ${s.bar}`} aria-hidden="true" />
                      {s.label}
                    </span>
                    <span className="font-mono">
                      {sessionTypeTotals[s.key]} · {Math.round((sessionTypeTotals[s.key] / totalLoadHours) * 100)}%
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Panel>
      </div>

      <Panel
        title="Heaviest faculty loads"
        meta="Top 8 by total weekly hours. Hours, not color, carry the ranking."
      >
        {topFaculty.length === 0 ? (
          <EmptyState title="No faculty loads" description="Import load rows to rank weekly hours." />
        ) : (
          <ol className="space-y-2">
            {topFaculty.map((f, rank) => (
              <li key={f.faculty_id} className="flex items-center gap-3">
                <span className="w-8 shrink-0 font-mono text-sm text-[var(--ink-muted)]">{rank + 1}.</span>
                 <span className="w-48 shrink-0 truncate text-sm font-semibold">{f.faculty_name ?? f.name}</span>
                <div className="h-5 flex-1 bg-[var(--paper-inset)]">
                  <div
                    className="h-5 bg-amber-500 transition-[width]"
                    style={{ width: `${(f.total_hours / maxFacultyHours) * 100}%` }}
                    role="img"
                     aria-label={`${f.faculty_name ?? f.name}: ${f.total_hours} hours`}
                  />
                </div>
                <span className="w-24 shrink-0 text-right font-mono text-sm">
                  {f.total_hours} hrs
                </span>
              </li>
            ))}
          </ol>
        )}
      </Panel>
    </div>
  );
}
