from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel


class LeaveBase(BaseModel):
    faculty_id: UUID
    leave_type: str  # CASUAL, SICK, EARNED, ON_DUTY, OTHER
    start_date: date
    end_date: date
    start_time: time | None = None
    end_time: time | None = None
    reason: str | None = None


class LeaveCreate(LeaveBase):
    pass


class LeaveUpdate(BaseModel):
    leave_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    reason: str | None = None


class LeaveResponse(LeaveBase):
    id: UUID
    status: str
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
