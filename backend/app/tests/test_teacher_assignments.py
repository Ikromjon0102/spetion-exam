"""Covers GET /admin/teachers/me/assignments — powers the exam-upload UI
filtering a teacher down to only their own (class, subject) pairs, e.g. a
teacher who teaches both Huquq and Tarix to different classes."""

from app.models.user import TeacherClassSubject
from app.tests.factories import make_admin, make_class, make_subject, make_teacher


def _login(client, username, password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_teacher_sees_only_own_class_subject_pairs(client, db_session):
    huquq = make_subject(db_session, name="Huquq")
    tarix = make_subject(db_session, name="Tarix")
    class_10 = make_class(db_session, label="huquq", grade_level=10)
    class_8 = make_class(db_session, label="huquq", grade_level=8)
    other_class = make_class(db_session, label="B", grade_level=7)

    teacher = make_teacher(db_session, username="abdullayev.r")
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=class_10.id, subject_id=huquq.id))
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=class_8.id, subject_id=huquq.id))
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=class_10.id, subject_id=tarix.id))
    db_session.commit()

    token = _login(client, "abdullayev.r")
    resp = client.get("/api/v1/admin/teachers/me/assignments", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 3

    pairs = {(r["class_name"], r["subject_name"]) for r in rows}
    assert pairs == {
        ("10-huquq", "Huquq"),
        ("8-huquq", "Huquq"),
        ("10-huquq", "Tarix"),
    }
    assert other_class.display_name not in {r["class_name"] for r in rows}


def test_admin_gets_empty_assignments_list(client, db_session):
    make_admin(db_session, username="admin_assign_test")
    db_session.commit()
    token = _login(client, "admin_assign_test")
    resp = client.get("/api/v1/admin/teachers/me/assignments", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []
