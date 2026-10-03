"""recompute_for_student(db, exam_id, student_id):
  - upsert exam_rankings for this student
  - recompute rank_in_class for the whole class (RANK() semantics: ties
    share a rank, the next rank skips accordingly)
  - upsert student_subject_stats
"""

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.models.attempt import AttemptStatus, ExamAttempt, StudentAnswer
from app.models.exam import Exam
from app.models.org import Class
from app.models.ranking import ExamRanking, StudentSubjectStats, Trend
from app.models.user import Student, User


def recompute_for_student(db, exam_id: int, student_id: int) -> None:
    exam = db.get(Exam, exam_id)
    attempt = db.query(ExamAttempt).filter_by(exam_id=exam_id, student_id=student_id).first()
    if attempt is None or attempt.score is None:
        return

    ranking = db.query(ExamRanking).filter_by(exam_id=exam_id, student_id=student_id).first()
    if ranking is None:
        ranking = ExamRanking(
            exam_id=exam_id,
            student_id=student_id,
            class_id=exam.class_id,
            score=attempt.score,
            rank_in_class=0,
        )
        db.add(ranking)
    else:
        ranking.score = attempt.score
    db.commit()

    _recompute_class_ranks(db, exam_id)
    _update_subject_stats(db, student_id, exam.subject_id)
    db.commit()


def remove_attempt(db, exam_id: int, student_id: int) -> bool:
    """The inverse of recompute_for_student — deletes one student's
    ExamAttempt (+ its StudentAnswer rows and ExamRanking row) for an exam,
    then re-derives that student's StudentSubjectStats and the remaining
    class's ranks from what's left. Used both by the single-attempt admin
    delete and by force-deleting a whole exam that already has attempts
    (see admin_exams.delete_exam) — a raw SQL delete of the attempt alone
    would leave StudentSubjectStats/ExamRanking stale, since those are
    derived data, not automatically kept in sync by a DB-level cascade.
    Returns False if there was no such attempt to remove."""
    exam = db.get(Exam, exam_id)
    attempt = db.query(ExamAttempt).filter_by(exam_id=exam_id, student_id=student_id).first()
    if attempt is None:
        return False

    db.query(StudentAnswer).filter_by(attempt_id=attempt.id).delete()
    db.query(ExamRanking).filter_by(exam_id=exam_id, student_id=student_id).delete()
    db.delete(attempt)
    db.commit()

    _recompute_class_ranks(db, exam_id)
    _update_subject_stats(db, student_id, exam.subject_id)
    db.commit()
    return True


def _recompute_class_ranks(db, exam_id: int) -> None:
    rows = db.query(ExamRanking).filter_by(exam_id=exam_id).order_by(ExamRanking.score.desc()).all()
    total = len(rows)
    rank = 0
    prev_score = None
    for i, row in enumerate(rows, start=1):
        if row.score != prev_score:
            rank = i
        row.rank_in_class = rank
        row.percentile = round(100 * (total - rank + 1) / total, 2) if total else None
        prev_score = row.score


def _update_subject_stats(db, student_id: int, subject_id: int) -> None:
    # Recomputed from all graded attempts each time rather than incremented in
    # place — cheap at this scale (one student+subject at a time) and immune
    # to incremental-update drift.
    attempts = (
        db.query(ExamAttempt)
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .filter(
            ExamAttempt.student_id == student_id,
            Exam.subject_id == subject_id,
            ExamAttempt.status.in_([AttemptStatus.submitted, AttemptStatus.auto_submitted]),
            ExamAttempt.score.isnot(None),
        )
        .order_by(ExamAttempt.submitted_at)
        .all()
    )
    stats = db.query(StudentSubjectStats).filter_by(student_id=student_id, subject_id=subject_id).first()
    if not attempts:
        # No graded attempt left for this subject (e.g. the last one was
        # just deleted) — a stale stats row must not survive it, or the
        # student keeps showing an old score/rank forever with nothing left
        # to back it up.
        if stats is not None:
            db.delete(stats)
        return

    if stats is None:
        stats = StudentSubjectStats(student_id=student_id, subject_id=subject_id)
        db.add(stats)

    stats.exams_taken_count = len(attempts)
    stats.total_points_earned = sum(float(a.score or 0) for a in attempts)
    stats.total_points_possible = sum(float(a.max_score or 0) for a in attempts)
    stats.average_percent = (
        round(100 * stats.total_points_earned / stats.total_points_possible, 2)
        if stats.total_points_possible
        else None
    )
    stats.last_exam_at = attempts[-1].submitted_at
    stats.trend = _compute_trend(attempts)


