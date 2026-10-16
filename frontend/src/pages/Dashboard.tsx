import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Users, Building2, Clock, AlertTriangle } from 'lucide-react';
import { academicTermApi, facultyApi, timetableApi, leaveApi, resourceApi } from '../api';
import type { AcademicTerm } from '../api/types';
import { ErrorState, LoadingState } from '../components/ui/States';

export function Dashboard() {
  const academicTermsQuery = useQuery({
    queryKey: ['academicTerms', { page_size: 100 }],
    queryFn: () => academicTermApi.list({ page_size: 100 }),
  });
  const { data: academicTerms } = academicTermsQuery;

  const currentTerm = academicTerms?.items.find((t: AcademicTerm) => t.is_current) || academicTerms?.items[0];

  const facultyQuery = useQuery({
    queryKey: ['faculty', 'count'],
    queryFn: () => facultyApi.list({ page_size: 1 }),
  });
  const { data: facultyData } = facultyQuery;

  const timetablesQuery = useQuery({
    queryKey: ['timetables'],
    queryFn: () => timetableApi.list(),
  });
  const { data: timetables } = timetablesQuery;

  const leavesQuery = useQuery({
    queryKey: ['leaves', 'pending'],
    queryFn: () => leaveApi.list({ status: 'PENDING' }),
  });
  const { data: leaves } = leavesQuery;

  const resourcesQuery = useQuery({
    queryKey: ['resources', 'count'],
    queryFn: () => resourceApi.list({ page_size: 1 }),
  });

  const queries = [academicTermsQuery, facultyQuery, timetablesQuery, leavesQuery, resourcesQuery];
  if (queries.some((query) => query.isLoading)) {
    return <LoadingState label="Loading planning desk" />;
  }
  if (queries.some((query) => query.error)) {
    return (
      <ErrorState
        title="Dashboard data did not load"
        description="The planning desk could not read the current records. No fallback numbers are shown."
        retry={<button className="min-h-[44px] border border-[var(--rule-strong)] px-4 py-2 font-semibold" onClick={() => queries.forEach((query) => query.refetch())}>Retry dashboard</button>}
      />
    );
  }

  const facultyCount = facultyData?.total || 0;
  const timetableCount = timetables?.timetables?.length || 0;
  const pendingLeavesCount = leaves?.leaves?.length || 0;
  const resourceCount = resourcesQuery.data?.total || 0;

  const stats = [
    { name: 'Total Faculty', value: String(facultyCount), icon: Users, color: 'bg-blue-500' },
    { name: 'Resources', value: String(resourceCount), icon: Building2, color: 'bg-green-500' },
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
            <Link to="/editorial/load" className="block w-full rounded-lg bg-blue-50 p-3 text-left transition-colors hover:bg-blue-100">
              <span className="font-medium text-blue-700">Import Load Distribution</span>
              <p className="text-sm text-gray-500">Upload Excel file to update faculty loads</p>
            </Link>
            <Link to="/timetables/generate" className="block w-full rounded-lg bg-green-50 p-3 text-left transition-colors hover:bg-green-100">
              <span className="font-medium text-green-700">Generate Timetable</span>
              <p className="text-sm text-gray-500">Create new timetable for current semester</p>
            </Link>
            <Link to="/timetables/master" className="block w-full rounded-lg bg-purple-50 p-3 text-left transition-colors hover:bg-purple-100">
              <span className="font-medium text-purple-700">View Master Timetable</span>
              <p className="text-sm text-gray-500">Check current approved timetable</p>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
