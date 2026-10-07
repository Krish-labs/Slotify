from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SubjectBase(BaseModel):
    code: str
    name: str
    subject_type: str  # THEORY, PRACTICAL, BOTH
    credits: int = 0
    theory_hours: int = 0
    practical_hours: int = 0
    tutorial_hours: int = 0
    semester: int
    department: str = "E&TC"


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    subject_type: str | None = None
    credits: int | None = None
    theory_hours: int | None = None
    practical_hours: int | None = None
    tutorial_hours: int | None = None
    semester: int | None = None
    department: str | None = None
    is_active: bool | None = None


class SubjectResponse(SubjectBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubjectListResponse(BaseModel):
    items: list[SubjectResponse]
    total: int
    page: int
    page_size: int
