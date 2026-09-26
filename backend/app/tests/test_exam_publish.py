from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models.exam import ExamStatus, Question, QuestionOption, QuestionType
from app.services.exam_service import publish_exam
from app.tests.factories import add_mcq_question, make_class, make_exam, make_subject


def _add_question_with_options(db_session, exam, option_count: int, correct_index: int = 0, order_index: int = 0):
    """Unlike add_mcq_question (always 4 options), builds a question with an
    arbitrary option count — for testing the now-relaxed "at least 2, not
    exactly 4" publish rule (True/False, 3-option, 5-option, etc.)."""
    question = Question(
        exam_id=exam.id,
        order_index=order_index,
        question_type=QuestionType.mcq,
        prompt_text=f"Savol {order_index + 1}?",
        points=1,
        needs_review=False,
    )
    db_session.add(question)
    db_session.flush()
    for i in range(option_count):
        db_session.add(
            QuestionOption(
                question_id=question.id, order_index=i, option_text=f"Variant {i}", is_correct=(i == correct_index)
            )
        )
    db_session.flush()
    db_session.refresh(question)
    return question


def _window():
    start = datetime.now(timezone.utc)
    return start, start + timedelta(hours=2)


def test_publish_fails_without_questions(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=end)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        publish_exam(db_session, exam)
    assert exc.value.status_code == 400


def test_publish_fails_if_any_question_needs_review(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=end)
    add_mcq_question(db_session, exam, needs_review=True)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        publish_exam(db_session, exam)
    assert exc.value.status_code == 400


def test_publish_fails_without_exactly_one_correct_option(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=end)
    question = add_mcq_question(db_session, exam, correct_index=0, needs_review=False)
    question.options[1].is_correct = True  # now 2 correct options
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        publish_exam(db_session, exam)
    assert exc.value.status_code == 400


def test_publish_fails_if_duration_exceeds_window(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start = datetime.now(timezone.utc)
    exam = make_exam(db_session, klass, subject, duration_minutes=999, start_at=start, end_at=start + timedelta(minutes=30))
    add_mcq_question(db_session, exam, needs_review=False)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        publish_exam(db_session, exam)
    assert exc.value.status_code == 400


def test_publish_fails_if_start_after_end(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start = datetime.now(timezone.utc)
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=start - timedelta(hours=1))
    add_mcq_question(db_session, exam, needs_review=False)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        publish_exam(db_session, exam)
    assert exc.value.status_code == 400


def test_publish_succeeds_and_recomputes_total_points(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=start, end_at=end)
    add_mcq_question(db_session, exam, needs_review=False, order_index=0, points=2)
    add_mcq_question(db_session, exam, needs_review=False, order_index=1, points=3)
    db_session.commit()

    published = publish_exam(db_session, exam)
    assert published.status == ExamStatus.scheduled
    assert published.published_at is not None
    assert float(published.total_points) == 5.0


def test_publish_succeeds_with_true_false_style_two_options(db_session):
    """The "exactly 4 options" rule was explicitly relaxed on the user's
    request — a True/False question (2 options) must publish fine now."""
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=end)
    _add_question_with_options(db_session, exam, option_count=2)
    db_session.commit()

    published = publish_exam(db_session, exam)
    assert published.status == ExamStatus.scheduled


def test_publish_succeeds_with_five_options(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=end)
    _add_question_with_options(db_session, exam, option_count=5)
    db_session.commit()

    published = publish_exam(db_session, exam)
    assert published.status == ExamStatus.scheduled


def test_publish_fails_with_only_one_option(db_session):
    """Still a floor: a single-option "question" isn't really a question."""
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=end)
    _add_question_with_options(db_session, exam, option_count=1)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        publish_exam(db_session, exam)
    assert exc.value.status_code == 400


def test_publish_twice_is_rejected(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=end)
    add_mcq_question(db_session, exam, needs_review=False)
    db_session.commit()

    publish_exam(db_session, exam)
    with pytest.raises(HTTPException) as exc:
        publish_exam(db_session, exam)
    assert exc.value.status_code == 409
