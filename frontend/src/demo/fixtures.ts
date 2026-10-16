import type {
  AcademicTerm,
  Faculty,
  FacultyLoad,
  FacultyLoadSummary,
  LoadSummary,
  Resource,
  TimetableEntry,
  TimetableGenerateResponse,
  TimeSlot,
  TimetableTemplate,
  TimetableVersionWithEntries,
  UserResponse,
  WorkbookReadinessResponse,
} from '../api/types';

const NOW = '2026-01-01T00:00:00Z';

export const DEMO_USER: UserResponse = {
  id: 'demo-user',
  email: 'demo@slotify.local',
  full_name: 'Local Demo User',
  is_active: true,
  roles: ['ADMIN'],
};

export const DEMO_TERM: AcademicTerm = {
  id: 'demo-term-2026-27',
  name: 'Demo Semester I',
  academic_year: '2026-27',
  semester: 1,
  start_date: '2026-07-01',
  end_date: '2026-12-31',
  is_active: true,
  is_current: true,
};

export const DEMO_FACULTY: Faculty[] = [
  ['Demo Faculty', 'A', 'demo-a@slotify.local'],
  ['Demo Faculty', 'B', 'demo-b@slotify.local'],
  ['Demo Faculty', 'C', 'demo-c@slotify.local'],
  ['Demo Faculty', 'D', 'demo-d@slotify.local'],
].map(([first_name, last_name, email], index) => {
  return {
    id: `demo-faculty-${index + 1}`,
    employee_id: `DEMO-${String(index + 1).padStart(3, '0')}`,
    first_name,
    last_name,
    email,
    department: 'E&TC',
    designation: 'Demo Faculty',
    max_hours_per_week: 16,
    is_active: true,
    created_at: NOW,
    updated_at: NOW,
  };
});

export const DEMO_RESOURCES: Resource[] = [
  ['Demo Room 101', 'CLASSROOM'],
  ['Demo Lab 201', 'HARDWARE_LAB'],
  ['Demo Room 301', 'CLASSROOM'],
].map(([name, resource_type], index) => ({
  id: `demo-resource-${index + 1}`,
  name,
  resource_type,
  capacity: 60,
  building: 'Demo Block',
  floor: String(index + 1),
  room_number: String(101 + index * 100),
  is_emergency: false,
  is_active: true,
  created_at: NOW,
  updated_at: NOW,
}));

const DEMO_LOAD_SPECS: Array<[string, string, FacultyLoad['session_type'], number, number, number]> = [
  ['Demo Signals', 'Demo Class A', 'THEORY', 3, 0, 0],
  ['Demo Networks', 'Demo Class A', 'PRACTICAL', 0, 2, 0],
  ['Demo Control', 'Demo Class B', 'THEORY', 2, 0, 0],
  ['Demo Embedded Lab', 'Demo Class B', 'PRACTICAL', 0, 2, 0],
  ['Demo Communication', 'Demo Class C', 'TUTORIAL', 0, 0, 1],
  ['Demo Project', 'Demo Class C', 'PROJECT', 0, 0, 0],
];

export const DEMO_LOADS: FacultyLoad[] = DEMO_LOAD_SPECS.map(([subject, className, session_type, theory_hours, practical_hours, tutorial_hours], index) => ({
  id: `demo-load-${index + 1}`,
  faculty_id: DEMO_FACULTY[index % DEMO_FACULTY.length].id,
  academic_term_id: DEMO_TERM.id,
  subject_id: `DEMO-${subject.toUpperCase().replace(/ /g, '-')}`,
  class_id: `DEMO-${className.toUpperCase().replace(/ /g, '-')}`,
  section_id: `DEMO-SECTION-${(index % 3) + 1}`,
  batch_id: session_type === 'PRACTICAL' ? `demo-batch-${index + 1}` : null,
  session_type: session_type as FacultyLoad['session_type'],
  theory_hours,
  practical_hours,
  tutorial_hours,
  project_hours: 0,
  session_duration: 1,
  required_resource_type: session_type === 'PRACTICAL' ? 'HARDWARE_LAB' : 'CLASSROOM',
  notes: 'Deterministic local fixture. Not stored in the database.',
  is_active: true,
  is_approved: true,
  approved_by: 'demo-user',
  approved_at: NOW,
  created_by: 'demo-user',
  created_at: NOW,
  updated_at: NOW,
}));

