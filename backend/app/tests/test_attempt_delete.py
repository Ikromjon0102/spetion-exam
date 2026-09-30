"""Covers DELETE /admin/exams/{id}/attempts/{student_id} (admin-only —
requested explicitly after a staff member's own test exam attempt left
stale data behind when it was cleaned up with a raw DB delete instead of
going through the app): removing an attempt must also unwind its
contribution to ExamRanking/StudentSubjectStats (ranking_service.
remove_attempt), not just delete the row, or a student who's had their
only attempt removed keeps showing an old score/rank forever. Also covers
the same admin-only override on DELETE /admin/exams/{id} (force-delete an
exam even if students already attempted it) and excluding deactivated
students from compute_overall_ranking.
"""

from datetime import datetime, timedelta, timezone

from app.models.ranking import StudentSubjectStats
from app.services import attempt_service, ranking_service
from app.services.exam_service import publish_exam
from app.tests.factories import add_mcq_question, make_admin, make_class, make_exam, make_student, make_subject, make_teacher


def _login(client, username, password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _make_scored_exam(db, klass, subject, n_questions=4):
    start = datetime.now(timezone.utc)
    exam = make_exam(db, klass, subject, duration_minutes=30, start_at=start, end_at=start + timedelta(hours=2))
    for i in range(n_questions):
        add_mcq_question(db, exam, correct_index=0, order_index=i, points=1)
    db.commit()
    publish_exam(db, exam)
    return exam


def _take_and_score(db, exam, student, correct_count, total_count=4):
    attempt = attempt_service.start_attempt(db, exam, student)
    for i, q in enumerate(exam.questions[:total_count]):
        chosen = q.options[0] if i < correct_count else q.options[1]
        attempt_service.record_answer(db, attempt, q.id, chosen.id, None)
    attempt_service.submit_attempt(db, attempt.id)
    return attempt


def test_remove_attempt_deletes_stats_row_when_it_was_the_only_attempt(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    student = make_student(db_session, klass)
    db_session.commit()
    exam = _make_scored_exam(db_session, klass, subject)
    _take_and_score(db_session, exam, student, correct_count=4)

    stats = db_session.query(StudentSubjectStats).filter_by(student_id=student.id, subject_id=subject.id).first()
    assert stats is not None and stats.total_points_possible == 4

    removed = ranking_service.remove_attempt(db_session, exam.id, student.id)
    assert removed is True

    stats_after = db_session.query(StudentSubjectStats).filter_by(student_id=student.id, subject_id=subject.id).first()
    assert stats_after is None


def test_remove_attempt_returns_false_when_nothing_to_remove(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    student = make_student(db_session, klass)
    db_session.commit()
    exam = _make_scored_exam(db_session, klass, subject)

    assert ranking_service.remove_attempt(db_session, exam.id, student.id) is False


def test_delete_attempt_endpoint_is_admin_only(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    teacher = make_teacher(db_session, subject=subject)
    make_admin(db_session, username="attempt_delete_admin")
    student = make_student(db_session, klass)
    db_session.commit()
    exam = _make_scored_exam(db_session, klass, subject)
    _take_and_score(db_session, exam, student, correct_count=4)

    teacher_token = _login(client, teacher.user.username)
    resp = client.delete(
        f"/api/v1/admin/exams/{exam.id}/attempts/{student.id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 403

    admin_token = _login(client, "attempt_delete_admin")
    resp = client.delete(
        f"/api/v1/admin/exams/{exam.id}/attempts/{student.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204

    resp = client.delete(
        f"/api/v1/admin/exams/{exam.id}/attempts/{student.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


def test_admin_can_force_delete_exam_with_real_attempts(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    make_admin(db_session, username="force_delete_admin")
    student = make_student(db_session, klass)
    db_session.commit()
    exam = _make_scored_exam(db_session, klass, subject)
    _take_and_score(db_session, exam, student, correct_count=4)

    token = _login(client, "force_delete_admin")
    resp = client.delete(f"/api/v1/admin/exams/{exam.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204

    stats = db_session.query(StudentSubjectStats).filter_by(student_id=student.id, subject_id=subject.id).first()
    assert stats is None


def test_teacher_still_blocked_from_deleting_exam_with_attempts(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    teacher = make_teacher(db_session, subject=subject)
    from app.models.user import TeacherClassSubject

    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id))
    student = make_student(db_session, klass)
    db_session.commit()
    exam = _make_scored_exam(db_session, klass, subject)
    _take_and_score(db_session, exam, student, correct_count=4)

    token = _login(client, teacher.user.username)
    resp = client.delete(f"/api/v1/admin/exams/{exam.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409


def test_overall_ranking_excludes_deactivated_students(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    active_student = make_student(db_session, klass, username="ranking_active", full_name="Active One")
    inactive_student = make_student(db_session, klass, username="ranking_inactive", full_name="Inactive One")
    db_session.commit()
    exam = _make_scored_exam(db_session, klass, subject)
    _take_and_score(db_session, exam, active_student, correct_count=4)
    _take_and_score(db_session, exam, inactive_student, correct_count=2)

    inactive_student.user.is_active = False
    db_session.commit()

    rows = ranking_service.compute_overall_ranking(db_session, class_id=klass.id)
    student_ids = {r["student_id"] for r in rows}
    assert active_student.id in student_ids
    assert inactive_student.id not in student_ids
