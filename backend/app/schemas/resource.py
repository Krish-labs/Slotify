from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ResourceBase(BaseModel):
    name: str
    resource_type: str  # CLASSROOM, SOFTWARE_LAB, HARDWARE_LAB
    capacity: int
    building: str | None = None
    floor: str | None = None
    room_number: str | None = None
    features: list[str] = []
    is_emergency: bool = False


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    name: str | None = None
    resource_type: str | None = None
    capacity: int | None = None
    building: str | None = None
    floor: str | None = None
    room_number: str | None = None
    features: list[str] | None = None
    is_emergency: bool | None = None
    is_active: bool | None = None


class ResourceResponse(ResourceBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResourceListResponse(BaseModel):
    items: list[ResourceResponse]
    total: int
    page: int
    page_size: int
