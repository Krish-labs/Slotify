import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { facultyApi, templateApi, timetableApi } from '../../api';
import type { TimetableVersionWithEntries, Faculty } from '../../api/types';
import { PageHeader } from '../../components/ui/PageHeader';
import { TimetableControls } from '../../components/ui/TimetableControls';
import { TimetableGrid, type GridEntry } from '../../components/ui/TimetableGrid';
import { ErrorState, LoadingState, EmptyState } from '../../components/ui/States';
import { WorkflowSteps } from '../../components/ui/WorkflowSteps';
import { latestReadableVersion } from '../../utils/timetable';

export function FacultyTimetable() {
  const [timetableId, setTimetableId] = useState('');
  const [versionId, setVersionId] = useState('');
  const [facultyId, setFacultyId] = useState('');

  const timetablesQuery = useQuery({ queryKey: ['timetables'], queryFn: () => timetableApi.list() });
  const timetables = timetablesQuery.data?.timetables;
  const versionsQuery = useQuery({
    queryKey: ['timetableVersions', timetableId],
    queryFn: () => timetableApi.listVersions(timetableId),
    enabled: !!timetableId,
  });
  const facultyQuery = useQuery({
    queryKey: ['faculty'],
    queryFn: () => facultyApi.list({ page_size: 100 }),
  });
  const facultyData = facultyQuery.data;
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

  useEffect(() => {
    if (!facultyId && facultyData?.items[0]) setFacultyId(facultyData.items[0].id);
  }, [facultyData, facultyId]);

  const entries: GridEntry[] = (versionQuery.data?.entries ?? [])
    .filter((e) => !facultyId || e.faculty_id === facultyId)
    .filter((e) => e.period_number != null)
    .map((e) => ({
      id: e.id,
       day_of_week: e.day_of_week,
       period_number: e.period_number as number,
       start_time: e.start_time,
       end_time: e.end_time,
       session_type: e.session_type,
      subject_label: e.subject_name || e.subject_id || 'Unmapped subject',
      line_two: e.section_name || e.section_id || 'Unmapped class',
      line_three: e.resource_name || e.resource_id || 'Unmapped room',
    }));

  const facultyName = facultyData?.items.find((f: Faculty) => f.id === facultyId);

  return (
    <div className="space-y-5">
      <PageHeader
        kicker="Clause 06"
        title="Faculty Timetable"
        description={facultyName ? `Weekly teaching sheet for ${facultyName.first_name} ${facultyName.last_name}.` : 'One teacher, one week. Pick faculty after the version.'}
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
          setFacultyId('');
        }}
        onVersion={(id) => {
          setVersionId(id);
          setFacultyId('');
        }}
        exportKind="faculty"
        extra={
          versionId ? (
            <label className="min-w-56 flex-1 text-sm">
              <span className="field-label">Faculty</span>
              <select value={facultyId} onChange={(e) => setFacultyId(e.target.value)} className="field-select">
                <option value="">Select faculty</option>
                {facultyData?.items.map((f: Faculty) => (
                  <option key={f.id} value={f.id}>
                    {f.first_name} {f.last_name} ({f.department})
                  </option>
                ))}
              </select>
            </label>
          ) : undefined
        }
      />
       {timetablesQuery.isLoading || versionsQuery.isLoading || facultyQuery.isLoading || timetableQuery.isLoading || slotsQuery.isLoading ? (
         <LoadingState label="Loading faculty timetable" />
       ) : timetablesQuery.error || versionsQuery.error || facultyQuery.error || timetableQuery.error || slotsQuery.error || versionQuery.error ? (
         <ErrorState title="Faculty timetable did not load" description="The selected timetable, faculty list, or template slots could not be read. No empty fallback is shown." retry={<button className="min-h-[44px] border border-[var(--rule-strong)] px-4 py-2 font-semibold" onClick={() => { void timetablesQuery.refetch(); void versionsQuery.refetch(); void facultyQuery.refetch(); void timetableQuery.refetch(); void slotsQuery.refetch(); void versionQuery.refetch(); }}>Retry timetable</button>} />
       ) : !versionId ? (
        <EmptyState
          title="Select a timetable version first"
          description="Faculty filtering unlocks after the version loads."
        />
      ) : !facultyId ? (
        <EmptyState
          title="Select a faculty member"
          description="The weekly sheet reads one teacher at a time for notice and workload checks."
        />
       ) : (
         <TimetableGrid entries={entries} periods={(slotsQuery.data ?? []).filter((slot) => slot.slot_type === 'TEACHING').map((slot) => ({ period_number: slot.period_number, start_time: slot.start_time, end_time: slot.end_time }))} caption="Faculty timetable grid" />
       )}
    </div>
  );
}
