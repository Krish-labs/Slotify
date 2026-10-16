import { Navigate, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { DashboardLayout } from './layouts/DashboardLayout';
import { Dashboard } from './pages/Dashboard';
import { Landing } from './pages/Landing';
import { Login } from './pages/Login';
import { LoadDistribution } from './pages/Editorial/LoadDistribution';
import { Resources } from './pages/Editorial/Resources';
import { ClassTimetable } from './pages/Timetables/ClassTimetable';
import { FacultyTimetable } from './pages/Timetables/FacultyTimetable';
import { MasterTimetable } from './pages/Timetables/MasterTimetable';
import { GenerateTimetable } from './pages/Timetables/Generate';
import { Leave } from './pages/Leave';
import { Analytics } from './pages/Analytics';
import { Substitution } from './pages/Substitution';
import { Reports } from './pages/Reports';
import { Settings } from './pages/Settings';
import { DEMO_MODE, LOCAL_AUTH_DISABLED } from './demo/mode';

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={DEMO_MODE || LOCAL_AUTH_DISABLED ? <Navigate to="/dashboard" replace /> : <Login />} />
        <Route element={LOCAL_AUTH_DISABLED ? <DashboardLayout /> : <ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="editorial/load" element={<LoadDistribution />} />
          <Route path="editorial/resources" element={<Resources />} />
          <Route path="timetables/generate" element={<GenerateTimetable />} />
          <Route path="timetables/class" element={<ClassTimetable />} />
          <Route path="timetables/faculty" element={<FacultyTimetable />} />
          <Route path="timetables/master" element={<MasterTimetable />} />
          <Route path="leave" element={<Leave />} />
          <Route path="substitution" element={<Substitution />} />
          <Route path="reports" element={<Reports />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}

export default App;
