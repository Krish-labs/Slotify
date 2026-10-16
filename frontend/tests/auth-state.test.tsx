import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../src/context/AuthContext';
import { ProtectedRoute } from '../src/components/ProtectedRoute';

const { authApi } = vi.hoisted(() => ({
  authApi: {
    me: vi.fn(),
    refresh: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
}));

vi.mock('../src/api', () => ({ authApi }));

function renderProtected() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/private']}>
        <AuthProvider>
          <Routes>
            <Route path="/private" element={<ProtectedRoute><p>Private timetable</p></ProtectedRoute>} />
            <Route path="/login" element={<p>Sign in</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  authApi.me.mockRejectedValue({ response: { status: 401 } });
  authApi.refresh.mockRejectedValue({ response: { status: 401 } });
});

describe('authentication state handling', () => {
  it('redirects to sign-in after a confirmed expired session', async () => {
    renderProtected();

    expect(await screen.findByText('Sign in')).toBeInTheDocument();
    expect(authApi.refresh).toHaveBeenCalledTimes(1);
  });

  it('keeps an authentication outage visible instead of redirecting', async () => {
    authApi.me.mockRejectedValue({ response: { status: 503 } });
    renderProtected();

    expect(await screen.findByText('Session check unavailable')).toBeInTheDocument();
    expect(authApi.refresh).not.toHaveBeenCalled();
  });
});
