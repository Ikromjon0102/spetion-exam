"""start_attempt / record_answer / submit_attempt.

start_attempt: rejects outside the exam window; INSERT ... ON CONFLICT DO
NOTHING on (exam_id, student_id) then re-select (never check-then-insert —
avoids a race when a whole class starts at once); on first creation sets
started_at=now(), deadline_at=min(now()+duration_minutes, end_at), and
persists a seeded (seed=attempt.id) shuffle of question/option order so a
refresh or the review screen shows the same order.

record_answer: rejects writes made after deadline_at server-side,
independent of the client countdown.

submit_attempt: locks the exam_attempts row (SELECT ... FOR UPDATE) before
grading so a concurrent beat-task auto-submit and a manual /submit can't
double-grade the same attempt; delegates to grading_service then
ranking_service, exactly like the beat sweep does.
"""

import random
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.timeutil import aware
from app.models.attempt import AttemptStatus, ExamAttempt, StudentAnswer
from app.models.exam import Exam, ExamStatus, Question, QuestionOption
from app.models.user import Student
from app.services import grading_service, ranking_service


def _insert(db: Session):
    """The on-conflict upsert API is identical between the postgresql and
    sqlite dialects — dispatch on the bound dialect so this also runs
    against the sqlite test DB, while production (postgres) keeps the exact
    INSERT ... ON CONFLICT DO NOTHING semantics docs/spec.md requires."""
    if db.get_bind().dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        return sqlite_insert
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    return pg_insert


def _build_question_order(exam: Exam, seed: int) -> dict:
    rng = random.Random(seed)
    question_ids = [q.id for q in exam.questions]
    if exam.shuffle_questions:
        rng.shuffle(question_ids)

    option_order: dict[str, list[int]] = {}
    for q in exam.questions:
        ids = [o.id for o in q.options]
        if exam.shuffle_options:
            rng.shuffle(ids)
        option_order[str(q.id)] = ids

    return {"questions": question_ids, "options": option_order}


def get_ordered_questions(exam: Exam, attempt: ExamAttempt) -> list[Question]:
    order = attempt.question_order or {}
    q_ids = order.get("questions") or [q.id for q in exam.questions]
    by_id = {q.id: q for q in exam.questions}
    return [by_id[qid] for qid in q_ids if qid in by_id]


def get_ordered_options(attempt: ExamAttempt, question: Question) -> list[QuestionOption]:
    order = attempt.question_order or {}
    opt_ids = (order.get("options") or {}).get(str(question.id)) or [o.id for o in question.options]
    by_id = {o.id: o for o in question.options}
    return [by_id[oid] for oid in opt_ids if oid in by_id]


def start_attempt(db: Session, exam: Exam, student: Student) -> ExamAttempt:
    now = datetime.now(timezone.utc)
    if exam.status not in (ExamStatus.scheduled, ExamStatus.active):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Imtihon hali e'lon qilinmagan")
    if not (exam.start_at and exam.end_at and aware(exam.start_at) <= now < aware(exam.end_at)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Imtihon oynasi hozir ochiq emas")

    stmt = (
        _insert(db)(ExamAttempt)
        .values(exam_id=exam.id, student_id=student.id, status=AttemptStatus.not_started)
        .on_conflict_do_nothing(index_elements=["exam_id", "student_id"])
    )
    db.execute(stmt)
    db.commit()

    attempt = (
        db.query(ExamAttempt)
        .filter_by(exam_id=exam.id, student_id=student.id)
        .with_for_update()
        .one()
    )

    if attempt.status == AttemptStatus.not_started:
        deadline = min(now + timedelta(minutes=exam.duration_minutes), aware(exam.end_at))
        attempt.status = AttemptStatus.in_progress
        attempt.started_at = now
        attempt.deadline_at = deadline
        attempt.question_order = _build_question_order(exam, attempt.id)
        db.commit()
        db.refresh(attempt)
    elif attempt.status != AttemptStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu imtihon allaqachon yakunlangan")

    return attempt


def record_answer(
    db: Session,
    attempt: ExamAttempt,
    question_id: int,
    selected_option_id: int | None,
    answer_text: str | None,
) -> StudentAnswer:
    now = datetime.now(timezone.utc)
    if attempt.status != AttemptStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu urinish faol emas")
    if attempt.deadline_at is None or now > aware(attempt.deadline_at):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vaqt tugagan")

    stmt = (
        _insert(db)(StudentAnswer)
        .values(
            attempt_id=attempt.id,
            question_id=question_id,
            selected_option_id=selected_option_id,
            answer_text=answer_text,
            answered_at=now,
        )
        .on_conflict_do_update(
            index_elements=["attempt_id", "question_id"],
            set_={
                "selected_option_id": selected_option_id,
                "answer_text": answer_text,
                "answered_at": now,
            },
        )
    )
    db.execute(stmt)
    db.commit()
    return db.query(StudentAnswer).filter_by(attempt_id=attempt.id, question_id=question_id).one()


def submit_attempt(db: Session, attempt_id: int) -> ExamAttempt:
    attempt = db.query(ExamAttempt).filter_by(id=attempt_id).with_for_update().one()

    if attempt.status in (AttemptStatus.submitted, AttemptStatus.auto_submitted):
        return attempt
    if attempt.status != AttemptStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu urinish topshirib bo'lmaydi")

    attempt.status = AttemptStatus.submitted
    attempt.submitted_at = datetime.now(timezone.utc)
    db.commit()

    grading_service.grade_attempt(db, attempt)
    ranking_service.recompute_for_student(db, attempt.exam_id, attempt.student_id)
    return attempt
