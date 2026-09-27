"""Covers AI-graded short_answer questions (post-launch roadmap item #4):
publish validation (a teacher must supply reference_answer), grading on
submit (AI grade counts immediately), and a teacher's manual override
afterward. The real Anthropic API is never called here —
ai_grading_service.grade_short_answer is monkeypatched everywhere a
graded submit happens, since a real backend/.env ANTHROPIC_API_KEY is
picked up by Settings even under pytest and would otherwise make a real,
billed network call on every test run.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.exam import ExamStatus
from app.services import attempt_service
from app.services.exam_service import publish_exam
from app.tests.factories import (
    add_mcq_question,
    add_short_answer_question,
    make_admin,
    make_class,
    make_exam,
    make_student,
    make_subject,
    make_teacher,
)


def _login(client, username, password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_publish_rejects_short_answer_question_without_reference_answer(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=datetime.now(timezone.utc), end_at=datetime.now(timezone.utc) + timedelta(hours=1))
    add_short_answer_question(db_session, exam, reference_answer="   ")
    db_session.commit()

    with pytest.raises(Exception) as exc_info:
        publish_exam(db_session, exam)
    assert "namunaviy javob" in str(exc_info.value.detail).lower()


def test_publish_succeeds_once_reference_answer_is_set(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start = datetime.now(timezone.utc)
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=start, end_at=start + timedelta(hours=1))
    add_short_answer_question(db_session, exam, reference_answer="Fotosintez — quyosh energiyasidan foydalanish jarayoni")
    db_session.commit()

    published = publish_exam(db_session, exam)
    assert published.status == ExamStatus.scheduled


def test_short_answer_graded_by_ai_immediately_on_submit(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.ai_grading_service.grade_short_answer",
        lambda **kwargs: (1.5, "Asosiy g'oya to'g'ri, lekin to'liq emas."),
    )

    klass = make_class(db_session)
    subject = make_subject(db_session)
    make_admin(db_session, username="ai_grading_admin")
    student = make_student(db_session, klass, username="ai_grading_student")
    db_session.commit()

    now = datetime.now(timezone.utc)
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=now - timedelta(minutes=5), end_at=now + timedelta(hours=1))
    question = add_short_answer_question(db_session, exam, reference_answer="Namunaviy javob", points=2)
    db_session.commit()
    publish_exam(db_session, exam)

    attempt = attempt_service.start_attempt(db_session, exam, student)
    attempt_service.record_answer(db_session, attempt, question.id, None, "O'quvchining javobi")
    attempt = attempt_service.submit_attempt(db_session, attempt.id)

    answer = attempt.answers[0]
    assert answer.points_awarded == 1.5
    assert answer.is_correct is False  # 1.5 < 2 (max points)
    assert answer.graded_by == "ai"
    assert answer.ai_feedback == "Asosiy g'oya to'g'ri, lekin to'liq emas."
    assert float(attempt.score) == 1.5

    token = _login(client, "ai_grading_admin")
    resp = client.get(
        f"/api/v1/admin/exams/{exam.id}/attempts/{student.id}/answers", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["reference_answer"] == "Namunaviy javob"
    assert body[0]["answer_text"] == "O'quvchining javobi"
    assert body[0]["points_awarded"] == 1.5
    assert body[0]["graded_by"] == "ai"
    assert body[0]["ai_feedback"] == "Asosiy g'oya to'g'ri, lekin to'liq emas."


def test_unanswered_short_answer_gets_zero_without_calling_ai(client, db_session, monkeypatch):
    """grade_short_answer itself short-circuits on an empty answer (see its
    own docstring) — this just confirms grading_service doesn't skip
    calling it, and the zero flows through to attempt.score correctly."""
    called = {"count": 0}

    def fake_grade(**kwargs):
        called["count"] += 1
        return (0.0, "O'quvchi javob yozmagan.")

    monkeypatch.setattr("app.services.ai_grading_service.grade_short_answer", fake_grade)

    klass = make_class(db_session)
    subject = make_subject(db_session)
    make_admin(db_session, username="ai_grading_empty_admin")
    student = make_student(db_session, klass, username="ai_grading_empty_student")
    db_session.commit()

    now = datetime.now(timezone.utc)
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=now - timedelta(minutes=5), end_at=now + timedelta(hours=1))
    add_short_answer_question(db_session, exam, reference_answer="Namunaviy javob", points=2)
    db_session.commit()
    publish_exam(db_session, exam)

    attempt = attempt_service.start_attempt(db_session, exam, student)
    # never answers the question at all
    attempt = attempt_service.submit_attempt(db_session, attempt.id)

    assert float(attempt.score) == 0.0
    assert called["count"] == 0  # no StudentAnswer row at all -> nothing to grade


def test_teacher_can_override_ai_grade(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.ai_grading_service.grade_short_answer",
        lambda **kwargs: (0.0, "Javob mos kelmadi."),
    )

    klass = make_class(db_session)
    subject = make_subject(db_session)
    make_admin(db_session, username="override_admin")
    student = make_student(db_session, klass, username="override_student")
    db_session.commit()

    now = datetime.now(timezone.utc)
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=now - timedelta(minutes=5), end_at=now + timedelta(hours=1))
    sa_question = add_short_answer_question(db_session, exam, reference_answer="Namunaviy javob", points=3, order_index=0)
    mcq_question = add_mcq_question(db_session, exam, correct_index=0, order_index=1, points=1)
    db_session.commit()
    publish_exam(db_session, exam)

    attempt = attempt_service.start_attempt(db_session, exam, student)
    attempt_service.record_answer(db_session, attempt, sa_question.id, None, "Aslida to'g'ri javob edi")
    attempt_service.record_answer(db_session, attempt, mcq_question.id, mcq_question.options[0].id, None)
    attempt = attempt_service.submit_attempt(db_session, attempt.id)
    assert float(attempt.score) == 1.0  # 0 (AI-graded short answer) + 1 (correct mcq)

    token = _login(client, "override_admin")
    headers = {"Authorization": f"Bearer {token}"}

    override_resp = client.put(
        f"/api/v1/admin/exams/{exam.id}/attempts/{student.id}/answers/{sa_question.id}",
        json={"points_awarded": 3},
        headers=headers,
    )
    assert override_resp.status_code == 200
    body = override_resp.json()
    assert body["points_awarded"] == 3.0
    assert body["is_correct"] is True
    assert body["graded_by"] == "teacher"

    db_session.refresh(attempt)
    assert float(attempt.score) == 4.0  # 3 (overridden) + 1 (mcq), AI's 0 is gone


def test_override_rejects_points_outside_valid_range(client, db_session, monkeypatch):
    monkeypatch.setattr("app.services.ai_grading_service.grade_short_answer", lambda **kwargs: (0.0, "x"))

    klass = make_class(db_session)
    subject = make_subject(db_session)
    make_admin(db_session, username="override_range_admin")
    student = make_student(db_session, klass, username="override_range_student")
    db_session.commit()

    now = datetime.now(timezone.utc)
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=now - timedelta(minutes=5), end_at=now + timedelta(hours=1))
    question = add_short_answer_question(db_session, exam, reference_answer="Namunaviy javob", points=2)
    db_session.commit()
    publish_exam(db_session, exam)

    attempt = attempt_service.start_attempt(db_session, exam, student)
    attempt_service.record_answer(db_session, attempt, question.id, None, "javob")
    attempt_service.submit_attempt(db_session, attempt.id)

    token = _login(client, "override_range_admin")
    headers = {"Authorization": f"Bearer {token}"}
    too_high = client.put(
        f"/api/v1/admin/exams/{exam.id}/attempts/{student.id}/answers/{question.id}",
        json={"points_awarded": 5},
        headers=headers,
    )
    assert too_high.status_code == 400

    negative = client.put(
        f"/api/v1/admin/exams/{exam.id}/attempts/{student.id}/answers/{question.id}",
        json={"points_awarded": -1},
        headers=headers,
    )
    assert negative.status_code == 400


def test_unconnected_teacher_cannot_view_or_override_answers(client, db_session, monkeypatch):
    monkeypatch.setattr("app.services.ai_grading_service.grade_short_answer", lambda **kwargs: (0.0, "x"))

    klass = make_class(db_session)
    subject = make_subject(db_session)
    unconnected = make_teacher(db_session, username="unconnected_reviewer")
    student = make_student(db_session, klass, username="unconnected_review_student")
    db_session.commit()

    now = datetime.now(timezone.utc)
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=now - timedelta(minutes=5), end_at=now + timedelta(hours=1))
    question = add_short_answer_question(db_session, exam, reference_answer="Namunaviy javob", points=2)
    db_session.commit()
    publish_exam(db_session, exam)

    attempt = attempt_service.start_attempt(db_session, exam, student)
    attempt_service.record_answer(db_session, attempt, question.id, None, "javob")
    attempt_service.submit_attempt(db_session, attempt.id)

    token = _login(client, "unconnected_reviewer")
    headers = {"Authorization": f"Bearer {token}"}
    forbidden_get = client.get(f"/api/v1/admin/exams/{exam.id}/attempts/{student.id}/answers", headers=headers)
    assert forbidden_get.status_code == 403

    forbidden_put = client.put(
        f"/api/v1/admin/exams/{exam.id}/attempts/{student.id}/answers/{question.id}",
        json={"points_awarded": 2},
        headers=headers,
    )
    assert forbidden_put.status_code == 403


def test_ai_grading_service_falls_back_without_crashing_when_unconfigured(monkeypatch):
    """Direct unit test of ai_grading_service itself (no monkeypatch of the
    function under test here) — confirms the real fallback path used when
    ANTHROPIC_API_KEY is unset, by clearing it just for this test."""
    from app.services import ai_grading_service

    monkeypatch.setattr("app.config.settings.anthropic_api_key", None)
    monkeypatch.setattr(ai_grading_service, "_client", None)

    points, feedback = ai_grading_service.grade_short_answer(
        prompt_text="Savol?", reference_answer="Javob", student_answer="Mening javobim", max_points=2.0
    )
    assert points == 0.0
    assert "sozlanmagan" in feedback.lower() or "ANTHROPIC_API_KEY" in feedback


def test_ai_grading_service_empty_answer_never_calls_the_api(monkeypatch):
    from app.services import ai_grading_service

    def fail_if_called(*args, **kwargs):
        raise AssertionError("should never construct a client for an empty answer")

    monkeypatch.setattr(ai_grading_service, "_get_client", fail_if_called)

    points, feedback = ai_grading_service.grade_short_answer(
        prompt_text="Savol?", reference_answer="Javob", student_answer="   ", max_points=2.0
    )
    assert points == 0.0
    assert feedback
