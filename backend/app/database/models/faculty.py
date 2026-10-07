import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class Faculty(BaseModel):
    __tablename__ = "faculty"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, unique=True
    )
    employee_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), default="E&TC", nullable=True)
    designation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    joining_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    user = relationship("User", back_populates="faculty_profile", foreign_keys=[user_id])
    archived_by_user = relationship("User", foreign_keys=[archived_by])
    loads = relationship("FacultyLoad", back_populates="faculty")
    assignments = relationship("TeachingAssignment", back_populates="faculty")
    leaves = relationship("Leave", back_populates="faculty")
    substitutions_as_original = relationship(
        "Substitution",
        foreign_keys="Substitution.original_faculty_id",
        back_populates="original_faculty",
    )
    substitutions_as_substitute = relationship(
        "Substitution",
        foreign_keys="Substitution.substitute_faculty_id",
        back_populates="substitute_faculty",
    )
    timetable_entries = relationship("TimetableEntry", back_populates="faculty")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
