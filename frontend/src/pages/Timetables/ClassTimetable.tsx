import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { templateApi, timetableApi } from '../../api';
import type { TimetableVersionWithEntries } from '../../api/types';
import { PageHeader } from '../../components/ui/PageHeader';
import { TimetableControls } from '../../components/ui/TimetableControls';
import { TimetableGrid, type GridEntry } from '../../components/ui/TimetableGrid';
import { ErrorState, LoadingState, EmptyState } from '../../components/ui/States';
import { WorkflowSteps } from '../../components/ui/WorkflowSteps';
import { latestReadableVersion } from '../../utils/timetable';

export function ClassTimetable() {
  const [timetableId, setTimetableId] = useState('');
  const [versionId, setVersionId] = useState('');
  const [sectionId, setSectionId] = useState('');

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

  // Every cell renders from persisted TimetableEntry records of the selected
  // CP-SAT generated version. The TT Faculty Excel workbook is only the
  // import/reference source (Load Distribution), never this grid's data.
  const allEntries = versionQuery.data?.entries ?? [];
  const sections = [...new Map(allEntries.filter((entry) => entry.section_id !== null).map((entry) => [entry.section_id as string, entry.section_name || entry.section_id as string] as const)).entries()];
  const entries: GridEntry[] = allEntries
    .filter((e) => !sectionId || e.section_id === sectionId)
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
      line_three: e.resource_name || e.resource_id || 'Unmapped room',
       batch_label: e.batch_name || null,
    }));

  return (
    <div className="space-y-5">
      <PageHeader
        kicker="Clause 06"
        title="Class Timetable"
         description="Monday through Saturday, with persisted template times shown for every placed session. Choose a section to narrow the grid."
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
           setSectionId('');
         }}
         onVersion={(id) => {
           setVersionId(id);
           setSectionId('');
         }}
         exportKind="class"
         extra={
           versionId ? (
             <label className="min-w-52 flex-1 text-sm">
               <span className="field-label">Class / section</span>
               <select value={sectionId} onChange={(event) => setSectionId(event.target.value)} className="field-select">
                 <option value="">All sections</option>
                 {sections.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
               </select>
             </label>
           ) : undefined
         }
       />
       {timetablesQuery.isLoading || versionsQuery.isLoading || timetableQuery.isLoading || slotsQuery.isLoading ? (
         <LoadingState label="Loading class timetable" />
       ) : timetablesQuery.error || versionsQuery.error || timetableQuery.error || slotsQuery.error || versionQuery.error ? (
         <ErrorState title="Class timetable did not load" description="The selected timetable or its template slots could not be read. No empty fallback is shown." retry={<button className="min-h-[44px] border border-[var(--rule-strong)] px-4 py-2 font-semibold" onClick={() => { void timetablesQuery.refetch(); void versionsQuery.refetch(); void timetableQuery.refetch(); void slotsQuery.refetch(); void versionQuery.refetch(); }}>Retry timetable</button>} />
       ) : !versionId ? (
         <EmptyState
           title="No readable timetable version"
           description="Generation must produce a filed version before the class grid can be read."
         />
       ) : (
         <TimetableGrid entries={entries} periods={(slotsQuery.data ?? []).filter((slot) => slot.slot_type === 'TEACHING').map((slot) => ({ period_number: slot.period_number, start_time: slot.start_time, end_time: slot.end_time }))} caption="Class timetable grid" />
       )}
    </div>
  );
}
