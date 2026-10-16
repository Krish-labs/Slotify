import { useState, useEffect, useCallback, ReactNode } from 'react';
import { authApi } from '../api';
import { AuthContext, type AuthContextType } from './AuthContextTypes';
import { DEMO_USER } from '../demo/fixtures';
import { DEMO_MODE, LOCAL_AUTH_DISABLED } from '../demo/mode';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthContextType['user']>(null);
  const [token, setToken] = useState<string | null>(() => {
    if (DEMO_MODE) return 'demo-local';
    if (LOCAL_AUTH_DISABLED) return null;
    try {
      return localStorage.getItem('access_token');
    } catch {
      return null;
    }
  });
  const [isLoading, setIsLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const clearStoredToken = useCallback(() => {
    try {
      localStorage.removeItem('access_token');
    } catch {
      /* storage unavailable */
    }
    setToken(null);
    setUser(null);
  }, []);

  const isUnauthorized = (error: unknown) =>
    (error as { response?: { status?: number } })?.response?.status === 401;

  const refreshUser = useCallback(async () => {
    if (DEMO_MODE) {
      setSessionError(null);
      setUser(DEMO_USER);
      setToken('demo-local');
      setIsLoading(false);
      return;
    }
    if (LOCAL_AUTH_DISABLED) {
      setSessionError(null);
      setUser(null);
      setToken(null);
      setIsLoading(false);
      return;
    }

    setSessionError(null);
    // Cookie-only sessions have no localStorage token but are still valid.
    // Only a confirmed 401 is an expired session. Network and server failures
    // stay visible so an outage is not reported as a sign-in problem.
    try {
      const response = await authApi.me();
      setUser(response);
    } catch (meError) {
      if (!isUnauthorized(meError)) {
        setSessionError('The authentication service is unavailable. Retry before signing in again.');
        return;
      }
      try {
        const response = await authApi.refresh();
        if (response.access_token) {
          try {
            localStorage.setItem('access_token', response.access_token);
          } catch {
            /* storage unavailable */
          }
          setToken(response.access_token);
          setUser(await authApi.me());
          return;
        }
        clearStoredToken();
      } catch (refreshError) {
        if (!isUnauthorized(refreshError)) {
          setSessionError('The session could not be refreshed because the authentication service is unavailable.');
          return;
        }
        clearStoredToken();
      }
    } finally {
      setIsLoading(false);
    }
  }, [clearStoredToken]);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (email: string, password: string) => {
    if (DEMO_MODE) {
      setUser(DEMO_USER);
      setToken('demo-local');
      return;
    }
    if (LOCAL_AUTH_DISABLED) return;
    setSessionError(null);
    const response = await authApi.login({ email, password });
    const { access_token } = response;
    localStorage.setItem('access_token', access_token);
    setToken(access_token);
    setUser(await authApi.me());
  };

  const logout = () => {
    // Best-effort server revocation (H1); always clear local state.
    if (!DEMO_MODE && !LOCAL_AUTH_DISABLED) authApi.logout().catch(() => undefined);
    setSessionError(null);
    clearStoredToken();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        sessionError,
        isAuthenticated: !!user,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
