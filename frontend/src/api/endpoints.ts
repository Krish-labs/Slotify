import { apiClient } from './client';
import type {
  AcademicTerm,
  AcademicTermListResponse,
  Faculty,
  FacultyListResponse,
  Subject,
  SubjectListResponse,
  AcademicClass,
  AcademicClassListResponse,
  Section,
  SectionListResponse,
  Batch,
  BatchListResponse,
  FacultyLoad,
  FacultyLoadListResponse,
  FacultyLoadImportPreview,
  FacultyLoadImportResult,
  FacultyLoadSummary,
  LoadSummary,
  Resource,
  ResourceListResponse,
  Timetable,
  TimetableVersion,
  TimetableVersionWithEntries,
  TimetableGenerateResponse,
  TimetableValidationResponse,
  TimetableRepairRequest,
  TimetableRepairResponse,
  TimetableListResponse,
  TimetableCreateRequest,
  GenerationReadinessResponse,
  WorkbookReadinessResponse,
  TimetableTemplate,
  TimeSlot,
  TimeSlotCreate,
  TemplateCreate,
  Leave,
  LeaveListResponse,
  Substitution,
  SubstitutionListResponse,
  NotificationListResponse,
  UserResponse,
  TokenResponse,
  LoginCredentials,
  TeachingAssignment,
  AssignmentDerivationResult,
  AssignmentDerivationPreview,
  LoadSourceListResponse,
  LoadSourceRow,
  LoadSourceRowDraft,
  LoadSourceImportResult,
  LoadSourceApprovalResponse,
  TimetableSummaryReport,
  FacultyLoadReport,
  ResourceUtilizationReport,
  ConflictReport,
  ValidationReport,
} from './types';

const extractData = <T>(promise: Promise<{ data: T }>) => promise.then((res) => res.data);

export const authApi = {
  login: (credentials: LoginCredentials) =>
    extractData(
      apiClient.post<TokenResponse>(
        '/auth/login',
        new URLSearchParams({ username: credentials.email, password: credentials.password }),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      )
    ),
  refresh: () => extractData(apiClient.post<TokenResponse>('/auth/refresh')),
  me: () => extractData(apiClient.get<UserResponse>('/auth/me')),
  logout: () => extractData(apiClient.post('/auth/logout')),
};

export const academicTermApi = {
  list: (params?: { page?: number; page_size?: number; is_active?: boolean; is_current?: boolean }) =>
    extractData(apiClient.get<AcademicTermListResponse>('/academic-terms', { params })),
  getCurrent: () => extractData(apiClient.get<AcademicTerm>('/academic-terms/current')),
  get: (id: string) => extractData(apiClient.get<AcademicTerm>(`/academic-terms/${id}`)),
  create: (data: Omit<AcademicTerm, 'id' | 'created_at' | 'updated_at'>) =>
    extractData(apiClient.post<AcademicTerm>('/academic-terms', data)),
  update: (id: string, data: Partial<AcademicTerm>) =>
    extractData(apiClient.put<AcademicTerm>(`/academic-terms/${id}`, data)),
  delete: (id: string) => extractData(apiClient.delete(`/academic-terms/${id}`)),
};

export const facultyApi = {
  list: (params?: {
    page?: number;
    page_size?: number;
    search?: string;
    department?: string;
    is_active?: boolean;
    include_archived?: boolean;
  }) => extractData(apiClient.get<FacultyListResponse>('/faculty', { params })),
  get: (id: string, includeArchived?: boolean) =>
    extractData(apiClient.get<Faculty>(`/faculty/${id}`, { params: { include_archived: includeArchived } })),
  create: (data: Omit<Faculty, 'id' | 'created_at' | 'updated_at' | 'max_hours_per_week' | 'is_active'> & { max_hours_per_week?: number; is_active?: boolean; phone?: string | null; joining_date?: string | null }) =>
    extractData(apiClient.post<Faculty>('/faculty', data)),
  update: (id: string, data: Partial<Faculty>) =>
    extractData(apiClient.put<Faculty>(`/faculty/${id}`, data)),
  archive: (id: string) => extractData(apiClient.patch<Faculty>(`/faculty/${id}/archive`)),
  restore: (id: string) => extractData(apiClient.patch<Faculty>(`/faculty/${id}/restore`)),
  delete: (id: string) => extractData(apiClient.delete(`/faculty/${id}`)),
  getLoadSummary: (id: string, academicTermId?: string) =>
    extractData(
      apiClient.get<{ faculty_id: string; total_load_hours: number; academic_term_id?: string }>(
        `/faculty/${id}/load-summary`,
        { params: { academic_term_id: academicTermId } }
      )
    ),
};

