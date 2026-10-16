from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.database.models.faculty_load import ResourceType, SessionType


class FacultyLoadBase(BaseModel):
    faculty_id: UUID
    academic_term_id: UUID
    subject_id: UUID
    class_id: UUID
    section_id: UUID
    batch_id: UUID | None = None
    session_type: SessionType = SessionType.THEORY
    theory_hours: int = Field(default=0, ge=0)
    practical_hours: int = Field(default=0, ge=0)
    tutorial_hours: int = Field(default=0, ge=0)
    project_hours: int = Field(default=0, ge=0)
    session_duration: int = Field(default=1, ge=1)
    required_resource_type: ResourceType = ResourceType.NONE
    notes: str | None = None


class FacultyLoadCreate(FacultyLoadBase):
    @model_validator(mode="after")
    def _practical_hours_fit_session_duration(self):
        # session_duration is the length of one practical session, in consecutive periods.
        if self.practical_hours % self.session_duration != 0:
            raise ValueError(
                f"practical_hours ({self.practical_hours}) must be a multiple of "
                f"session_duration ({self.session_duration})"
            )
        return self


class FacultyLoadUpdate(BaseModel):
    theory_hours: int | None = Field(default=None, ge=0)
    practical_hours: int | None = Field(default=None, ge=0)
    tutorial_hours: int | None = Field(default=None, ge=0)
    project_hours: int | None = Field(default=None, ge=0)
    session_duration: int | None = Field(default=None, ge=1)
    required_resource_type: ResourceType | None = None
    notes: str | None = None
    is_active: bool | None = None
    is_approved: bool | None = None


class FacultyLoadResponse(FacultyLoadBase):
    id: UUID
    is_active: bool
    is_approved: bool
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @property
    def total_hours(self) -> int:
        return self.theory_hours + self.practical_hours + self.tutorial_hours + self.project_hours

    class Config:
        from_attributes = True


class FacultyLoadListResponse(BaseModel):
    items: list[FacultyLoadResponse]
    total: int
    page: int
    page_size: int


class FacultyLoadImportPreview(BaseModel):
    row_index: int
    data: dict
    errors: list[str]
    warnings: list[str]


class FacultyLoadImportResult(BaseModel):
    preview: list[FacultyLoadImportPreview]
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicates: int


class LoadSourceRowBase(BaseModel):
    source_semester: str
    source_row_number: int = 0
    serial_number: str | None = None
    faculty_name: str | None = None
    designation: str | None = None
    class_name: str | None = None
    subject_name: str | None = None
    theory: str | None = None
    practical: str | None = None
    tutorial: str | None = None
    project_stage: str | None = None
    total_load: str | None = None
    sign: str | None = None
    faculty_id: UUID | None = None
    subject_id: UUID | None = None
    class_id: UUID | None = None
    section_id: UUID | None = None
    batch_id: UUID | None = None
    academic_term_id: UUID | None = None


class LoadSourceRowCreate(LoadSourceRowBase):
    pass


class LoadSourceRowUpdate(BaseModel):
    serial_number: str | None = None
    faculty_name: str | None = None
    designation: str | None = None
    class_name: str | None = None
    subject_name: str | None = None
    theory: str | None = None
    practical: str | None = None
    tutorial: str | None = None
    project_stage: str | None = None
    total_load: str | None = None
    sign: str | None = None
    faculty_id: UUID | None = None
    subject_id: UUID | None = None
    class_id: UUID | None = None
    section_id: UUID | None = None
    batch_id: UUID | None = None
    academic_term_id: UUID | None = None


class LoadSourceRowResponse(LoadSourceRowBase):
    id: UUID
    source_file: str
    source_sheet: str
    validation_errors: list[str]
    is_deleted: bool
    is_approved: bool
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    faculty_load_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LoadSourceListResponse(BaseModel):
    items: list[LoadSourceRowResponse]
    semesters: list[str]
    total: int


class LoadSourceImportResult(BaseModel):
    imported: int
    invalid: int


class LoadSourceApprovalResponse(LoadSourceRowResponse):
    assignments_created: int = 0
