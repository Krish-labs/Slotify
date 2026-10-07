import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download } from 'lucide-react';
import { timetableApi, facultyApi } from '../../api';
import type { TimetableVersionWithEntries, Faculty } from '../../api/types';

const DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
const PERIODS = [
  { num: 1, time: '08:00-08:50' },
  { num: 2, time: '08:50-09:40' },
  { num: 3, time: '09:40-10:30' },
  { num: 4, time: '10:40-11:30' },
  { num: 5, time: '11:30-12:20' },
  { num: 6, time: '12:20-01:10' },
  { num: 7, time: '01:10-02:00' },
  { num: 8, time: '02:00-02:50' },
];

export function FacultyTimetable() {
  const [selectedTimetableId, setSelectedTimetableId] = useState<string>('');
  const [selectedVersionId, setSelectedVersionId] = useState<string>('');
  const [selectedFacultyId, setSelectedFacultyId] = useState<string>('');

  const { data: timetables } = useQuery({
    queryKey: ['timetables'],
    queryFn: () => timetableApi.list(),
  });

  const { data: versions } = useQuery({
    queryKey: ['timetableVersions', selectedTimetableId],
    queryFn: () => timetableApi.listVersions(selectedTimetableId),
    enabled: !!selectedTimetableId,
  });

  const { data: facultyData } = useQuery({
    queryKey: ['faculty'],
    queryFn: () => facultyApi.list({ page_size: 100 }),
  });

  const { data: versionData } = useQuery<TimetableVersionWithEntries>({
    queryKey: ['timetableVersion', selectedTimetableId, selectedVersionId],
    queryFn: () => timetableApi.getVersion(selectedTimetableId, selectedVersionId),
    enabled: !!selectedTimetableId && !!selectedVersionId,
  });

  const allEntries = versionData?.entries || [];
  const entries = allEntries.filter((e) => e.faculty_id === selectedFacultyId);

  const getCellContent = (day: string, periodNum: number) => {
    const dayIndex = DAYS.indexOf(day) + 1;
    const entry = entries.find(
      (e) => e.day_of_week === dayIndex && e.period_number === periodNum
    );
    if (!entry) return null;

    const isPractical = entry.session_type === 'PRACTICAL' || entry.session_type === 'P';

    return (
      <div
        className={`p-2 rounded ${
          isPractical
            ? 'bg-purple-50 border-l-4 border-purple-500'
            : 'bg-blue-50 border-l-4 border-blue-500'
        }`}
      >
        <div className="font-medium text-sm">{entry.subject_id || 'Unknown Subject'}</div>
        <div className="text-xs text-gray-600">{entry.section_id || 'Unknown Class'}</div>
        <div className="text-xs text-gray-500">{entry.resource_id || 'Unknown Room'}</div>
        <span
          className={`inline-block mt-1 px-1 py-0.5 text-xs rounded ${
            isPractical ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'
          }`}
        >
          {isPractical ? 'Lab' : 'Lecture'}
        </span>
      </div>
    );
  };

  const handleExport = async () => {
    if (!selectedTimetableId) return;
    try {
      const blob = await timetableApi.exportFaculty(selectedTimetableId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `faculty_timetable_${selectedTimetableId}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export:', err);
      alert('Failed to export timetable');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Faculty Timetable</h1>
          <p className="text-gray-500">View individual faculty timetables</p>
        </div>
        <div className="flex flex-wrap items-center space-x-3">
          <select
            value={selectedTimetableId}
            onChange={(e) => {
              setSelectedTimetableId(e.target.value);
              setSelectedVersionId('');
              setSelectedFacultyId('');
            }}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 min-w-[300px]"
          >
            <option value="">Select Timetable</option>
            {timetables?.timetables?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.academic_year} Sem {t.semester}) - {t.status}
              </option>
            ))}
          </select>
          {selectedTimetableId && (
            <select
              value={selectedVersionId}
              onChange={(e) => {
                setSelectedVersionId(e.target.value);
                setSelectedFacultyId('');
              }}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 min-w-[250px]"
            >
              <option value="">Select Version</option>
              {versions?.versions?.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.version_number} - {v.status} - {v.change_type}
                </option>
              ))}
            </select>
          )}
          {selectedVersionId && facultyData?.items.length && (
            <select
              value={selectedFacultyId}
              onChange={(e) => setSelectedFacultyId(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 min-w-[300px]"
            >
              <option value="">Select Faculty</option>
              {facultyData.items.map((f: Faculty) => (
                <option key={f.id} value={f.id}>
                  {f.first_name} {f.last_name} ({f.department})
                </option>
              ))}
            </select>
          )}
          {selectedFacultyId && (
            <button onClick={handleExport} className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
              <Download className="w-4 h-4 mr-2" />
              Export
            </button>
          )}
        </div>
      </div>

      {selectedFacultyId && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px]">
              <thead className="bg-gray-50">
                <tr>
                  <th className="w-32 px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Period / Time
                  </th>
                  {DAYS.map((day) => (
                    <th key={day} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">
                      {day}
                    </th>
                  ))}
                </tr>
                <tr className="border-t border-gray-200">
                  <th className="w-32 px-3 py-1 text-left text-xs text-gray-400"></th>
                  {DAYS.map(() => (
                    <th className="px-3 py-1 text-center text-xs text-gray-400">Class / Lab</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {PERIODS.map((period) => (
                  <tr key={period.num} className="hover:bg-gray-50">
                    <td className="w-32 px-3 py-2 text-sm font-medium text-gray-900 whitespace-nowrap">
                      P{period.num}<br />
                      <span className="text-xs text-gray-500">{period.time}</span>
                    </td>
                    {DAYS.map((day) => (
                      <td key={`${day}-${period.num}`} className="px-2 py-2 align-top min-h-[80px]">
                        {getCellContent(day, period.num)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}