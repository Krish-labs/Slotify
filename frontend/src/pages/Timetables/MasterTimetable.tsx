import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download } from 'lucide-react';
import { timetableApi } from '../../api';
import type { TimetableVersionWithEntries, Resource } from '../../api/types';

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

const TYPE_COLORS: Record<string, string> = {
  CLASSROOM: 'bg-blue-100 text-blue-800',
  SOFTWARE_LAB: 'bg-purple-100 text-purple-800',
  HARDWARE_LAB: 'bg-orange-100 text-orange-800',
};

interface ResourceWithEntries extends Resource {
  entryCount: number;
}

export function MasterTimetable() {
  const [viewMode, setViewMode] = useState<'resource' | 'consolidated'>('resource');
  const [filterType, setFilterType] = useState('all');
  const [selectedTimetableId, setSelectedTimetableId] = useState<string>('');
  const [selectedVersionId, setSelectedVersionId] = useState<string>('');

  const { data: timetables } = useQuery({
    queryKey: ['timetables'],
    queryFn: () => timetableApi.list(),
  });

  const { data: versions } = useQuery({
    queryKey: ['timetableVersions', selectedTimetableId],
    queryFn: () => timetableApi.listVersions(selectedTimetableId),
    enabled: !!selectedTimetableId,
  });

  const { data: versionData } = useQuery<TimetableVersionWithEntries>({
    queryKey: ['timetableVersion', selectedTimetableId, selectedVersionId],
    queryFn: () => timetableApi.getVersion(selectedTimetableId, selectedVersionId),
    enabled: !!selectedTimetableId && !!selectedVersionId,
  });

  const entries = versionData?.entries || [];

  // Extract unique resources from entries
  const resourceIds = [...new Set(entries.map((e) => e.resource_id).filter(Boolean))];
  const resources: ResourceWithEntries[] = resourceIds
    .filter((id): id is string => id !== null)
    .map((id) => {
      const resourceEntries = entries.filter((e) => e.resource_id === id);
      return {
        id,
        name: id,
        resource_type: 'CLASSROOM',
        capacity: 0,
        building: null,
        floor: null,
        room_number: null,
        is_emergency: false,
        is_active: true,
        created_at: '',
        updated_at: '',
        entryCount: resourceEntries.length,
      };
    })
    .filter((r) => filterType === 'all' || r.resource_type === filterType);

  const handleExport = async () => {
    if (!selectedTimetableId) return;
    try {
      const blob = await timetableApi.exportMaster(selectedTimetableId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `master_timetable_${selectedTimetableId}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export:', err);
      alert('Failed to export timetable');
    }
  };

  const getCellContent = (resourceId: string, day: string, periodNum: number) => {
    const dayIndex = DAYS.indexOf(day) + 1;
    const entry = entries.find(
      (e) => e.resource_id === resourceId && e.day_of_week === dayIndex && e.period_number === periodNum
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
        <div className="font-medium text-sm">{entry.subject_id || 'Unknown'}</div>
        <div className="text-xs text-gray-600">{entry.faculty_id || 'Unknown'}</div>
        <div className="text-xs text-gray-500">{entry.section_id || 'Unknown'}</div>
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

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Master Timetable</h1>
          <p className="text-gray-500">Department-wide resource allocation view</p>
        </div>
        <div className="flex flex-wrap items-center space-x-3">
          <select
            value={selectedTimetableId}
            onChange={(e) => {
              setSelectedTimetableId(e.target.value);
              setSelectedVersionId('');
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
              onChange={(e) => setSelectedVersionId(e.target.value)}
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
          <div className="flex items-center space-x-2">
            <span className="text-sm text-gray-500">View:</span>
            <button
              onClick={() => setViewMode('resource')}
              className={`px-3 py-1 rounded ${viewMode === 'resource' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}
            >
              By Resource
            </button>
            <button
              onClick={() => setViewMode('consolidated')}
              className={`px-3 py-1 rounded ${viewMode === 'consolidated' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}
            >
              Consolidated
            </button>
          </div>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Types</option>
            <option value="CLASSROOM">Classrooms</option>
            <option value="SOFTWARE_LAB">Software Labs</option>
            <option value="HARDWARE_LAB">Hardware Labs</option>
          </select>
          {selectedVersionId && (
            <button onClick={handleExport} className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
              <Download className="w-4 h-4 mr-2" />
              Export Master
            </button>
          )}
        </div>
      </div>

      {selectedVersionId && (
        <div className="space-y-6">
          {resources.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
              No resources found for this timetable version
            </div>
          ) : (
            resources.map((resource) => (
              <div key={resource.id} className="bg-white rounded-lg shadow">
                <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${TYPE_COLORS[resource.resource_type] || 'bg-gray-100 text-gray-800'}`}>
                      {resource.resource_type.replace('_', ' ')}
                    </span>
                    <h3 className="font-semibold text-gray-900">{resource.name}</h3>
                    <span className="text-sm text-gray-500">Entries: {resource.entryCount}</span>
                  </div>
                </div>
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
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {PERIODS.map((period) => (
                        <tr key={`${resource.id}-${period.num}`} className="hover:bg-gray-50">
                          <td className="w-32 px-3 py-2 text-sm font-medium text-gray-900 whitespace-nowrap">
                            P{period.num}<br />
                            <span className="text-xs text-gray-500">{period.time}</span>
                          </td>
                          {DAYS.map((day) => (
                            <td key={`${day}-${period.num}`} className="px-2 py-2 align-top min-h-[60px]">
                              {getCellContent(resource.id, day, period.num) || (
                                <div className="text-xs text-gray-300 text-center py-4">—</div>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}