export const subjectApi = {
  list: (params?: { page?: number; page_size?: number; search?: string; semester?: number; is_active?: boolean }) =>
    extractData(apiClient.get<SubjectListResponse>('/subjects', { params })),
  create: (data: Omit<Subject, 'id' | 'created_at' | 'updated_at' | 'is_active'>) =>
    extractData(apiClient.post<Subject>('/subjects', data)),
};

export const classApi = {
  list: (params?: { page?: number; page_size?: number; search?: string; academic_year?: string; is_active?: boolean }) =>
    extractData(apiClient.get<AcademicClassListResponse>('/classes', { params })),
  create: (data: Omit<AcademicClass, 'id' | 'created_at' | 'updated_at' | 'is_active'>) =>
    extractData(apiClient.post<AcademicClass>('/classes', data)),
};

export const sectionApi = {
  list: (params?: { page?: number; page_size?: number; class_id?: string; is_active?: boolean }) =>
    extractData(apiClient.get<SectionListResponse>('/sections', { params })),
  create: (data: Omit<Section, 'id' | 'created_at' | 'updated_at' | 'is_active'>) =>
    extractData(apiClient.post<Section>('/sections', data)),
};

export const batchApi = {
  list: (params?: { page?: number; page_size?: number; section_id?: string; is_active?: boolean }) =>
    extractData(apiClient.get<BatchListResponse>('/batches', { params })),
  create: (data: Omit<Batch, 'id' | 'created_at' | 'updated_at' | 'is_active'>) =>
    extractData(apiClient.post<Batch>('/batches', data)),
};

