"""Covers GET /admin/classes/{id}/daily-results — backs the "sinf raxbari"
end-of-day Telegram share (post-launch roadmap item #2): once today's
exams for a class have finished, the homeroom teacher downloads a
combined image of every exam's ranking and shares it themselves via their
own Telegram (no bot integration, by explicit user request). Only the
data endpoint is covered here; the image export itself is a pure
client-side html2canvas render of what this endpoint returns.
"""

from datetime import datetime, timedelta, timezone

from app.core.timeutil import local_day_bounds_utc
from app.services import attempt_service
from app.services.exam_service import publish_exam
from app.tests.factories import (
    add_mcq_question,
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


def _make_scored_exam(db_session, klass, subject, student, end_at, correct_count=3, total_count=4):
    """Creates, publishes, takes and submits the exam through the real
    window-currently-open window (start_attempt/submit_attempt both check
    against the actual clock), then backdates/forward-dates `end_at` to
    the target moment afterward — purely to control which calendar day the
    daily-results query buckets it into, without touching the already-
    computed ExamRanking rows."""
    now = datetime.now(timezone.utc)
    exam = make_exam(
        db_session, klass, subject, duration_minutes=30, start_at=now - timedelta(hours=1), end_at=now + timedelta(hours=2)
    )
    for i in range(total_count):
        add_mcq_question(db_session, exam, correct_index=0, order_index=i, points=1)
    db_session.commit()
    publish_exam(db_session, exam)

    attempt = attempt_service.start_attempt(db_session, exam, student)
    for i, q in enumerate(exam.questions):
        chosen = q.options[0] if i < correct_count else q.options[1]
        attempt_service.record_answer(db_session, attempt, q.id, chosen.id, None)
    attempt_service.submit_attempt(db_session, attempt.id)

    exam.end_at = end_at
    db_session.commit()
    return exam


def test_admin_sees_todays_exams_grouped_with_their_rankings(client, db_session):
    klass = make_class(db_session)
    math = make_subject(db_session, name="Matematika")
    physics = make_subject(db_session, name="Fizika")
    make_admin(db_session, username="daily_admin")
    student = make_student(db_session, klass, username="daily_student")
    db_session.commit()

    _, day_start, _ = local_day_bounds_utc()
    today_moment = day_start + timedelta(hours=6)  # safely inside today's local window
    yesterday_moment = day_start - timedelta(hours=1)  # falls in the previous local day

    todays_exam = _make_scored_exam(db_session, klass, math, student, end_at=today_moment, correct_count=3)
    _make_scored_exam(db_session, klass, physics, student, end_at=yesterday_moment, correct_count=1)

    token = _login(client, "daily_admin")
    resp = client.get(f"/api/v1/admin/classes/{klass.id}/daily-results", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["exams"]) == 1
    assert body["exams"][0]["exam_id"] == todays_exam.id
    assert body["exams"][0]["subject_name"] == "Matematika"
    assert body["exams"][0]["rankings"][0]["full_name"] == student.user.full_name
    assert body["exams"][0]["rankings"][0]["score"] == 3.0


def test_homeroom_teacher_sees_results_for_a_subject_they_dont_teach(client, db_session):
    """The scoping fix this endpoint needed: list_exams's teacher_class_subjects
    filter would hide a subject the homeroom teacher doesn't personally teach —
    _ensure_class_view_access is used here instead, same as class detail/roster."""
    klass = make_class(db_session)
    subject = make_subject(db_session, name="Kimyo")
    homeroom = make_teacher(db_session, username="daily_homeroom")
    klass.homeroom_teacher_id = homeroom.id
    student = make_student(db_session, klass, username="daily_homeroom_student")
    db_session.commit()

    _, day_start, _ = local_day_bounds_utc()
    _make_scored_exam(db_session, klass, subject, student, end_at=day_start + timedelta(hours=6))

    token = _login(client, "daily_homeroom")
    resp = client.get(f"/api/v1/admin/classes/{klass.id}/daily-results", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()["exams"]) == 1


def test_unconnected_teacher_forbidden(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    unconnected = make_teacher(db_session, username="daily_unconnected")
    student = make_student(db_session, klass, username="daily_unconnected_student")
    db_session.commit()

    _, day_start, _ = local_day_bounds_utc()
    _make_scored_exam(db_session, klass, subject, student, end_at=day_start + timedelta(hours=6))

    token = _login(client, "daily_unconnected")
    resp = client.get(f"/api/v1/admin/classes/{klass.id}/daily-results", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_explicit_date_param_overrides_default_today(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    make_admin(db_session, username="daily_date_admin")
    student = make_student(db_session, klass, username="daily_date_student")
    db_session.commit()

    resolved_today, day_start, _ = local_day_bounds_utc()
    yesterday_str, y_start, _ = local_day_bounds_utc((day_start - timedelta(days=1)).strftime("%Y-%m-%d"))
    exam = _make_scored_exam(db_session, klass, subject, student, end_at=y_start + timedelta(hours=6))

    token = _login(client, "daily_date_admin")
    headers = {"Authorization": f"Bearer {token}"}

    empty_today = client.get(f"/api/v1/admin/classes/{klass.id}/daily-results", headers=headers)
    assert empty_today.json()["date"] == resolved_today
    assert empty_today.json()["exams"] == []

    with_date = client.get(
        f"/api/v1/admin/classes/{klass.id}/daily-results?date={yesterday_str}", headers=headers
    )
    assert with_date.json()["date"] == yesterday_str
    assert len(with_date.json()["exams"]) == 1
    assert with_date.json()["exams"][0]["exam_id"] == exam.id