export const DEMO_TIME_SLOTS: TimeSlot[] = [
  ['08:00:00', '09:00:00'],
  ['09:00:00', '10:00:00'],
  ['10:00:00', '11:00:00'],
  ['11:00:00', '12:00:00'],
  ['13:00:00', '14:00:00'],
  ['14:00:00', '15:00:00'],
].flatMap(([start_time, end_time], index) =>
  Array.from({ length: 6 }, (_, day_of_week) => ({
    id: `demo-slot-${day_of_week + 1}-${index + 1}`,
    template_id: 'demo-template-1',
    day_of_week,
    period_number: index + 1,
    start_time,
    end_time,
    slot_type: 'TEACHING',
    shift: 'MORNING',
    is_active: true,
  })),
);

const DEMO_PERIOD_TIMES = new Map(
  DEMO_TIME_SLOTS.filter((slot) => slot.day_of_week === 0).map((slot) => [
    slot.period_number,
    [slot.start_time, slot.end_time],
  ]),
);

export const DEMO_RESOLVED_ENTRIES: TimetableEntry[] = [
  [0, 1, 'Demo Signals', 'Demo Faculty A', 'Demo Class A', 'Demo Room 101', 'THEORY'],
  [0, 2, 'Demo Networks', 'Demo Faculty B', 'Demo Class A', 'Demo Lab 201', 'PRACTICAL'],
  [1, 1, 'Demo Control', 'Demo Faculty C', 'Demo Class B', 'Demo Room 301', 'THEORY'],
  [2, 3, 'Demo Embedded Lab', 'Demo Faculty D', 'Demo Class B', 'Demo Lab 201', 'PRACTICAL'],
  [3, 2, 'Demo Communication', 'Demo Faculty A', 'Demo Class C', 'Demo Room 101', 'TUTORIAL'],
].map(([day_of_week, period_number, subject_name, faculty_name, section_name, resource_name, session_type], index) => ({
  id: `demo-entry-${index + 1}`,
  version_id: 'demo-version-1',
  assignment_id: `demo-assignment-${index + 1}`,
  faculty_id: DEMO_FACULTY[index % DEMO_FACULTY.length].id,
  subject_id: `DEMO-SUBJECT-${index + 1}`,
  section_id: `DEMO-SECTION-${(index % 3) + 1}`,
  batch_id: session_type === 'PRACTICAL' ? `demo-batch-${index + 1}` : null,
  resource_id: DEMO_RESOURCES[index % DEMO_RESOURCES.length].id,
  time_slot_id: `demo-slot-${index + 1}`,
  day_of_week,
  period_number,
   start_time: DEMO_PERIOD_TIMES.get(Number(period_number))?.[0],
   end_time: DEMO_PERIOD_TIMES.get(Number(period_number))?.[1],
  session_type,
  subject_name,
  faculty_name,
  section_name,
  resource_name,
  batch_name: session_type === 'PRACTICAL' ? 'Demo Batch A' : null,
} as TimetableEntry));

export const DEMO_VERSION: TimetableVersionWithEntries = {
  id: 'demo-version-1',
  timetable_id: 'demo-timetable-1',
  version_number: 1,
  parent_version_id: null,
  change_type: 'DEMO_DATA',
  status: 'DEMO_DATA',
  change_summary: 'Deterministic local fixture. Not generated or validated by OR-Tools.',
  created_by: 'demo-user',
  created_at: NOW,
  entries: DEMO_RESOLVED_ENTRIES,
};

