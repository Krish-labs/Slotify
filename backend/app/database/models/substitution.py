import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class Substitution(BaseModel):
    __tablename__ = "substitutions"

    leave_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leaves.id"), nullable=True
    )
    # The timetable the substitution applies to. Required so approval can never
    # fall back to a globally-latest version (which could target the wrong
    # timetable). Nullable only for rows created before this column existed.
    timetable_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("timetables.id"), nullable=True, index=True
    )
    original_faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), nullable=False, index=True
    )
    substitute_faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), nullable=False, index=True
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
    # quoted: a bare `date` annotation would resolve to this very column on
    # Python 3.12, where class-body annotations are evaluated eagerly.
    date: Mapped["date"] = mapped_column(Date, nullable=False, index=True)
    time_slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("time_slots.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    leave = relationship("Leave", back_populates="substitutions")
    original_faculty = relationship(
        "Faculty", foreign_keys=[original_faculty_id], back_populates="substitutions_as_original"
    )
    substitute_faculty = relationship(
        "Faculty",
        foreign_keys=[substitute_faculty_id],
        back_populates="substitutions_as_substitute",
    )
    subject = relationship("Subject")
    section = relationship("Section")
    batch = relationship("Batch")
    time_slot = relationship("TimeSlot")
    approver = relationship("User", foreign_keys=[approved_by])
