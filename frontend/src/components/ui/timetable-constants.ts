export interface GridEntry {
  id: string;
  day_of_week: number;
  period_number: number;
  start_time?: string | null;
  end_time?: string | null;
  session_type?: string | null;
  subject_label: string;
  line_two: string;
  line_three?: string;
  batch_label?: string | null;
}

export interface GridPeriod {
  period_number: number;
  start_time?: string | null;
  end_time?: string | null;
}

export const GRID_DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'] as const;
