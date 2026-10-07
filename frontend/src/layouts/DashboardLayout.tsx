import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, FileText, Building2, Calendar, User, Settings, ClipboardList, AlertTriangle } from 'lucide-react'

export function DashboardLayout() {
  const location = useLocation()

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Load Distribution', href: '/editorial/load', icon: FileText },
    { name: 'Resources', href: '/editorial/resources', icon: Building2 },
    { name: 'Class Timetable', href: '/timetables/class', icon: Calendar },
    { name: 'Faculty Timetable', href: '/timetables/faculty', icon: User },
    { name: 'Master Timetable', href: '/timetables/master', icon: ClipboardList },
    { name: 'Leave', href: '/leave', icon: AlertTriangle },
    { name: 'Substitution', href: '/substitution', icon: AlertTriangle },
    { name: 'Reports', href: '/reports', icon: ClipboardList },
    { name: 'Settings', href: '/settings', icon: Settings },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <aside className="fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-lg">
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-center h-16 border-b border-gray-200">
            <h1 className="text-xl font-bold text-blue-600">SchedulAI</h1>
          </div>
          <nav className="flex-1 px-4 py-4 space-y-2 overflow-y-auto">
            {navigation.map((item) => (
              <NavLink
                key={item.name}
                to={item.href}
                className={({ isActive }) =>
                  `flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`
                }
              >
                <item.icon className="w-5 h-5 mr-3" aria-hidden="true" />
                {item.name}
              </NavLink>
            ))}
          </nav>
        </div>
      </aside>

      <main className="ml-64 min-h-screen">
        <header className="sticky top-0 z-40 bg-white shadow-sm">
          <div className="flex items-center justify-between px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">
              {navigation.find(n => n.href === location.pathname)?.name || 'SchedulAI'}
            </h2>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-500">E&TC Department</span>
            </div>
          </div>
        </header>
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}