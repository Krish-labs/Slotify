import type { TimetableVersion } from '../api/types';

const READABLE_VERSION_STATUSES = new Set([
  'GENERATED',
  'VALIDATED',
  'UNDER_REVIEW',
  'APPROVED',
  'PUBLISHED',
  'DEMO_DATA',
]);

/** Prefer a version that can be read as timetable output, not a rejected/archive record. */
export function latestReadableVersion(versions: TimetableVersion[]): TimetableVersion | null {
  return versions.find((version) => READABLE_VERSION_STATUSES.has(version.status)) ?? null;
}

export function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'error' in detail) {
    const message = (detail as { error?: unknown }).error;
    if (typeof message === 'string') return message;
  }
  return fallback;
}
