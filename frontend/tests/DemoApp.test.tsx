import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import App from '../src/App';
import { ThemeContext } from '../src/context/theme-context';
import { DEMO_MODE } from '../src/demo/mode';

describe('local demo app', () => {
  it('opens the fixture dashboard without login when demo mode is enabled', async () => {
    if (!DEMO_MODE) return;

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <ThemeContext.Provider value={{ theme: 'light', toggleTheme: () => {}, setTheme: () => {} }}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/dashboard']}>
            <App />
          </MemoryRouter>
        </QueryClientProvider>
      </ThemeContext.Provider>,
    );

    expect(await screen.findByRole('heading', { name: 'Dashboard', level: 1 })).toBeInTheDocument();
    expect(screen.getByText(/DEMO DATA/)).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });
});
