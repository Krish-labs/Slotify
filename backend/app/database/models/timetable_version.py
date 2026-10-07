import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class TimetableVersion(BaseModel):
    __tablename__ = "timetable_versions"

    timetable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("timetables.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("timetable_versions.id"), nullable=True
    )
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # LOAD_CHANGE, RESOURCE_CHANGE, LEAVE, SUBSTITUTION, TEMPLATE_CHANGE, FULL_REGENERATION
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING"
    )  # PENDING, VALIDATING, VALIDATED, APPROVED, REJECTED
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    timetable = relationship("Timetable", back_populates="versions")
    parent_version = relationship("TimetableVersion", remote_side="TimetableVersion.id")
    entries = relationship("TimetableEntry", back_populates="version", cascade="all, delete-orphan")
    creator = relationship("User")

    __table_args__ = (UniqueConstraint("timetable_id", "version_number", name="uq_version_number"),)
