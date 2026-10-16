import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { templateApi, timetableApi } from '../../api';
import type { TimetableVersionWithEntries } from '../../api/types';
import { PageHeader } from '../../components/ui/PageHeader';
import { TimetableControls } from '../../components/ui/TimetableControls';
import { TimetableGrid, type GridEntry } from '../../components/ui/TimetableGrid';
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States';
import { WorkflowSteps } from '../../components/ui/WorkflowSteps';
import { Badge } from '../../components/ui/Badge';
import { latestReadableVersion } from '../../utils/timetable';

export function MasterTimetable() {
  const [timetableId, setTimetableId] = useState('');
  const [versionId, setVersionId] = useState('');
  const [viewMode, setViewMode] = useState<'resource' | 'consolidated'>('resource');
  const [resourceId, setResourceId] = useState('');

  const timetablesQuery = useQuery({ queryKey: ['timetables'], queryFn: () => timetableApi.list() });
  const timetables = timetablesQuery.data?.timetables;
  const versionsQuery = useQuery({
    queryKey: ['timetableVersions', timetableId],
    queryFn: () => timetableApi.listVersions(timetableId),
    enabled: !!timetableId,
  });
  const readableVersion = latestReadableVersion(versionsQuery.data?.versions ?? []);
  const readableVersionId = readableVersion?.id;
  const timetableQuery = useQuery({
    queryKey: ['timetable', timetableId],
    queryFn: () => timetableApi.get(timetableId),
    enabled: !!timetableId,
  });
  const slotsQuery = useQuery({
    queryKey: ['timeSlots', timetableQuery.data?.template_id],
    queryFn: () => templateApi.listTimeSlots(timetableQuery.data!.template_id),
    enabled: !!timetableQuery.data?.template_id,
  });
  const versionQuery = useQuery<TimetableVersionWithEntries>({
    queryKey: ['timetableVersion', timetableId, versionId],
    queryFn: () => timetableApi.getVersion(timetableId, versionId),
    enabled: !!timetableId && !!versionId,
  });

  useEffect(() => {
    if (!timetableId && timetables?.[0]) setTimetableId(timetables[0].id);
  }, [timetableId, timetables]);

  useEffect(() => {
    if (timetableId && !versionId && readableVersionId) setVersionId(readableVersionId);
  }, [readableVersionId, timetableId, versionId]);

  const allEntries = versionQuery.data?.entries ?? [];
  // Rooms come from the server-resolved resource_name on TimetableEntry, with
  // the id as fallback; the select lists real room names, not raw UUIDs.
  const resourceIds = [...new Set(allEntries.map((e) => e.resource_id).filter(Boolean))] as string[];
  const resourceNames = new Map(
    allEntries
      .filter((e) => e.resource_id && e.resource_name)
      .map((e) => [e.resource_id as string, e.resource_name as string]),
  );
  const resourceLabel = (id: string) => resourceNames.get(id) || id;
  const activeResource = resourceId || resourceIds[0] || '';
  const visible =
    viewMode === 'consolidated'
      ? allEntries
      : allEntries.filter((e) => e.resource_id === activeResource);

  const entries: GridEntry[] = visible
    .filter((e) => e.period_number != null)
    .map((e) => ({
      id: e.id,
       day_of_week: e.day_of_week,
       period_number: e.period_number as number,
       start_time: e.start_time,
       end_time: e.end_time,
       session_type: e.session_type,
      subject_label: e.subject_name || e.subject_id || 'Unmapped subject',
      line_two: e.faculty_name || e.faculty_id || 'Unmapped faculty',
      line_three: e.section_name || e.section_id || undefined,
       batch_label: e.batch_name || null,
    }));

  return (
    <div className="space-y-5">
      <PageHeader
        kicker="Clause 06 to 08"
        title="Master Timetable"
        description="Every room, every period. Read by resource for clashes, or consolidated for the full department."
      />
      <WorkflowSteps current={5} />
      <TimetableControls
         timetables={timetables ?? []}
         versions={versionsQuery.data?.versions ?? []}
        selectedTimetableId={timetableId}
        selectedVersionId={versionId}
        onTimetable={(id) => {
          setTimetableId(id);
          setVersionId('');
          setResourceId('');
        }}
         onVersion={(id) => {
           setVersionId(id);
           setResourceId('');
         }}
        exportKind="master"
        extra={
          versionId ? (
            <>
              <div className="flex items-center gap-1" role="group" aria-label="View mode">
                {(['resource', 'consolidated'] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setViewMode(m)}
                    aria-pressed={viewMode === m}
                    className={`rounded border px-3 py-2 text-sm font-semibold ${
                      viewMode === m
                        ? 'border-[var(--ink)] bg-[var(--ink)] text-[var(--paper)]'
                        : 'border-[var(--rule-strong)] hover:bg-[var(--paper-inset)]'
                    }`}
                  >
                    {m === 'resource' ? 'By resource' : 'Consolidated'}
                  </button>
                ))}
              </div>
              {viewMode === 'resource' && resourceIds.length > 0 && (
                <label className="min-w-48 flex-1 text-sm">
                  <span className="field-label">Resource</span>
                  <select value={activeResource} onChange={(e) => setResourceId(e.target.value)} className="field-select">
                    {resourceIds.map((id) => (
                      <option key={id} value={id}>
                        {resourceLabel(id)}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </>
          ) : undefined
        }
      />
       {timetablesQuery.isLoading || versionsQuery.isLoading || timetableQuery.isLoading || slotsQuery.isLoading ? (
         <LoadingState label="Loading master timetable" />
       ) : timetablesQuery.error || versionsQuery.error || timetableQuery.error || slotsQuery.error || versionQuery.error ? (
         <ErrorState title="Master timetable did not load" description="The selected timetable or its template slots could not be read. No empty fallback is shown." retry={<button className="min-h-[44px] border border-[var(--rule-strong)] px-4 py-2 font-semibold" onClick={() => { void timetablesQuery.refetch(); void versionsQuery.refetch(); void timetableQuery.refetch(); void slotsQuery.refetch(); void versionQuery.refetch(); }}>Retry timetable</button>} />
       ) : !versionId ? (
        <EmptyState
          title="Select a timetable version to read the master"
          description="The master binds rooms to periods. It appears after generation and validation."
        />
       ) : (
        <>
          <p className="flex flex-wrap gap-2">
            <Badge tone="neutral">
              {allEntries.length} placed sessions
            </Badge>
            <Badge tone="neutral">{resourceIds.length} resources in use</Badge>
            {viewMode === 'resource' && activeResource && (
              <Badge tone="lab">Room {resourceLabel(activeResource)}</Badge>
            )}
          </p>
           <TimetableGrid entries={entries} periods={(slotsQuery.data ?? []).filter((slot) => slot.slot_type === 'TEACHING').map((slot) => ({ period_number: slot.period_number, start_time: slot.start_time, end_time: slot.end_time }))} caption="Master timetable grid" />
        </>
      )}
    </div>
  );
}
