from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class FacultyBase(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    department: str = "E&TC"
    designation: str | None = None
    joining_date: date | None = None


class FacultyCreate(FacultyBase):
    pass


class FacultyUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    department: str | None = None
    designation: str | None = None
    joining_date: date | None = None
    is_active: bool | None = None


class FacultyArchive(BaseModel):
    archived_by: UUID


class FacultyResponse(FacultyBase):
    id: UUID
    is_active: bool
    is_archived: bool
    archived_at: datetime | None = None
    archived_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FacultyListResponse(BaseModel):
    items: list[FacultyResponse]
    total: int
    page: int
    page_size: int
