export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AcademicTerm {
  id: string;
  name: string;
  academic_year: string;
  semester: number;
  start_date: string;
  end_date: string;
  is_active: boolean;
  is_current: boolean;
}

export interface AcademicTermListResponse {
  items: AcademicTerm[];
  total: number;
  page: number;
  page_size: number;
}

export interface Faculty {
  id: string;
  employee_id: string;
  first_name: string;
  last_name: string;
  email: string;
  department: string;
  designation: string;
  max_hours_per_week: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FacultyListResponse {
  items: Faculty[];
  total: number;
  page: number;
  page_size: number;
}

export interface Subject {
  id: string;
  code: string;
  name: string;
  subject_type: string;
  credits: number;
  theory_hours: number;
  practical_hours: number;
  tutorial_hours: number;
  semester: number;
  department: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SubjectListResponse { items: Subject[]; total: number; page: number; page_size: number }

export interface AcademicClass {
  id: string;
  name: string;
  year: number;
  branch: string;
  academic_year: string;
  strength: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AcademicClassListResponse { items: AcademicClass[]; total: number; page: number; page_size: number }

export interface Section {
  id: string;
  class_id: string;
  name: string;
  strength: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SectionListResponse { items: Section[]; total: number; page: number; page_size: number }

export interface Batch {
  id: string;
  section_id: string;
  name: string;
  batch_number: number;
  strength: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BatchListResponse { items: Batch[]; total: number; page: number; page_size: number }

export interface SessionType {
  THEORY: 'THEORY';
  PRACTICAL: 'PRACTICAL';
  TUTORIAL: 'TUTORIAL';
  PROJECT: 'PROJECT';
}

export type SessionTypeValue = 'THEORY' | 'PRACTICAL' | 'TUTORIAL' | 'PROJECT';

export interface FacultyLoad {
  id: string;
  faculty_id: string;
  academic_term_id: string;
  subject_id: string;
  class_id: string;
  section_id: string;
  batch_id: string | null;
  session_type: SessionTypeValue;
  theory_hours: number;
  practical_hours: number;
  tutorial_hours: number;
  project_hours: number;
  session_duration: number;
  required_resource_type: string | null;
  notes: string | null;
  is_active: boolean;
  is_approved: boolean;
  approved_by: string | null;
  approved_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  faculty?: Faculty;
  academic_term?: AcademicTerm;
}

export interface FacultyLoadListResponse {
  items: FacultyLoad[];
  total: number;
  page: number;
  page_size: number;
}

export interface FacultyLoadImportPreview {
  row_index: number;
  faculty_employee_id: string;
  faculty_name: string;
  subject_code: string;
  subject_name: string;
  class_name: string;
  section: string;
  batch: string | null;
  session_type: SessionTypeValue;
  theory_hours: number;
  practical_hours: number;
  tutorial_hours: number;
  project_hours: number;
  session_duration: number;
  required_resource_type: string | null;
  notes: string | null;
  academic_year: string;
  semester: number;
  errors: string[];
}

export interface FacultyLoadImportResult {
  preview: FacultyLoadImportPreview[];
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicates: number;
}

export interface LoadSourceRow {
  id: string;
  source_file: string;
  source_sheet: string;
  source_semester: string;
  source_row_number: number;
  serial_number: string | null;
  faculty_name: string | null;
  designation: string | null;
  class_name: string | null;
  subject_name: string | null;
  theory: string | null;
  practical: string | null;
  tutorial: string | null;
  project_stage: string | null;
  total_load: string | null;
  sign: string | null;
  faculty_id: string | null;
  subject_id: string | null;
  class_id: string | null;
  section_id: string | null;
  batch_id: string | null;
  academic_term_id: string | null;
  validation_errors: string[];
  is_deleted: boolean;
  is_approved: boolean;
  approved_by: string | null;
  approved_at: string | null;
  faculty_load_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface LoadSourceListResponse {
  items: LoadSourceRow[];
  semesters: string[];
  total: number;
}

export interface LoadSourceImportResult {
  imported: number;
  invalid: number;
}

export interface LoadSourceApprovalResponse extends LoadSourceRow {
  assignments_created: number;
}

export type LoadSourceRowDraft = Omit<LoadSourceRow, 'id' | 'source_file' | 'source_sheet' | 'validation_errors' | 'is_deleted' | 'is_approved' | 'approved_by' | 'approved_at' | 'faculty_load_id' | 'created_at' | 'updated_at'>;

export interface FacultyLoadSummary {
  faculty_id: string;
  employee_id?: string;
  name: string;
  theory_hours: number;
  practical_hours: number;
  tutorial_hours: number;
  project_hours: number;
  total_hours: number;
  faculty_name?: string;
  total_theory_hours?: number;
  total_practical_hours?: number;
  total_tutorial_hours?: number;
  total_project_hours?: number;
  subject_count?: number;
}

export interface ClassLoadSummary {
  class_id: string;
  class_name?: string;
  name?: string;
  total_theory_hours?: number;
  total_practical_hours?: number;
  total_tutorial_hours?: number;
  total_project_hours?: number;
  total_hours: number;
  subject_count?: number;
}

export interface SubjectLoadSummary {
  subject_id: string;
  subject_code?: string;
  subject_name?: string;
  code?: string;
  name?: string;
  total_theory_hours?: number;
  total_practical_hours?: number;
  total_tutorial_hours?: number;
  total_project_hours?: number;
  total_hours: number;
  faculty_count?: number;
}

export interface LoadSummary {
  faculty_summary: FacultyLoadSummary[];
  class_summary: ClassLoadSummary[];
  subject_summary: SubjectLoadSummary[];
}

export interface TimetableSummaryReport {
  timetable_id: string;
  timetable_name: string;
  version_number: number;
  version_status: string;
  total_entries: number;
  entries_by_type: Record<string, number>;
  entries_by_section: Record<string, number>;
  entries_by_faculty: Record<string, number>;
  entries_by_resource: Record<string, number>;
}

export interface FacultyLoadReport {
  academic_term_id: string;
  summary: FacultyLoadSummary[];
}

export interface ResourceUtilizationRow {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  capacity: number;
  used_slots: number;
  total_slots: number;
  utilization_percent: number;
}

export interface ResourceUtilizationReport {
  timetable_id: string;
  total_resources: number;
  total_time_slots: number;
  utilization: ResourceUtilizationRow[];
}

export interface ConflictReport {
  timetable_id: string;
  version_number: number;
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  violations: Record<string, unknown>;
}

export interface ValidationReport {
  timetable_id: string;
  version_number: number;
  status: 'PASS' | 'WARNING' | 'FAIL';
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  violations: Record<string, unknown>;
  total_entries: number;
}

export interface Resource {
  id: string;
  name: string;
  resource_type: string;
  capacity: number;
  building: string | null;
  floor: string | null;
  room_number: string | null;
  is_emergency: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ResourceListResponse {
  items: Resource[];
  total: number;
  page: number;
  page_size: number;
}

export interface Timetable {
  id: string;
  name: string;
  template_id: string;
  academic_year: string;
  semester: number;
  status: string;
  generated_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TimetableVersion {
  id: string;
  timetable_id: string;
  version_number: number;
  parent_version_id: string | null;
  change_type: string;
  status: string;
  change_summary: string | null;
  created_by: string | null;
  created_at: string;
}

export interface TimetableVersionWithEntries extends TimetableVersion {
  entries: TimetableEntry[];
}

export interface TimetableEntry {
  id: string;
  version_id: string;
  assignment_id: string | null;
  faculty_id: string | null;
  subject_id: string | null;
  section_id: string | null;
  batch_id: string | null;
  resource_id: string | null;
  time_slot_id: string | null;
  day_of_week: number;
  period_number: number | null;
  start_time?: string | null;
  end_time?: string | null;
  session_type: string;
  /** Display names resolved server-side from the TimetableEntry relations. */
  subject_name?: string | null;
  faculty_name?: string | null;
  section_name?: string | null;
  resource_name?: string | null;
  batch_name?: string | null;
}

export interface TimetableGenerateResponse {
  success: boolean;
  version_id?: string;
  version_number?: number;
  entries_count?: number;
  warnings?: string[];
  solve_time?: number;
  diff?: { added: number; removed: number; changed: number; kept: number };
  error?: string;
  stage?: string;
  details?: string[];
  complete?: boolean;
  status?: string;
  source_file?: string;
  semester?: string;
  source_demands?: number;
  required_sessions?: number;
  scheduled_sessions?: number;
  unscheduled_sessions?: number;
  unscheduled?: string[];
  excluded_rows?: string[];
  solver_status?: string;
  optimality_proven?: boolean;
  validation_status?: string;
  conflicts?: Record<string, number>;
  batch_practical_sessions?: number;
}

export interface WorkbookReadinessResponse {
  timetable_id: string;
  source_file: string;
  reference_file: string;
  timing_reference_available?: boolean;
  timing_intervals?: number;
  source_sheet?: string;
  semester: string;
  rows_read: number;
  source_demands: number;
  source_hours: number;
  required_sessions: number;
  unrepresented_hours: number;
  invalid_rows: string[];
  excluded_rows: string[];
  ready: boolean;
  stage?: string;
  sheet?: string | null;
  row?: number | null;
  field?: string | null;
  details?: string[];
}

export interface TimetableCreateRequest {
  name: string;
  template_id: string;
  academic_year: string;
  semester: number;
}

export interface ReadinessCheck {
  check: string;
  status: 'OK' | 'WARNING' | 'FAIL';
  message: string;
}

export interface GenerationReadinessResponse {
  timetable_id: string;
  ready: boolean;
  errors: string[];
  warnings: string[];
  checks: ReadinessCheck[];
}

export interface TimetableTemplate {
  id: string;
  name: string;
  description: string | null;
  academic_year: string;
  is_default: boolean;
  is_active: boolean;
}

export interface TimeSlot {
  id: string;
  template_id: string;
  day_of_week: number;
  period_number: number;
  start_time: string;
  end_time: string;
  slot_type: string;
  shift: string;
  is_active: boolean;
}

export interface TimeSlotCreate {
  day_of_week: number;
  period_number: number;
  start_time: string;
  end_time: string;
  slot_type?: string;
  shift?: string;
}

export interface TemplateCreate {
  name: string;
  description?: string | null;
  academic_year: string;
  is_default?: boolean;
}

export interface TimetableValidationResponse {
  status: 'PASS' | 'WARNING' | 'FAIL';
  errors: string[];
  warnings: string[];
  violations: Record<string, unknown>;
}

export interface TimetableRepairRequest {
  adjustments?: Array<{
    kind: 'full_regeneration' | 'extend_time_limit' | 'include_resources' | 'lift_availability_block';
    reason?: string;
    time_limit_seconds?: number;
    resource_ids?: string[];
    faculty_slot_ids?: string[];
    resource_slot_ids?: string[];
  }>;
  max_retries?: number;
  approve_hard_relaxation?: boolean;
  suggest?: boolean;
}

export interface TimetableRepairAttempt {
  attempt: number;
  adjustment?: { kind: string; reason?: string } | null;
  solver_status: string;
  validation_errors: string[];
  solver_diagnostics: string[];
  applied: boolean;
}

export interface TimetableRepairResponse {
  success?: boolean;
  repaired?: boolean;
  status?: string;
  version_id?: string;
  version_number?: number;
  entries_count?: number;
  solver_status?: string;
  validation_status?: string;
  repair_attempts: number;
  attempts?: TimetableRepairAttempt[];
  not_attempted?: Array<Record<string, unknown>>;
  original_diagnostics?: string[];
  unscheduled?: Array<{ assignment_id: string; required_hours: number; scheduled_hours: number }>;
  diff?: { added: number; removed: number; changed: number; kept: number };
  error?: string;
  stage?: string;
  outcome?: string;
}

export interface TimetableListResponse {
  timetables: Array<{
    id: string;
    name: string;
    academic_year: string;
    semester: number;
    status: string;
  }>;
}

export interface Leave {
  id: string;
  faculty_id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: string;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
  faculty?: Faculty;
}

export interface LeaveListResponse {
  leaves: Leave[];
}

export interface Substitution {
  id: string;
  original_faculty_id: string;
  substitute_faculty_id: string;
  subject_id: string;
  class_id: string;
  section_id: string;
  batch_id: string | null;
  date: string;
  time_slot_id: string;
  status: string;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
  original_faculty?: Faculty;
  substitute_faculty?: Faculty;
}

export interface SubstitutionListResponse {
  substitutions: Substitution[];
}

export interface Notification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  type: string;
  reference_type: string | null;
  reference_id: string | null;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: Notification[];
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  roles: string[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string | null;
  token_type: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface TeachingAssignment {
  id: string;
  faculty_id: string;
  academic_term_id: string;
  subject_id: string;
  section_id: string;
  batch_id: string | null;
  hours_per_week: number;
  session_duration: number;
  required_resource_type: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  faculty?: Faculty;
}

export interface AssignmentDerivationResult {
  created: number;
  skipped: number;
  errors: string[];
}

export interface AssignmentDerivationPreview {
  faculty_id: string;
  faculty_name: string;
  subject_id: string;
  subject_name: string;
  section_id: string;
  section_name: string;
  batch_id: string | null;
  batch_name: string | null;
  hours_per_week: number;
  session_duration: number;
  required_resource_type: string | null;
}
