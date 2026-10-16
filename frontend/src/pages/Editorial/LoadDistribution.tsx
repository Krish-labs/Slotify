import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload, Download, Search } from 'lucide-react';
import { academicTermApi, facultyApi, loadApi } from '../../api';
import type { FacultyLoad, FacultyLoadListResponse } from '../../api/types';
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States';
import { DEMO_MODE } from '../../demo/mode';
import { errorMessage } from '../../utils/timetable';

export function LoadDistribution() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTermId, setSelectedTermId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const termsQuery = useQuery({
    queryKey: ['academicTerms', { page_size: 100 }],
    queryFn: () => academicTermApi.list({ page_size: 100 }),
  });
  const { data: terms } = termsQuery;

  const facultyQuery = useQuery({
    queryKey: ['faculty', { page_size: 100 }],
    queryFn: () => facultyApi.list({ page_size: 100 }),
  });

  useEffect(() => {
    if (!selectedTermId && terms?.items.length) {
      setSelectedTermId((terms.items.find((term) => term.is_current) ?? terms.items[0]).id);
    }
  }, [selectedTermId, terms]);

  const { data: loadData, isLoading, error } = useQuery<FacultyLoadListResponse>({
    queryKey: ['loadDistribution', selectedTermId],
    queryFn: () =>
      loadApi.list({
        academic_term_id: selectedTermId || undefined,
        page_size: 100,
      }),
    enabled: !!selectedTermId,
  });

  const importMutation = useMutation({
    mutationFn: (file: File) => loadApi.import(file),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['loadDistribution'] });
    },
    onError: (error) => setActionError(errorMessage(error, 'The load import failed.')),
  });

  const facultyById = useMemo(
    () => new Map((facultyQuery.data?.items ?? []).map((faculty) => [faculty.id, faculty])),
    [facultyQuery.data],
  );
  const filteredLoads = loadData?.items.filter((load: FacultyLoad) => {
    const faculty = facultyById.get(load.faculty_id);
    const facultyName = faculty ? `${faculty.first_name} ${faculty.last_name}` : '';
    return facultyName.toLowerCase().includes(searchTerm.toLowerCase()) ||
    load.subject_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    load.class_id?.toLowerCase().includes(searchTerm.toLowerCase())
  }) || [];

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      importMutation.mutate(file);
    }
  };

  const downloadTemplate = async () => {
    try {
      const blob = await loadApi.getTemplate();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'load_distribution_template.xlsx';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setActionError(errorMessage(err, 'The load template could not be downloaded.'));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Load Distribution</h1>
          <p className="text-gray-500">Manage faculty teaching load assignments</p>
          {DEMO_MODE && <p className="mt-1 text-sm font-semibold text-amber-800">DEMO DATA · Read-only fixture rows. Import and edits are disabled.</p>}
        </div>
        <div className="flex flex-wrap items-center space-x-3">
          <select
            value={selectedTermId || ''}
            onChange={(e) => setSelectedTermId(e.target.value || null)}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 min-w-[250px]"
          >
            <option value="">Select Academic Term</option>
            {terms?.items.map((term) => (
              <option key={term.id} value={term.id}>
                {term.academic_year} Sem {term.semester} ({term.name})
              </option>
            ))}
          </select>
           <button onClick={downloadTemplate} disabled={DEMO_MODE} className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:cursor-not-allowed disabled:opacity-50">
            <Download className="w-4 h-4 mr-2" />
            Export Template
          </button>
           <label className={`flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg transition-colors ${DEMO_MODE ? 'cursor-not-allowed opacity-50' : 'cursor-pointer hover:bg-blue-700'}`}>
            <Upload className="w-4 h-4 mr-2" />
            Import Excel
             <input type="file" accept=".xlsx,.xls" onChange={handleFileUpload} disabled={DEMO_MODE} className="hidden" />
          </label>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Search faculty, subject, class..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

         {actionError && <p className="border-t border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert">{actionError}</p>}
         <div className="overflow-x-auto">
          {termsQuery.isLoading || facultyQuery.isLoading || isLoading ? (
            <LoadingState label="Loading load distribution" />
          ) : termsQuery.error || facultyQuery.error || error ? (
            <ErrorState
              title="Load distribution did not load"
              description="The selected term or its load rows could not be read. No fallback rows are shown."
              retry={<button className="min-h-[44px] border border-[var(--rule-strong)] px-4 py-2 font-semibold" onClick={() => { void termsQuery.refetch(); void facultyQuery.refetch(); void queryClient.invalidateQueries({ queryKey: ['loadDistribution'] }); }}>Retry load data</button>}
            />
          ) : !selectedTermId ? (
            <div className="p-8 text-center text-gray-500">Please select an academic term to view load distribution</div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                   {['Faculty', 'Subject', 'Class', 'Section', 'Theory', 'Practical', 'Tutorial', 'Project', 'Type', 'Duration', 'Status'].map((header) => (
                    <th key={header} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredLoads.length === 0 ? (
                   <tr>
                     <td colSpan={11}>
                       <EmptyState title="No load entries found" description="This term has no rows matching the current search." />
                     </td>
                   </tr>
                ) : (
                  filteredLoads.map((load: FacultyLoad) => (
                    <tr key={load.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm text-gray-900">
                         {(() => {
                           const faculty = facultyById.get(load.faculty_id);
                           return faculty ? `${faculty.first_name} ${faculty.last_name}` : `Faculty ${load.faculty_id.slice(0, 8)}`;
                         })()}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">{load.subject_id}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{load.class_id}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{load.section_id}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {load.theory_hours}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {load.practical_hours}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {load.tutorial_hours}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {load.project_hours}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          {load.session_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">{load.session_duration}hr</td>
                      <td className="px-4 py-3 text-sm">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          load.is_approved ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                        }`}>
                          {load.is_approved ? 'Approved' : 'Pending'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
