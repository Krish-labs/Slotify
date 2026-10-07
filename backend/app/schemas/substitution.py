import datetime as dt
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class SubstitutionBase(BaseModel):
    leave_id: UUID | None = None
    timetable_id: UUID | None = None
    original_faculty_id: UUID
    substitute_faculty_id: UUID
    subject_id: UUID
    section_id: UUID
    batch_id: UUID | None = None
    date: date
    time_slot_id: UUID


class SubstitutionCreate(SubstitutionBase):
    # Request-only: substitutions have no class column (class is implied by the
    # section), but clients send it so a class/section mismatch can be rejected.
    class_id: UUID | None = None


class SubstitutionUpdate(BaseModel):
    leave_id: UUID | None = None
    timetable_id: UUID | None = None
    substitute_faculty_id: UUID | None = None
    subject_id: UUID | None = None
    section_id: UUID | None = None
    batch_id: UUID | None = None
    date: dt.date | None = None
    time_slot_id: UUID | None = None


class SubstitutionResponse(SubstitutionBase):
    id: UUID
    status: str
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