export const DEMO_TIMETABLE = {
  id: 'demo-timetable-1',
  name: 'Demo timetable (not solver output)',
  template_id: 'demo-template-1',
  academic_year: DEMO_TERM.academic_year,
  semester: DEMO_TERM.semester,
  status: 'DEMO_DATA',
  generated_by: null,
  approved_by: null,
  approved_at: null,
  created_at: NOW,
  updated_at: NOW,
};

export const DEMO_TEMPLATE: TimetableTemplate = {
  id: 'demo-template-1',
  name: 'Demo template (display only)',
  description: 'Local fixture template. It is not persisted.',
  academic_year: DEMO_TERM.academic_year,
  is_default: true,
  is_active: true,
};

export const DEMO_READINESS: WorkbookReadinessResponse = {
  timetable_id: DEMO_TIMETABLE.id,
  source_file: 'Demo fixture only',
  reference_file: 'Demo fixture timing only',
  timing_reference_available: true,
  timing_intervals: 6,
  source_sheet: 'Demo data',
  semester: DEMO_TERM.name,
  rows_read: DEMO_LOADS.length,
  source_demands: DEMO_LOADS.length,
  source_hours: 10,
  required_sessions: DEMO_RESOLVED_ENTRIES.length,
  unrepresented_hours: 0,
  invalid_rows: [],
  excluded_rows: [],
  ready: true,
};

const hoursFor = (load: FacultyLoad) => ({
  theory_hours: load.theory_hours,
  practical_hours: load.practical_hours,
  tutorial_hours: load.tutorial_hours,
  project_hours: load.project_hours,
});

const sumHours = (loads: FacultyLoad[]) =>
  loads.reduce(
    (total, load) =>
      total + load.theory_hours + load.practical_hours + load.tutorial_hours + load.project_hours,
    0,
  );

export const DEMO_FACULTY_SUMMARY: FacultyLoadSummary[] = DEMO_FACULTY.map((faculty) => {
  const loads = DEMO_LOADS.filter((load) => load.faculty_id === faculty.id);
  const hours = loads.reduce(
    (totals, load) => {
      const loadHours = hoursFor(load);
      return {
        theory_hours: totals.theory_hours + loadHours.theory_hours,
        practical_hours: totals.practical_hours + loadHours.practical_hours,
        tutorial_hours: totals.tutorial_hours + loadHours.tutorial_hours,
        project_hours: totals.project_hours + loadHours.project_hours,
      };
    },
    { theory_hours: 0, practical_hours: 0, tutorial_hours: 0, project_hours: 0 },
  );
  return {
    faculty_id: faculty.id,
    employee_id: faculty.employee_id,
    name: `${faculty.first_name} ${faculty.last_name}`,
    ...hours,
    total_hours: sumHours(loads),
    subject_count: loads.length,
  };
});

export const DEMO_CLASS_SUMMARY = [...new Set(DEMO_LOADS.map((load) => load.class_id))].map((classId) => {
  const loads = DEMO_LOADS.filter((load) => load.class_id === classId);
  return { class_id: classId, name: classId.replace('DEMO-', '').split('-').join(' '), total_hours: sumHours(loads) };
});

export const DEMO_SUBJECT_SUMMARY = [...new Set(DEMO_LOADS.map((load) => load.subject_id))].map((subjectId) => {
  const loads = DEMO_LOADS.filter((load) => load.subject_id === subjectId);
  return { subject_id: subjectId, code: subjectId.replace('DEMO-', ''), name: subjectId.replace('DEMO-', '').split('-').join(' '), total_hours: sumHours(loads) };
});

export const DEMO_LOAD_SUMMARY: LoadSummary = {
  faculty_summary: DEMO_FACULTY_SUMMARY,
  class_summary: DEMO_CLASS_SUMMARY,
  subject_summary: DEMO_SUBJECT_SUMMARY,
};

export const DEMO_GENERATION_BLOCKED: TimetableGenerateResponse = {
  success: false,
  error: 'Demo mode does not run OR-Tools or persist timetable versions.',
  stage: 'demo_mode',
  details: ['Open Master Timetable to view the clearly labeled deterministic demo fixture.'],
};
