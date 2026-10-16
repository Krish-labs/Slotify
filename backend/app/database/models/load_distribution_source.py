import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import BaseModel


class LoadDistributionSourceRow(BaseModel):
    """A faithful, editable copy of a source load-distribution workbook row.

    These rows intentionally remain separate from FacultyLoad until all required
    master-data mappings are authoritative and validated.
    """

    __tablename__ = "load_distribution_source_rows"

    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(100), nullable=False)
    source_semester: Mapped[str] = mapped_column(String(50), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    faculty_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    class_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    theory: Mapped[str | None] = mapped_column(String(30), nullable=True)
    practical: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tutorial: Mapped[str | None] = mapped_column(String(30), nullable=True)
    project_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    total_load: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sign: Mapped[str | None] = mapped_column(String(255), nullable=True)
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), nullable=True, index=True
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True, index=True
    )
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id"), nullable=True, index=True
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id"), nullable=True, index=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id"), nullable=True, index=True
    )
    academic_term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_terms.id"), nullable=True, index=True
    )
    validation_errors: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    faculty_load_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty_loads.id"), nullable=True, unique=True
    )

    __table_args__ = (
        UniqueConstraint(
            "source_file",
            "source_sheet",
            "source_row_number",
            name="uq_load_source_row_location",
        ),
    )
