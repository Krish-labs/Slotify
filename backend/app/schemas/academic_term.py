from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class AcademicTermBase(BaseModel):
    name: str
    academic_year: str
    semester: int
    start_date: date
    end_date: date
    is_active: bool = True
    is_current: bool = False


class AcademicTermCreate(AcademicTermBase):
    pass


class AcademicTermUpdate(BaseModel):
    name: str | None = None
    academic_year: str | None = None
    semester: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None
    is_current: bool | None = None


class AcademicTermResponse(AcademicTermBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AcademicTermListResponse(BaseModel):
    items: list[AcademicTermResponse]
    total: int
    page: int
    page_size: int
