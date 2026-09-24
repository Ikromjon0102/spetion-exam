"""Regression test: an unanswered question must still appear in the result
(0 pts, no selection) instead of silently vanishing — a live UI smoke test
caught this because the result page only had one question card when the
exam had two.
"""

from datetime import datetime, timedelta, timezone

from app.services import attempt_service
from app.services.exam_service import publish_exam
from app.tests.factories import add_mcq_question, make_class, make_exam, make_student, make_subject


def test_result_endpoint_includes_unanswered_question_with_zero_points(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    start = datetime.now(timezone.utc)
    exam = make_exam(db_session, klass, subject, duration_minutes=30, start_at=start, end_at=start + timedelta(hours=2))
    q1 = add_mcq_question(db_session, exam, correct_index=0, order_index=0, points=2)
    q2 = add_mcq_question(db_session, exam, correct_index=0, order_index=1, points=3)
    db_session.commit()
    publish_exam(db_session, exam)

    student = make_student(db_session, klass, username="student_result_test")
    db_session.commit()

    attempt = attempt_service.start_attempt(db_session, exam, student)
    attempt_service.record_answer(db_session, attempt, q1.id, q1.options[0].id, None)  # leave q2 unanswered
    attempt_service.submit_attempt(db_session, attempt.id)

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "student_result_test", "password": "secret123", "class_id": klass.id},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    resp = client.get(f"/api/v1/student/exams/{exam.id}/result", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["questions"]) == 2
    by_id = {q["question_id"]: q for q in body["questions"]}
    assert by_id[q1.id]["is_correct"] is True
    assert by_id[q1.id]["points_awarded"] == 2.0
    assert by_id[q2.id]["selected_option_id"] is None
    assert by_id[q2.id]["is_correct"] is False
    assert by_id[q2.id]["points_awarded"] == 0.0
