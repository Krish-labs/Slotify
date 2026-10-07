import uuid
from datetime import time

from sqlalchemy import Boolean, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class ResourceAvailability(BaseModel):
    __tablename__ = "resource_availability"

    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources.id"), nullable=False, index=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon, 6=Sun
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)

    resource = relationship("Resource", back_populates="availability")

    __table_args__ = (
        UniqueConstraint(
            "resource_id",
            "day_of_week",
            "start_time",
            "academic_year",
            name="uq_resource_availability",
        ),
    )
