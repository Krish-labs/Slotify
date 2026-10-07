import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class TimetableEntry(BaseModel):
    __tablename__ = "timetable_entries"

    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("timetable_versions.id"), nullable=False, index=True
    )
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teaching_assignments.id"),
        nullable=True,
        index=True,
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False, index=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id"), nullable=True
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources.id"), nullable=False, index=True
    )
    time_slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("time_slots.id"), nullable=False, index=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    period_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Scheduling metadata persisted with each entry so approval/publish-time
    # validation is exactly as strong as generation-time validation (the
    # validator needs per-entry session duration and the strengths that were
    # checked against room capacity). Nullable so historical rows load; new
    # rows are always populated by the worker.
    session_duration: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    section_strength: Mapped[int | None] = mapped_column(Integer, nullable=True)
    batch_strength: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    version = relationship("TimetableVersion", back_populates="entries")
    assignment = relationship("TeachingAssignment", back_populates="timetable_entries")
    faculty = relationship("Faculty", back_populates="timetable_entries")
    subject = relationship("Subject", back_populates="timetable_entries")
    section = relationship("Section", back_populates="timetable_entries")
    batch = relationship("Batch", back_populates="timetable_entries")
    resource = relationship("Resource", back_populates="timetable_entries")
    time_slot = relationship("TimeSlot", back_populates="timetable_entries")

    __table_args__ = (
        UniqueConstraint(
            "version_id", "resource_id", "time_slot_id", name="uq_entry_resource_slot"
        ),
        UniqueConstraint("version_id", "faculty_id", "time_slot_id", name="uq_entry_faculty_slot"),
        # Only lectures occupy the whole section. Practicals/tutorials are per-batch, and
        # several batches of one section legitimately run in the same slot.
        Index(
            "uq_entry_section_lecture_slot",
            "version_id",
            "section_id",
            "time_slot_id",
            unique=True,
            postgresql_where=text("session_type = 'LECTURE'"),
            sqlite_where=text("session_type = 'LECTURE'"),
        ),
        UniqueConstraint("version_id", "batch_id", "time_slot_id", name="uq_entry_batch_slot"),
    )
