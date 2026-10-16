import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { GenerateTimetable } from '../src/pages/Timetables/Generate';

const { stubs } = vi.hoisted(() => ({
  stubs: {
    academicTermApi: { list: vi.fn() },
    templateApi: { list: vi.fn() },
    timetableApi: {
      create: vi.fn(),
      workbookReadiness: vi.fn(),
      generateFromWorkbook: vi.fn(),
      repair: vi.fn(),
    },
  },
}));

vi.mock('../src/api', () => stubs);

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <GenerateTimetable />
    </QueryClientProvider>,
  );
}

const term = {
  id: 'term-1',
  name: 'Sem I 2026-27',
  academic_year: '2026-27',
  semester: 1,
  start_date: '2026-07-01',
  end_date: '2026-12-31',
  is_active: true,
  is_current: true,
};
const template = { id: 'tpl-1', name: 'Two-hour grid', academic_year: '2026-27' };

beforeEach(() => {
  vi.clearAllMocks();
  stubs.academicTermApi.list.mockResolvedValue({ items: [term], total: 1 });
  stubs.templateApi.list.mockResolvedValue([template]);
  stubs.timetableApi.create.mockResolvedValue({ id: 'tt-1', name: 'T', academic_year: '2026-27', semester: 1 });
  stubs.timetableApi.workbookReadiness.mockResolvedValue({
    ready: true,
    source_file: 'Load Distribution.xlsx',
    reference_file: 'TT.xlsx',
    semester: 'Semester I',
    source_demands: 0,
    required_sessions: 0,
    unrepresented_hours: 0,
    invalid_rows: [],
    excluded_rows: [],
  });
});

describe('GenerateTimetable repair step', () => {
  it('shows bounded repair after a failed generation and posts approval explicitly', async () => {
    stubs.timetableApi.generateFromWorkbook.mockRejectedValue({
      response: { data: { detail: { error: 'Solver did not produce a timetable', stage: 'cp_sat', details: ['INFEASIBLE'] } } },
    });
    stubs.timetableApi.repair.mockResolvedValue({
      success: true,
      repaired: true,
      version_number: 2,
      entries_count: 7,
      repair_attempts: 1,
      solver_status: 'OPTIMAL',
      validation_status: 'PASS',
    });

    renderPage();

    fireEvent.change(await screen.findByLabelText(/academic semester/i), { target: { value: '2026-27|1' } });
    fireEvent.click(await screen.findByRole('button', { name: /create timetable/i }));
    await waitFor(() => expect(stubs.timetableApi.workbookReadiness).toHaveBeenCalled());

    // Generation fails -> repair section appears (and only then).
    expect(screen.queryByRole('button', { name: /run bounded repair/i })).not.toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: /generate timetable from load distribution/i }));
    const repairButton = await screen.findByRole('button', { name: /run bounded repair/i });

    // Approval defaults to off: availability overrides need explicit opt-in.
    expect(stubs.timetableApi.repair).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(repairButton);

    await waitFor(() => expect(stubs.timetableApi.repair).toHaveBeenCalledTimes(1));
    expect(stubs.timetableApi.repair).toHaveBeenCalledWith('tt-1', {
      max_retries: 2,
      approve_hard_relaxation: true,
    });
    expect(await screen.findByText(/repaired and validated as version v2/i)).toBeInTheDocument();
  });

  it('surfaces repair diagnostics when repair cannot produce a valid timetable', async () => {
    stubs.timetableApi.generateFromWorkbook.mockRejectedValue({
      response: { data: { detail: { error: 'Solver did not produce a timetable', stage: 'cp_sat' } } },
    });
    stubs.timetableApi.repair.mockResolvedValue({
      error: 'Repair failed after 1 attempt(s)',
      stage: 'repair_exhausted',
      outcome: 'infeasible',
      repair_attempts: 1,
      attempts: [
        { attempt: 1, adjustment: { kind: 'full_regeneration' }, solver_status: 'INFEASIBLE', validation_errors: [], solver_diagnostics: ['room shortage'], applied: false },
      ],
      original_diagnostics: ['Coverage mismatch: assignment X'],
      unscheduled: [{ assignment_id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee', required_hours: 2, scheduled_hours: 0 }],
    });

    renderPage();

    fireEvent.change(await screen.findByLabelText(/academic semester/i), { target: { value: '2026-27|1' } });
    fireEvent.click(await screen.findByRole('button', { name: /create timetable/i }));
    await waitFor(() => expect(stubs.timetableApi.workbookReadiness).toHaveBeenCalled());
    fireEvent.click(await screen.findByRole('button', { name: /generate timetable from load distribution/i }));
    fireEvent.click(await screen.findByRole('button', { name: /run bounded repair/i }));

    expect(await screen.findByText(/repair failed after 1 attempt/i)).toBeInTheDocument();
    expect(screen.getByText(/coverage mismatch: assignment x/i)).toBeInTheDocument();
    expect(screen.getByText(/attempt 1 \(full_regeneration\): solver infeasible/i)).toBeInTheDocument();
  });
});
