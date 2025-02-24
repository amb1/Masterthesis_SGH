import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth'; // Sie müssen diesen Hook erstellen

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div>Laden...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
} 