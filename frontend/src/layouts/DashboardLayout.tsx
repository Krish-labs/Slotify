import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { Sun, Moon, LogOut } from 'lucide-react';
import { useTheme } from '../context/useTheme';
import { useAuth } from '../hooks/useAuth';
import { DEMO_MODE, LOCAL_AUTH_DISABLED } from '../demo/mode';

const GROUPS: Array<{ heading: string; items: Array<{ name: string; href: string }> }> = [
  {
    heading: 'Plan',
    items: [
      { name: 'Dashboard', href: '/dashboard' },
      { name: 'Load Distribution', href: '/editorial/load' },
      { name: 'Resources', href: '/editorial/resources' },
    ],
  },
  {
    heading: 'Timetables',
    items: [
      { name: 'Generate Timetable', href: '/timetables/generate' },
      { name: 'Class Timetable', href: '/timetables/class' },
      { name: 'Faculty Timetable', href: '/timetables/faculty' },
      { name: 'Master Timetable', href: '/timetables/master' },
    ],
  },
  {
    heading: 'People',
    items: [
      { name: 'Leave', href: '/leave' },
      { name: 'Substitution', href: '/substitution' },
    ],
  },
  {
    heading: 'Office',
    items: [
      { name: 'Reports', href: '/reports' },
      { name: 'Analytics', href: '/analytics' },
      { name: 'Settings', href: '/settings' },
    ],
  },
];

const FLAT = GROUPS.flatMap((g) => g.items);

/*
 * Reason for the ledger sidebar: navigation is grouped by workflow stage.
 * The active page gets a solid ink marker plus bold text, never color alone.
 */
export function DashboardLayout() {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { logout } = useAuth();
  const active = FLAT.find((n) => n.href === location.pathname)?.name ?? 'Slotify';

  return (
    <div className="min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[60] focus:bg-[var(--ink)] focus:px-3 focus:py-2 focus:text-[var(--paper)]">
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 z-50 hidden w-64 flex-col border-r border-[var(--rule)] bg-[var(--paper-raised)] md:flex" aria-label="Primary">
        <div className="border-b-2 border-[var(--ink)] px-5 py-4">
          <p className="kicker">Timetable Office</p>
          <p className="font-display text-2xl leading-none">Slotify</p>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {GROUPS.map((group) => (
            <div key={group.heading} className="mb-4">
              <p className="px-2 font-mono text-[0.68rem] uppercase tracking-[0.14em] text-[var(--ink-muted)]">
                {group.heading}
              </p>
              <ul className="mt-1 space-y-0.5">
                {group.items.map((item) => (
                  <li key={item.href}>
                    <NavLink
                      to={item.href}
                      className={({ isActive }) =>
                        `flex items-center gap-3 border-l-2 px-2 py-2 text-sm transition-colors ${
                          isActive
                            ? 'border-[var(--ink)] bg-[var(--paper-inset)] font-bold text-[var(--ink)]'
                            : 'border-transparent text-[var(--ink-secondary)] hover:bg-[var(--paper-inset)] hover:text-[var(--ink)]'
                        }`
                      }
                    >
                      {item.name}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="border-t border-[var(--rule)] px-5 py-3 text-xs text-[var(--ink-muted)]">
           <p>{DEMO_MODE ? 'Local demo mode' : LOCAL_AUTH_DISABLED ? 'Local prototype' : 'Authorized session'}</p>
        </div>
      </aside>

      <div className="md:ml-64">
        <header className="sticky top-0 z-40 border-b border-[var(--rule)] bg-[var(--paper)]">
          {DEMO_MODE && (
            <div className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-xs font-semibold text-amber-950 md:px-6" role="status">
              DEMO DATA · Local frontend fixtures only. No backend, database, or OR-Tools calls are made.
            </div>
          )}
          <div className="flex items-center justify-between gap-3 px-4 py-3 md:px-6">
            <div className="min-w-0">
              <p className="kicker md:hidden">Slotify</p>
              <h2 className="truncate font-display text-lg text-[var(--ink)]">{active}</h2>
            </div>
            <div className="flex items-center gap-2">
              {!DEMO_MODE && !LOCAL_AUTH_DISABLED && (
                <button
                  onClick={logout}
                  className="inline-flex min-h-[44px] items-center gap-1 rounded border border-[var(--rule-strong)] px-3 text-sm font-semibold text-[var(--ink)] hover:bg-[var(--paper-inset)]"
                >
                  <LogOut className="h-4 w-4" aria-hidden="true" />
                  Sign out
                </button>
              )}
              <button
                onClick={toggleTheme}
                className="rounded border border-[var(--rule-strong)] p-2 text-[var(--ink)] hover:bg-[var(--paper-inset)]"
                aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
                aria-pressed={theme === 'dark'}
              >
                {theme === 'light' ? (
                  <Moon className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Sun className="h-4 w-4" aria-hidden="true" />
                )}
              </button>
            </div>
          </div>
          <nav aria-label="Sections" className="flex gap-1 overflow-x-auto border-t border-[var(--rule)] px-4 py-2 md:hidden">
            {FLAT.map((item) => (
              <NavLink
                key={item.href}
                to={item.href}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded border px-2 py-1 text-xs font-semibold ${
                    isActive
                      ? 'border-[var(--ink)] bg-[var(--ink)] text-[var(--paper)]'
                      : 'border-[var(--rule)] text-[var(--ink-secondary)]'
                  }`
                }
              >
                {item.name}
              </NavLink>
            ))}
          </nav>
        </header>
        <main id="main-content" className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 md:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
