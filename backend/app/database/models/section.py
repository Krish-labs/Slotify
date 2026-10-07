import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class Section(BaseModel):
    __tablename__ = "sections"

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(10), nullable=False)
    strength: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    class_ = relationship("Class", back_populates="sections")
    batches = relationship("Batch", back_populates="section")
    loads = relationship("FacultyLoad", back_populates="section")
    assignments = relationship("TeachingAssignment", back_populates="section")
    timetable_entries = relationship("TimetableEntry", back_populates="section")

    __table_args__ = (UniqueConstraint("class_id", "name", name="uq_section_class"),)
