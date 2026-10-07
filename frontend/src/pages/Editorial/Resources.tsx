import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Building2, Monitor, Cpu, Plus, Edit, Trash2, Shield, Search, AlertCircle } from 'lucide-react';
import { resourceApi } from '../../api';
import type { Resource, ResourceListResponse } from '../../api/types';

export function Resources() {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('all');

  const { data: resourcesData, isLoading, error } = useQuery<ResourceListResponse>({
    queryKey: ['resources'],
    queryFn: () => resourceApi.list({ page_size: 100 }),
  });

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'CLASSROOM':
        return <Building2 className="w-4 h-4" />;
      case 'SOFTWARE_LAB':
        return <Monitor className="w-4 h-4" />;
      case 'HARDWARE_LAB':
        return <Cpu className="w-4 h-4" />;
      default:
        return <Building2 className="w-4 h-4" />;
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'CLASSROOM':
        return 'bg-blue-100 text-blue-800';
      case 'SOFTWARE_LAB':
        return 'bg-purple-100 text-purple-800';
      case 'HARDWARE_LAB':
        return 'bg-orange-100 text-orange-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const filteredResources = resourcesData?.items.filter((r: Resource) => {
    const matchesSearch =
      r.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.resource_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.building?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = filterType === 'all' || r.resource_type === filterType;
    return matchesSearch && matchesType;
  }) || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Resources</h1>
          <p className="text-gray-500">Manage classrooms, labs, and equipment</p>
        </div>
        <button className="flex items-center px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors">
          <Plus className="w-4 h-4 mr-2" />
          Add Resource
        </button>
      </div>

      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b border-gray-200 flex flex-wrap items-center justify-between gap-4">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Search resources..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Types</option>
            <option value="CLASSROOM">Classrooms</option>
            <option value="SOFTWARE_LAB">Software Labs</option>
            <option value="HARDWARE_LAB">Hardware Labs</option>
          </select>
        </div>

        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="p-8 text-center text-gray-500">Loading resources...</div>
          ) : error ? (
            <div className="p-8 text-center">
              <AlertCircle className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">Unable to load resources. The resources API is not yet implemented.</p>
              <p className="text-sm text-gray-400 mt-2">Please check backend implementation.</p>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  {['Name', 'Type', 'Capacity', 'Building', 'Floor', 'Room', 'Emergency', 'Actions'].map((header) => (
                    <th key={header} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredResources.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
                      No resources found
                    </td>
                  </tr>
                ) : (
                  filteredResources.map((resource: Resource) => (
                    <tr key={resource.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{resource.name}</td>
                      <td className="px-4 py-3 text-sm">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTypeColor(resource.resource_type)}`}>
                          {getTypeIcon(resource.resource_type)}
                          <span className="ml-1">{resource.resource_type.replace('_', ' ')}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">{resource.capacity}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{resource.building || '—'}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{resource.floor || '—'}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{resource.room_number || '—'}</td>
                      <td className="px-4 py-3 text-sm">
                        {resource.is_emergency ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                            <Shield className="w-3 h-3 mr-1" />
                            Emergency
                          </span>
                        ) : (
                          <span className="text-gray-400">Normal</span>
                        )}
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