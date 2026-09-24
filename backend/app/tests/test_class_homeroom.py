"""Covers the "sinf rahbari" (homeroom teacher) feature: a class can have
one teacher assigned who gets read/write access to that class's own
detail page and student roster, without being able to touch any other
class — everyone else (a subject teacher with no homeroom, or a teacher
with no connection to the class at all) is scoped to read-only or nothing.
"""

from app.models.user import TeacherClassSubject
from app.tests.factories import make_admin, make_class, make_student, make_subject, make_teacher


def _login(client, username, password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_class_detail_visible_to_admin_and_homeroom_teacher_not_to_strangers(client, db_session):
    klass = make_class(db_session)
    homeroom = make_teacher(db_session, username="homeroom_t")
    stranger = make_teacher(db_session, username="stranger_t")
    klass.homeroom_teacher_id = homeroom.id
    make_admin(db_session, username="admin_class_detail")
    db_session.commit()

    admin_token = _login(client, "admin_class_detail")
    homeroom_token = _login(client, "homeroom_t")
    stranger_token = _login(client, "stranger_t")

    admin_resp = client.get(f"/api/v1/admin/classes/{klass.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_resp.status_code == 200
    assert admin_resp.json()["can_manage_students"] is True

    homeroom_resp = client.get(
        f"/api/v1/admin/classes/{klass.id}", headers={"Authorization": f"Bearer {homeroom_token}"}
    )
    assert homeroom_resp.status_code == 200
    assert homeroom_resp.json()["can_manage_students"] is True
    assert homeroom_resp.json()["homeroom_teacher_name"] == "Ustoz"

    stranger_resp = client.get(
        f"/api/v1/admin/classes/{klass.id}", headers={"Authorization": f"Bearer {stranger_token}"}
    )
    assert stranger_resp.status_code == 403


def test_class_detail_view_only_for_subject_teacher_without_homeroom(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    teacher = make_teacher(db_session, subject=subject, username="subject_only_t")
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id))
    db_session.commit()
    token = _login(client, "subject_only_t")

    resp = client.get(f"/api/v1/admin/classes/{klass.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["can_manage_students"] is False


def test_subject_teacher_without_homeroom_can_view_but_not_mutate_roster(client, db_session):
    """A teacher who just teaches a subject in this class (not homeroom)
    can now see the student list read-only — they used to get only a
    student count with no names, per a follow-up user request."""
    own_class = make_class(db_session)
    other_class = make_class(db_session)
    subject = make_subject(db_session)
    teacher = make_teacher(db_session, subject=subject, username="viewer_t")
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=own_class.id, subject_id=subject.id))
    make_student(db_session, own_class, username="viewed_student", full_name="Ko'rinadigan Talaba")
    make_student(db_session, other_class, username="hidden_student")
    db_session.commit()
    token = _login(client, "viewer_t")
    headers = {"Authorization": f"Bearer {token}"}

    list_own = client.get(f"/api/v1/admin/students?class_id={own_class.id}", headers=headers)
    assert list_own.status_code == 200
    assert len(list_own.json()) == 1
    assert list_own.json()[0]["full_name"] == "Ko'rinadigan Talaba"

    # still can't see a class they have no connection to at all
    list_other = client.get(f"/api/v1/admin/students?class_id={other_class.id}", headers=headers)
    assert list_other.status_code == 403

    # and still can't mutate the roster of the class they *can* view
    create_resp = client.post(
        "/api/v1/admin/students",
        json={
            "username": "sneaky.viewer.student",
            "password": "secret123",
            "full_name": "Sneaky",
            "class_id": own_class.id,
            "student_code": "VT-001",
        },
        headers=headers,
    )
    assert create_resp.status_code == 403


def test_admin_can_assign_and_unassign_homeroom_teacher(client, db_session):
    klass = make_class(db_session)
    teacher = make_teacher(db_session, username="assignable_t")
    make_admin(db_session, username="admin_assign_homeroom")
    db_session.commit()
    token = _login(client, "admin_assign_homeroom")
    headers = {"Authorization": f"Bearer {token}"}

    set_resp = client.put(
        f"/api/v1/admin/classes/{klass.id}", json={"homeroom_teacher_id": teacher.id}, headers=headers
    )
    assert set_resp.status_code == 200
    assert set_resp.json()["homeroom_teacher_id"] == teacher.id
    assert set_resp.json()["homeroom_teacher_name"] == "Ustoz"

    unset_resp = client.put(
        f"/api/v1/admin/classes/{klass.id}", json={"homeroom_teacher_id": None}, headers=headers
    )
    assert unset_resp.status_code == 200
    assert unset_resp.json()["homeroom_teacher_id"] is None


