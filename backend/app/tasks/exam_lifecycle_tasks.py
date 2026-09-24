"""Celery beat tasks — the actual authority for exam timing, not the client.

auto_submit_expired_attempts(): every ~20s, scans
  exam_attempts WHERE status='in_progress' AND deadline_at < now()
and force-submits them (status='auto_submitted'), calling the SAME
grading_service.grade_attempt() the manual /submit endpoint uses. Each
attempt row is locked before grading so this can't race a late manual
submit for the same attempt.

mark_expired_unstarted(): every ~60s, marks exam_attempts still
'not_started' as 'expired_unstarted' once exam.end_at has passed (also
covers students who never called /start at all — iterates exams whose
end_at just passed and creates/flags missing attempt rows for their class).
"""

from datetime import datetime, timezone

from app.db.base import SessionLocal
from app.models.attempt import AttemptStatus, ExamAttempt
from app.models.exam import Exam, ExamStatus
from app.models.user import Student
from app.services import grading_service, ranking_service
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.exam_lifecycle_tasks.auto_submit_expired_attempts")
def auto_submit_expired_attempts() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired_ids = [
            row.id
            for row in db.query(ExamAttempt.id).filter(
                ExamAttempt.status == AttemptStatus.in_progress, ExamAttempt.deadline_at < now
            )
        ]
        for attempt_id in expired_ids:
            attempt = db.query(ExamAttempt).filter_by(id=attempt_id).with_for_update().one()
            if attempt.status != AttemptStatus.in_progress:
                continue  # a manual /submit won the race in the meantime

            attempt.status = AttemptStatus.auto_submitted
            attempt.submitted_at = now
            db.commit()

            grading_service.grade_attempt(db, attempt)
            ranking_service.recompute_for_student(db, attempt.exam_id, attempt.student_id)
    finally:
        db.close()


@celery_app.task(name="app.tasks.exam_lifecycle_tasks.mark_expired_unstarted")
def mark_expired_unstarted() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        exams = (
            db.query(Exam)
            .filter(
                Exam.status.in_([ExamStatus.scheduled, ExamStatus.active]),
                Exam.end_at.isnot(None),
                Exam.end_at < now,
            )
            .all()
        )
        for exam in exams:
            student_ids = [row.id for row in db.query(Student.id).filter_by(class_id=exam.class_id)]
            if not student_ids:
                continue

            existing_by_student = {
                row.student_id: row
                for row in db.query(ExamAttempt).filter(
                    ExamAttempt.exam_id == exam.id, ExamAttempt.student_id.in_(student_ids)
                )
            }
            for student_id in student_ids:
                attempt = existing_by_student.get(student_id)
                if attempt is None:
                    db.add(
                        ExamAttempt(
                            exam_id=exam.id,
                            student_id=student_id,
                            status=AttemptStatus.expired_unstarted,
                        )
                    )
                elif attempt.status == AttemptStatus.not_started:
                    attempt.status = AttemptStatus.expired_unstarted
            db.commit()
    finally:
        db.close()
