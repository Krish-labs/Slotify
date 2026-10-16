import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DEMO_FACULTY_SUMMARY, DEMO_LOADS, DEMO_LOAD_SUMMARY } from '../src/demo/fixtures';
import { TimetableGrid } from '../src/components/ui/TimetableGrid';
import { latestReadableVersion } from '../src/utils/timetable';
import type { TimetableVersion } from '../src/api/types';

describe('frontend reliability contracts', () => {
  it('derives demo faculty totals from theory, practical, tutorial, and project hours', () => {
    for (const summary of DEMO_FACULTY_SUMMARY) {
      expect(summary.total_hours).toBe(
        summary.theory_hours +
          summary.practical_hours +
          summary.tutorial_hours +
          summary.project_hours,
      );
      expect(summary.subject_count).toBe(
        DEMO_LOADS.filter((load) => load.faculty_id === summary.faculty_id).length,
      );
    }

    expect(DEMO_LOAD_SUMMARY.class_summary.length).toBeGreaterThan(0);
    expect(DEMO_LOAD_SUMMARY.subject_summary.length).toBeGreaterThan(0);
  });

  it('renders supplied template periods, free cells, and multiple entries in one cell', () => {
    render(
      <TimetableGrid
        caption="Reliability timetable"
        periods={[
          { period_number: 1, start_time: '08:00:00', end_time: '09:00:00' },
          { period_number: 2, start_time: '09:00:00', end_time: '10:00:00' },
        ]}
        entries={[
          {
            id: 'entry-1',
            day_of_week: 0,
            period_number: 1,
            session_type: 'THEORY',
            subject_label: 'Signals',
            line_two: 'Faculty A',
          },
          {
            id: 'entry-2',
            day_of_week: 0,
            period_number: 1,
            session_type: 'PRACTICAL',
            subject_label: 'Networks lab',
            line_two: 'Faculty B',
          },
        ]}
      />,
    );

    expect(screen.getByRole('rowheader', { name: /P1.*08:00 to 09:00/ })).toBeInTheDocument();
    expect(screen.getByRole('rowheader', { name: /P2.*09:00 to 10:00/ })).toBeInTheDocument();
    expect(screen.getByText('Signals')).toBeInTheDocument();
    expect(screen.getByText('Networks lab')).toBeInTheDocument();
    expect(screen.getAllByText('Free period').length).toBeGreaterThan(0);
  });

  it('does not select rejected or archived versions as the readable version', () => {
    const versions = [
      { id: 'v3', version_number: 3, status: 'ARCHIVED' },
      { id: 'v2', version_number: 2, status: 'REJECTED' },
      { id: 'v1', version_number: 1, status: 'VALIDATED' },
    ] as TimetableVersion[];

    expect(latestReadableVersion(versions)?.id).toBe('v1');
  });
});
