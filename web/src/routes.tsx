import { Routes as RouterRoutes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import { Dashboard } from './components/Dashboard';
import { Login } from './components/Login';
import { ProjectDetails } from './components/Projects/ProjectDetails';
import { ProjectEdit } from './components/Projects/ProjectEdit';
import { AuthForm } from './components/Auth/AuthForm';

// PrivateRoute Komponente
function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { session } = useAuth();
  return session ? children : <Navigate to="/auth" />;
}

// Routes Komponente
export function Routes() {
  return (
    <RouterRoutes>
      <Route path="/auth" element={<AuthForm />} />
      
      <Route path="/" element={
        <PrivateRoute>
          <Dashboard />
        </PrivateRoute>
      } />
      
      <Route path="/login" element={<Login />} />
      
      <Route path="/projects/:id" element={
        <PrivateRoute>
          <ProjectDetails />
        </PrivateRoute>
      } />
      
      <Route path="/projects/:id/edit" element={
        <PrivateRoute>
          <ProjectEdit />
        </PrivateRoute>
      } />

      {/* Fallback Route */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </RouterRoutes>
  );
} 