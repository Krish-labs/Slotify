import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle, Download, FileText, Users, Building2, AlertTriangle } from 'lucide-react';
import { academicTermApi, reportApi, timetableApi } from '../api';
import type {
  ConflictReport,
  FacultyLoadReport,
  ResourceUtilizationReport,
  TimetableSummaryReport,
  ValidationReport,
} from '../api/types';
import { PageHeader } from '../components/ui/PageHeader';
import { Panel } from '../components/ui/Panel';
import { Badge } from '../components/ui/Badge';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States';
import { DEMO_MODE } from '../demo/mode';
import { errorMessage, latestReadableVersion } from '../utils/timetable';

type ReportTab = 'summary' | 'faculty-load' | 'resource-util' | 'conflicts' | 'validation';

interface SummaryData {
  summary: TimetableSummaryReport;
  validation: ValidationReport;
}

const reports: Array<{ id: ReportTab; name: string; icon: typeof FileText; description: string }> = [
  { id: 'summary', name: 'Timetable Summary', icon: FileText, description: 'Filed sessions and validation status' },
  { id: 'faculty-load', name: 'Faculty Load', icon: Users, description: 'Separate theory, practical, tutorial, and project hours' },
  { id: 'resource-util', name: 'Resource Utilization', icon: Building2, description: 'Room and lab usage from the selected version' },
  { id: 'conflicts', name: 'Conflicts', icon: AlertTriangle, description: 'Validation conflicts from the selected version' },
  { id: 'validation', name: 'Validation', icon: CheckCircle, description: 'Validation response and diagnostics' },
];

