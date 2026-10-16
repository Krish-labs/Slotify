export function isLocalDemoEnvironment({
  enabled,
  dev,
  hostname,
}: {
  enabled: string | undefined;
  dev: boolean;
  hostname: string;
}) {
  return enabled === 'true' && dev && ['localhost', '127.0.0.1', '::1'].includes(hostname);
}

export const DEMO_MODE = isLocalDemoEnvironment({
  enabled: import.meta.env.VITE_DEMO_MODE,
  dev: import.meta.env.DEV,
  hostname: typeof window === 'undefined' ? '' : window.location.hostname,
});

// Unlike DEMO_MODE, this keeps the real API and database path enabled.
export const LOCAL_AUTH_DISABLED = isLocalDemoEnvironment({
  enabled: import.meta.env.VITE_AUTH_DISABLED,
  dev: import.meta.env.DEV,
  hostname: typeof window === 'undefined' ? '' : window.location.hostname,
});
