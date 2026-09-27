"""Covers GET /admin/classes/{id}/daily-results — backs the "sinf raxbari"
end-of-day Telegram share (post-launch roadmap item #2): once today's
exams for a class have finished, the homeroom teacher downloads a
combined image of the day's results and shares it themselves via their
own Telegram (no bot integration, by explicit user request). Only the
data endpoint is covered here; the image export itself is a pure
client-side html2canvas render of what this endpoint returns.

The response shape is one combined table (one row per student, one column
per exam that day, plus a total) rather than one ranking table per exam —
the user explicitly asked for this after a class routinely takes several
exams (different subjects) on the same day and wanted "who did best across
the whole day", not several separate leaderboards to cross-reference.

Which exams count as "today's" is keyed off ExamAttempt.submitted_at, not
Exam.end_at — a real production bug: this school's exam windows are
routinely multi-day (end_at days after students actually took it), so the
original end_at-based filter silently returned nothing for almost every
real exam. These tests backdate/forward-date each attempt's submitted_at
directly (not the exam's end_at) to control which calendar day it lands in.
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


def _make_scored_exam(db_session, klass, subject, student, submitted_at, correct_count=3, total_count=4):
    """Single-student convenience wrapper around _make_multi_scored_exam
    (see below) — kept for the tests that only need one student's score."""
    return _make_multi_scored_exam(db_session, klass, subject, [(student, correct_count)], submitted_at, total_count)


def _make_multi_scored_exam(db_session, klass, subject, student_scores, submitted_at, total_count=4):
    """Creates, publishes, and takes the exam for every (student,
    correct_count) pair through the real window-currently-open window
    (start_attempt/submit_attempt both check against the actual clock —
    the exam's own start_at/end_at stay real and open, never touched
    afterward, since the daily-results query no longer looks at end_at at
    all). Each resulting attempt's submitted_at is then backdated/forward-
    dated directly, purely to control which calendar day the daily-results
    query buckets it into, without touching the already-computed
    ExamRanking rows."""
    now = datetime.now(timezone.utc)
    exam = make_exam(
        db_session, klass, subject, duration_minutes=30, start_at=now - timedelta(hours=1), end_at=now + timedelta(hours=2)
    )
    for i in range(total_count):
        add_mcq_question(db_session, exam, correct_index=0, order_index=i, points=1)
    db_session.commit()
    publish_exam(db_session, exam)

    for student, correct_count in student_scores:
        attempt = attempt_service.start_attempt(db_session, exam, student)
        for i, q in enumerate(exam.questions):
            chosen = q.options[0] if i < correct_count else q.options[1]
            attempt_service.record_answer(db_session, attempt, q.id, chosen.id, None)
        attempt_service.submit_attempt(db_session, attempt.id)
        attempt.submitted_at = submitted_at
    db_session.commit()
    return exam


def test_admin_sees_only_todays_exams(client, db_session):
    klass = make_class(db_session)
    math = make_subject(db_session, name="Matematika")
    physics = make_subject(db_session, name="Fizika")
    make_admin(db_session, username="daily_admin")
    student = make_student(db_session, klass, username="daily_student")
    db_session.commit()

    _, day_start, _ = local_day_bounds_utc()
    today_moment = day_start + timedelta(hours=6)  # safely inside today's local window
    yesterday_moment = day_start - timedelta(hours=1)  # falls in the previous local day

    todays_exam = _make_scored_exam(db_session, klass, math, student, submitted_at=today_moment, correct_count=3)
    _make_scored_exam(db_session, klass, physics, student, submitted_at=yesterday_moment, correct_count=1)

    token = _login(client, "daily_admin")
    resp = client.get(f"/api/v1/admin/classes/{klass.id}/daily-results", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["exams"]) == 1
    assert body["exams"][0]["exam_id"] == todays_exam.id
    assert body["exams"][0]["subject_name"] == "Matematika"
    assert body["students"][0]["full_name"] == student.user.full_name
    assert body["students"][0]["scores"] == [3.0]
    assert body["students"][0]["total"] == 3.0


