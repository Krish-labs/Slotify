from datetime import datetime, time
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


class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    academic_year: str
    is_default: bool = False


class TemplateResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    academic_year: str
    is_default: bool
    is_active: bool

    class Config:
        from_attributes = True


class TimeSlotCreate(BaseModel):
    day_of_week: int  # 0=Mon .. 5=Sat
    period_number: int
    start_time: time
    end_time: time
    slot_type: str = "TEACHING"  # TEACHING, BREAK, LUNCH
    shift: str = "MORNING"  # MORNING, LATE


class TimeSlotBulkCreate(BaseModel):
    """Generate one teaching slot per (day, period) from a period grid."""

    days: list[int]  # e.g. [0, 1, 2, 3, 4, 5]
    periods: list[TimeSlotCreate]


class TimeSlotResponse(BaseModel):
    id: UUID
    template_id: UUID
    day_of_week: int
    period_number: int
    start_time: time
    end_time: time
    slot_type: str
    shift: str
    is_active: bool

    class Config:
        from_attributes = True
