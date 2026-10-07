import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { DashboardLayout } from './layouts/DashboardLayout';
import { Dashboard } from './pages/Dashboard';
import { LoadDistribution } from './pages/Editorial/LoadDistribution';
import { Resources } from './pages/Editorial/Resources';
import { ClassTimetable } from './pages/Timetables/ClassTimetable';
import { FacultyTimetable } from './pages/Timetables/FacultyTimetable';
import { MasterTimetable } from './pages/Timetables/MasterTimetable';
import { Leave } from './pages/Leave';
import { Substitution } from './pages/Substitution';
import { Reports } from './pages/Reports';
import { Settings } from './pages/Settings';
import { Login } from './pages/Login';

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="editorial/load" element={<LoadDistribution />} />
          <Route path="editorial/resources" element={<Resources />} />
          <Route path="timetables/class" element={<ClassTimetable />} />
          <Route path="timetables/faculty" element={<FacultyTimetable />} />
          <Route path="timetables/master" element={<MasterTimetable />} />
          <Route path="leave" element={<Leave />} />
          <Route path="substitution" element={<Substitution />} />
          <Route path="reports" element={<Reports />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}

export default App;