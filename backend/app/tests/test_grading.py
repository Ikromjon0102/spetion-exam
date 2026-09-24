from app.models.attempt import AttemptStatus, ExamAttempt, StudentAnswer
from app.services import grading_service
from app.services.exam_service import recompute_total_points
from app.tests.factories import add_mcq_question, make_class, make_exam, make_student, make_subject


def test_grade_attempt_sums_only_correct_answers(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    q1 = add_mcq_question(db_session, exam, correct_index=0, order_index=0, points=2)
    q2 = add_mcq_question(db_session, exam, correct_index=1, order_index=1, points=3)
    recompute_total_points(db_session, exam)
    db_session.commit()

    student = make_student(db_session, klass)
    attempt = ExamAttempt(exam_id=exam.id, student_id=student.id, status=AttemptStatus.in_progress)
    db_session.add(attempt)
    db_session.flush()
    db_session.add(StudentAnswer(attempt_id=attempt.id, question_id=q1.id, selected_option_id=q1.options[0].id))  # correct
    db_session.add(StudentAnswer(attempt_id=attempt.id, question_id=q2.id, selected_option_id=q2.options[0].id))  # wrong
    db_session.commit()
    db_session.refresh(attempt)

    graded = grading_service.grade_attempt(db_session, attempt)
    assert float(graded.score) == 2.0
    assert float(graded.max_score) == 5.0

    answers = {a.question_id: a for a in graded.answers}
    assert answers[q1.id].is_correct is True
    assert answers[q1.id].points_awarded == 2.0
    assert answers[q2.id].is_correct is False
    assert answers[q2.id].points_awarded == 0.0


def test_grade_attempt_unanswered_question_scores_zero(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    add_mcq_question(db_session, exam, correct_index=0, points=1)
    recompute_total_points(db_session, exam)
    db_session.commit()

    student = make_student(db_session, klass)
    attempt = ExamAttempt(exam_id=exam.id, student_id=student.id, status=AttemptStatus.in_progress)
    db_session.add(attempt)
    db_session.commit()
    db_session.refresh(attempt)

    graded = grading_service.grade_attempt(db_session, attempt)
    assert float(graded.score) == 0.0


def test_grade_attempt_null_selected_option_is_not_correct(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    q1 = add_mcq_question(db_session, exam, correct_index=0, points=1)
    recompute_total_points(db_session, exam)
    db_session.commit()

    student = make_student(db_session, klass)
    attempt = ExamAttempt(exam_id=exam.id, student_id=student.id, status=AttemptStatus.in_progress)
    db_session.add(attempt)
    db_session.flush()
    db_session.add(StudentAnswer(attempt_id=attempt.id, question_id=q1.id, selected_option_id=None, answer_text=""))
    db_session.commit()
    db_session.refresh(attempt)

    graded = grading_service.grade_attempt(db_session, attempt)
    assert float(graded.score) == 0.0