export function Reports() {
  const [activeTab, setActiveTab] = useState<ReportTab>('summary');
  const [selectedTimetableId, setSelectedTimetableId] = useState('');
  const [selectedVersionId, setSelectedVersionId] = useState('');
  const [exportError, setExportError] = useState<string | null>(null);

  const timetablesQuery = useQuery({ queryKey: ['timetables'], queryFn: () => timetableApi.list() });
  const timetables = timetablesQuery.data?.timetables;
  const termsQuery = useQuery({
    queryKey: ['academicTerms', { page_size: 100 }],
    queryFn: () => academicTermApi.list({ page_size: 100 }),
  });
  const currentTerm = termsQuery.data?.items.find((term) => term.is_current) ?? termsQuery.data?.items[0];

  const versionsQuery = useQuery({
    queryKey: ['reportVersions', selectedTimetableId],
    queryFn: () => timetableApi.listVersions(selectedTimetableId),
    enabled: !!selectedTimetableId,
  });
  const readableVersion = latestReadableVersion(versionsQuery.data?.versions ?? []);
  const readableVersionId = readableVersion?.id;

  useEffect(() => {
    if (!selectedTimetableId && timetables?.[0]) setSelectedTimetableId(timetables[0].id);
  }, [selectedTimetableId, timetables]);

  useEffect(() => {
    if (selectedTimetableId && !selectedVersionId && readableVersionId) setSelectedVersionId(readableVersionId);
  }, [readableVersionId, selectedTimetableId, selectedVersionId]);

  const summaryQuery = useQuery<SummaryData>({
    queryKey: ['reportSummary', selectedTimetableId, selectedVersionId],
    queryFn: async () => {
      const [summary, validation] = await Promise.all([
        reportApi.timetableSummary(selectedTimetableId, selectedVersionId),
        reportApi.validation(selectedTimetableId, selectedVersionId),
      ]);
      return { summary, validation };
    },
    enabled: activeTab === 'summary' && !!selectedTimetableId && !!selectedVersionId,
  });

  const facultyLoadQuery = useQuery<FacultyLoadReport>({
    queryKey: ['facultyLoadReport', currentTerm?.id],
    queryFn: () => reportApi.facultyLoad(currentTerm!.id),
    enabled: activeTab === 'faculty-load' && !!currentTerm?.id,
  });

  const resourceQuery = useQuery<ResourceUtilizationReport>({
    queryKey: ['resourceUtilizationReport', selectedTimetableId, selectedVersionId],
    queryFn: () => reportApi.resourceUtilization(selectedTimetableId, selectedVersionId),
    enabled: activeTab === 'resource-util' && !!selectedTimetableId && !!selectedVersionId,
  });

  const conflictsQuery = useQuery<ConflictReport>({
    queryKey: ['conflictReport', selectedTimetableId, selectedVersionId],
    queryFn: () => reportApi.conflicts(selectedTimetableId, selectedVersionId),
    enabled: activeTab === 'conflicts' && !!selectedTimetableId && !!selectedVersionId,
  });

  const validationQuery = useQuery<ValidationReport>({
    queryKey: ['validationReport', selectedTimetableId, selectedVersionId],
    queryFn: () => reportApi.validation(selectedTimetableId, selectedVersionId),
    enabled: activeTab === 'validation' && !!selectedTimetableId && !!selectedVersionId,
  });

  const activeQuery =
    activeTab === 'summary'
      ? summaryQuery
      : activeTab === 'faculty-load'
        ? facultyLoadQuery
        : activeTab === 'resource-util'
          ? resourceQuery
          : activeTab === 'conflicts'
            ? conflictsQuery
            : validationQuery;

  const handleExport = async (kind: 'class' | 'faculty' | 'master' | 'resource') => {
    if (DEMO_MODE) {
      setExportError('Read-only demo mode does not create or download workbooks.');
      return;
    }
    if (!selectedTimetableId || !selectedVersionId) {
      setExportError('Select a filed timetable version before exporting.');
      return;
    }
    try {
      const blob =
        kind === 'class'
          ? await timetableApi.exportClass(selectedTimetableId, selectedVersionId)
          : kind === 'faculty'
            ? await timetableApi.exportFaculty(selectedTimetableId, selectedVersionId)
            : kind === 'master'
              ? await timetableApi.exportMaster(selectedTimetableId, selectedVersionId)
              : await timetableApi.exportResourceAllocation(selectedTimetableId, selectedVersionId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${kind}_timetable_${selectedVersionId}.xlsx`;
      link.click();
      window.URL.revokeObjectURL(url);
      setExportError(null);
    } catch (error) {
      setExportError(errorMessage(error, 'The report could not be exported.'));
    }
  };

  const selector = (
    <div className="grid gap-3 border-b border-[var(--rule)] pb-4 md:grid-cols-2">
      <label className="text-sm">
        <span className="field-label">Timetable</span>
        <select value={selectedTimetableId} onChange={(event) => { setSelectedTimetableId(event.target.value); setSelectedVersionId(''); }} className="field-select">
          <option value="">Select timetable</option>
          {(timetables ?? []).map((timetable) => <option key={timetable.id} value={timetable.id}>{timetable.name} ({timetable.academic_year} Sem {timetable.semester})</option>)}
        </select>
      </label>
      <label className="text-sm">
        <span className="field-label">Filed version</span>
        <select value={selectedVersionId} onChange={(event) => setSelectedVersionId(event.target.value)} className="field-select" disabled={!selectedTimetableId}>
          <option value="">Select version</option>
          {(versionsQuery.data?.versions ?? []).map((version) => <option key={version.id} value={version.id}>v{version.version_number} [{version.status}]</option>)}
        </select>
      </label>
    </div>
  );

  const showVersionLoading = activeTab !== 'faculty-load' && !!selectedTimetableId && (versionsQuery.isLoading || (!!versionsQuery.data?.versions.length && !selectedVersionId));
  const showLoading = timetablesQuery.isLoading || (activeTab === 'faculty-load' ? termsQuery.isLoading || facultyLoadQuery.isLoading : showVersionLoading || activeQuery.isLoading);
  const showError = timetablesQuery.error || (activeTab === 'faculty-load' ? termsQuery.error || facultyLoadQuery.error : versionsQuery.error || activeQuery.error);

  return (
    <div className="space-y-5">
      <PageHeader kicker="Office" title="Reports" description="Read backend report responses for the selected term and filed timetable version." />
      {DEMO_MODE && <p className="border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-950" role="status">DEMO DATA · Reports use deterministic fixture responses and are read-only.</p>}
      <div className="paper-panel p-4">
        <nav className="flex gap-2 overflow-x-auto border-b border-[var(--rule)] pb-3" aria-label="Reports tabs">
          {reports.map((report) => {
            const Icon = report.icon;
            return <button key={report.id} onClick={() => setActiveTab(report.id)} aria-pressed={activeTab === report.id} className={`inline-flex min-h-[44px] items-center gap-2 whitespace-nowrap border-b-2 px-3 text-sm font-semibold ${activeTab === report.id ? 'border-[var(--ink)] text-[var(--ink)]' : 'border-transparent text-[var(--ink-secondary)]'}`}><Icon className="h-4 w-4" aria-hidden="true" />{report.name}</button>;
          })}
        </nav>
        <div className="mt-4">{selector}</div>
        {exportError && <p className="mt-4 border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" role="alert">{exportError}</p>}
      </div>

      {showLoading ? <LoadingState label="Loading report" /> : showError ? <ErrorState title="Report data did not load" description="The report service failed. No empty values are substituted for the missing response." retry={<button className="min-h-[44px] border border-[var(--rule-strong)] px-4 py-2 font-semibold" onClick={() => { void timetablesQuery.refetch(); void termsQuery.refetch(); void versionsQuery.refetch(); void activeQuery.refetch(); }}>Retry report</button>} /> : (
        <>
          {activeTab === 'summary' && <SummaryPanel data={summaryQuery.data} hasSelection={!!selectedVersionId} onExport={handleExport} />}
          {activeTab === 'faculty-load' && <FacultyLoadPanel data={facultyLoadQuery.data} hasTerm={!!currentTerm} />}
          {activeTab === 'resource-util' && <ResourcePanel data={resourceQuery.data} hasSelection={!!selectedVersionId} />}
          {activeTab === 'conflicts' && <ConflictPanel data={conflictsQuery.data} hasSelection={!!selectedVersionId} />}
          {activeTab === 'validation' && <ValidationPanel data={validationQuery.data} hasSelection={!!selectedVersionId} />}
        </>
      )}
    </div>
  );
}

function SummaryPanel({ data, hasSelection, onExport }: { data?: SummaryData; hasSelection: boolean; onExport: (kind: 'class' | 'faculty' | 'master' | 'resource') => void }) {
  if (!hasSelection) return <EmptyState title="Select a filed version" description="Choose a timetable and a readable version to load the summary response." />;
  if (!data) return <EmptyState title="No summary response" description="The selected version has no report response yet." />;
  const { summary, validation } = data;
  return <div className="space-y-4">
    <div className="grid gap-4 md:grid-cols-3">
      <Panel title="Entries" meta="From timetable-summary"><p className="font-display text-4xl">{summary.total_entries}</p></Panel>
      <Panel title="Validation" meta={`Version ${validation.version_number}`}><p className="font-display text-4xl">{validation.status}</p></Panel>
      <Panel title="Version" meta={summary.version_status}><p className="font-display text-4xl">v{summary.version_number}</p></Panel>
    </div>
    <div className="flex flex-wrap items-center gap-2">
      {(['class', 'faculty', 'master', 'resource'] as const).map((kind) => <button key={kind} disabled={DEMO_MODE} onClick={() => onExport(kind)} className="inline-flex min-h-[44px] items-center gap-2 border border-[var(--rule-strong)] px-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"><Download className="h-4 w-4" aria-hidden="true" />Export {kind} workbook</button>)}
      {DEMO_MODE && <Badge tone="neutral">Exports disabled in read-only demo</Badge>}
    </div>
  </div>;
}

function FacultyLoadPanel({ data, hasTerm }: { data?: FacultyLoadReport; hasTerm: boolean }) {
  if (!hasTerm) return <EmptyState title="No current academic term" description="Set a current term before loading faculty workload." />;
  if (!data?.summary.length) return <EmptyState title="No faculty load rows" description="The selected term has no faculty load summary rows." />;
  return <Panel title="Faculty load" meta={`Term ${data.academic_term_id}`}><div className="overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Faculty load by teaching mode</caption><thead><tr>{['Faculty', 'Theory', 'Practical', 'Tutorial', 'Project', 'Total', 'Subjects'].map((heading) => <th key={heading} className="border-b border-[var(--rule)] px-3 py-2 text-left font-mono text-xs uppercase">{heading}</th>)}</tr></thead><tbody>{data.summary.map((faculty) => <tr key={faculty.faculty_id} className="border-b border-[var(--rule)]"><th scope="row" className="px-3 py-2 text-left">{faculty.faculty_name ?? faculty.name}</th><td className="px-3 py-2">{faculty.theory_hours}</td><td className="px-3 py-2">{faculty.practical_hours}</td><td className="px-3 py-2">{faculty.tutorial_hours}</td><td className="px-3 py-2">{faculty.project_hours}</td><td className="px-3 py-2 font-semibold">{faculty.total_hours}</td><td className="px-3 py-2">{faculty.subject_count ?? 'Not supplied'}</td></tr>)}</tbody></table></div></Panel>;
}

function ResourcePanel({ data, hasSelection }: { data?: ResourceUtilizationReport; hasSelection: boolean }) {
  if (!hasSelection) return <EmptyState title="Select a filed version" description="Resource utilization is calculated from the selected timetable version." />;
  if (!data?.utilization.length) return <EmptyState title="No resource usage" description="The selected version contains no resource utilization rows." />;
  return <Panel title="Resource utilization" meta={`${data.total_resources} resources, ${data.total_time_slots} time slots`}><div className="overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Resource utilization report</caption><thead><tr>{['Resource', 'Type', 'Used slots', 'Total slots', 'Utilization'].map((heading) => <th key={heading} className="border-b border-[var(--rule)] px-3 py-2 text-left font-mono text-xs uppercase">{heading}</th>)}</tr></thead><tbody>{data.utilization.map((resource) => <tr key={resource.resource_id} className="border-b border-[var(--rule)]"><th scope="row" className="px-3 py-2 text-left">{resource.resource_name}</th><td className="px-3 py-2">{resource.resource_type}</td><td className="px-3 py-2">{resource.used_slots}</td><td className="px-3 py-2">{resource.total_slots}</td><td className="px-3 py-2">{resource.utilization_percent}%</td></tr>)}</tbody></table></div></Panel>;
}

function ConflictPanel({ data, hasSelection }: { data?: ConflictReport; hasSelection: boolean }) {
  if (!hasSelection) return <EmptyState title="Select a filed version" description="Conflict results are tied to a timetable version." />;
  if (!data) return <EmptyState title="No conflict response" description="The selected version has no conflict report response." />;
  return <Panel title="Conflict report" meta={`Version ${data.version_number}`}><p className="font-semibold">{data.is_valid ? 'No conflicts reported.' : `${data.errors.length} conflict(s) reported.`}</p>{data.errors.length > 0 && <ul className="mt-3 list-inside list-disc space-y-1 text-sm">{data.errors.map((error) => <li key={error}>{error}</li>)}</ul>}{data.warnings.length > 0 && <p className="mt-3 text-sm">Warnings: {data.warnings.join('; ')}</p>}</Panel>;
}

function ValidationPanel({ data, hasSelection }: { data?: ValidationReport; hasSelection: boolean }) {
  if (!hasSelection) return <EmptyState title="Select a filed version" description="Validation results are tied to a timetable version." />;
  if (!data) return <EmptyState title="No validation response" description="The selected version has no validation report response." />;
  return <Panel title="Validation report" meta={`Version ${data.version_number}`}><p className="font-display text-3xl">{data.status}</p><p className="mt-2 text-sm">{data.total_entries} entries, {data.errors.length} errors, {data.warnings.length} warnings.</p>{data.errors.length > 0 && <ul className="mt-3 list-inside list-disc space-y-1 text-sm">{data.errors.map((error) => <li key={error}>{error}</li>)}</ul>}{data.warnings.length > 0 && <p className="mt-3 text-sm">Warnings: {data.warnings.join('; ')}</p>}</Panel>;
}
