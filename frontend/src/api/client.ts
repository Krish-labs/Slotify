import axios, { type AxiosResponse } from 'axios';
import { demoAdapter } from '../demo/adapter';
import { DEMO_MODE, LOCAL_AUTH_DISABLED } from '../demo/mode';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // H5: send HttpOnly auth cookies alongside the Bearer fallback.
  withCredentials: true,
  // Solver calls (CP-SAT) can run for minutes; 60s covers API + proxy
  // defaults without hanging forever on a dead connection.
  timeout: 60000,
});

// The guarded demo adapter never reaches the backend or database.
if (DEMO_MODE) {
  apiClient.defaults.adapter = demoAdapter;
}

// Shared in-flight refresh promise to prevent concurrent refresh requests
let inFlightRefresh: Promise<AxiosResponse<{ access_token?: string }>> | null = null;

apiClient.interceptors.request.use((config) => {
  if (DEMO_MODE || LOCAL_AUTH_DISABLED) return config;

  // Bearer fallback for backwards compat; preferred path is the
  // HttpOnly cookie set by POST /auth/login (not readable from JS).
  const token = localStorage.getItem('access_token');
  // Never attach an access token to refresh. The browser sends the scoped
  // HttpOnly refresh cookie, and an expired access token must not shadow it.
  const url = config.url ?? '';
  if (token && !url.includes('/auth/refresh') && !url.includes('/auth/login')) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalConfig = error.config as unknown as {
      _retried?: boolean;
      url?: string;
      headers?: Record<string, unknown>;
    };

    if (LOCAL_AUTH_DISABLED) return Promise.reject(error);

    if (error.response?.status === 401) {
      const requestUrl = originalConfig?.url ?? '';
      const isAuthRequest = requestUrl.includes('/auth/');
      // Single refresh attempt before forcing login (H1 rotation support).
      if (
        originalConfig &&
        !originalConfig._retried &&
        typeof originalConfig.url === 'string' &&
        !isAuthRequest
      ) {
        // Prevent concurrent refresh requests. Every waiting request gets one
        // retry and cannot start a second refresh cycle.
        originalConfig._retried = true;
        const isRefreshOwner = !inFlightRefresh;
        if (!inFlightRefresh) {
          inFlightRefresh = apiClient.post<{ access_token?: string }>('/auth/refresh');
        }
        try {
          const refreshResponse = await inFlightRefresh;
          const next = refreshResponse.data?.access_token;
          if (next) {
            try {
              localStorage.setItem('access_token', next);
            } catch {
              /* storage unavailable */
            }
            originalConfig.headers = {
              ...((originalConfig.headers as Record<string, unknown> | undefined) ?? {}),
              Authorization: `Bearer ${next}`,
            };
          }
          return apiClient(originalConfig as never);
        } catch (refreshErr) {
          if ((refreshErr as { response?: { status?: number } })?.response?.status === 401) {
            try {
              localStorage.removeItem('access_token');
            } catch {
              /* storage unavailable */
            }
            if (window.location.pathname !== '/login' && window.location.pathname !== '/') {
              window.location.href = '/login';
            }
          }
          return Promise.reject(refreshErr);
        } finally {
          if (isRefreshOwner) inFlightRefresh = null;
        }
      }
      // Auth endpoints report their own failure. AuthContext decides whether
      // that means an anonymous visitor or an expired session.
      if (!isAuthRequest && window.location.pathname !== '/login' && window.location.pathname !== '/') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
