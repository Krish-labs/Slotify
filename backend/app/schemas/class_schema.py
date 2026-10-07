from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ClassBase(BaseModel):
    name: str
    year: int
    branch: str
    academic_year: str
    strength: int = 0


class ClassCreate(ClassBase):
    pass


class ClassUpdate(BaseModel):
    name: str | None = None
    year: int | None = None
    branch: str | None = None
    strength: int | None = None
    is_active: bool | None = None


class ClassResponse(ClassBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClassListResponse(BaseModel):
    items: list[ClassResponse]
    total: int
    page: int
    page_size: int
