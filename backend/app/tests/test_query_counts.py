"""Guards the admin list endpoints against N+1 queries.

Reported after the school grew (117 students, dozens of exams): admin pages
sat on "Yuklanmoqda..." for 1-5 seconds. The lists issued a handful of extra
queries *per row* (the row's user, class, subject, question collection,
attempt check...) and every one of those is a network round trip to
Postgres, on a 1-vCPU box shared with five other projects. The fix is to
batch, and these tests pin it: the number of SQL statements an endpoint
issues must not grow with the number of rows it returns.

The shared test session caches everything the seeding code touched, which
would hide exactly this bug — hence expunge_all() before each measurement.
"""

from contextlib import contextmanager

from sqlalchemy import event

from app.models.user import TeacherClassSubject
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
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@contextmanager
def count_queries(db_session):
    """Yields a list whose length is the number of SQL statements run inside
    the block. The ORM identity map is cleared first so lazy loads can't hide
    behind objects the seeding code already loaded."""
    db_session.commit()
    db_session.expunge_all()
    statements: list[str] = []

    def before(conn, cursor, statement, *_args):
        statements.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", before)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", before)


def _admin(client, db_session, username="qc_admin"):
    make_admin(db_session, username=username)
    db_session.commit()
    return _login(client, username)


def test_list_students_query_count_does_not_grow_with_rows(client, db_session):
    klass = make_class(db_session)
    headers = _admin(client, db_session)
    for i in range(3):
        make_student(db_session, klass, username=f"qc_s_small_{i}")

    with count_queries(db_session) as small:
        assert client.get("/api/v1/admin/students", headers=headers).status_code == 200

    for i in range(20):
        make_student(db_session, klass, username=f"qc_s_big_{i}")

    with count_queries(db_session) as big:
        resp = client.get("/api/v1/admin/students", headers=headers)
    assert len(resp.json()) == 23
    assert len(big) <= len(small), f"{len(small)} queries for 3 students vs {len(big)} for 23"


def test_list_teachers_query_count_does_not_grow_with_rows(client, db_session):
    headers = _admin(client, db_session)
    for i in range(3):
        make_teacher(db_session, username=f"qc_t_small_{i}")

    with count_queries(db_session) as small:
        assert client.get("/api/v1/admin/teachers", headers=headers).status_code == 200

    for i in range(20):
        make_teacher(db_session, username=f"qc_t_big_{i}")

    with count_queries(db_session) as big:
        assert len(client.get("/api/v1/admin/teachers", headers=headers).json()) == 23
    assert len(big) <= len(small), f"{len(small)} vs {len(big)}"


def test_list_classes_query_count_does_not_grow_with_rows(client, db_session):
    headers = _admin(client, db_session)

    def add_classes(n, tag):
        for i in range(n):
            klass = make_class(db_session, label=f"{tag}{i}")
            klass.homeroom_teacher_id = make_teacher(db_session, username=f"qc_hr_{tag}{i}").id

    add_classes(3, "S")
    with count_queries(db_session) as small:
        assert client.get("/api/v1/admin/classes", headers=headers).status_code == 200

    add_classes(15, "B")
    with count_queries(db_session) as big:
        assert len(client.get("/api/v1/admin/classes", headers=headers).json()) == 18
    assert len(big) <= len(small), f"{len(small)} vs {len(big)}"


def test_list_exams_query_count_does_not_grow_with_rows(client, db_session):
    headers = _admin(client, db_session)
    klass = make_class(db_session)
    subject = make_subject(db_session)

    def add_exams(n):
        for _ in range(n):
            exam = make_exam(db_session, klass, subject)
            for i in range(3):
                add_mcq_question(db_session, exam, order_index=i, needs_review=bool(i % 2))

    add_exams(2)
    with count_queries(db_session) as small:
        assert client.get("/api/v1/admin/exams", headers=headers).status_code == 200

    add_exams(15)
    with count_queries(db_session) as big:
        body = client.get("/api/v1/admin/exams", headers=headers).json()
    assert len(body) == 17
    assert all(e["question_count"] == 3 and e["needs_review_count"] == 1 for e in body)
    assert len(big) <= len(small), f"{len(small)} vs {len(big)}"


def test_list_exam_attempts_query_count_does_not_grow_with_rows(client, db_session):
    headers = _admin(client, db_session)
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    for i in range(3):
        make_student(db_session, klass, username=f"qc_a_small_{i}")

    with count_queries(db_session) as small:
        assert client.get(f"/api/v1/admin/exams/{exam.id}/attempts", headers=headers).status_code == 200

    for i in range(20):
        make_student(db_session, klass, username=f"qc_a_big_{i}")

    with count_queries(db_session) as big:
        assert len(client.get(f"/api/v1/admin/exams/{exam.id}/attempts", headers=headers).json()) == 23
    assert len(big) <= len(small), f"{len(small)} vs {len(big)}"


def test_teacher_scoped_exam_list_matches_assignments(client, db_session):
    """Batching must not change who sees what: a teacher only gets exams for
    their own (class, subject) pairs."""
    klass = make_class(db_session)
    other_class = make_class(db_session)
    subject = make_subject(db_session)
    teacher = make_teacher(db_session, username="qc_scoped_teacher")
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id))
    mine = make_exam(db_session, klass, subject)
    make_exam(db_session, other_class, subject)
    db_session.commit()

    headers = _login(client, "qc_scoped_teacher")
    body = client.get("/api/v1/admin/exams", headers=headers).json()
    assert [e["id"] for e in body] == [mine.id]
