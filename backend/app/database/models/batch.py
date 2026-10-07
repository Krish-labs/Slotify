import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class Batch(BaseModel):
    __tablename__ = "batches"

    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    batch_number: Mapped[int] = mapped_column(Integer, nullable=False)
    strength: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    section = relationship("Section", back_populates="batches")
    loads = relationship("FacultyLoad", back_populates="batch")
    assignments = relationship("TeachingAssignment", back_populates="batch")
    timetable_entries = relationship("TimetableEntry", back_populates="batch")

    __table_args__ = (UniqueConstraint("section_id", "name", name="uq_batch_section"),)
