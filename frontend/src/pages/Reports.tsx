import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileText, Download, BarChart, AlertTriangle, CheckCircle, Clock, Users, Building2 } from 'lucide-react';
import { timetableApi, loadApi, academicTermApi } from '../api';
import type { TimetableValidationResponse } from '../api/types';

interface TimetableSummaryData {
  entriesCount: number;
  validation: TimetableValidationResponse;
  versionNumber: number;
  versionStatus: string;
}

export function Reports() {
  const [activeTab, setActiveTab] = useState('summary');
  const [selectedTimetableId, setSelectedTimetableId] = useState<string>('');

  const { data: timetables } = useQuery({
    queryKey: ['timetables'],
    queryFn: () => timetableApi.list(),
  });

  const { data: currentTerm } = useQuery({
    queryKey: ['currentTerm'],
    queryFn: () => academicTermApi.getCurrent(),
  });

  const { data: summaryData } = useQuery<TimetableSummaryData | null>({
    queryKey: ['timetableSummary', selectedTimetableId],
    queryFn: async () => {
      if (!selectedTimetableId) return null;
      const version = await timetableApi.listVersions(selectedTimetableId);
      const latestVersion = version.versions?.[0];
      if (!latestVersion) return null;
      const versionData = await timetableApi.getVersion(selectedTimetableId, latestVersion.id);
      const validation = await timetableApi.validate(selectedTimetableId);
      return {
        entriesCount: versionData?.entries?.length || 0,
        validation,
        versionNumber: latestVersion.version_number,
        versionStatus: latestVersion.status,
      };
    },
    enabled: !!selectedTimetableId,
  });

  const { data: loadSummary } = useQuery({
    queryKey: ['loadSummary', currentTerm?.id],
    queryFn: () => loadApi.getLoadSummary(currentTerm!.id),
    enabled: !!currentTerm?.id,
  });

  const reports = [
    { id: 'summary', name: 'Timetable Summary', icon: FileText, description: 'Overview of generated timetable' },
    { id: 'faculty-load', name: 'Faculty Load Report', icon: Users, description: 'Faculty teaching load distribution' },
    { id: 'resource-util', name: 'Resource Utilization', icon: Building2, description: 'Room and lab usage statistics' },
    { id: 'conflicts', name: 'Conflict Report', icon: AlertTriangle, description: 'Detected scheduling conflicts' },
    { id: 'validation', name: 'Validation Report', icon: CheckCircle, description: 'Timetable validation results' },
  ];

  const handleExport = async (type: string) => {
    if (!selectedTimetableId) return;
    try {
      let blob;
      switch (type) {
        case 'class':
          blob = await timetableApi.exportClass(selectedTimetableId);
          break;
        case 'faculty':
          blob = await timetableApi.exportFaculty(selectedTimetableId);
          break;
        case 'master':
          blob = await timetableApi.exportMaster(selectedTimetableId);
          break;
        case 'resource':
          blob = await timetableApi.exportResourceAllocation(selectedTimetableId);
          break;
        default:
          return;
      }
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${type}_timetable_${selectedTimetableId}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export:', err);
      alert('Failed to export report');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
        <p className="text-gray-500">Generate and view timetable reports</p>
      </div>

      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200">
          <nav className="flex overflow-x-auto px-4" aria-label="Reports tabs">
            {reports.map((report) => (
              <button
                key={report.id}
                onClick={() => setActiveTab(report.id)}
                className={`flex items-center px-4 py-4 border-b-2 text-sm font-medium transition-colors ${
                  activeTab === report.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <report.icon className="w-5 h-5 mr-2" />
                {report.name}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {activeTab === 'summary' && (
            <div className="space-y-6">
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Select Timetable</label>
                <select
                  value={selectedTimetableId}
                  onChange={(e) => setSelectedTimetableId(e.target.value)}
                  className="w-full max-w-md px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select a timetable to view summary</option>
                  {timetables?.timetables?.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.academic_year} Sem {t.semester}) - {t.status}
                    </option>
                  ))}
                </select>
              </div>

              {selectedTimetableId && summaryData && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="bg-blue-50 rounded-lg p-6">
                    <div className="flex items-center">
                      <div className="p-3 bg-blue-600 rounded-full">
                        <BarChart className="w-6 h-6 text-white" />
                      </div>
                      <div className="ml-4">
                        <p className="text-sm text-gray-500">Total Entries</p>
                        <p className="text-3xl font-bold text-gray-900">{summaryData.entriesCount.toLocaleString()}</p>
                      </div>
                    </div>
                  </div>
                  <div className="bg-green-50 rounded-lg p-6">
                    <div className="flex items-center">
                      <div className="p-3 bg-green-600 rounded-full">
                        <CheckCircle className="w-6 h-6 text-white" />
                      </div>
                      <div className="ml-4">
                        <p className="text-sm text-gray-500">Validation Status</p>
                        <p className="text-3xl font-bold text-gray-900">{summaryData.validation?.status || 'N/A'}</p>
                      </div>
                    </div>
                  </div>
                  <div className="bg-yellow-50 rounded-lg p-6">
                    <div className="flex items-center">
                      <div className="p-3 bg-yellow-600 rounded-full">
                        <Clock className="w-6 h-6 text-white" />
                      </div>
                      <div className="ml-4">
                        <p className="text-sm text-gray-500">Version</p>
                        <p className="text-3xl font-bold text-gray-900">v{summaryData.versionNumber}</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {!selectedTimetableId && (
                <div className="text-center text-gray-500 py-8">
                  Select a timetable to view summary statistics
                </div>
              )}

              <div className="border-t border-gray-200 pt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Export Options</h3>
                <div className="flex flex-wrap gap-4">
                  {selectedTimetableId ? (
                    <>
                      <button onClick={() => handleExport('class')} className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                        <Download className="w-4 h-4 mr-2" />
                        Export Class Timetables (Excel)
                      </button>
                      <button onClick={() => handleExport('faculty')} className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                        <Download className="w-4 h-4 mr-2" />
                        Export Faculty Timetables (Excel)
                      </button>
                      <button onClick={() => handleExport('master')} className="flex items-center px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700">
                        <Download className="w-4 h-4 mr-2" />
                        Export Master Timetable (Excel)
                      </button>
                      <button onClick={() => handleExport('resource')} className="flex items-center px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700">
                        <Download className="w-4 h-4 mr-2" />
                        Export Resource Allocation (Excel)
                      </button>
                    </>
                  ) : (
                    <p className="text-gray-500">Select a timetable to enable exports</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'faculty-load' && (
            <div className="space-y-4">
              {currentTerm ? (
                <>
                  <p className="text-gray-500">
                    Faculty load distribution for {currentTerm.academic_year} Sem {currentTerm.semester}
                  </p>
                  {loadSummary && (
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Faculty</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Theory Hours</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Practical Hours</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tutorial Hours</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Total Hours</th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Subjects</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                          {loadSummary.faculty_summary?.map((f) => (
                            <tr key={f.faculty_id} className="hover:bg-gray-50">
                              <td className="px-4 py-3 text-sm text-gray-900">{f.faculty_name}</td>
                              <td className="px-4 py-3 text-sm text-gray-900">{f.total_theory_hours}</td>
                              <td className="px-4 py-3 text-sm text-gray-900">{f.total_practical_hours}</td>
                              <td className="px-4 py-3 text-sm text-gray-900">{f.total_tutorial_hours}</td>
                              <td className="px-4 py-3 text-sm font-medium text-gray-900">{f.total_hours}</td>
                              <td className="px-4 py-3 text-sm text-gray-900">{f.subject_count}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <button className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                    <Download className="w-4 h-4 mr-2" />
                    Export Faculty Load Report
                  </button>
                </>
              ) : (
                <p className="text-gray-500">No current academic term set</p>
              )}
            </div>
          )}

          {activeTab === 'resource-util' && (
            <div className="space-y-4">
              <p className="text-gray-500">Resource utilization statistics - requires timetable data</p>
              {selectedTimetableId && (
                <button onClick={() => handleExport('resource')} className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                  <Download className="w-4 h-4 mr-2" />
                  Export Resource Utilization Report
                </button>
              )}
            </div>
          )}

          {activeTab === 'conflicts' && (
            <div className="space-y-4">
              {selectedTimetableId && summaryData ? (
                <>
                  <p className="text-gray-500">
                    {summaryData.validation?.status === 'PASS'
                      ? 'No conflicts detected in current timetable version.'
                      : `${summaryData.validation?.errors?.length || 0} conflict(s) detected.`
                    }
                  </p>
                  {summaryData.validation?.errors?.length && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                      <h4 className="font-medium text-red-800 mb-2">Conflicts:</h4>
                      <ul className="text-sm text-red-700 space-y-1">
                        {summaryData.validation.errors.map((error: string, i: number) => (
                          <li key={i}>• {error}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <button className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                    <Download className="w-4 h-4 mr-2" />
                    Export Conflict Report
                  </button>
                </>
              ) : (
                <p className="text-gray-500">Select a timetable to view conflicts</p>
              )}
            </div>
          )}

          {activeTab === 'validation' && (
            <div className="space-y-4">
              {selectedTimetableId && summaryData ? (
                <>
                  {summaryData.validation?.status === 'PASS' ? (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                      <div className="flex items-center">
                        <CheckCircle className="w-6 h-6 text-green-600 mr-3" />
                        <div>
                          <p className="font-medium text-green-800">Validation Passed</p>
                          <p className="text-sm text-green-700">
                            {summaryData.validation?.warnings?.length || 0} warning(s).
                          </p>
                        </div>
                      </div>
                    </div>
                  ) : summaryData.validation?.status === 'WARNING' ? (
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                      <div className="flex items-center">
                        <AlertTriangle className="w-6 h-6 text-yellow-600 mr-3" />
                        <div>
                          <p className="font-medium text-yellow-800">Validation Warning</p>
                          <p className="text-sm text-yellow-700">
                            {summaryData.validation?.warnings?.length || 0} warning(s).
                          </p>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                      <div className="flex items-center">
                        <AlertTriangle className="w-6 h-6 text-red-600 mr-3" />
                        <div>
                          <p className="font-medium text-red-800">Validation Failed</p>
                          <p className="text-sm text-red-700">
                            {summaryData.validation?.errors?.length || 0} error(s).
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                  <button className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                    <Download className="w-4 h-4 mr-2" />
                    Export Validation Report
                  </button>
                </>
              ) : (
                <p className="text-gray-500">Select a timetable to view validation results</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}