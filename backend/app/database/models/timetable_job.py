import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class TimetableJob(BaseModel):
    """Durable record of a background timetable operation.

    Redis only transports work; this row is the source of truth for job state
    (QUEUED -> RUNNING -> SUCCEEDED | FAILED | CANCELLED). Both the API and the
    UI read job state from here, so a Redis loss or worker crash can never make
    a job invisible.

    Idempotency: ``idempotency_key`` is unique; enqueueing the same logical
    operation while a job for it is still QUEUED/RUNNING returns the existing
    job instead of creating a duplicate.
    """

    __tablename__ = "timetable_jobs"

    timetable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("timetables.id"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(String(30), nullable=False)  # generate | reoptimize
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="QUEUED"
    )  # QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    change_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    result: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("timetable_versions.id"), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    timetable = relationship("Timetable")
    parent_version = relationship("TimetableVersion")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_job_idempotency_key"),
        Index("idx_job_status", "status"),
        Index("idx_job_timetable", "timetable_id", "created_at"),
    )
