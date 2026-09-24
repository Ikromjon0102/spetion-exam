"""Covers the admin management panel's backend surface: creating a class
without the caller having to know school_id/academic_year_id (v1 is
single-tenant — the backend resolves/creates that context itself), editing
a student, and the teacher <-> class/subject assignment CRUD used by the
"reassign a teacher" flow.
"""

from app.tests.factories import make_admin, make_class, make_student, make_subject, make_teacher
from app.models.org import AcademicYear, School


def _login(client, username, password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_create_class_auto_resolves_school_and_year(client, db_session):
    make_admin(db_session, username="admin_class_test")
    db_session.commit()
    token = _login(client, "admin_class_test")

    resp = client.post(
        "/api/v1/admin/classes",
        json={"grade_level": 6, "label": "A", "display_name": "6-A"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["display_name"] == "6-A"

    # a second class create call reuses the same school/year context rather
    # than creating a duplicate school or academic year each time
    resp2 = client.post(
        "/api/v1/admin/classes",
        json={"grade_level": 6, "label": "B", "display_name": "6-B"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 201
    assert db_session.query(School).count() == 1
    assert db_session.query(AcademicYear).count() == 1


def test_create_class_duplicate_rejected(client, db_session):
    make_admin(db_session, username="admin_class_dup")
    db_session.commit()
    token = _login(client, "admin_class_dup")

    body = {"grade_level": 7, "label": "A", "display_name": "7-A"}
    first = client.post("/api/v1/admin/classes", json=body, headers={"Authorization": f"Bearer {token}"})
    assert first.status_code == 201
    second = client.post("/api/v1/admin/classes", json=body, headers={"Authorization": f"Bearer {token}"})
    assert second.status_code == 409


def test_update_student_class_and_active_status(client, db_session):
    klass_a = make_class(db_session)
    klass_b = make_class(db_session)
    student = make_student(db_session, klass_a, username="student_edit_test")
    make_admin(db_session, username="admin_student_edit")
    db_session.commit()
    token = _login(client, "admin_student_edit")

    resp = client.put(
        f"/api/v1/admin/students/{student.id}",
        json={"class_id": klass_b.id, "is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["class_id"] == klass_b.id
    assert body["class_name"] == klass_b.display_name
    assert body["is_active"] is False


def test_bulk_import_students_generates_unique_usernames_and_codes(client, db_session):
    klass = make_class(db_session)
    make_student(db_session, klass, username="ali.valiyev", full_name="Ali Valiyev")
    make_admin(db_session, username="admin_bulk_import")
    db_session.commit()
    token = _login(client, "admin_bulk_import")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/admin/students/bulk-import",
        json={
            "class_id": klass.id,
            # a blank line (as pasted from Excel) and a name that collides
            # with the pre-seeded student's username must both be handled
            "full_names": ["Ali Valiyev", "  ", "Bekzod Tursunov"],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["errors"] == []
    assert len(body["created"]) == 2

    usernames = [row["username"] for row in body["created"]]
    assert len(set(usernames)) == 2
    # the colliding name got a disambiguating suffix, not a duplicate/crash
    assert "ali.valiyev2" in usernames
    for row in body["created"]:
        assert row["password"] == "Spetion2026!"

    list_resp = client.get(f"/api/v1/admin/students?class_id={klass.id}", headers=headers)
    assert len(list_resp.json()) == 3  # 1 pre-seeded + 2 bulk-created

    codes = {s["student_code"] for s in list_resp.json()}
    assert len(codes) == 3  # all unique


def test_bulk_import_students_unknown_class_404s(client, db_session):
    make_admin(db_session, username="admin_bulk_404")
    db_session.commit()
    token = _login(client, "admin_bulk_404")

    resp = client.post(
        "/api/v1/admin/students/bulk-import",
        json={"class_id": 999999, "full_names": ["Nobody"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_reset_class_passwords_updates_every_student_in_class(client, db_session):
    klass_a = make_class(db_session)
    klass_b = make_class(db_session)
    student1 = make_student(db_session, klass_a, username="reset_test_1")
    student2 = make_student(db_session, klass_a, username="reset_test_2")
    other_class_student = make_student(db_session, klass_b, username="reset_test_other")
    make_admin(db_session, username="admin_reset_pw")
    db_session.commit()
    token = _login(client, "admin_reset_pw")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        f"/api/v1/admin/classes/{klass_a.id}/reset-password",
        json={"new_password": "huquq2026"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 2

    # both students in the class can now log in with the new password
    login1 = client.post(
        "/api/v1/auth/login", json={"username": "reset_test_1", "password": "huquq2026", "class_id": klass_a.id}
    )
    assert login1.status_code == 200
    login2 = client.post(
        "/api/v1/auth/login", json={"username": "reset_test_2", "password": "huquq2026", "class_id": klass_a.id}
    )
    assert login2.status_code == 200

    # a student in a different class is untouched
    other_old = client.post(
        "/api/v1/auth/login", json={"username": "reset_test_other", "password": "secret123", "class_id": klass_b.id}
    )
    assert other_old.status_code == 200
    other_new = client.post(
        "/api/v1/auth/login", json={"username": "reset_test_other", "password": "huquq2026", "class_id": klass_b.id}
    )
    assert other_new.status_code == 401


def test_reset_class_passwords_rejects_short_password(client, db_session):
    klass = make_class(db_session)
    make_student(db_session, klass, username="reset_short_pw")
    make_admin(db_session, username="admin_reset_short")
    db_session.commit()
    token = _login(client, "admin_reset_short")

    resp = client.post(
        f"/api/v1/admin/classes/{klass.id}/reset-password",
        json={"new_password": "abc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_teacher_assignment_create_list_delete(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    teacher = make_teacher(db_session, username="assign_test_teacher")
    make_admin(db_session, username="admin_assign_crud")
    db_session.commit()
    token = _login(client, "admin_assign_crud")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        f"/api/v1/admin/teachers/{teacher.id}/class-subjects",
        json={"teacher_id": teacher.id, "class_id": klass.id, "subject_id": subject.id},
        headers=headers,
    )
    assert create_resp.status_code == 201
    link_id = create_resp.json()["id"]
    assert create_resp.json()["class_name"] == klass.display_name

    dup_resp = client.post(
        f"/api/v1/admin/teachers/{teacher.id}/class-subjects",
        json={"teacher_id": teacher.id, "class_id": klass.id, "subject_id": subject.id},
        headers=headers,
    )
    assert dup_resp.status_code == 409

    list_resp = client.get(f"/api/v1/admin/teachers/{teacher.id}/assignments", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    delete_resp = client.delete(f"/api/v1/admin/teachers/{teacher.id}/class-subjects/{link_id}", headers=headers)
    assert delete_resp.status_code == 204

    list_after = client.get(f"/api/v1/admin/teachers/{teacher.id}/assignments", headers=headers)
    assert list_after.json() == []