def test_teacher_cannot_assign_homeroom_teacher(client, db_session):
    klass = make_class(db_session)
    teacher = make_teacher(db_session, username="cant_assign_t")
    db_session.commit()
    token = _login(client, "cant_assign_t")

    resp = client.put(
        f"/api/v1/admin/classes/{klass.id}",
        json={"homeroom_teacher_id": teacher.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_homeroom_teacher_can_manage_own_class_students_only(client, db_session):
    own_class = make_class(db_session)
    other_class = make_class(db_session)
    homeroom = make_teacher(db_session, username="homeroom_manage_t")
    own_class.homeroom_teacher_id = homeroom.id
    make_student(db_session, other_class, username="other_class_student")
    db_session.commit()
    token = _login(client, "homeroom_manage_t")
    headers = {"Authorization": f"Bearer {token}"}

    # can list own (empty) class roster
    list_own = client.get(f"/api/v1/admin/students?class_id={own_class.id}", headers=headers)
    assert list_own.status_code == 200
    assert list_own.json() == []

    # cannot list a class that isn't theirs
    list_other = client.get(f"/api/v1/admin/students?class_id={other_class.id}", headers=headers)
    assert list_other.status_code == 403

    # can create a student in their own class
    create_resp = client.post(
        "/api/v1/admin/students",
        json={
            "username": "new.homeroom.student",
            "password": "secret123",
            "full_name": "Yangi Talaba",
            "class_id": own_class.id,
            "student_code": "HR-001",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    student_id = create_resp.json()["id"]

    # cannot create a student in a class that isn't theirs
    create_other = client.post(
        "/api/v1/admin/students",
        json={
            "username": "sneaky.student",
            "password": "secret123",
            "full_name": "Sneaky",
            "class_id": other_class.id,
            "student_code": "HR-002",
        },
        headers=headers,
    )
    assert create_other.status_code == 403

    # can edit name/active status of their own student
    edit_resp = client.put(
        f"/api/v1/admin/students/{student_id}", json={"is_active": False}, headers=headers
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["is_active"] is False

    # cannot move a student to a different class themselves
    move_resp = client.put(
        f"/api/v1/admin/students/{student_id}", json={"class_id": other_class.id}, headers=headers
    )
    assert move_resp.status_code == 403

    # bulk-import into their own class works
    bulk_resp = client.post(
        "/api/v1/admin/students/bulk-import",
        json={"class_id": own_class.id, "full_names": ["Yana Bir Talaba"]},
        headers=headers,
    )
    assert bulk_resp.status_code == 200
    assert len(bulk_resp.json()["created"]) == 1

    # bulk-import into a class that isn't theirs is rejected
    bulk_other = client.post(
        "/api/v1/admin/students/bulk-import",
        json={"class_id": other_class.id, "full_names": ["Should Not Work"]},
        headers=headers,
    )
    assert bulk_other.status_code == 403

    # password reset for their own class works
    reset_resp = client.post(
        f"/api/v1/admin/classes/{own_class.id}/reset-password",
        json={"new_password": "homeroom2026"},
        headers=headers,
    )
    assert reset_resp.status_code == 200

    # password reset for a class that isn't theirs is rejected
    reset_other = client.post(
        f"/api/v1/admin/classes/{other_class.id}/reset-password",
        json={"new_password": "homeroom2026"},
        headers=headers,
    )
    assert reset_other.status_code == 403


def test_teacher_without_homeroom_gets_empty_student_list_by_default(client, db_session):
    make_teacher(db_session, username="no_homeroom_t")
    db_session.commit()
    token = _login(client, "no_homeroom_t")

    resp = client.get("/api/v1/admin/students", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_me_endpoint_reports_homeroom_class_ids(client, db_session):
    klass = make_class(db_session)
    homeroom = make_teacher(db_session, username="me_homeroom_t")
    klass.homeroom_teacher_id = homeroom.id
    db_session.commit()
    token = _login(client, "me_homeroom_t")

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["homeroom_class_ids"] == [klass.id]
