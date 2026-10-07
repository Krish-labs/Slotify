from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TeachingAssignmentBase(BaseModel):
    faculty_id: UUID
    subject_id: UUID
    section_id: UUID
    batch_id: UUID | None = None
    session_type: str  # LECTURE, PRACTICAL, TUTORIAL, PROJECT
    hours_per_week: int
    # Consecutive periods per session; hours_per_week must be a multiple of it.
    session_duration: int = Field(default=1, ge=1)
    preferred_days: list[str] = []
    preferred_shifts: list[str] = []
    academic_year: str
    semester: int

    @model_validator(mode="after")
    def _hours_divisible_by_duration(self):
        if self.hours_per_week % self.session_duration != 0:
            raise ValueError(
                f"hours_per_week ({self.hours_per_week}) must be a multiple of "
                f"session_duration ({self.session_duration})"
            )
        return self


class TeachingAssignmentCreate(TeachingAssignmentBase):
    pass


class TeachingAssignmentUpdate(BaseModel):
    hours_per_week: int | None = None
    session_duration: int | None = Field(default=None, ge=1)
    preferred_days: list[str] | None = None
    preferred_shifts: list[str] | None = None
    is_active: bool | None = None


class TeachingAssignmentResponse(TeachingAssignmentBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
