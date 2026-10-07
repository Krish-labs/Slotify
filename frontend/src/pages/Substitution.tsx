import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { User, Plus, CheckCircle, XCircle, Calendar, Clock } from 'lucide-react';
import { leaveApi, facultyApi } from '../api';
import type { Substitution, Faculty } from '../api/types';

export function Substitution() {
  const queryClient = useQueryClient();
  const [filterStatus, setFilterStatus] = useState('all');
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    original_faculty_id: '',
    substitute_faculty_id: '',
    subject_id: '',
    class_id: '',
    section_id: '',
    batch_id: '',
    date: '',
    time_slot_id: '',
  });

  const { data: subsData, isLoading: subsLoading } = useQuery({
    queryKey: ['substitutions', filterStatus],
    queryFn: () => leaveApi.listSubstitutions({ status: filterStatus === 'all' ? undefined : filterStatus }),
  });

  const { data: facultyData } = useQuery({
    queryKey: ['faculty'],
    queryFn: () => facultyApi.list({ page_size: 100, is_active: true }),
  });

  const createMutation = useMutation({
    mutationFn: (data: { original_faculty_id: string; substitute_faculty_id: string; subject_id: string; class_id: string; section_id: string; batch_id: string | null; date: string; time_slot_id: string }) =>
      leaveApi.createSubstitution({
        original_faculty_id: data.original_faculty_id,
        substitute_faculty_id: data.substitute_faculty_id,
        subject_id: data.subject_id,
        class_id: data.class_id,
        section_id: data.section_id,
        batch_id: data.batch_id,
        date: data.date,
        time_slot_id: data.time_slot_id,
        status: 'PENDING',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['substitutions'] });
      setShowForm(false);
      setFormData({
        original_faculty_id: '',
        substitute_faculty_id: '',
        subject_id: '',
        class_id: '',
        section_id: '',
        batch_id: '',
        date: '',
        time_slot_id: '',
      });
    },
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => leaveApi.approveSubstitution(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['substitutions'] }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => leaveApi.rejectSubstitution(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['substitutions'] }),
  });

  const filteredSubs = subsData?.substitutions || [];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'APPROVED': return 'bg-green-100 text-green-800';
      case 'PENDING': return 'bg-yellow-100 text-yellow-800';
      case 'REJECTED': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'APPROVED': return <CheckCircle className="w-4 h-4" />;
      case 'PENDING': return <Clock className="w-4 h-4" />;
      case 'REJECTED': return <XCircle className="w-4 h-4" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.original_faculty_id || !formData.substitute_faculty_id || !formData.subject_id ||
        !formData.class_id || !formData.section_id || !formData.date || !formData.time_slot_id) {
      alert('Please fill all required fields');
      return;
    }
    createMutation.mutate({
      original_faculty_id: formData.original_faculty_id,
      substitute_faculty_id: formData.substitute_faculty_id,
      subject_id: formData.subject_id,
      class_id: formData.class_id,
      section_id: formData.section_id,
      batch_id: formData.batch_id || null,
      date: formData.date,
      time_slot_id: formData.time_slot_id,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Substitution Management</h1>
          <p className="text-gray-500">Manage faculty substitution requests</p>
        </div>
        <div className="flex items-center space-x-3">
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Status</option>
            <option value="PENDING">Pending</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Substitution
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          {subsLoading ? (
            <div className="p-8 text-center text-gray-500">Loading substitutions...</div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  {['Original Faculty', 'Substitute Faculty', 'Subject', 'Class', 'Date', 'Time', 'Status', 'Actions'].map((header) => (
                    <th key={header} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredSubs.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
                      No substitution requests found
                    </td>
                  </tr>
                ) : (
                  filteredSubs.map((sub: Substitution) => (
                    <tr key={sub.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="flex items-center space-x-2">
                          <User className="w-5 h-5 text-gray-400" />
                          <span className="font-medium text-gray-900">
                            {sub.original_faculty ? `${sub.original_faculty.first_name} ${sub.original_faculty.last_name}` : 'Unknown'}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center space-x-2">
                          <User className="w-5 h-5 text-blue-600" />
                          <span className="font-medium text-gray-900">
                            {sub.substitute_faculty ? `${sub.substitute_faculty.first_name} ${sub.substitute_faculty.last_name}` : 'Unknown'}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">{sub.subject_id}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{sub.class_id}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        <div className="flex items-center space-x-1">
                          <Calendar className="w-4 h-4 text-gray-400" />
                          {sub.date}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        <div className="flex items-center space-x-1">
                          <Clock className="w-4 h-4 text-gray-400" />
                          {sub.time_slot_id}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(sub.status)}`}>
                          {getStatusIcon(sub.status)}
                          <span className="ml-1">{sub.status}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {sub.status === 'PENDING' && (
                          <div className="flex items-center space-x-2">
                            <button
                              onClick={() => approveMutation.mutate(sub.id)}
                              disabled={approveMutation.isPending}
                              className="text-green-600 hover:text-green-900 disabled:opacity-50"
                              title="Approve"
                            >
                              <CheckCircle className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => rejectMutation.mutate(sub.id)}
                              disabled={rejectMutation.isPending}
                              className="text-red-600 hover:text-red-900 disabled:opacity-50"
                              title="Reject"
                            >
                              <XCircle className="w-4 h-4" />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">New Substitution Request</h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Original Faculty</label>
                <select
                  value={formData.original_faculty_id}
                  onChange={(e) => setFormData({ ...formData, original_faculty_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="">Select Original Faculty</option>
                  {facultyData?.items?.map((f: Faculty) => (
                    <option key={f.id} value={f.id}>
                      {f.first_name} {f.last_name} ({f.department})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Substitute Faculty</label>
                <select
                  value={formData.substitute_faculty_id}
                  onChange={(e) => setFormData({ ...formData, substitute_faculty_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="">Select Substitute Faculty</option>
                  {facultyData?.items?.map((f: Faculty) => (
                    <option key={f.id} value={f.id}>
                      {f.first_name} {f.last_name} ({f.department})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                <select
                  value={formData.subject_id}
                  onChange={(e) => setFormData({ ...formData, subject_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="">Select Subject</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Class / Section</label>
                <select
                  value={formData.class_id}
                  onChange={(e) => setFormData({ ...formData, class_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="">Select Class</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Section</label>
                <select
                  value={formData.section_id}
                  onChange={(e) => setFormData({ ...formData, section_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="">Select Section</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Date</label>
                  <input
                    type="date"
                    value={formData.date}
                    onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Time Slot</label>
                  <select
                    value={formData.time_slot_id}
                    onChange={(e) => setFormData({ ...formData, time_slot_id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    required
                  >
                    <option value="">Select Time Slot</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {createMutation.isPending ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}