def test_exam_with_a_multi_day_window_still_counts_as_todays_if_submitted_today(client, db_session):
    """The exact production bug: a real exam's end_at can be days after
    students actually took it (multi-day windows are the norm here, not
    a single sitting) — that must never hide it from "today's" results as
    long as the submission itself happened today."""
    klass = make_class(db_session)
    subject = make_subject(db_session)
    make_admin(db_session, username="multiday_admin")
    student = make_student(db_session, klass, username="multiday_student")
    db_session.commit()

    now = datetime.now(timezone.utc)
    exam = make_exam(
        db_session, klass, subject, duration_minutes=30, start_at=now - timedelta(hours=1), end_at=now + timedelta(days=5)
    )
    add_mcq_question(db_session, exam, correct_index=0, points=1)
    db_session.commit()
    publish_exam(db_session, exam)

    attempt = attempt_service.start_attempt(db_session, exam, student)
    attempt_service.record_answer(db_session, attempt, exam.questions[0].id, exam.questions[0].options[0].id, None)
    attempt_service.submit_attempt(db_session, attempt.id)
    # submitted_at defaults to "now" (today) from submit_attempt itself —
    # left untouched here, unlike every other test in this file, to prove
    # the far-future end_at (5 days out) doesn't matter at all.
    db_session.refresh(exam)
    assert exam.end_at > now + timedelta(days=4)  # sanity-check the multi-day window is really set up

    token = _login(client, "multiday_admin")
    resp = client.get(f"/api/v1/admin/classes/{klass.id}/daily-results", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["exams"]) == 1
    assert body["exams"][0]["exam_id"] == exam.id


def test_combines_several_same_day_exams_into_one_ranked_table(client, db_session):
    """The core of this feature: a class takes more than one exam (subject)
    on the same day, and the response is one table — one row per student,
    one score per exam in the same order as `exams`, plus a summed total —
    ranked by that total, not by any single exam."""
    klass = make_class(db_session)
    math = make_subject(db_session, name="Matematika")
    physics = make_subject(db_session, name="Fizika")
    make_admin(db_session, username="daily_combo_admin")
    # explicit full_name: make_student defaults every student to "Talaba",
    # which would collide once both rows are keyed by name below.
    top_student = make_student(db_session, klass, username="daily_combo_top", full_name="Combo Top")
    partial_student = make_student(db_session, klass, username="daily_combo_partial", full_name="Combo Partial")
    db_session.commit()

    _, day_start, _ = local_day_bounds_utc()
    math_moment = day_start + timedelta(hours=4)
    physics_moment = day_start + timedelta(hours=8)

    math_exam = _make_scored_exam(db_session, klass, math, top_student, submitted_at=math_moment, correct_count=4)
    # partial_student only takes the physics exam — should still show up,
    # with a null (not zero) slot for the math exam they never took.
    physics_exam = _make_multi_scored_exam(
        db_session, klass, physics, [(top_student, 2), (partial_student, 4)], submitted_at=physics_moment
    )

    token = _login(client, "daily_combo_admin")
    resp = client.get(f"/api/v1/admin/classes/{klass.id}/daily-results", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()

    assert {e["exam_id"] for e in body["exams"]} == {math_exam.id, physics_exam.id}

    by_student_id_row = {row["student_id"]: row for row in body["students"]}
    top_row = by_student_id_row[top_student.id]
    assert top_row["full_name"] == "Combo Top"
    assert set(top_row["scores"]) == {4.0, 2.0}
    assert top_row["total"] == 6.0
    assert top_row["rank"] == 1

    partial_row = by_student_id_row[partial_student.id]
    assert partial_row["full_name"] == "Combo Partial"
    assert None in partial_row["scores"]
    assert 4.0 in partial_row["scores"]
    assert partial_row["total"] == 4.0
    assert partial_row["rank"] == 2


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
    _make_scored_exam(db_session, klass, subject, student, submitted_at=day_start + timedelta(hours=6))

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
    _make_scored_exam(db_session, klass, subject, student, submitted_at=day_start + timedelta(hours=6))

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
    exam = _make_scored_exam(db_session, klass, subject, student, submitted_at=y_start + timedelta(hours=6))

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
