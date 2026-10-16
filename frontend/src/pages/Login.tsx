import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { errorMessage } from '../utils/timetable';

export function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      await login(email, password);
      const destination = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
      navigate(destination && destination !== '/login' ? destination : '/dashboard', { replace: true });
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setError(
        status === 401
          ? 'Sign-in was not authorized. Check the account details or contact an administrator.'
          : errorMessage(err, 'Sign-in could not be completed. Check the service and try again.'),
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-[var(--paper)] px-4 py-12 text-[var(--ink)]">
      <div className="mx-auto w-full max-w-md">
        <div className="rule-top pt-4">
          <p className="kicker">Timetable Office</p>
          <h1 className="font-display mt-2 text-4xl">Sign in to Slotify</h1>
          <p className="mt-2 text-[var(--ink-secondary)]">Use an authorized department account to open the planning desk.</p>
        </div>

        <form onSubmit={handleSubmit} className="paper-panel mt-8 space-y-5 p-5">
          {error && (
            <div role="alert" className="border-l-4 border-[var(--ink)] bg-[var(--paper-inset)] px-3 py-2 text-sm">
              {error}
            </div>
          )}
          <label className="field-label">
            Email
            <input
              className="field-input mt-1"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label className="field-label">
            Password
            <input
              className="field-input mt-1"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          <button
            type="submit"
            disabled={isSubmitting}
            className="min-h-[44px] w-full bg-[var(--ink)] px-4 py-2 text-sm font-bold text-[var(--paper)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </main>
  );
}
