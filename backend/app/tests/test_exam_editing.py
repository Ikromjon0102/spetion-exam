"""Covers editing a published exam: the user asked whether a teacher can
still change an exam after scheduling it. Answer implemented here: yes,
right up until a student actually starts it (see
exam_service.ensure_no_attempts) — a started ExamAttempt snapshots
question/option order and eventually a score, so editing after that would
desync a student's view or invalidate a recorded grade. Before that,
draft *or* already-scheduled/active exams are equally editable.
"""

from datetime import datetime, timedelta, timezone

from app.models.attempt import AttemptStatus, ExamAttempt
from app.models.exam import ExamStatus
from app.tests.factories import add_mcq_question, make_admin, make_class, make_exam, make_student, make_subject


def _window():
    start = datetime.now(timezone.utc)
    return start, start + timedelta(hours=2)


def _login(client, username, password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_headers(client, db_session, username="exam_edit_admin"):
    make_admin(db_session, username=username)
    db_session.commit()
    return {"Authorization": f"Bearer {_login(client, username)}"}


def _publish(db_session, exam):
    exam.status = ExamStatus.scheduled
    exam.published_at = datetime.now(timezone.utc)
    db_session.commit()


def test_can_edit_true_for_scheduled_exam_with_no_attempts(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=end)
    add_mcq_question(db_session, exam, needs_review=False)
    _publish(db_session, exam)
    headers = _admin_headers(client, db_session)

    resp = client.get(f"/api/v1/admin/exams/{exam.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["can_edit"] is True
    assert resp.json()["status"] == "scheduled"


def test_can_edit_false_once_a_student_starts(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=end)
    add_mcq_question(db_session, exam, needs_review=False)
    _publish(db_session, exam)
    student = make_student(db_session, klass)
    db_session.add(ExamAttempt(exam_id=exam.id, student_id=student.id, status=AttemptStatus.in_progress))
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.get(f"/api/v1/admin/exams/{exam.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["can_edit"] is False


def test_editing_question_on_scheduled_exam_with_no_attempts_succeeds(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=end)
    question = add_mcq_question(db_session, exam, needs_review=False, points=1)
    _publish(db_session, exam)
    headers = _admin_headers(client, db_session)

    resp = client.put(
        f"/api/v1/admin/exams/{exam.id}/questions/{question.id}",
        json={"prompt_text": "Yangilangan savol matni", "points": 5},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["prompt_text"] == "Yangilangan savol matni"

    # total_points recomputed even though the exam was already published
    detail = client.get(f"/api/v1/admin/exams/{exam.id}", headers=headers)
    assert detail.json()["total_points"] == 5.0


def test_editing_question_blocked_once_a_student_starts(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=end)
    question = add_mcq_question(db_session, exam, needs_review=False)
    _publish(db_session, exam)
    student = make_student(db_session, klass)
    db_session.add(ExamAttempt(exam_id=exam.id, student_id=student.id, status=AttemptStatus.in_progress))
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.put(
        f"/api/v1/admin/exams/{exam.id}/questions/{question.id}",
        json={"prompt_text": "Should not be allowed"},
        headers=headers,
    )
    assert resp.status_code == 409


def test_add_and_delete_question_recompute_total_points(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=end)
    q1 = add_mcq_question(db_session, exam, needs_review=False, order_index=0, points=2)
    _publish(db_session, exam)
    headers = _admin_headers(client, db_session)

    add_resp = client.post(
        f"/api/v1/admin/exams/{exam.id}/questions",
        json={
            "prompt_text": "Yangi savol",
            "points": 3,
            "options": [
                {"option_text": "A", "is_correct": True},
                {"option_text": "B", "is_correct": False},
                {"option_text": "C", "is_correct": False},
                {"option_text": "D", "is_correct": False},
            ],
        },
        headers=headers,
    )
    assert add_resp.status_code == 201

    detail = client.get(f"/api/v1/admin/exams/{exam.id}", headers=headers)
    assert detail.json()["total_points"] == 5.0  # 2 + 3

    delete_resp = client.delete(f"/api/v1/admin/exams/{exam.id}/questions/{q1.id}", headers=headers)
    assert delete_resp.status_code == 204

    detail2 = client.get(f"/api/v1/admin/exams/{exam.id}", headers=headers)
    assert detail2.json()["total_points"] == 3.0


def test_reschedule_scheduled_exam_with_no_attempts_succeeds(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=start, end_at=end)
    add_mcq_question(db_session, exam, needs_review=False)
    _publish(db_session, exam)
    headers = _admin_headers(client, db_session)

    resp = client.put(
        f"/api/v1/admin/exams/{exam.id}", json={"duration_minutes": 45}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["duration_minutes"] == 45


def test_reschedule_blocked_once_a_student_starts(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start, end = _window()
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=start, end_at=end)
    add_mcq_question(db_session, exam, needs_review=False)
    _publish(db_session, exam)
    student = make_student(db_session, klass)
    db_session.add(ExamAttempt(exam_id=exam.id, student_id=student.id, status=AttemptStatus.in_progress))
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.put(
        f"/api/v1/admin/exams/{exam.id}", json={"duration_minutes": 45}, headers=headers
    )
    assert resp.status_code == 409
