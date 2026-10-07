import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class SessionType(str, enum.Enum):
    LECTURE = "LECTURE"
    PRACTICAL = "PRACTICAL"
    TUTORIAL = "TUTORIAL"
    PROJECT = "PROJECT"


class TeachingAssignment(BaseModel):
    __tablename__ = "teaching_assignments"

    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), nullable=False, index=True
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_terms.id"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id"), nullable=True
    )
    session_type: Mapped[SessionType] = mapped_column(
        SQLEnum(SessionType, name="teaching_session_type"), nullable=False
    )
    hours_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    # Consecutive periods per session (e.g. 2 for a two-period lab). Copied from
    # FacultyLoad.session_duration; hours_per_week is the weekly total of periods.
    session_duration: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    # Required lab type for practical sessions: SOFTWARE_LAB, HARDWARE_LAB, or None for lectures.
    # Populated from FacultyLoad.required_resource_type during derivation.
    required_lab_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    preferred_days: Mapped[Any] = mapped_column(JSON, default=list, nullable=True)
    preferred_shifts: Mapped[Any] = mapped_column(JSON, default=list, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    faculty = relationship("Faculty", back_populates="assignments")
    academic_term = relationship("AcademicTerm", back_populates="assignments")
    timetable_entries = relationship("TimetableEntry", back_populates="assignment")
    subject = relationship("Subject")
    section = relationship("Section")
    batch = relationship("Batch")

    __table_args__ = (
        CheckConstraint("session_duration >= 1", name="ck_assignment_duration_positive"),
        CheckConstraint(
            "hours_per_week % session_duration = 0", name="ck_assignment_duration_divides_hours"
        ),
    )