export const loadApi = {
  sourceList: (semester?: string) =>
    extractData(apiClient.get<LoadSourceListResponse>('/load/source', { params: { semester } })),
  sourceCreate: (data: LoadSourceRowDraft) =>
    extractData(apiClient.post<LoadSourceRow>('/load/source', data)),
  sourceUpdate: (id: string, data: Partial<LoadSourceRowDraft>) =>
    extractData(apiClient.put<LoadSourceRow>(`/load/source/${id}`, data)),
  sourceDelete: (id: string) => extractData(apiClient.delete(`/load/source/${id}`)),
  sourceApprove: (id: string) => extractData(apiClient.post<LoadSourceApprovalResponse>(`/load/source/${id}/approve`)),
  list: (params?: {
    page?: number;
    page_size?: number;
    faculty_id?: string;
    academic_term_id?: string;
    subject_id?: string;
    class_id?: string;
    section_id?: string;
    session_type?: string;
    is_active?: boolean;
    is_approved?: boolean;
  }) => extractData(apiClient.get<FacultyLoadListResponse>('/load', { params })),
  get: (id: string) => extractData(apiClient.get<FacultyLoad>(`/load/${id}`)),
  create: (data: Omit<FacultyLoad, 'id' | 'created_at' | 'updated_at' | 'approved_by' | 'approved_at'>) =>
    extractData(apiClient.post<FacultyLoad>('/load', data)),
  update: (id: string, data: Partial<FacultyLoad>) =>
    extractData(apiClient.put<FacultyLoad>(`/load/${id}`, data)),
  approve: (id: string) => extractData(apiClient.patch<FacultyLoad>(`/load/${id}/approve`)),
  delete: (id: string) => extractData(apiClient.delete(`/load/${id}`)),
  previewImport: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return extractData(
      apiClient.post<FacultyLoadImportPreview[]>('/load/import/preview', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    );
  },
  import: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return extractData(
      apiClient.post<FacultyLoadImportResult | LoadSourceImportResult>('/load/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    );
  },
  getTemplate: () =>
    extractData(apiClient.get<Blob>('/load/template', { responseType: 'blob' })),
  getFacultySummary: (academicTermId: string) =>
    extractData(
      apiClient.get<{ academic_term_id: string; summary: FacultyLoadSummary[] }>(
        '/load/reports/faculty-summary',
        { params: { academic_term_id: academicTermId } }
      )
    ),
  getClassSummary: (academicTermId: string) =>
    extractData(
      apiClient.get<{ academic_term_id: string; summary: unknown[] }>(
        '/load/reports/class-summary',
        { params: { academic_term_id: academicTermId } }
      )
    ),
  getSubjectSummary: (academicTermId: string) =>
    extractData(
      apiClient.get<{ academic_term_id: string; summary: unknown[] }>(
        '/load/reports/subject-summary',
        { params: { academic_term_id: academicTermId } }
      )
    ),
  getLoadSummary: (academicTermId: string) =>
    extractData(
      apiClient.get<LoadSummary>('/load/reports/load-summary', {
        params: { academic_term_id: academicTermId },
      })
    ),
};

export const resourceApi = {
  list: (params?: { page?: number; page_size?: number }) =>
    extractData(apiClient.get<ResourceListResponse>('/resources', { params })),
  get: (id: string) => extractData(apiClient.get<Resource>(`/resources/${id}`)),
  create: (data: Omit<Resource, 'id' | 'created_at' | 'updated_at'>) =>
    extractData(apiClient.post<Resource>('/resources', data)),
  update: (id: string, data: Partial<Resource>) =>
    extractData(apiClient.put<Resource>(`/resources/${id}`, data)),
  delete: (id: string) => extractData(apiClient.delete(`/resources/${id}`)),
};

export const timetableApi = {
  list: () => extractData(apiClient.get<TimetableListResponse>('/timetable')),
  get: (id: string) => extractData(apiClient.get<Timetable>(`/timetable/${id}`)),
  create: (data: TimetableCreateRequest) =>
    extractData(apiClient.post<Omit<Timetable, 'created_at' | 'updated_at' | 'approved_by' | 'approved_at' | 'generated_by'>>('/timetable', data)),
  readiness: (id: string) =>
    extractData(apiClient.get<GenerationReadinessResponse>(`/timetable/${id}/readiness`)),
  generate: (id: string) =>
    extractData(apiClient.post<TimetableGenerateResponse>(`/timetable/${id}/generate`)),
  workbookReadiness: (id: string) =>
    extractData(apiClient.get<WorkbookReadinessResponse>(`/timetable/${id}/workbook-readiness`)),
  generateFromWorkbook: (id: string) =>
    extractData(apiClient.post<TimetableGenerateResponse>(`/timetable/${id}/generate-source`)),
  validate: (id: string, versionId?: string) =>
    extractData(apiClient.post<TimetableValidationResponse>(`/timetable/${id}/validate`, null, { params: { version_id: versionId } })),
  repair: (id: string, data: TimetableRepairRequest) =>
    extractData(apiClient.post<TimetableRepairResponse>(`/timetable/${id}/repair`, data)),
  listVersions: (id: string) =>
    extractData(apiClient.get<{ versions: TimetableVersion[] }>(`/timetable/${id}/versions`)),
  getVersion: (timetableId: string, versionId: string) =>
    extractData(apiClient.get<TimetableVersionWithEntries>(`/timetable/${timetableId}/versions/${versionId}`)),
  approveVersion: (timetableId: string, versionId: string) =>
    extractData(apiClient.post(`/timetable/${timetableId}/versions/${versionId}/approve`)),
  rejectVersion: (timetableId: string, versionId: string) =>
    extractData(apiClient.post(`/timetable/${timetableId}/versions/${versionId}/reject`)),
  submitForReview: (timetableId: string, versionId: string) =>
    extractData(apiClient.post(`/timetable/${timetableId}/versions/${versionId}/submit-review`)),
  publishVersion: (timetableId: string, versionId: string) =>
    extractData(apiClient.post(`/timetable/${timetableId}/versions/${versionId}/publish`)),
  archiveVersion: (timetableId: string, versionId: string) =>
    extractData(apiClient.post(`/timetable/${timetableId}/versions/${versionId}/archive`)),
  exportClass: (timetableId: string, versionId?: string) =>
    extractData(apiClient.get<Blob>(`/timetable/${timetableId}/export/class`, { params: { version_id: versionId }, responseType: 'blob' })),
  exportFaculty: (timetableId: string, versionId?: string) =>
    extractData(apiClient.get<Blob>(`/timetable/${timetableId}/export/faculty`, { params: { version_id: versionId }, responseType: 'blob' })),
  exportMaster: (timetableId: string, versionId?: string) =>
    extractData(apiClient.get<Blob>(`/timetable/${timetableId}/export/master`, { params: { version_id: versionId }, responseType: 'blob' })),
  exportResourceAllocation: (timetableId: string, versionId?: string) =>
    extractData(apiClient.get<Blob>(`/timetable/${timetableId}/export/resource-allocation`, { params: { version_id: versionId }, responseType: 'blob' })),
  exportChangeHistory: (timetableId: string) =>
    extractData(apiClient.get<Blob>(`/timetable/${timetableId}/export/change-history`, { responseType: 'blob' })),
};

export const reportApi = {
  facultyLoad: (academicTermId: string) =>
    extractData(apiClient.get<FacultyLoadReport>('/reports/faculty-load', { params: { academic_term_id: academicTermId } })),
  timetableSummary: (timetableId: string, versionId?: string) =>
    extractData(apiClient.get<TimetableSummaryReport>('/reports/timetable-summary', { params: { timetable_id: timetableId, version_id: versionId } })),
  resourceUtilization: (timetableId: string, versionId?: string) =>
    extractData(apiClient.get<ResourceUtilizationReport>('/reports/resource-utilization', { params: { timetable_id: timetableId, version_id: versionId } })),
  conflicts: (timetableId: string, versionId?: string) =>
    extractData(apiClient.get<ConflictReport>('/reports/conflicts', { params: { timetable_id: timetableId, version_id: versionId } })),
  validation: (timetableId: string, versionId?: string) =>
    extractData(apiClient.get<ValidationReport>('/reports/validation', { params: { timetable_id: timetableId, version_id: versionId } })),
};

export const templateApi = {
  list: () => extractData(apiClient.get<TimetableTemplate[]>('/templates')),
  get: (id: string) => extractData(apiClient.get<TimetableTemplate>(`/templates/${id}`)),
  create: (data: TemplateCreate) => extractData(apiClient.post<TimetableTemplate>('/templates', data)),
  listTimeSlots: (templateId: string) =>
    extractData(apiClient.get<TimeSlot[]>(`/templates/${templateId}/time-slots`)),
  createTimeSlots: (templateId: string, slots: TimeSlotCreate[]) =>
    extractData(apiClient.post<TimeSlot[]>(`/templates/${templateId}/time-slots`, slots)),
  bulkCreateTimeSlots: (templateId: string, days: number[], periods: TimeSlotCreate[]) =>
    extractData(apiClient.post<TimeSlot[]>(`/templates/${templateId}/time-slots/bulk`, { days, periods })),
};

export const leaveApi = {
  list: (params?: { status?: string; faculty_id?: string }) =>
    extractData(apiClient.get<LeaveListResponse>('/leave', { params })),
  get: (id: string) => extractData(apiClient.get<Leave>(`/leave/${id}`)),
  create: (data: Omit<Leave, 'id' | 'created_at' | 'updated_at' | 'approved_by' | 'approved_at'>) =>
    extractData(apiClient.post<Leave>('/leave', data)),
  update: (id: string, data: Partial<Leave>) =>
    extractData(apiClient.put<Leave>(`/leave/${id}`, data)),
  delete: (id: string) => extractData(apiClient.delete(`/leave/${id}`)),
  approve: (id: string) => extractData(apiClient.post<Leave>(`/leave/${id}/approve`)),
  reject: (id: string) => extractData(apiClient.post<Leave>(`/leave/${id}/reject`)),
  cancel: (id: string) => extractData(apiClient.post<Leave>(`/leave/${id}/cancel`)),
  listSubstitutions: (params?: { status?: string; faculty_id?: string }) =>
    extractData(apiClient.get<SubstitutionListResponse>('/leave/substitutions', { params })),
  getSubstitution: (id: string) => extractData(apiClient.get<Substitution>(`/leave/substitutions/${id}`)),
  createSubstitution: (data: Omit<Substitution, 'id' | 'created_at' | 'updated_at' | 'approved_by' | 'approved_at'>) =>
    extractData(apiClient.post<Substitution>('/leave/substitutions', data)),
  updateSubstitution: (id: string, data: Partial<Substitution>) =>
    extractData(apiClient.put<Substitution>(`/leave/substitutions/${id}`, data)),
  deleteSubstitution: (id: string) => extractData(apiClient.delete(`/leave/substitutions/${id}`)),
  approveSubstitution: (id: string) => extractData(apiClient.post<Substitution>(`/leave/substitutions/${id}/approve`)),
  rejectSubstitution: (id: string) => extractData(apiClient.post<Substitution>(`/leave/substitutions/${id}/reject`)),
};

export const substitutionApi = {
  list: (params?: { status?: string; faculty_id?: string }) =>
    extractData(apiClient.get<SubstitutionListResponse>('/substitutions', { params })),
  get: (id: string) => extractData(apiClient.get<Substitution>(`/substitutions/${id}`)),
  create: (data: Omit<Substitution, 'id' | 'created_at' | 'updated_at' | 'approved_by' | 'approved_at'>) =>
    extractData(apiClient.post<Substitution>('/substitutions', data)),
  update: (id: string, data: Partial<Substitution>) =>
    extractData(apiClient.put<Substitution>(`/substitutions/${id}`, data)),
  delete: (id: string) => extractData(apiClient.delete(`/substitutions/${id}`)),
  approve: (id: string) => extractData(apiClient.post<Substitution>(`/substitutions/${id}/approve`)),
  reject: (id: string) => extractData(apiClient.post<Substitution>(`/substitutions/${id}/reject`)),
};

export const notificationApi = {
  list: (params?: { unread_only?: boolean }) =>
    extractData(apiClient.get<NotificationListResponse>('/notifications', { params })),
  markRead: (id: string) => extractData(apiClient.post(`/notifications/${id}/read`)),
  markAllRead: () => extractData(apiClient.post('/notifications/read-all')),
};

export const assignmentApi = {
  list: (params?: {
    page?: number;
    page_size?: number;
    faculty_id?: string;
    academic_term_id?: string;
    subject_id?: string;
    section_id?: string;
  }) => extractData(apiClient.get<TeachingAssignment[]>('/assignments', { params })),
  get: (id: string) => extractData(apiClient.get<TeachingAssignment>(`/assignments/${id}`)),
  create: (data: Omit<TeachingAssignment, 'id' | 'created_at' | 'updated_at'>) =>
    extractData(apiClient.post<TeachingAssignment>('/assignments', data)),
  update: (id: string, data: Partial<TeachingAssignment>) =>
    extractData(apiClient.put<TeachingAssignment>(`/assignments/${id}`, data)),
  delete: (id: string) => extractData(apiClient.delete(`/assignments/${id}`)),
  derive: (academicTermId: string, force?: boolean) =>
    extractData(
      apiClient.post<AssignmentDerivationResult>('/assignments/derive', null, {
        params: { academic_term_id: academicTermId, force },
      })
    ),
  previewDerivation: (academicTermId: string) =>
    extractData(
      apiClient.get<AssignmentDerivationPreview[]>('/assignments/derive/preview', {
        params: { academic_term_id: academicTermId },
      })
    ),
};
