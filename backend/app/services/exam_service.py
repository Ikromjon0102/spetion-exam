"""Exam authoring authorization + lifecycle transitions: draft -> review -> scheduled.

publish_exam(db, exam) enforces, server-side (never trust the frontend to
have checked this):
  - every question.needs_review is False
  - every mcq question has exactly 4 options with exactly 1 is_correct=True
  - exam.start_at < exam.end_at
  - exam.duration_minutes <= (end_at - start_at) in minutes
  - at least 1 question exists
On success: status='scheduled', published_at=now(), total_points recomputed.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.attempt import ExamAttempt
from app.models.exam import Exam, ExamStatus, Question, QuestionType
from app.models.user import TeacherClassSubject, User, UserRole


def ensure_can_author_exam(db: Session, user: User, class_id: int, subject_id: int) -> None:
    """Raises 403 unless `user` is an admin, or a teacher assigned to teach
    `subject_id` to `class_id` via teacher_class_subjects."""
    if user.role == UserRole.admin:
        return
    if user.role != UserRole.teacher or user.teacher is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ruxsat yo'q")
    assigned = (
        db.query(TeacherClassSubject)
        .filter_by(teacher_id=user.teacher.id, class_id=class_id, subject_id=subject_id)
        .first()
    )
    if assigned is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu sinf/fan uchun ruxsatingiz yo'q",
        )


def ensure_can_manage_exam(db: Session, user: User, exam: Exam) -> None:
    ensure_can_author_exam(db, user, exam.class_id, exam.subject_id)


def has_attempts(db: Session, exam: Exam) -> bool:
    return db.query(ExamAttempt).filter_by(exam_id=exam.id).first() is not None


def ensure_no_attempts(db: Session, exam: Exam) -> None:
    """Both question/option edits and schedule-field edits (duration/
    start/end/shuffle) share one rule: allowed on a draft *and* on an
    already-published (scheduled/active) exam, right up until the moment
    any student actually starts it. A started attempt snapshots the
    question/option order and, once submitted, its score — editing
    content out from under that would desync the student's view or
    invalidate a grade already recorded, so this is the one hard line."""
    if has_attempts(db, exam):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu imtihonni allaqachon boshlagan o'quvchilar bor, endi tahrirlab bo'lmaydi",
        )


def recompute_total_points(db: Session, exam: Exam) -> None:
    # A direct query, not exam.questions — that in-memory collection can be
    # stale right after this same request added/removed a question (the
    # child's exam_id FK was set directly, not via the relationship, so the
    # parent's loaded collection doesn't auto-update).
    total = db.query(func.sum(Question.points)).filter_by(exam_id=exam.id).scalar()
    exam.total_points = float(total) if total else None


def publish_exam(db: Session, exam: Exam) -> Exam:
    if exam.status not in (ExamStatus.draft, ExamStatus.review):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu imtihon allaqachon chop etilgan")

    if not exam.questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kamida 1 ta savol bo'lishi kerak")

    for q in exam.questions:
        if q.needs_review:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Savol #{q.order_index + 1} hali tekshirilmagan (needs_review)",
            )
        if q.question_type == QuestionType.mcq:
            if len(q.options) != 4:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Savol #{q.order_index + 1} aynan 4 ta variantga ega bo'lishi kerak",
                )
            correct_count = sum(1 for o in q.options if o.is_correct)
            if correct_count != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Savol #{q.order_index + 1} aynan 1 ta to'g'ri javobga ega bo'lishi kerak",
                )

    if exam.start_at is None or exam.end_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_at/end_at belgilanmagan")
    if exam.start_at >= exam.end_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_at end_at'dan oldin bo'lishi kerak")
    window_minutes = (exam.end_at - exam.start_at).total_seconds() / 60
    if exam.duration_minutes > window_minutes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duration_minutes oyna uzunligidan katta bo'lishi mumkin emas",
        )

    recompute_total_points(db, exam)
    exam.status = ExamStatus.scheduled
    exam.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(exam)
    return exam
