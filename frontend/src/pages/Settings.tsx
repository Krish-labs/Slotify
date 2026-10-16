import { useState } from 'react';
import { User, Bell, Shield, Palette, Database, Key, Download } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../context/useTheme';
import { DEMO_MODE } from '../demo/mode';

export function Settings() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('profile');
  const { theme, setTheme } = useTheme();
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    department: '',
    role: '',
  });

  const tabs = [
    { id: 'profile', name: 'Profile', icon: User },
    { id: 'notifications', name: 'Notifications', icon: Bell },
    { id: 'security', name: 'Security', icon: Shield },
    { id: 'appearance', name: 'Appearance', icon: Palette },
    { id: 'data', name: 'Data Management', icon: Database },
    { id: 'api', name: 'API Keys', icon: Key },
  ];

  // Initialize form data from user
  if (user && !formData.first_name) {
    const nameParts = user.full_name?.split(' ') || ['', ''];
    setFormData({
      first_name: nameParts[0] || '',
      last_name: nameParts.slice(1).join(' ') || '',
      email: user.email || '',
      department: '',
      role: user.roles?.[0] || '',
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500">Manage your account and application preferences</p>
        <p className="mt-1 text-sm font-semibold text-amber-800">{DEMO_MODE ? 'DEMO DATA · Account settings are read-only.' : 'Account profile updates are not available from the backend yet.'}</p>
      </div>

      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200">
          <nav className="flex overflow-x-auto px-4" aria-label="Settings tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center px-4 py-4 border-b-2 text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className="w-5 h-5 mr-2" />
                {tab.name}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6 max-w-3xl">
          {activeTab === 'profile' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
                  <input
                    type="text"
                    value={formData.first_name}
                     readOnly
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
                  <input
                    type="text"
                    value={formData.last_name}
                     readOnly
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                   <input
                     type="email"
                     value={formData.email}
                     readOnly
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
                <input
                  type="text"
                  value={formData.department}
                  onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="Not editable from here"
                  readOnly
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
                <input
                  type="text"
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="Assigned by administrator"
                  readOnly
                />
              </div>
               <p className="border border-[var(--rule)] bg-[var(--paper-inset)] px-3 py-2 text-sm text-[var(--ink-secondary)]">Profile changes are display-only until a backend profile update endpoint is available.</p>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">Email Notifications</h3>
              <div className="space-y-4">
                {[
                  { label: 'Timetable Generated', desc: 'Receive email when a new timetable is generated' },
                  { label: 'Leave Requests', desc: 'Get notified about leave applications' },
                  { label: 'Substitution Requests', desc: 'Get notified about substitution requests' },
                  { label: 'Timetable Approved', desc: 'Receive email when timetable is approved' },
                  { label: 'Conflict Alerts', desc: 'Get notified about scheduling conflicts' },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-gray-900">{item.label}</p>
                      <p className="text-sm text-gray-500">{item.desc}</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" defaultChecked className="sr-only peer" />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'security' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Change Password</h3>
                  <form className="space-y-4" onSubmit={(event) => event.preventDefault()}>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Current Password</label>
                    <input type="password" className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
                    <input type="password" className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Confirm New Password</label>
                    <input type="password" className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
                  </div>
                   <button type="submit" disabled className="px-4 py-2 bg-blue-600 text-white rounded-lg opacity-50">Password update unavailable</button>
                </form>
              </div>
              <div className="border-t border-gray-200 pt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Two-Factor Authentication</h3>
                <p className="text-gray-500 mb-4">Add an extra layer of security to your account.</p>
                 <button disabled className="px-4 py-2 bg-gray-600 text-white rounded-lg opacity-50">2FA setup unavailable</button>
              </div>
            </div>
          )}

          {activeTab === 'appearance' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Theme</h3>
                <div className="grid grid-cols-3 gap-4">
                  {(['light', 'dark'] as const).map((themeOption) => (
                    <button
                      key={themeOption}
                      type="button"
                      onClick={() => setTheme(themeOption)}
                      aria-pressed={theme === themeOption}
                      className={`p-4 border-2 rounded-lg text-center transition-colors ${theme === themeOption ? 'border-blue-600 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}
                    >
                      <p className="font-medium text-gray-900">{themeOption === 'light' ? 'Light' : 'Dark'}</p>
                      <p className="text-sm text-gray-500 mt-1">{themeOption} mode</p>
                    </button>
                  ))}
                </div>
              </div>
              <div className="border-t border-gray-200 pt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Density</h3>
                <div className="flex space-x-4">
                  {['Comfortable', 'Compact'].map((density) => (
                    <label key={density} className="flex items-center cursor-pointer">
                      <input type="radio" name="density" className="mr-2" />
                      <span className="text-gray-900">{density}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'data' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Export Data</h3>
                <div className="space-y-3">
                   <div className="w-full flex items-center justify-between p-4 border border-gray-200">
                    <div>
                      <p className="font-medium text-gray-900">Export All Timetables</p>
                      <p className="text-sm text-gray-500">Download all timetable data as Excel</p>
                    </div>
                    <Download className="w-5 h-5 text-gray-400" />
                   </div>
                   <div className="w-full flex items-center justify-between p-4 border border-gray-200">
                    <div>
                      <p className="font-medium text-gray-900">Export Faculty Data</p>
                      <p className="text-sm text-gray-500">Download faculty information</p>
                    </div>
                    <Download className="w-5 h-5 text-gray-400" />
                   </div>
                   <div className="w-full flex items-center justify-between p-4 border border-gray-200">
                    <div>
                      <p className="font-medium text-gray-900">Export Resource Data</p>
                      <p className="text-sm text-gray-500">Download resource configurations</p>
                    </div>
                    <Download className="w-5 h-5 text-gray-400" />
                   </div>
                   <p className="text-sm text-gray-500">Data exports are not connected to a backend endpoint yet.</p>
                </div>
              </div>
              <div className="border-t border-gray-200 pt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Import Data</h3>
                <div className="space-y-3">
                  <div className="p-4 border border-gray-200 rounded-lg">
                    <p className="font-medium text-gray-900">Import Load Distribution</p>
                    <p className="text-sm text-gray-500">Upload Excel file to update faculty loads</p>
                     <input type="file" accept=".xlsx,.xls" disabled className="mt-2 w-full px-3 py-2 border border-gray-300 rounded-lg opacity-50" />
                     <p className="mt-1 text-sm text-gray-500">Import is available from Load Distribution.</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'api' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">API Keys</h3>
                <p className="text-gray-500 mb-4">Manage API keys for external integrations.</p>
                 <button disabled className="px-4 py-2 bg-blue-600 text-white rounded-lg opacity-50">API keys unavailable</button>
              </div>
              <div className="border-t border-gray-200 pt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Existing Keys</h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                    <div>
                      <p className="font-medium text-gray-900">No API keys configured</p>
                      <p className="text-sm text-gray-500 font-mono">Generate a key to get started</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
