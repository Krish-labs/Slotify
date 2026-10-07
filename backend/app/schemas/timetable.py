from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TimetableBase(BaseModel):
    name: str
    template_id: UUID
    academic_year: str
    semester: int


class TimetableCreate(TimetableBase):
    pass


class TimetableUpdate(BaseModel):
    name: str | None = None
    status: str | None = None


class TimetableResponse(TimetableBase):
    id: UUID
    status: str
    generated_by: UUID | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TimetableVersionBase(BaseModel):
    change_summary: str | None = None
    change_type: str | None = None


class TimetableVersionCreate(TimetableVersionBase):
    pass


class TimetableVersionResponse(TimetableVersionBase):
    id: UUID
    timetable_id: UUID
    version_number: int
    parent_version_id: UUID | None = None
    status: str
    created_by: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class TimetableEntryBase(BaseModel):
    faculty_id: UUID
    subject_id: UUID
    section_id: UUID
    batch_id: UUID | None = None
    resource_id: UUID
    time_slot_id: UUID
    day_of_week: int
    session_type: str


class TimetableEntryCreate(TimetableEntryBase):
    pass


class TimetableEntryResponse(TimetableEntryBase):
    id: UUID
    version_id: UUID
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TimetableGenerateRequest(BaseModel):
    academic_term_id: UUID
    template_id: UUID
    solver_time_limit_seconds: int = 300


class TimetableGenerateResponse(BaseModel):
    timetable_id: UUID
    status: str
    message: str
