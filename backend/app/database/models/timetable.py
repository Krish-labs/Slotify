import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class Timetable(BaseModel):
    __tablename__ = "timetables"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("timetable_templates.id"), nullable=False
    )
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="DRAFT"
    )  # DRAFT, GENERATED, VALIDATED, UNDER_REVIEW, APPROVED, PUBLISHED, ARCHIVED
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    template = relationship("TimetableTemplate", back_populates="timetables")
    versions = relationship("TimetableVersion", back_populates="timetable")
    generator = relationship("User", foreign_keys=[generated_by])
    approver = relationship("User", foreign_keys=[approved_by])
