import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useAuth } from '../hooks/useAuth';
import { ErrorState } from './ui/States';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isLoading, isAuthenticated, sessionError, refreshUser } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <div className="min-h-screen bg-[var(--paper)] p-8 text-center text-[var(--ink-secondary)]">Checking session…</div>;
  }

  if (sessionError) {
    return (
      <div className="min-h-screen bg-[var(--paper)] p-8">
        <ErrorState
          title="Session check unavailable"
          description={sessionError}
          retry={<button className="min-h-[44px] border border-[var(--rule-strong)] px-4 py-2 font-semibold" onClick={() => void refreshUser()}>Retry session check</button>}
        />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>;
}
