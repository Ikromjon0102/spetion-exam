"""Covers POST /admin/exams/{id}/duplicate — a teacher who gives the
identical lesson/exam to several parallel classes (e.g. 7B and 7R)
shouldn't have to re-author or re-upload the same questions per class.
"""

from datetime import datetime, timedelta, timezone

from app.models.exam import Exam, ExamStatus
from app.models.user import TeacherClassSubject
from app.tests.factories import (
    add_mcq_question,
    add_short_answer_question,
    make_admin,
    make_class,
    make_exam,
    make_subject,
    make_teacher,
)


def _login(client, username, password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_teacher_duplicates_exam_into_a_parallel_class_they_teach(client, db_session):
    subject = make_subject(db_session, name="Matematika")
    class_7b = make_class(db_session, label="B", grade_level=7)
    class_7r = make_class(db_session, label="R", grade_level=7)
    teacher = make_teacher(db_session, subject=subject, username="parallel_teacher")
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=class_7b.id, subject_id=subject.id))
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=class_7r.id, subject_id=subject.id))
    db_session.commit()

    start = datetime.now(timezone.utc)
    exam = make_exam(
        db_session,
        class_7b,
        subject,
        duration_minutes=45,
        start_at=start,
        end_at=start + timedelta(hours=2),
        created_by=teacher.user,
    )
    q1 = add_mcq_question(db_session, exam, correct_index=2, order_index=0, needs_review=False, points=2)
    add_short_answer_question(
        db_session, exam, reference_answer="Namunaviy javob", order_index=1, points=3, needs_review=True
    )
    db_session.commit()

    token = _login(client, "parallel_teacher")
    resp = client.post(
        f"/api/v1/admin/exams/{exam.id}/duplicate",
        json={"class_ids": [class_7r.id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    copy = body[0]
    assert copy["class_id"] == class_7r.id
    assert copy["class_name"] == class_7r.display_name
    assert copy["subject_id"] == subject.id
    assert copy["title"] == exam.title
    assert copy["status"] == "draft"
    assert copy["duration_minutes"] == 45
    assert copy["question_count"] == 2
    assert copy["needs_review_count"] == 1  # only the short-answer question started needs_review=True
    assert copy["total_points"] == 5.0

    copied_exam = db_session.get(Exam, copy["id"])
    assert copied_exam.exam_upload_id is None
    assert copied_exam.start_at == exam.start_at
    assert copied_exam.end_at == exam.end_at
    copied_questions = sorted(copied_exam.questions, key=lambda q: q.order_index)
    assert copied_questions[0].question_type.value == "mcq"
    assert copied_questions[0].needs_review is False
    assert sum(1 for o in copied_questions[0].options if o.is_correct) == 1
    assert copied_questions[1].question_type.value == "short_answer"
    assert copied_questions[1].reference_answer == "Namunaviy javob"

    # the source exam itself must be completely untouched
    db_session.refresh(exam)
    assert exam.class_id == class_7b.id
    assert len(exam.questions) == 2
    assert q1.id in [q.id for q in exam.questions]


def test_duplicate_into_several_classes_at_once(client, db_session):
    subject = make_subject(db_session)
    class_a = make_class(db_session, label="A")
    class_b = make_class(db_session, label="B")
    class_c = make_class(db_session, label="C")
    teacher = make_teacher(db_session, subject=subject, username="multi_dup_teacher")
    for klass in (class_a, class_b, class_c):
        db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id))
    db_session.commit()

    exam = make_exam(db_session, class_a, subject, created_by=teacher.user)
    add_mcq_question(db_session, exam, correct_index=0, needs_review=False)
    db_session.commit()

    token = _login(client, "multi_dup_teacher")
    resp = client.post(
        f"/api/v1/admin/exams/{exam.id}/duplicate",
        json={"class_ids": [class_b.id, class_c.id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert {row["class_id"] for row in body} == {class_b.id, class_c.id}


def test_cannot_duplicate_into_a_class_not_taught_by_this_teacher(client, db_session):
    subject = make_subject(db_session)
    own_class = make_class(db_session, label="Own")
    other_class = make_class(db_session, label="Other")
    teacher = make_teacher(db_session, subject=subject, username="restricted_dup_teacher")
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=own_class.id, subject_id=subject.id))
    db_session.commit()

    exam = make_exam(db_session, own_class, subject, created_by=teacher.user)
    add_mcq_question(db_session, exam, correct_index=0)
    db_session.commit()

    token = _login(client, "restricted_dup_teacher")
    resp = client.post(
        f"/api/v1/admin/exams/{exam.id}/duplicate",
        json={"class_ids": [other_class.id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403

    # nothing should have been created for the unauthorized class either
    assert db_session.query(Exam).filter_by(class_id=other_class.id).count() == 0


def test_admin_can_duplicate_into_any_class(client, db_session):
    subject = make_subject(db_session)
    class_a = make_class(db_session, label="A")
    class_b = make_class(db_session, label="B")
    make_admin(db_session, username="dup_admin")
    db_session.commit()

    exam = make_exam(db_session, class_a, subject)
    add_mcq_question(db_session, exam, correct_index=0)
    db_session.commit()

    token = _login(client, "dup_admin")
    resp = client.post(
        f"/api/v1/admin/exams/{exam.id}/duplicate",
        json={"class_ids": [class_b.id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()[0]["class_id"] == class_b.id


def test_duplicating_into_only_the_source_class_is_rejected(client, db_session):
    subject = make_subject(db_session)
    klass = make_class(db_session)
    teacher = make_teacher(db_session, subject=subject, username="self_dup_teacher")
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id))
    db_session.commit()

    exam = make_exam(db_session, klass, subject, created_by=teacher.user)
    add_mcq_question(db_session, exam, correct_index=0)
    db_session.commit()

    token = _login(client, "self_dup_teacher")
    resp = client.post(
        f"/api/v1/admin/exams/{exam.id}/duplicate",
        json={"class_ids": [klass.id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
