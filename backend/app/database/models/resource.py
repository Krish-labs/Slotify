from typing import Any

from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class Resource(BaseModel):
    __tablename__ = "resources"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # CLASSROOM, SOFTWARE_LAB, HARDWARE_LAB
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    building: Mapped[str | None] = mapped_column(String(100), nullable=True)
    floor: Mapped[str | None] = mapped_column(String(20), nullable=True)
    room_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    features: Mapped[Any] = mapped_column(JSON, default=list, nullable=True)
    is_emergency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    availability = relationship("ResourceAvailability", back_populates="resource")
    timetable_entries = relationship("TimetableEntry", back_populates="resource")
