import uuid
from datetime import time

from sqlalchemy import Boolean, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class TimeSlot(BaseModel):
    __tablename__ = "time_slots"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("timetable_templates.id"), nullable=False, index=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon, 5=Sat
    period_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_type: Mapped[str] = mapped_column(String(20), nullable=False)  # TEACHING, BREAK, LUNCH
    shift: Mapped[str] = mapped_column(String(20), nullable=False)  # MORNING, LATE
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    template = relationship("TimetableTemplate", back_populates="time_slots")
    timetable_entries = relationship("TimetableEntry", back_populates="time_slot")
    # resource_availability_links removed due to complex non-FK join
    # Use explicit queries to find related resource availability

    __table_args__ = (
        UniqueConstraint(
            "template_id", "day_of_week", "period_number", name="uq_time_slot_template"
        ),
    )
