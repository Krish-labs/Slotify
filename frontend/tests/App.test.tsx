import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import App from '../src/App'
import { ThemeContext } from '../src/context/theme-context'
import { LOCAL_AUTH_DISABLED } from '../src/demo/mode'

describe('App', () => {
  it('shows the public landing at / with an entry to the planner', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    )
    expect(await screen.findByRole('link', { name: 'Open planner' })).toBeInTheDocument()
  })

  it('does not turn an authentication service outage into a sign-in redirect', async () => {
    if (LOCAL_AUTH_DISABLED) return

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <ThemeContext.Provider value={{ theme: 'light', toggleTheme: () => {}, setTheme: () => {} }}>
          <QueryClientProvider client={queryClient}>
            <App />
          </QueryClientProvider>
        </ThemeContext.Provider>
      </MemoryRouter>
    )
    expect(await screen.findByText('Session check unavailable')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Sign in to Slotify', level: 1 })).not.toBeInTheDocument()
  })

  it('opens the planner directly when local authentication is disabled', async () => {
    if (!LOCAL_AUTH_DISABLED) return

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <ThemeContext.Provider value={{ theme: 'light', toggleTheme: () => {}, setTheme: () => {} }}>
          <QueryClientProvider client={queryClient}>
            <App />
          </QueryClientProvider>
        </ThemeContext.Provider>
      </MemoryRouter>
    )

    expect(screen.getAllByRole('link', { name: 'Dashboard' })).toHaveLength(2)
    expect(screen.queryByRole('heading', { name: 'Sign in to Slotify', level: 1 })).not.toBeInTheDocument()
  })
})
