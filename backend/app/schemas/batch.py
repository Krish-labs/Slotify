from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BatchBase(BaseModel):
    section_id: UUID
    name: str
    batch_number: int
    strength: int = 0


class BatchCreate(BatchBase):
    pass


class BatchUpdate(BaseModel):
    name: str | None = None
    batch_number: int | None = None
    strength: int | None = None
    is_active: bool | None = None


class BatchResponse(BatchBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BatchListResponse(BaseModel):
    items: list[BatchResponse]
    total: int
    page: int
    page_size: int
