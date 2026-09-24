import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import UTCDateTime
from app.db.base import Base


class Trend(str, enum.Enum):
    improving = "improving"
    declining = "declining"
    stable = "stable"


class ExamRanking(Base):
    """Materialized per-exam leaderboard row, recomputed after each submit
    (not batched) so the leaderboard page never runs ORDER BY live."""

    __tablename__ = "exam_rankings"
    __table_args__ = (UniqueConstraint("exam_id", "student_id", name="uq_ranking_exam_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    score: Mapped[float] = mapped_column(Numeric)
    rank_in_class: Mapped[int] = mapped_column(Integer)
    percentile: Mapped[float | None] = mapped_column(Numeric, nullable=True)


class StudentSubjectStats(Base):
    """Rolling per-student-per-subject aggregate. This is what the profile's
    'progress over time' view reads directly; recomputed incrementally after
    each graded exam rather than aggregated live on every page load."""

    __tablename__ = "student_subject_stats"
    __table_args__ = (UniqueConstraint("student_id", "subject_id", name="uq_stats_student_subject"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    exams_taken_count: Mapped[int] = mapped_column(Integer, default=0)
    total_points_earned: Mapped[float] = mapped_column(Numeric, default=0)
    total_points_possible: Mapped[float] = mapped_column(Numeric, default=0)
    average_percent: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    last_exam_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    trend: Mapped[Trend | None] = mapped_column(Enum(Trend), nullable=True)
