import enum
from datetime import datetime

from sqlalchemy import JSON, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import UTCDateTime
from app.db.base import Base


class AttemptStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    submitted = "submitted"
    auto_submitted = "auto_submitted"
    expired_unstarted = "expired_unstarted"


class ExamAttempt(Base):
    """One row per student per exam. UNIQUE(exam_id, student_id) is what
    prevents double attempts under concurrent /start calls — always insert
    with ON CONFLICT DO NOTHING then re-select, never check-then-insert."""

    __tablename__ = "exam_attempts"
    __table_args__ = (UniqueConstraint("exam_id", "student_id", name="uq_attempt_exam_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))

    status: Mapped[AttemptStatus] = mapped_column(Enum(AttemptStatus), default=AttemptStatus.not_started)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Authoritative deadline for this student = min(started_at + exam.duration_minutes, exam.end_at).
    # Every write endpoint must re-check this server-side; never trust the client's clock.
    deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    question_order: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    answers: Mapped[list["StudentAnswer"]] = relationship(back_populates="attempt")


class StudentAnswer(Base):
    __tablename__ = "student_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_answer_attempt_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    selected_option_id: Mapped[int | None] = mapped_column(ForeignKey("question_options.id"), nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(nullable=True)
    points_awarded: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # short_answer only — the AI's brief justification for points_awarded,
    # shown to the teacher on review so they aren't overriding blind.
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "ai" | "teacher" | None — None for mcq (deterministic, not applicable).
    # Set to "ai" by ai_grading_service; a teacher's manual override in the
    # review UI sets it to "teacher" so it's visible that a human, not the
    # model, produced the final points_awarded on this answer.
    graded_by: Mapped[str | None] = mapped_column(String(10), nullable=True)

    attempt: Mapped["ExamAttempt"] = relationship(back_populates="answers")
