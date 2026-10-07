import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # CREATE, UPDATE, DELETE, APPROVE, REJECT, GENERATE
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # FACULTY, LOAD, TIMETABLE, RESOURCE, etc.
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    old_values: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    new_values: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User")

    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_user_time", "user_id", "created_at"),
        Index("idx_audit_time", "created_at"),
    )
