"""Covers GET /admin/students/{id}/performance — the backend for the new
"past/yaxshi o'zlashtirish" (low/high performer) view requested after the
first school-leadership demo. This endpoint existed since early on
(StudentSubjectStats already tracked per-subject averages/trends for the
student's own profile) but was never actually reachable from any admin/
teacher UI until now, and had never been access-scoped — this locks that
down to the same view-access rule used everywhere else (admin unrestricted,
teacher only for a class they're connected to).
"""

from datetime import datetime, timedelta, timezone

from app.models.user import TeacherClassSubject
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


def _score_exam(db_session, klass, subject, student, correct_count, total_count):
    start = datetime.now(timezone.utc)
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=start, end_at=start + timedelta(hours=2))
    for i in range(total_count):
        add_mcq_question(db_session, exam, correct_index=0, order_index=i, points=1)
    db_session.commit()
    publish_exam(db_session, exam)

    attempt = attempt_service.start_attempt(db_session, exam, student)
    for i, q in enumerate(exam.questions):
        chosen = q.options[0] if i < correct_count else q.options[1]
        attempt_service.record_answer(db_session, attempt, q.id, chosen.id, None)
    attempt_service.submit_attempt(db_session, attempt.id)


def test_admin_sees_weak_and_strong_subjects_for_any_student(client, db_session):
    klass = make_class(db_session)
    weak_subject = make_subject(db_session, name="Matematika")
    strong_subject = make_subject(db_session, name="Adabiyot")
    make_admin(db_session, username="perf_admin")
    student = make_student(db_session, klass, username="perf_student")
    db_session.commit()

    _score_exam(db_session, klass, weak_subject, student, correct_count=1, total_count=4)  # 25%
    _score_exam(db_session, klass, strong_subject, student, correct_count=4, total_count=4)  # 100%

    token = _login(client, "perf_admin")
    resp = client.get(f"/api/v1/admin/students/{student.id}/performance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    by_name = {s["subject_name"]: s for s in body["subjects"]}
    assert by_name["Matematika"]["average_percent"] == 25.0
    assert by_name["Adabiyot"]["average_percent"] == 100.0


def test_connected_teacher_can_view_but_unconnected_teacher_cannot(client, db_session):
    own_class = make_class(db_session)
    other_class = make_class(db_session)
    subject = make_subject(db_session)
    connected_teacher = make_teacher(db_session, subject=subject, username="perf_connected_teacher")
    db_session.add(
        TeacherClassSubject(teacher_id=connected_teacher.id, class_id=own_class.id, subject_id=subject.id)
    )
    unconnected_teacher = make_teacher(db_session, username="perf_unconnected_teacher")
    student = make_student(db_session, own_class, username="perf_scoped_student")
    make_student(db_session, other_class, username="perf_other_class_student")
    db_session.commit()

    _score_exam(db_session, own_class, subject, student, correct_count=2, total_count=4)

    connected_token = _login(client, "perf_connected_teacher")
    ok = client.get(
        f"/api/v1/admin/students/{student.id}/performance",
        headers={"Authorization": f"Bearer {connected_token}"},
    )
    assert ok.status_code == 200

    unconnected_token = _login(client, "perf_unconnected_teacher")
    forbidden = client.get(
        f"/api/v1/admin/students/{student.id}/performance",
        headers={"Authorization": f"Bearer {unconnected_token}"},
    )
    assert forbidden.status_code == 403
