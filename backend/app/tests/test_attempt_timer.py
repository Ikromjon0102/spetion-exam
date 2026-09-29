from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models.attempt import AttemptStatus
from app.models.exam import ExamStatus
from app.services import attempt_service
from app.tests.factories import add_mcq_question, make_class, make_exam, make_student, make_subject


def _scheduled_exam_with_student(db, duration_minutes=30, start_delta=timedelta(minutes=-5), end_delta=timedelta(hours=1)):
    klass = make_class(db)
    subject = make_subject(db)
    now = datetime.now(timezone.utc)
    exam = make_exam(
        db,
        klass,
        subject,
        status=ExamStatus.scheduled,
        duration_minutes=duration_minutes,
        start_at=now + start_delta,
        end_at=now + end_delta,
    )
    add_mcq_question(db, exam, correct_index=0)
    student = make_student(db, klass)
    db.commit()
    return exam, student


def test_start_attempt_sets_deadline_and_persists_order(db_session):
    exam, student = _scheduled_exam_with_student(db_session, duration_minutes=30)
    attempt = attempt_service.start_attempt(db_session, exam, student)

    assert attempt.status == AttemptStatus.in_progress
    assert attempt.started_at is not None
    assert attempt.deadline_at is not None
    assert attempt.question_order is not None


def test_start_attempt_deadline_capped_by_exam_end(db_session):
    # duration_minutes (999) would overshoot end_at — deadline must be capped there
    exam, student = _scheduled_exam_with_student(
        db_session, duration_minutes=999, start_delta=timedelta(minutes=-5), end_delta=timedelta(minutes=10)
    )
    attempt = attempt_service.start_attempt(db_session, exam, student)
    # sqlite drops the tz offset on refresh; compare naive-vs-aware by value only
    assert attempt.deadline_at.replace(tzinfo=None) == exam.end_at.replace(tzinfo=None)


def test_start_attempt_double_call_is_idempotent_not_duplicated(db_session):
    exam, student = _scheduled_exam_with_student(db_session)
    first = attempt_service.start_attempt(db_session, exam, student)
    second = attempt_service.start_attempt(db_session, exam, student)
    assert first.id == second.id
    assert first.deadline_at == second.deadline_at


def test_start_attempt_rejected_before_window_opens(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    now = datetime.now(timezone.utc)
    exam = make_exam(
        db_session, klass, subject, status=ExamStatus.scheduled, start_at=now + timedelta(hours=1), end_at=now + timedelta(hours=2)
    )
    add_mcq_question(db_session, exam)
    student = make_student(db_session, klass)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        attempt_service.start_attempt(db_session, exam, student)
    assert exc.value.status_code == 400


def test_start_attempt_rejected_after_window_closes(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    now = datetime.now(timezone.utc)
    exam = make_exam(
        db_session, klass, subject, status=ExamStatus.scheduled, start_at=now - timedelta(hours=2), end_at=now - timedelta(hours=1)
    )
    add_mcq_question(db_session, exam)
    student = make_student(db_session, klass)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        attempt_service.start_attempt(db_session, exam, student)
    assert exc.value.status_code == 400


def test_start_attempt_succeeds_after_expired_unstarted_row_and_reschedule(db_session):
    """The lifecycle sweep (mark_expired_unstarted) creates an
    expired_unstarted ExamAttempt for a student who never opened the exam
    once its window first closed. If a teacher then edits the exam to
    reopen the window (allowed — see ensure_no_attempts, expired_unstarted
    doesn't count as "started"), the student must actually be able to
    start it, not get a stale 409 as if they'd already finished."""
    exam, student = _scheduled_exam_with_student(db_session)
    attempt = attempt_service.start_attempt(db_session, exam, student)
    # Simulate the sweep marking it expired (window closed, never opened)
    # instead of actually going through it — same end state either way.
    attempt.status = AttemptStatus.expired_unstarted
    attempt.started_at = None
    attempt.deadline_at = None
    db_session.commit()

    resumed = attempt_service.start_attempt(db_session, exam, student)
    assert resumed.id == attempt.id
    assert resumed.status == AttemptStatus.in_progress
    assert resumed.started_at is not None


def test_record_answer_rejected_after_deadline_even_if_status_in_progress(db_session):
    """The server-side deadline check, not the client countdown, is what
    must block a late write — see docs/spec.md section 3 step 7."""
    exam, student = _scheduled_exam_with_student(db_session)
    attempt = attempt_service.start_attempt(db_session, exam, student)
    attempt.deadline_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    question = exam.questions[0]
    with pytest.raises(HTTPException) as exc:
        attempt_service.record_answer(db_session, attempt, question.id, question.options[0].id, None)
    assert exc.value.status_code == 403


def test_record_answer_upserts_same_question(db_session):
    exam, student = _scheduled_exam_with_student(db_session)
    attempt = attempt_service.start_attempt(db_session, exam, student)
    question = exam.questions[0]

    attempt_service.record_answer(db_session, attempt, question.id, question.options[0].id, None)
    answer = attempt_service.record_answer(db_session, attempt, question.id, question.options[1].id, None)

    assert answer.selected_option_id == question.options[1].id
    assert len(attempt.answers) == 1


def test_submit_grades_and_is_idempotent(db_session):
    exam, student = _scheduled_exam_with_student(db_session)
    attempt = attempt_service.start_attempt(db_session, exam, student)
    question = exam.questions[0]
    correct_option = next(o for o in question.options if o.is_correct)
    attempt_service.record_answer(db_session, attempt, question.id, correct_option.id, None)

    submitted = attempt_service.submit_attempt(db_session, attempt.id)
    assert submitted.status == AttemptStatus.submitted
    assert float(submitted.score) == float(question.points)

    again = attempt_service.submit_attempt(db_session, attempt.id)
    assert again.status == AttemptStatus.submitted
    assert again.submitted_at == submitted.submitted_at
