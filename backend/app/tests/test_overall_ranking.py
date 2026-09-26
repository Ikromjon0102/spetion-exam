"""Covers the new "umumiy reyting" feature: overall class-wide and
school-wide leaderboards ranking students by their average percent across
*all* subjects (summed points, not an average-of-averages), requested
after the platform's first demo to school leadership. Built on top of the
already-maintained StudentSubjectStats rows rather than re-scanning every
attempt.
"""

from datetime import datetime, timedelta, timezone

from app.services import attempt_service
from app.services.exam_service import publish_exam
from app.tests.factories import add_mcq_question, make_class, make_exam, make_student, make_subject


def _login(client, username, password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _take_and_score(db_session, exam, student, correct_count, total_count):
    """Answers `correct_count` of `total_count` questions correctly (the
    rest wrong), submits, and returns the resulting percent."""
    attempt = attempt_service.start_attempt(db_session, exam, student)
    questions = exam.questions
    for i, q in enumerate(questions[:total_count]):
        chosen = q.options[0] if i < correct_count else q.options[1]
        attempt_service.record_answer(db_session, attempt, q.id, chosen.id, None)
    attempt_service.submit_attempt(db_session, attempt.id)


def _make_scored_exam(db_session, klass, subject, n_questions=4):
    start = datetime.now(timezone.utc)
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=start, end_at=start + timedelta(hours=2))
    for i in range(n_questions):
        add_mcq_question(db_session, exam, correct_index=0, order_index=i, points=1)
    db_session.commit()
    publish_exam(db_session, exam)
    return exam


