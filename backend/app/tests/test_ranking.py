from datetime import datetime, timezone

from app.models.attempt import AttemptStatus, ExamAttempt
from app.models.ranking import ExamRanking, StudentSubjectStats
from app.services import ranking_service
from app.tests.factories import make_class, make_exam, make_student, make_subject


def _graded_attempt(db, exam, student, score, max_score=10):
    attempt = ExamAttempt(
        exam_id=exam.id,
        student_id=student.id,
        status=AttemptStatus.submitted,
        score=score,
        max_score=max_score,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    db.commit()
    return attempt


def test_ranking_ties_share_rank_and_next_rank_skips(db_session):
    """Mirrors RANK() OVER (PARTITION BY exam_id ORDER BY score DESC): two
    students tied at the top both get rank 1, the next student gets rank 3,
    not 2 — see docs/spec.md section 3 step 9."""
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    db_session.commit()

    s1 = make_student(db_session, klass)
    s2 = make_student(db_session, klass)
    s3 = make_student(db_session, klass)
    db_session.commit()

    _graded_attempt(db_session, exam, s1, score=8)
    _graded_attempt(db_session, exam, s2, score=8)
    _graded_attempt(db_session, exam, s3, score=5)

    for student in (s1, s2, s3):
        ranking_service.recompute_for_student(db_session, exam.id, student.id)

    rows = {r.student_id: r for r in db_session.query(ExamRanking).filter_by(exam_id=exam.id)}
    assert rows[s1.id].rank_in_class == 1
    assert rows[s2.id].rank_in_class == 1
    assert rows[s3.id].rank_in_class == 3


def test_ranking_recompute_updates_existing_row_not_duplicate(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    db_session.commit()
    student = make_student(db_session, klass)
    db_session.commit()

    attempt = _graded_attempt(db_session, exam, student, score=4)
    ranking_service.recompute_for_student(db_session, exam.id, student.id)

    attempt.score = 9
    db_session.commit()
    ranking_service.recompute_for_student(db_session, exam.id, student.id)

    rows = db_session.query(ExamRanking).filter_by(exam_id=exam.id, student_id=student.id).all()
    assert len(rows) == 1
    assert float(rows[0].score) == 9.0


def test_ranking_updates_student_subject_stats(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    db_session.commit()
    student = make_student(db_session, klass)
    db_session.commit()

    _graded_attempt(db_session, exam, student, score=7, max_score=10)
    ranking_service.recompute_for_student(db_session, exam.id, student.id)

    stats = db_session.query(StudentSubjectStats).filter_by(student_id=student.id, subject_id=subject.id).first()
    assert stats is not None
    assert stats.exams_taken_count == 1
    assert float(stats.average_percent) == 70.0


def test_ranking_skips_ungraded_attempt(db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    db_session.commit()
    student = make_student(db_session, klass)
    db_session.commit()
    db_session.add(ExamAttempt(exam_id=exam.id, student_id=student.id, status=AttemptStatus.in_progress))
    db_session.commit()

    ranking_service.recompute_for_student(db_session, exam.id, student.id)

    assert db_session.query(ExamRanking).filter_by(exam_id=exam.id, student_id=student.id).first() is None
