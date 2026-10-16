import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Loader2, Play, Plus, Wrench, XCircle } from 'lucide-react';
import { academicTermApi, templateApi, timetableApi } from '../../api';
import type {
  TimetableGenerateResponse,
  TimetableRepairResponse,
  WorkbookReadinessResponse,
} from '../../api/types';
import { Link } from 'react-router-dom';
import { DEMO_MODE } from '../../demo/mode';

/**
 * Generate Optimized Timetable, the core workflow action.
 *
 * Generation is synchronous: the pending mutation state is the CP-SAT solve
 * indicator. Nothing is shown as success unless the backend persisted a
 * validated TimetableVersion.
 */
export function GenerateTimetable() {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [academicYear, setAcademicYear] = useState('');
  const [semester, setSemester] = useState('1');
  const [createdId, setCreatedId] = useState<string | null>(null);
  const [result, setResult] = useState<TimetableGenerateResponse | null>(null);
  const [repairRetries, setRepairRetries] = useState('2');
  const [approveRelaxation, setApproveRelaxation] = useState(false);
  const [repairResult, setRepairResult] = useState<TimetableRepairResponse | null>(null);

  const termsQuery = useQuery({
    queryKey: ['mappingTerms'],
    queryFn: () => academicTermApi.list({ page_size: 100, is_active: true }),
  });
  const templatesQuery = useQuery({ queryKey: ['templates'], queryFn: () => templateApi.list() });

  useEffect(() => {
    const first = termsQuery.data?.items?.[0];
    if (!academicYear && first) {
      setAcademicYear(first.academic_year);
      setSemester(String(first.semester));
    }
  }, [academicYear, termsQuery.data]);

  useEffect(() => {
    if (!templateId) {
      const matching = templatesQuery.data?.find((template) => template.academic_year === academicYear);
      if (matching) setTemplateId(matching.id);
    }
  }, [academicYear, templateId, templatesQuery.data]);

  const createMutation = useMutation({
    mutationFn: () =>
      timetableApi.create({
        name: name.trim() || `Timetable ${academicYear} Sem ${semester}`,
        template_id: templateId,
        academic_year: academicYear,
        semester: Number(semester),
      }),
    onSuccess: (timetable) => {
      setCreatedId(timetable.id);
      setResult(null);
      queryClient.invalidateQueries({ queryKey: ['timetables'] });
    },
  });

  const sourceReadinessQuery = useQuery<WorkbookReadinessResponse>({
    queryKey: ['workbookReadiness', createdId],
    queryFn: () => timetableApi.workbookReadiness(createdId!),
    enabled: !!createdId,
    refetchInterval: false,
  });

  const generateMutation = useMutation({
    mutationFn: () => timetableApi.generateFromWorkbook(createdId!),
    onSuccess: (data) => {
      setResult(data);
      setRepairResult(null);
      queryClient.invalidateQueries({ queryKey: ['timetables'] });
      queryClient.invalidateQueries({ queryKey: ['timetableVersions', createdId] });
    },
    onError: () => setResult(null),
  });

  const repairMutation = useMutation({
    mutationFn: () =>
      timetableApi.repair(createdId!, {
        max_retries: Number(repairRetries),
        approve_hard_relaxation: approveRelaxation,
      }),
    onSuccess: (data) => {
      setRepairResult(data);
      if (data.success) {
        queryClient.invalidateQueries({ queryKey: ['timetables'] });
        queryClient.invalidateQueries({ queryKey: ['timetableVersions', createdId] });
      }
    },
    onError: () => setRepairResult(null),
  });

  const terms = termsQuery.data?.items ?? [];
  const ready = sourceReadinessQuery.data?.ready ?? false;
  const generating = generateMutation.isPending;

  // The backend wraps generation failures as HTTP 422 with a detail payload
  // (validation, missing inputs, INFEASIBLE diagnostics); surface all of it.
  const generateError = (() => {
    if (!generateMutation.error) return null;
    const err = generateMutation.error as { response?: { data?: { detail?: unknown } } };
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string') return { error: detail, details: [] as string[] };
    if (detail && typeof detail === 'object') {
      const d = detail as { error?: string; details?: string[]; unscheduled?: string[]; stage?: string };
      return { error: d.error ?? 'Generation failed', details: [...(d.details ?? []), ...(d.unscheduled ?? [])], stage: d.stage };
    }
    return { error: String(generateMutation.error), details: [] as string[] };
  })();

  const readinessError = (() => {
    if (!sourceReadinessQuery.error) return null;
    const err = sourceReadinessQuery.error as { response?: { data?: { detail?: unknown } } };
    const detail = err.response?.data?.detail;
    if (detail && typeof detail === 'object') {
      const d = detail as {
        error?: string;
        details?: string[];
        sheet?: string | null;
        row?: number | null;
        field?: string | null;
      };
      return {
        error: d.error ?? 'Unable to parse the source workbook',
        details: d.details ?? [],
        location: [d.sheet && `sheet ${d.sheet}`, d.row && `row ${d.row}`, d.field && `field ${d.field}`]
          .filter(Boolean)
          .join(', '),
      };
    }
    return { error: 'Unable to parse the source workbook', details: [], location: '' };
  })();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Generate Optimized Timetable</h1>
        <p className="text-gray-500">
           Load Distribution → CP-SAT hard constraints and optimization → independent validation → persisted TimetableVersion.
        </p>
        {DEMO_MODE && (
          <div className="mt-3 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950" role="status">
            <strong>DEMO DATA.</strong> OR-Tools generation, validation, and persistence are unavailable here.{' '}
            <Link className="font-semibold underline" to="/timetables/master">Open the deterministic demo timetable</Link>.
          </div>
        )}
      </div>

      {/* Step 1: anchor the timetable to a real template and academic term */}
      <section className="rounded-lg border border-gray-200 bg-white shadow p-5 space-y-4">
        <h2 className="font-semibold text-gray-900">1. Timetable anchor</h2>
        <p className="text-sm text-gray-500">
          A timetable must reference an active template and an existing academic term; generation
          resolves assignments through that term.
        </p>
        <div className="grid gap-3 md:grid-cols-4">
          <label className="text-sm text-gray-700 md:col-span-2">
            Name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Sem I 2026-27 main timetable"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
            />
          </label>
          <label className="text-sm text-gray-700">
            Template
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
            >
              <option value="">Select template</option>
              {(templatesQuery.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.academic_year})
                </option>
              ))}
            </select>
          </label>
           <div className="grid grid-cols-1 gap-3">
             <label className="text-sm text-gray-700">
             Academic semester
             <select
               value={`${academicYear}|${semester}`}
               onChange={(e) => {
                  const [year, sem] = e.target.value.split('|');
                  setAcademicYear(year);
                  setSemester(sem);
                  setTemplateId('');
                  setCreatedId(null);
                  setResult(null);
               }}
               className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
             >
               <option value="|">Select academic semester</option>
               {(termsQuery.data?.items ?? []).map((term) => (
                 <option key={term.id} value={`${term.academic_year}|${term.semester}`}>
                   {term.name}
                 </option>
               ))}
             </select>
            </label>
           </div>
        </div>
         {terms.length === 0 && (
           <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
             No active academic terms exist. Create one in Load Distribution (Map dialog → Academic
             term) before generating.
           </div>
         )}
         {termsQuery.error && (
           <p role="alert" className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
             Academic terms could not be loaded. Retry the page before creating a timetable.
           </p>
         )}
         {templatesQuery.error && (
           <p role="alert" className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
             Timetable templates could not be loaded. Retry the page before creating a timetable.
           </p>
         )}
         {templateId && academicYear && semester && !DEMO_MODE && (
          <button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 shadow-sm disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            {createMutation.isPending ? 'Creating…' : 'Create timetable (DRAFT)'}
          </button>
        )}
         {createdId && (
             <p className="text-sm text-emerald-700">
              Timetable created. Source parsing runs below before CP-SAT generation.
           </p>
         )}
         {DEMO_MODE && (
           <p className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">
             Generation is intentionally disabled in demo mode. The timetable shown elsewhere is fixture data, not solver output.
           </p>
         )}
         {createMutation.error && (
           <p role="alert" className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
             Timetable creation failed. Check the selected term, template, and account permissions, then retry.
           </p>
         )}
      </section>

       {/* Step 2: source parsing and generation inputs */}
      {createdId && (
        <section className="rounded-lg border border-gray-200 bg-white shadow p-5 space-y-3">
           <h2 className="font-semibold text-gray-900">2. Source parsing</h2>
           {sourceReadinessQuery.isLoading && <p className="text-sm text-gray-500">Parsing Load Distribution.xlsx…</p>}
            {readinessError && (
              <div className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
                <p className="font-medium">{readinessError.error}</p>
                {!!readinessError.location && <p className="mt-1 text-xs">Location: {readinessError.location}</p>}
                {!!readinessError.details.length && (
                  <ul className="mt-1 list-inside list-disc">
                    {readinessError.details.map((detail, index) => <li key={index}>{detail}</li>)}
                  </ul>
                )}
                <button
                  type="button"
                  onClick={() => sourceReadinessQuery.refetch()}
                  className="mt-2 rounded border border-rose-300 px-2 py-1 text-xs font-medium hover:bg-rose-100"
                >
                  Retry parsing
                </button>
              </div>
            )}
           {sourceReadinessQuery.data && (
             <>
               <ul className="space-y-1.5 text-sm text-gray-700">
                  <li>Source: {sourceReadinessQuery.data.source_file}</li>
                  <li>Source sheet: {sourceReadinessQuery.data.source_sheet ?? 'Sheet1'}</li>
                  <li>Timing reference: {sourceReadinessQuery.data.reference_file} ({sourceReadinessQuery.data.timing_reference_available ? `${sourceReadinessQuery.data.timing_intervals ?? 0} hourly intervals` : 'missing'})</li>
                 <li>Selected semester: {sourceReadinessQuery.data.semester}</li>
                  <li>{sourceReadinessQuery.data.source_demands} teaching demands, {sourceReadinessQuery.data.required_sessions} one-hour sessions from the timing reference</li>
                  <li>{sourceReadinessQuery.data.unrepresented_hours} source hour(s) could not be represented by the timing reference</li>
                 <li>{sourceReadinessQuery.data.excluded_rows.length} non-ENTC/M.Tech source row(s) excluded from the FE/SY/TE/BE run</li>
               </ul>
               <button
                onClick={() => generateMutation.mutate()}
                disabled={!ready || generating}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 font-semibold text-white hover:bg-emerald-700 shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
              >
                {generating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                     Solving with OR-Tools CP-SAT…
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    Generate Timetable from Load Distribution
                  </>
                )}
              </button>
            </>
          )}
        </section>
      )}

       {/* Step 3: persisted result */}
      {generateError && (
        <section className="rounded-lg border border-rose-200 bg-rose-50 p-5">
          <h2 className="flex items-center gap-2 font-semibold text-rose-800">
            <XCircle className="h-5 w-5" /> Generation failed
          </h2>
          <p className="mt-2 text-sm text-rose-900">{generateError.error}</p>
          {generateError.stage && (
            <p className="mt-1 text-xs text-rose-700">Failed at stage: {generateError.stage}</p>
          )}
          {!!generateError.details?.length && (
            <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-rose-800">
              {generateError.details.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          )}
        </section>
      )}
      {generateError && createdId && (
        <section aria-live="polite" className="rounded-lg border border-amber-200 bg-amber-50 p-5 space-y-3">
          <h2 className="flex items-center gap-2 font-semibold text-amber-900">
            <Wrench className="h-5 w-5" /> Bounded repair
          </h2>
          <p className="text-sm text-amber-800">
            Re-runs CP-SAT with revised inputs (at most {repairRetries} attempt(s)), then validates
            independently. Unaffected entries stay pinned where feasible. Nothing is published
            unless the repaired candidate validates — failed repair leaves the last version untouched.
          </p>
          <div className="flex flex-wrap items-center gap-4 text-sm text-amber-900">
            <label>
              Max attempts
              <select
                value={repairRetries}
                onChange={(e) => setRepairRetries(e.target.value)}
                className="ml-2 rounded-lg border border-amber-300 bg-white px-2 py-1"
              >
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="3">3</option>
              </select>
            </label>
            <label className="inline-flex items-start gap-2">
              <input
                type="checkbox"
                checked={approveRelaxation}
                onChange={(e) => setApproveRelaxation(e.target.checked)}
                className="mt-1"
              />
              <span>
                Approve availability overrides (leave/blackout exceptions, standby rooms).
                Hard scheduling rules are never relaxed.
              </span>
            </label>
          </div>
          <button
            onClick={() => repairMutation.mutate()}
            disabled={repairMutation.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 font-semibold text-white hover:bg-amber-700 shadow-sm disabled:opacity-50"
          >
            {repairMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Repairing…
              </>
            ) : (
              <>
                <Wrench className="h-4 w-4" /> Run bounded repair
              </>
            )}
          </button>
          {repairMutation.error && !repairResult && (
            <p className="text-sm text-rose-800">Repair request failed: {String(repairMutation.error)}</p>
          )}
          {repairResult?.success && (
            <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
              <p className="font-medium">
                Repaired and validated as version v{repairResult.version_number} ({repairResult.entries_count} entries,{' '}
                {repairResult.repair_attempts} attempt(s), solver {repairResult.solver_status}).
              </p>
              {repairResult.diff && (
                <p className="mt-1">
                  Diff vs previous version: {repairResult.diff.added} added, {repairResult.diff.changed}{' '}
                  changed, {repairResult.diff.removed} removed, {repairResult.diff.kept} kept.
                </p>
              )}
            </div>
          )}
          {repairResult && !repairResult.success && (
            <div className="text-sm text-amber-900">
              <p className="font-medium">{repairResult.error ?? 'Repair did not produce a valid timetable.'}</p>
              {!!repairResult.original_diagnostics?.length && (
                <ul className="mt-2 list-inside list-disc space-y-1">
                  {repairResult.original_diagnostics.map((d, i) => (
                    <li key={i}>{d}</li>
                  ))}
                </ul>
              )}
              {!!repairResult.attempts?.length && (
                <ul className="mt-2 space-y-1 text-xs">
                  {repairResult.attempts.map((a) => (
                    <li key={a.attempt}>
                      Attempt {a.attempt} ({a.adjustment?.kind ?? 'none'}): solver {a.solver_status}
                      {!!a.validation_errors.length && ` — ${a.validation_errors.join('; ')}`}
                    </li>
                  ))}
                </ul>
              )}
              {!!repairResult.unscheduled?.length && (
                <p className="mt-2 text-xs">
                  Unscheduled: {repairResult.unscheduled.map((u) => `${u.assignment_id.slice(0, 8)} (${u.scheduled_hours}/${u.required_hours}h)`).join(', ')}
                </p>
              )}
            </div>
          )}
        </section>
      )}
      {result && !result.success && (
        <section className="rounded-lg border border-rose-200 bg-rose-50 p-5">
          <h2 className="font-semibold text-rose-800">Generation failed</h2>
          <p className="mt-2 text-sm text-rose-900">{result.error}</p>
          {!!result.details?.length && (
            <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-rose-800">
              {result.details.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          )}
        </section>
      )}
      {result?.success && (
        <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
           <h2 className="flex items-center gap-2 font-semibold text-emerald-800">
             <CheckCircle2 className="h-5 w-5" /> {result.complete ? 'Timetable generated and validated' : 'Timetable generated with unscheduled source demand'}
          </h2>
          <ul className="mt-2 space-y-1 text-sm text-emerald-900">
            <li>Version: v{result.version_number} ({result.version_id})</li>
             <li>Entries persisted: {result.entries_count}</li>
              <li>Solver: {result.solver_status ?? 'CP-SAT'}; validation: {result.validation_status ?? 'PASS'}</li>
              {typeof result.optimality_proven === 'boolean' && <li>Optimality proven: {result.optimality_proven ? 'yes' : 'no, feasible result accepted'}</li>}
             <li>Source demands: {result.source_demands ?? 'n/a'}; required sessions: {result.required_sessions ?? 'n/a'}; scheduled: {result.scheduled_sessions ?? 'n/a'}</li>
             {!!result.unscheduled_sessions && <li>Unscheduled two-hour sessions: {result.unscheduled_sessions}</li>}
            {typeof result.solve_time === 'number' && <li>Solve time: {result.solve_time.toFixed(1)}s</li>}
            {result.diff && (
              <li>
                Diff vs previous version: {result.diff.added} added, {result.diff.changed} changed,{' '}
                {result.diff.removed} removed, {result.diff.kept} kept
              </li>
            )}
            {!!result.warnings?.length && <li>Warnings: {result.warnings.join('; ')}</li>}
          </ul>
           {!!result.unscheduled?.length && (
             <ul className="mt-3 max-h-48 list-inside list-disc overflow-y-auto text-sm text-amber-900">
               {result.unscheduled.map((item) => <li key={item}>{item}</li>)}
             </ul>
           )}
           {!!result.excluded_rows?.length && (
             <p className="mt-2 text-xs text-amber-800">Excluded from this FE/SY/TE/BE run: {result.excluded_rows.length} source row(s), including non-ENTC/M.Tech classes.</p>
           )}
           <p className="mt-3 text-sm text-emerald-800">
             View it under Class, Faculty, or Master Timetable. Every cell there is rendered from the
            persisted TimetableEntry records of this version.
          </p>
        </section>
      )}
    </div>
  );
}
