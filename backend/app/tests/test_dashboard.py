"""GET /admin/dashboard — the staff dashboard's one aggregate call (replaces
downloading every class/subject/student/teacher list, then each live exam's
roster in a second wave)."""

from datetime import datetime, timedelta, timezone

from app.models.attempt import AttemptStatus, ExamAttempt
from app.models.exam import ExamStatus
from app.models.user import TeacherClassSubject
from app.tests.factories import make_admin, make_class, make_exam, make_student, make_subject, make_teacher
from app.tests.test_query_counts import count_queries


def _login(client, username, password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _live_exam(db, klass, subject):
    now = datetime.now(timezone.utc)
    return make_exam(
        db, klass, subject, status=ExamStatus.scheduled, start_at=now - timedelta(minutes=10), end_at=now + timedelta(hours=1)
    )


def test_admin_dashboard_counts_and_live_progress(client, db_session):
    klass = make_class(db_session)
    other = make_class(db_session)
    subject = make_subject(db_session)
    make_admin(db_session, username="dash_admin")
    make_teacher(db_session, username="dash_teacher")
    students = [make_student(db_session, klass, username=f"dash_s{i}") for i in range(4)]
    make_student(db_session, other, username="dash_other")
    exam = _live_exam(db_session, klass, subject)
    now = datetime.now(timezone.utc)
    db_session.add(ExamAttempt(exam_id=exam.id, student_id=students[0].id, status=AttemptStatus.submitted, submitted_at=now))
    db_session.add(ExamAttempt(exam_id=exam.id, student_id=students[1].id, status=AttemptStatus.in_progress, started_at=now))
    db_session.commit()

    body = client.get("/api/v1/admin/dashboard", headers=_login(client, "dash_admin")).json()

    assert body["counts"] == {"classes": 2, "subjects": 1, "students": 5, "teachers": 1}
    assert {c["count"] for c in body["students_per_class"]} == {4, 1}
    assert len(body["live"]) == 1
    live = body["live"][0]
    assert (live["total"], live["submitted"], live["in_progress"], live["not_started"]) == (4, 1, 1, 2)


def test_closed_and_future_exams_are_not_live(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    make_admin(db_session, username="dash_admin2")
    now = datetime.now(timezone.utc)
    make_exam(db_session, klass, subject, status=ExamStatus.scheduled, start_at=now - timedelta(hours=3), end_at=now - timedelta(hours=1))
    make_exam(db_session, klass, subject, status=ExamStatus.scheduled, start_at=now + timedelta(hours=1), end_at=now + timedelta(hours=2))
    make_exam(db_session, klass, subject, status=ExamStatus.draft, start_at=now - timedelta(minutes=5), end_at=now + timedelta(hours=1))
    db_session.commit()

    body = client.get("/api/v1/admin/dashboard", headers=_login(client, "dash_admin2")).json()
    assert body["live"] == []


def test_teacher_dashboard_is_scoped_and_hides_school_wide_numbers(client, db_session):
    klass = make_class(db_session)
    other = make_class(db_session)
    subject = make_subject(db_session)
    teacher = make_teacher(db_session, username="dash_teacher2")
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id))
    mine = _live_exam(db_session, klass, subject)
    _live_exam(db_session, other, subject)
    db_session.commit()

    body = client.get("/api/v1/admin/dashboard", headers=_login(client, "dash_teacher2")).json()

    assert [e["exam_id"] for e in body["live"]] == [mine.id]
    assert body["counts"] is None
    assert body["students_per_class"] is None


def test_students_cannot_open_the_dashboard(client, db_session):
    klass = make_class(db_session)
    make_student(db_session, klass, username="dash_student")
    db_session.commit()
    resp = client.post("/api/v1/auth/login", json={"username": "dash_student", "password": "secret123", "class_id": klass.id})
    token = resp.json()["access_token"]
    assert client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_dashboard_query_count_does_not_grow_with_school_size(client, db_session):
    subject = make_subject(db_session)
    make_admin(db_session, username="dash_admin3")
    db_session.commit()
    headers = _login(client, "dash_admin3")

    def grow(n, tag):
        for i in range(n):
            klass = make_class(db_session, label=f"{tag}{i}")
            make_student(db_session, klass, username=f"dash_q_{tag}{i}")
            _live_exam(db_session, klass, subject)

    grow(2, "S")
    with count_queries(db_session) as small:
        assert client.get("/api/v1/admin/dashboard", headers=headers).status_code == 200
    grow(12, "B")
    with count_queries(db_session) as big:
        assert len(client.get("/api/v1/admin/dashboard", headers=headers).json()["live"]) == 14
    assert len(big) <= len(small), f"{len(small)} vs {len(big)}"
