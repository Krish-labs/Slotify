from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class Subject(BaseModel):
    __tablename__ = "subjects"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)  # THEORY, PRACTICAL, BOTH
    credits: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    theory_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    practical_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    tutorial_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    department: Mapped[str] = mapped_column(String(50), default="E&TC", nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    loads = relationship("FacultyLoad", back_populates="subject")
    assignments = relationship("TeachingAssignment", back_populates="subject")
    timetable_entries = relationship("TimetableEntry", back_populates="subject")