def compute_overall_ranking(db, class_id: int | None = None, grade_level: int | None = None) -> list[dict]:
    """Ranks students by their overall average percent across *all* subjects
    (sum of every StudentSubjectStats row's earned/possible points, not an
    average-of-averages — a student who aced one exam and skipped the rest
    shouldn't outrank one with a consistent record). class_id/grade_level
    both None ranks the whole school; class_id ranks one class; grade_level
    ranks every parallel class sharing that grade together (e.g. 7B + 7R
    combined, to see who's best across all of "7th grade") — the two are
    mutually exclusive, pass at most one. Students with no graded exam yet
    (total_points_possible == 0) are excluded rather than ranked last at 0%
    — that would misrepresent "no data" as "failed everything"."""
    query = (
        db.query(
            Student.id.label("student_id"),
            Class.id.label("class_id"),
            Class.display_name.label("class_name"),
            func.sum(StudentSubjectStats.total_points_earned).label("earned"),
            func.sum(StudentSubjectStats.total_points_possible).label("possible"),
            func.sum(StudentSubjectStats.exams_taken_count).label("exams_taken_count"),
        )
        .join(StudentSubjectStats, StudentSubjectStats.student_id == Student.id)
        .join(Class, Class.id == Student.class_id)
        .join(User, User.id == Student.user_id)
        # A deactivated student (left the school, duplicate/test account,
        # etc.) shouldn't keep showing up in a live ranking just because
        # their old StudentSubjectStats rows are still on file.
        .filter(User.is_active.is_(True))
        .group_by(Student.id, Class.id, Class.display_name)
    )
    if class_id is not None:
        query = query.filter(Student.class_id == class_id)
    elif grade_level is not None:
        query = query.filter(Class.grade_level == grade_level)

    rows = [r for r in query.all() if r.possible]
    student_ids = [r.student_id for r in rows]
    names = {
        s.id: s.user.full_name
        for s in db.query(Student).options(joinedload(Student.user)).filter(Student.id.in_(student_ids)).all()
    }

    scored = sorted(
        (
            {
                "student_id": r.student_id,
                "class_id": r.class_id,
                "class_name": r.class_name,
                "exams_taken_count": r.exams_taken_count,
                "average_percent": round(100 * float(r.earned) / float(r.possible), 2),
                "full_name": names.get(r.student_id, ""),
            }
            for r in rows
        ),
        key=lambda x: x["average_percent"],
        reverse=True,
    )

    rank = 0
    prev_percent = None
    for i, row in enumerate(scored, start=1):
        if row["average_percent"] != prev_percent:
            rank = i
        row["rank"] = rank
        prev_percent = row["average_percent"]

    return scored


def _compute_trend(attempts: list[ExamAttempt]) -> Trend | None:
    def pct(a: ExamAttempt) -> float | None:
        return (float(a.score or 0) / float(a.max_score)) if a.max_score else None

    recent = [p for p in (pct(a) for a in attempts[-3:]) if p is not None]
    prior = [p for p in (pct(a) for a in attempts[-6:-3]) if p is not None]
    if not recent or not prior:
        return None

    recent_avg = sum(recent) / len(recent)
    prior_avg = sum(prior) / len(prior)
    if recent_avg - prior_avg > 0.03:
        return Trend.improving
    if prior_avg - recent_avg > 0.03:
        return Trend.declining
    return Trend.stable
