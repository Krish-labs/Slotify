import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { timetableApi } from '../../api';
import { Button } from './Button';
import { Badge } from './Badge';
import { DEMO_MODE } from '../../demo/mode';
import { errorMessage } from '../../utils/timetable';

interface Props {
  timetables: Array<{ id: string; name: string; academic_year: string; semester: number; status: string }>;
  versions: Array<{ id: string; version_number: number; status: string; change_type: string }>;
  selectedTimetableId: string;
  selectedVersionId: string;
  onTimetable: (id: string) => void;
  onVersion: (id: string) => void;
  extra?: React.ReactNode;
  exportKind: 'class' | 'faculty' | 'master';
}

/*
 * Reason for shared controls: class, faculty, and master views query the same
 * timetable and version, so selectors, generate, validate, and export behave
 * identically. Generate stays ink-filled as the primary workflow action.
 */
export function TimetableControls({
  timetables,
  versions,
  selectedTimetableId,
  selectedVersionId,
  onTimetable,
  onVersion,
  extra,
  exportKind,
}: Props) {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);

  const generateMutation = useMutation({
    mutationFn: () => timetableApi.generateFromWorkbook(selectedTimetableId),
    onSuccess: (res) => {
      setNotice(
        res.success
          ? `Generation filed version ${res.version_number ?? ''} with ${res.entries_count ?? 0} sessions.`
          : `Generation reported: ${res.error ?? 'no version filed'}.`,
      );
      queryClient.invalidateQueries({ queryKey: ['timetableVersions'] });
    },
     onError: (e) => setNotice(`Generation failed: ${errorMessage(e, 'The generation request failed.')}`),
  });

  const validateMutation = useMutation({
     mutationFn: () => timetableApi.validate(selectedTimetableId, selectedVersionId),
    onSuccess: (res) => {
      const errors = res.errors?.length ?? 0;
      const warnings = res.warnings?.length ?? 0;
      setNotice(
        res.status === 'PASS'
          ? `Validation passed with ${warnings} warnings.`
          : `Validation ${res.status.toLowerCase()}: ${errors} errors, ${warnings} warnings. See Reports.`,
      );
    },
    onError: (e) => setNotice(`Validation failed: ${errorMessage(e, 'The validation request failed.')}`),
  });

  const exportFile = async () => {
    if (DEMO_MODE) {
      setNotice('Read-only demo mode does not create or download workbooks.');
      return;
    }
    if (!selectedVersionId) {
      setNotice('Select a filed version before exporting.');
      return;
    }
    try {
      const blob =
        exportKind === 'class'
          ? await timetableApi.exportClass(selectedTimetableId, selectedVersionId)
          : exportKind === 'faculty'
            ? await timetableApi.exportFaculty(selectedTimetableId, selectedVersionId)
            : await timetableApi.exportMaster(selectedTimetableId, selectedVersionId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${exportKind}_timetable_${selectedTimetableId}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      setNotice('Export failed. Retry after validation passes.');
    }
  };

  return (
    <div className="paper-panel space-y-3 p-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-56 flex-1 text-sm">
          <span className="field-label">Timetable</span>
          <select value={selectedTimetableId} onChange={(e) => onTimetable(e.target.value)} className="field-select">
            <option value="">Select timetable</option>
            {timetables.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.academic_year} Sem {t.semester}) [{t.status}]
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-52 flex-1 text-sm">
          <span className="field-label">Version</span>
          <select
            value={selectedVersionId}
            onChange={(e) => onVersion(e.target.value)}
            className="field-select"
            disabled={!selectedTimetableId}
          >
            <option value="">Select version</option>
            {versions.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.version_number} [{v.status}] {v.change_type}
              </option>
            ))}
          </select>
        </label>
        {extra}
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-[var(--rule)] pt-3">
         <Button variant="primary" disabled={DEMO_MODE || !selectedTimetableId || generateMutation.isPending} onClick={() => generateMutation.mutate()}>
          {generateMutation.isPending ? 'Generating…' : 'Generate Optimized Timetable'}
        </Button>
         <Button disabled={DEMO_MODE || !selectedTimetableId || !selectedVersionId || validateMutation.isPending} onClick={() => validateMutation.mutate()}>
          {validateMutation.isPending ? 'Validating…' : 'Validate timetable'}
        </Button>
         <Button disabled={DEMO_MODE || !selectedTimetableId || !selectedVersionId} onClick={exportFile}>
          Export {exportKind} Excel
        </Button>
         {DEMO_MODE ? (
           <Badge tone="neutral">Demo: actions disabled</Badge>
         ) : selectedVersionId ? (
           <Badge tone="neutral">Reading a filed version, not a draft</Badge>
         ) : null}
      </div>
      {notice && (
        <p role="status" className="text-sm text-[var(--ink-secondary)]">
          {notice}
        </p>
      )}
    </div>
  );
}
