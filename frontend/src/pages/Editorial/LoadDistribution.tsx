import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload, Download, Plus, Edit, Trash2, Search } from 'lucide-react';
import { academicTermApi, loadApi } from '../../api';
import type { FacultyLoad, FacultyLoadListResponse } from '../../api/types';

export function LoadDistribution() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTermId, setSelectedTermId] = useState<string | null>(null);

  const { data: terms } = useQuery({
    queryKey: ['academicTerms'],
    queryFn: () => academicTermApi.list({ page_size: 20 }),
  });

  const { data: loadData, isLoading, error } = useQuery<FacultyLoadListResponse>({
    queryKey: ['loadDistribution', selectedTermId, searchTerm],
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
      queryClient.invalidateQueries({ queryKey: ['loadDistribution'] });
    },
  });

  const filteredLoads = loadData?.items.filter((load: FacultyLoad) =>
    load.faculty?.first_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    load.faculty?.last_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    load.subject_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    load.class_id?.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

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
      console.error('Failed to download template:', err);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Load Distribution</h1>
          <p className="text-gray-500">Manage faculty teaching load assignments</p>
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
          <button onClick={downloadTemplate} className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors">
            <Download className="w-4 h-4 mr-2" />
            Export Template
          </button>
          <label className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors cursor-pointer">
            <Upload className="w-4 h-4 mr-2" />
            Import Excel
            <input type="file" accept=".xlsx,.xls" onChange={handleFileUpload} className="hidden" />
          </label>
          <button className="flex items-center px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors">
            <Plus className="w-4 h-4 mr-2" />
            Add Entry
          </button>
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

        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="p-8 text-center text-gray-500">Loading...</div>
          ) : error ? (
            <div className="p-8 text-center text-red-500">Error loading data: {String(error)}</div>
          ) : !selectedTermId ? (
            <div className="p-8 text-center text-gray-500">Please select an academic term to view load distribution</div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  {['Faculty', 'Subject', 'Class', 'Section', 'Theory', 'Practical', 'Tutorial', 'Type', 'Duration', 'Status', 'Actions'].map((header) => (
                    <th key={header} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredLoads.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="px-4 py-8 text-center text-gray-500">
                      No load entries found for this term
                    </td>
                  </tr>
                ) : (
                  filteredLoads.map((load: FacultyLoad) => (
                    <tr key={load.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {load.faculty ? `${load.faculty.first_name} ${load.faculty.last_name}` : 'Unknown'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">{load.subject_id}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{load.class_id}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{load.section_id}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {load.session_type === 'THEORY' ? load.hours_per_week : 0}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {load.session_type === 'PRACTICAL' ? load.hours_per_week : 0}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {load.session_type === 'TUTORIAL' ? load.hours_per_week : 0}
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
                      <td className="px-4 py-3 text-sm">
                        <div className="flex items-center space-x-2">
                          <button className="text-blue-600 hover:text-blue-900"><Edit className="w-4 h-4" /></button>
                          <button className="text-red-600 hover:text-red-900"><Trash2 className="w-4 h-4" /></button>
                        </div>
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