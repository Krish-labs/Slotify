from datetime import date

from sqlalchemy import Boolean, Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class AcademicTerm(BaseModel):
    __tablename__ = "academic_terms"

    name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "2026-27 Sem I"
    academic_year: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # e.g., "2026-27"
    semester: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # 1-8
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    loads = relationship("FacultyLoad", back_populates="academic_term")
    assignments = relationship("TeachingAssignment", back_populates="academic_term")

    __table_args__ = (UniqueConstraint("academic_year", "semester", name="uq_academic_term"),)
