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
  hours_per_week: number;
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

export interface FacultyLoadSummary {
  faculty_id: string;
  faculty_name: string;
  total_theory_hours: number;
  total_practical_hours: number;
  total_tutorial_hours: number;
  total_project_hours: number;
  total_hours: number;
  subject_count: number;
}

export interface ClassLoadSummary {
  class_id: string;
  class_name: string;
  total_theory_hours: number;
  total_practical_hours: number;
  total_tutorial_hours: number;
  total_project_hours: number;
  total_hours: number;
  subject_count: number;
}

export interface SubjectLoadSummary {
  subject_id: string;
  subject_code: string;
  subject_name: string;
  total_theory_hours: number;
  total_practical_hours: number;
  total_tutorial_hours: number;
  total_project_hours: number;
  total_hours: number;
  faculty_count: number;
}

export interface LoadSummary {
  faculty_summary: FacultyLoadSummary[];
  class_summary: ClassLoadSummary[];
  subject_summary: SubjectLoadSummary[];
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
  session_type: string;
}

export interface TimetableGenerateResponse {
  success: boolean;
  version_id?: string;
  version_number?: number;
  entries_count?: number;
  error?: string;
}

export interface TimetableValidationResponse {
  status: 'PASS' | 'WARNING' | 'FAIL';
  errors: string[];
  warnings: string[];
  violations: Record<string, unknown>;
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