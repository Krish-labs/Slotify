from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class Class(BaseModel):
    __tablename__ = "classes"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    branch: Mapped[str] = mapped_column(String(50), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    strength: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    sections = relationship("Section", back_populates="class_")
    loads = relationship("FacultyLoad", back_populates="class_")

    __table_args__ = (UniqueConstraint("name", "academic_year", name="uq_class_year"),)
