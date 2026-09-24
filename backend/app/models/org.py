from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AcademicYear(Base):
    __tablename__ = "academic_years"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    label: Mapped[str] = mapped_column(String(20))  # "2025-2026"
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)


class Class(Base):
    """A sinf, e.g. "9-A"."""

    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "grade_level", "label", name="uq_class_year_grade_label"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"))
    grade_level: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(10))  # "A"
    display_name: Mapped[str] = mapped_column(String(20))  # "9-A"
    # The homeroom ("sinf rahbari") teacher — grants that teacher edit
    # rights over this class's own student roster (see
    # admin_management.py's _ensure_class_homeroom). Nullable: not every
    # class has one assigned yet.
    homeroom_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True)

    students: Mapped[list["Student"]] = relationship(back_populates="klass")  # noqa: F821
