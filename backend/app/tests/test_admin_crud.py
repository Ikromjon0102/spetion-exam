"""Covers the edit/delete side of admin management for classes, subjects,
students and teachers — added after the user asked for full CRUD ("edit va
delete") on every entity in the admin panel. The common theme in every
delete endpoint: block with 409 when real data (exam history, attempts,
active assignments) depends on the row, but silently clean up harmless
join-table/label references rather than making the admin do that by hand.
"""

from app.models.attempt import AttemptStatus, ExamAttempt
from app.models.user import Teacher, TeacherClassSubject
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


def _admin_headers(client, db_session, username="crud_admin"):
    make_admin(db_session, username=username)
    db_session.commit()
    return {"Authorization": f"Bearer {_login(client, username)}"}


def test_update_subject_name_and_code(client, db_session):
    subject = make_subject(db_session, name="Kimyo")
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.put(f"/api/v1/admin/subjects/{subject.id}", json={"code": "KIM"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Kimyo"
    assert resp.json()["code"] == "KIM"


def test_update_subject_rejects_duplicate_name(client, db_session):
    make_subject(db_session, name="Fizika")
    subject2 = make_subject(db_session, name="Biologiya")
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.put(f"/api/v1/admin/subjects/{subject2.id}", json={"name": "Fizika"}, headers=headers)
    assert resp.status_code == 409


def test_delete_subject_blocked_by_exam(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    make_exam(db_session, klass, subject)
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.delete(f"/api/v1/admin/subjects/{subject.id}", headers=headers)
    assert resp.status_code == 409


def test_delete_subject_blocked_by_assignment_but_clears_main_subject_label(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    teacher = make_teacher(db_session, subject=subject)
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id))
    db_session.commit()
    headers = _admin_headers(client, db_session)

    blocked = client.delete(f"/api/v1/admin/subjects/{subject.id}", headers=headers)
    assert blocked.status_code == 409

    db_session.query(TeacherClassSubject).filter_by(subject_id=subject.id).delete()
    db_session.commit()

    ok = client.delete(f"/api/v1/admin/subjects/{subject.id}", headers=headers)
    assert ok.status_code == 204
    db_session.refresh(teacher)
    assert teacher.subject_id is None


def test_delete_class_blocked_by_students_then_succeeds_once_empty(client, db_session):
    klass = make_class(db_session)
    student = make_student(db_session, klass)
    db_session.commit()
    headers = _admin_headers(client, db_session)

    blocked = client.delete(f"/api/v1/admin/classes/{klass.id}", headers=headers)
    assert blocked.status_code == 409

    db_session.delete(student.user)
    db_session.delete(student)
    db_session.commit()

    ok = client.delete(f"/api/v1/admin/classes/{klass.id}", headers=headers)
    assert ok.status_code == 204


def test_delete_class_removes_teacher_assignments(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    teacher = make_teacher(db_session, subject=subject)
    link = TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id)
    db_session.add(link)
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.delete(f"/api/v1/admin/classes/{klass.id}", headers=headers)
    assert resp.status_code == 204
    assert db_session.query(TeacherClassSubject).filter_by(teacher_id=teacher.id).first() is None


def test_delete_class_blocked_by_exam(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    make_exam(db_session, klass, subject)
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.delete(f"/api/v1/admin/classes/{klass.id}", headers=headers)
    assert resp.status_code == 409


def test_delete_student_blocked_by_attempt_then_succeeds_without_one(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    student_with_attempt = make_student(db_session, klass, username="attempted_student")
    student_without = make_student(db_session, klass, username="fresh_student")
    db_session.add(
        ExamAttempt(exam_id=exam.id, student_id=student_with_attempt.id, status=AttemptStatus.in_progress)
    )
    db_session.commit()
    headers = _admin_headers(client, db_session)

    blocked = client.delete(f"/api/v1/admin/students/{student_with_attempt.id}", headers=headers)
    assert blocked.status_code == 409

    ok = client.delete(f"/api/v1/admin/students/{student_without.id}", headers=headers)
    assert ok.status_code == 204


def test_homeroom_teacher_can_delete_own_class_student_not_other_class(client, db_session):
    own_class = make_class(db_session)
    other_class = make_class(db_session)
    homeroom = make_teacher(db_session, username="delete_homeroom_t")
    own_class.homeroom_teacher_id = homeroom.id
    own_student = make_student(db_session, own_class, username="own_del_student")
    other_student = make_student(db_session, other_class, username="other_del_student")
    db_session.commit()
    token = _login(client, "delete_homeroom_t")
    headers = {"Authorization": f"Bearer {token}"}

    forbidden = client.delete(f"/api/v1/admin/students/{other_student.id}", headers=headers)
    assert forbidden.status_code == 403

    ok = client.delete(f"/api/v1/admin/students/{own_student.id}", headers=headers)
    assert ok.status_code == 204


def test_update_teacher_full_name(client, db_session):
    teacher = make_teacher(db_session)
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.put(f"/api/v1/admin/teachers/{teacher.id}", json={"full_name": "Yangi Ism"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Yangi Ism"


def test_delete_teacher_blocked_by_created_exam(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    teacher = make_teacher(db_session, subject=subject)
    make_exam(db_session, klass, subject, created_by=teacher.user)
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.delete(f"/api/v1/admin/teachers/{teacher.id}", headers=headers)
    assert resp.status_code == 409


def test_delete_teacher_clears_assignments_and_homeroom(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    teacher = make_teacher(db_session, subject=subject)
    klass.homeroom_teacher_id = teacher.id
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id))
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.delete(f"/api/v1/admin/teachers/{teacher.id}", headers=headers)
    assert resp.status_code == 204
    assert db_session.get(Teacher, teacher.id) is None
    db_session.refresh(klass)
    assert klass.homeroom_teacher_id is None
    assert db_session.query(TeacherClassSubject).filter_by(teacher_id=teacher.id).first() is None