def test_class_overall_ranking_orders_by_average_percent_across_subjects(client, db_session):
    from app.tests.factories import make_admin

    klass = make_class(db_session)
    other_class = make_class(db_session)
    math = make_subject(db_session, name="Matematika")
    physics = make_subject(db_session, name="Fizika")
    make_admin(db_session, username="ranking_admin")
    db_session.commit()

    top_student = make_student(db_session, klass, username="ranking_top")
    mid_student = make_student(db_session, klass, username="ranking_mid")
    other_class_student = make_student(db_session, other_class, username="ranking_other_class")
    db_session.commit()

    exam1 = _make_scored_exam(db_session, klass, math)
    exam2 = _make_scored_exam(db_session, klass, physics)
    other_exam = _make_scored_exam(db_session, other_class, math)

    _take_and_score(db_session, exam1, top_student, correct_count=4, total_count=4)  # 100%
    _take_and_score(db_session, exam2, top_student, correct_count=4, total_count=4)  # 100%

    _take_and_score(db_session, exam1, mid_student, correct_count=2, total_count=4)  # 50%
    _take_and_score(db_session, exam2, mid_student, correct_count=1, total_count=4)  # 25%

    _take_and_score(db_session, other_exam, other_class_student, correct_count=4, total_count=4)

    token = _login(client, "ranking_admin")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get(f"/api/v1/admin/classes/{klass.id}/overall-ranking", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == "class"
    assert body["class_id"] == klass.id
    ids_in_order = [r["student_id"] for r in body["rankings"]]
    assert ids_in_order == [top_student.id, mid_student.id]  # top student ranked first
    assert other_class_student.id not in ids_in_order  # other class excluded

    top_row = body["rankings"][0]
    assert top_row["rank"] == 1
    assert top_row["average_percent"] == 100.0
    mid_row = body["rankings"][1]
    assert mid_row["rank"] == 2
    assert mid_row["average_percent"] == 37.5  # (2+1)/(4+4) * 100


def test_school_overall_ranking_spans_every_class_and_is_admin_only(client, db_session):
    from app.tests.factories import make_admin, make_teacher

    klass = make_class(db_session)
    other_class = make_class(db_session)
    subject = make_subject(db_session)
    make_admin(db_session, username="school_ranking_admin")
    teacher = make_teacher(db_session, username="school_ranking_teacher")
    db_session.commit()

    s1 = make_student(db_session, klass, username="school_ranking_s1")
    s2 = make_student(db_session, other_class, username="school_ranking_s2")
    db_session.commit()

    exam1 = _make_scored_exam(db_session, klass, subject)
    exam2 = _make_scored_exam(db_session, other_class, subject)
    _take_and_score(db_session, exam1, s1, correct_count=4, total_count=4)
    _take_and_score(db_session, exam2, s2, correct_count=2, total_count=4)

    admin_token = _login(client, "school_ranking_admin")
    resp = client.get(
        "/api/v1/admin/school/overall-ranking", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == "school"
    ids = {r["student_id"] for r in body["rankings"]}
    assert {s1.id, s2.id} <= ids

    teacher_token = _login(client, "school_ranking_teacher")
    forbidden = client.get(
        "/api/v1/admin/school/overall-ranking", headers={"Authorization": f"Bearer {teacher_token}"}
    )
    assert forbidden.status_code == 403


def test_grade_overall_ranking_combines_parallel_classes_and_is_admin_only(client, db_session):
    """The user's real use case: "7- sinflarni zo'ri kim" — who's best
    across *all* 7th-grade classes (e.g. 7B and 7R combined), not just one
    of them. class_id filters to one class; grade_level spans every class
    sharing that grade_level, mutually exclusive with class_id."""
    from app.tests.factories import make_admin, make_teacher

    klass_b = make_class(db_session, label="B", grade_level=7)
    klass_r = make_class(db_session, label="R", grade_level=7)
    other_grade_class = make_class(db_session, label="A", grade_level=8)
    subject = make_subject(db_session)
    make_admin(db_session, username="grade_ranking_admin")
    teacher = make_teacher(db_session, username="grade_ranking_teacher")
    db_session.commit()

    top = make_student(db_session, klass_b, username="grade_ranking_top")
    mid = make_student(db_session, klass_r, username="grade_ranking_mid")
    other_grade_student = make_student(db_session, other_grade_class, username="grade_ranking_other")
    db_session.commit()

    exam_b = _make_scored_exam(db_session, klass_b, subject)
    exam_r = _make_scored_exam(db_session, klass_r, subject)
    other_exam = _make_scored_exam(db_session, other_grade_class, subject)
    _take_and_score(db_session, exam_b, top, correct_count=4, total_count=4)
    _take_and_score(db_session, exam_r, mid, correct_count=2, total_count=4)
    _take_and_score(db_session, other_exam, other_grade_student, correct_count=4, total_count=4)

    admin_token = _login(client, "grade_ranking_admin")
    resp = client.get(
        "/api/v1/admin/grades/7/overall-ranking", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == "grade"
    assert body["grade_level"] == 7
    ids_in_order = [r["student_id"] for r in body["rankings"]]
    assert ids_in_order == [top.id, mid.id]  # both 7B and 7R students present, ranked together
    assert other_grade_student.id not in ids_in_order  # grade 8 excluded

    teacher_token = _login(client, "grade_ranking_teacher")
    forbidden = client.get(
        "/api/v1/admin/grades/7/overall-ranking", headers={"Authorization": f"Bearer {teacher_token}"}
    )
    assert forbidden.status_code == 403


def test_overall_ranking_excludes_students_with_no_graded_exams(client, db_session):
    from app.tests.factories import make_admin

    klass = make_class(db_session)
    subject = make_subject(db_session)
    make_admin(db_session, username="no_exam_admin")
    db_session.commit()

    scored_student = make_student(db_session, klass, username="no_exam_scored")
    unscored_student = make_student(db_session, klass, username="no_exam_unscored")
    db_session.commit()

    exam = _make_scored_exam(db_session, klass, subject)
    _take_and_score(db_session, exam, scored_student, correct_count=3, total_count=4)

    token = _login(client, "no_exam_admin")
    resp = client.get(
        f"/api/v1/admin/classes/{klass.id}/overall-ranking", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    ids = [r["student_id"] for r in resp.json()["rankings"]]
    assert scored_student.id in ids
    assert unscored_student.id not in ids
