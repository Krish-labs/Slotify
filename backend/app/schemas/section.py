from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SectionBase(BaseModel):
    class_id: UUID
    name: str
    strength: int = 0


class SectionCreate(SectionBase):
    pass


class SectionUpdate(BaseModel):
    name: str | None = None
    strength: int | None = None
    is_active: bool | None = None


class SectionResponse(SectionBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SectionListResponse(BaseModel):
    items: list[SectionResponse]
    total: int
    page: int
    page_size: int
