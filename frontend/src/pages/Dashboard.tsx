import { useQuery } from '@tanstack/react-query';
import { Users, Building2, Clock, AlertTriangle } from 'lucide-react';
import { academicTermApi, facultyApi, timetableApi, leaveApi } from '../api';
import type { AcademicTerm } from '../api/types';

export function Dashboard() {
  const { data: academicTerms } = useQuery({
    queryKey: ['academicTerms'],
    queryFn: () => academicTermApi.list({ page_size: 1 }),
  });

  const currentTerm = academicTerms?.items.find((t: AcademicTerm) => t.is_current) || academicTerms?.items[0];

  const { data: facultyData } = useQuery({
    queryKey: ['faculty', 'count'],
    queryFn: () => facultyApi.list({ page_size: 1 }),
    enabled: !!currentTerm,
  });

  const { data: timetables } = useQuery({
    queryKey: ['timetables'],
    queryFn: () => timetableApi.list(),
  });

  const { data: leaves } = useQuery({
    queryKey: ['leaves', 'pending'],
    queryFn: () => leaveApi.list({ status: 'PENDING' }),
  });

  const facultyCount = facultyData?.total || 0;
  const timetableCount = timetables?.timetables?.length || 0;
  const pendingLeavesCount = leaves?.leaves?.length || 0;
  const resourceCount = 0;

  const stats = [
    { name: 'Total Faculty', value: String(facultyCount), icon: Users, color: 'bg-blue-500' },
    { name: 'Classrooms', value: String(resourceCount), icon: Building2, color: 'bg-green-500' },
    { name: 'Timetables', value: String(timetableCount), icon: Clock, color: 'bg-purple-500' },
    { name: 'Pending Leaves', value: String(pendingLeavesCount), icon: AlertTriangle, color: 'bg-orange-500' },
  ];

  const recentActivity: Array<{ text: string; time: string }> = [];

  if (timetables?.timetables?.length) {
    recentActivity.push({
      text: `Timetable "${timetables.timetables[0].name}" ${timetables.timetables[0].status.toLowerCase()}`,
      time: 'Recently',
    });
  }
  if (leaves?.leaves?.length) {
    recentActivity.push({
      text: `${leaves.leaves.length} leave request(s) pending`,
      time: 'Today',
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500">
          {currentTerm
            ? `E&TC Department Timetable Management - ${currentTerm.academic_year} Sem ${currentTerm.semester}`
            : 'E&TC Department Timetable Management'}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <div key={stat.name} className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className={`p-3 rounded-full ${stat.color}`}>
                <stat.icon className="w-6 h-6 text-white" />
              </div>
              <div className="ml-4">
                <p className="text-sm text-gray-500">{stat.name}</p>
                <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h3>
          <div className="space-y-3">
            {recentActivity.length > 0 ? (
              recentActivity.map((activity, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <span className="text-sm text-gray-600">{activity.text}</span>
                  <span className="text-xs text-gray-400">{activity.time}</span>
                </div>
              ))
            ) : (
              <div className="text-center text-gray-500 py-8">
                No recent activity
              </div>
            )}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h3>
          <div className="space-y-3">
            <button className="w-full p-3 text-left bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors">
              <span className="font-medium text-blue-700">Import Load Distribution</span>
              <p className="text-sm text-gray-500">Upload Excel file to update faculty loads</p>
            </button>
            <button className="w-full p-3 text-left bg-green-50 rounded-lg hover:bg-green-100 transition-colors">
              <span className="font-medium text-green-700">Generate Timetable</span>
              <p className="text-sm text-gray-500">Create new timetable for current semester</p>
            </button>
            <button className="w-full p-3 text-left bg-purple-50 rounded-lg hover:bg-purple-100 transition-colors">
              <span className="font-medium text-purple-700">View Master Timetable</span>
              <p className="text-sm text-gray-500">Check current approved timetable</p>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}