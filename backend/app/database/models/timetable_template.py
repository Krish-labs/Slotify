from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class TimetableTemplate(BaseModel):
    __tablename__ = "timetable_templates"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    time_slots = relationship("TimeSlot", back_populates="template")
    timetables = relationship("Timetable", back_populates="template")
