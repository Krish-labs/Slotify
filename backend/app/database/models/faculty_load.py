import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class SessionType(str, enum.Enum):
    THEORY = "THEORY"
    PRACTICAL = "PRACTICAL"
    TUTORIAL = "TUTORIAL"
    PROJECT = "PROJECT"


class ResourceType(str, enum.Enum):
    CLASSROOM = "CLASSROOM"
    LAB = "LAB"
    COMPUTER_LAB = "COMPUTER_LAB"
    SEMINAR_HALL = "SEMINAR_HALL"
    WORKSHOP = "WORKSHOP"
    NONE = "NONE"


class FacultyLoad(BaseModel):
    __tablename__ = "faculty_loads"

    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), nullable=False, index=True
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_terms.id"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False, index=True
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False, index=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id"), nullable=True, index=True
    )
    session_type: Mapped[SessionType] = mapped_column(
        SQLEnum(SessionType, name="faculty_load_session_type"),
        nullable=False,
        default=SessionType.THEORY,
        index=True,
    )
    # Nullable in the database, but SQLAlchemy always writes the default on
    # insert, so every row the application creates holds a real number.
    theory_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    practical_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    tutorial_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    project_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    session_duration: Mapped[int] = mapped_column(Integer, default=1, nullable=True)
    required_resource_type: Mapped[ResourceType | None] = mapped_column(
        SQLEnum(ResourceType), default=ResourceType.NONE, nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    faculty = relationship("Faculty", back_populates="loads")
    academic_term = relationship("AcademicTerm", back_populates="loads")
    subject = relationship("Subject", back_populates="loads")
    class_ = relationship("Class", back_populates="loads")
    section = relationship("Section", back_populates="loads")
    batch = relationship("Batch", back_populates="loads")
    approved_by_user = relationship("User", foreign_keys=[approved_by])

    __table_args__ = (
        UniqueConstraint(
            "faculty_id",
            "academic_term_id",
            "subject_id",
            "class_id",
            "section_id",
            "batch_id",
            "session_type",
            name="uq_faculty_load_detail",
        ),
    )

    @property
    def total_hours(self) -> int:
        return (
            (self.theory_hours or 0)
            + (self.practical_hours or 0)
            + (self.tutorial_hours or 0)
            + (self.project_hours or 0)
        )
