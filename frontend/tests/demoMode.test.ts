import { describe, expect, it } from 'vitest';
import { isLocalDemoEnvironment } from '../src/demo/mode';

describe('local demo mode guard', () => {
  it('enables fixtures only for the Vite dev server on localhost', () => {
    expect(isLocalDemoEnvironment({ enabled: 'true', dev: true, hostname: 'localhost' })).toBe(true);
    expect(isLocalDemoEnvironment({ enabled: 'true', dev: true, hostname: '127.0.0.1' })).toBe(true);
  });

  it('rejects production builds and non-local hosts', () => {
    expect(isLocalDemoEnvironment({ enabled: 'true', dev: false, hostname: 'localhost' })).toBe(false);
    expect(isLocalDemoEnvironment({ enabled: 'true', dev: true, hostname: 'demo.example.com' })).toBe(false);
    expect(isLocalDemoEnvironment({ enabled: 'false', dev: true, hostname: 'localhost' })).toBe(false);
  });
});
