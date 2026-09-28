"""Admin-facing results/ranking views: class leaderboard, cross-subject
student performance, class-subject performance trend. See docs/spec.md
sections 1.4 and 2.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.timeutil import local_day_bounds_utc
from app.db.base import get_db
from app.dependencies import require_role
from app.models.attempt import AttemptStatus, ExamAttempt
from app.models.exam import Exam, Question
from app.models.ranking import ExamRanking, StudentSubjectStats
from app.models.user import Student, Subject, User
from app.routers.admin_management import _ensure_class_view_access
from app.schemas.attempt import SubjectHistoryOut, SubjectHistoryPointOut
from app.schemas.results import (
    ClassRankingOut,
    ClassRankingRowOut,
    ClassSubjectExamPointOut,
    ClassSubjectPerformanceOut,
    DailyClassResultsOut,
    DailyResultsExamOut,
    DailyStudentRowOut,
    OverallRankingOut,
    OverallRankingRowOut,
    StudentPerformanceOut,
    StudentPerformanceSubjectOut,
)
from app.services import ranking_service

router = APIRouter(prefix="/api/v1/admin", tags=["results"])


@router.get("/exams/{exam_id}/ranking", response_model=ClassRankingOut)
def get_exam_ranking(
    exam_id: int, db: Session = Depends(get_db), _user: User = Depends(require_role("teacher", "admin"))
):
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imtihon topilmadi")
    rows = db.query(ExamRanking).filter_by(exam_id=exam_id).order_by(ExamRanking.rank_in_class).all()
    return ClassRankingOut(
        exam_id=exam.id,
        exam_title=exam.title,
        rankings=[
            ClassRankingRowOut(
                rank_in_class=r.rank_in_class,
                student_id=r.student_id,
                full_name=db.get(Student, r.student_id).user.full_name,
                score=float(r.score),
                percentile=float(r.percentile) if r.percentile is not None else None,
            )
            for r in rows
        ],
    )


@router.get("/students/{student_id}/performance", response_model=StudentPerformanceOut)
def get_student_performance(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="O'quvchi topilmadi")
    # Same view-access scoping as class detail/roster: admin unrestricted,
    # a teacher only for a class they're connected to (homeroom or teach a
    # subject there) — this endpoint existed since early on but was never
    # actually reachable from the UI until the "past/yaxshi o'zlashtirish"
    # feature wired it up, so it had never been scoped; don't leave it open.
    _ensure_class_view_access(db, user, student.class_id)

    subjects = []
    for s in db.query(StudentSubjectStats).filter_by(student_id=student_id):
        subject = db.get(Subject, s.subject_id)
        subjects.append(
            StudentPerformanceSubjectOut(
                subject_id=s.subject_id,
                subject_name=subject.name if subject else "",
                exams_taken_count=s.exams_taken_count,
                average_percent=float(s.average_percent) if s.average_percent is not None else None,
                trend=s.trend.value if s.trend else None,
                last_exam_at=s.last_exam_at,
            )
        )
    return StudentPerformanceOut(student_id=student.id, full_name=student.user.full_name, subjects=subjects)


@router.get("/students/{student_id}/subjects/{subject_id}/history", response_model=SubjectHistoryOut)
def get_student_subject_history(
    student_id: int, subject_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    """Same shape and same underlying data as the student's own
    GET /student/me/subjects/{id}/history (ProfilePage.tsx's Sparkline) —
    this is that view for admin/teacher looking up *any* student, powering
    the full LineChart on StudentPerformancePage.tsx. Duplicated rather
    than sharing a helper with routers/student.py: the two call sites
    differ in exactly one line (whose student_id) and in access control
    (self vs. _ensure_class_view_access), not worth a cross-router
    abstraction for two places."""
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="O'quvchi topilmadi")
    _ensure_class_view_access(db, user, student.class_id)

    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fan topilmadi")

    stats = db.query(StudentSubjectStats).filter_by(student_id=student_id, subject_id=subject_id).first()
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

    timeline = [
        SubjectHistoryPointOut(
            exam_id=a.exam_id,
            exam_title=db.get(Exam, a.exam_id).title,
            score=float(a.score or 0),
            max_score=float(a.max_score or 0),
            date=a.submitted_at,
        )
        for a in attempts
    ]

    return SubjectHistoryOut(
        subject_id=subject_id,
        subject_name=subject.name,
        exams_taken_count=stats.exams_taken_count if stats else 0,
        average_percent=float(stats.average_percent) if stats and stats.average_percent is not None else None,
        trend=stats.trend.value if stats and stats.trend else None,
        timeline=timeline,
    )


@router.get("/classes/{class_id}/subjects/{subject_id}/performance", response_model=ClassSubjectPerformanceOut)
def get_class_subject_performance(
    class_id: int,
    subject_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("teacher", "admin")),
):
    exams = (
        db.query(Exam)
        .filter(Exam.class_id == class_id, Exam.subject_id == subject_id)
        .order_by(Exam.start_at)
        .all()
    )
    points = []
    for exam in exams:
        rankings = db.query(ExamRanking).filter_by(exam_id=exam.id).all()
        if not rankings:
            continue
        avg_score = sum(float(r.score) for r in rankings) / len(rankings)
        points.append(
            ClassSubjectExamPointOut(
                exam_id=exam.id,
                exam_title=exam.title,
                average_score=round(avg_score, 2),
                max_score=float(exam.total_points or 0),
                start_at=exam.start_at,
            )
        )
    return ClassSubjectPerformanceOut(class_id=class_id, subject_id=subject_id, exams=points)


@router.get("/classes/{class_id}/overall-ranking", response_model=OverallRankingOut)
def get_class_overall_ranking(
    class_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    klass = _ensure_class_view_access(db, user, class_id)
    rows = ranking_service.compute_overall_ranking(db, class_id=class_id)
    return OverallRankingOut(
        scope="class",
        class_id=klass.id,
        class_name=klass.display_name,
        rankings=[OverallRankingRowOut(**row) for row in rows],
    )


@router.get("/grades/{grade_level}/overall-ranking", response_model=OverallRankingOut)
def get_grade_overall_ranking(
    grade_level: int, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))
):
    # Admin-only: this spans every parallel class in the grade (e.g. 7B +
    # 7R), which would otherwise leak another class/teacher's students —
    # the same reasoning as school-wide ranking below, not a class a
    # teacher is necessarily connected to.
    rows = ranking_service.compute_overall_ranking(db, grade_level=grade_level)
    return OverallRankingOut(scope="grade", grade_level=grade_level, rankings=[OverallRankingRowOut(**row) for row in rows])


@router.get("/school/overall-ranking", response_model=OverallRankingOut)
def get_school_overall_ranking(db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))):
    rows = ranking_service.compute_overall_ranking(db, class_id=None)
    return OverallRankingOut(scope="school", rankings=[OverallRankingRowOut(**row) for row in rows])


@router.get("/classes/{class_id}/daily-results", response_model=DailyClassResultsOut)
def get_class_daily_results(
    class_id: int,
    date: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    """Backs the "sinf raxbari"'s end-of-day Telegram share. A class
    routinely takes *several* exams on the same day (one per subject) —
    the first version of this endpoint returned one ranking table per
    exam, but the user pointed out that's not what's wanted: one combined
    table, one row per student, one column per subject, plus an overall
    total — so a parent/teacher can see "who did best across the whole
    day" at a glance instead of hunting across several separate tables.
    View-scoped the same as class detail/roster (_ensure_class_view_access)
    rather than list_exams' teacher_class_subjects filter — a homeroom
    teacher who doesn't personally teach any subject in their own class
    still needs to see every subject's results here, not just ones
    they're assigned to.

    Which exams count as "today's" is keyed off when students actually
    SUBMITTED (ExamAttempt.submitted_at), not the exam's own end_at — a
    real production bug found by the user: this school's exam windows are
    routinely multi-day (end_at days after students actually took it), so
    filtering by end_at falling in "today" silently returned nothing for
    almost every exam, even ones the whole class had just finished. A
    student's own attempt.submitted_at is the only signal that actually
    means "this happened today"."""
    klass = _ensure_class_view_access(db, user, class_id)
    resolved_date, day_start, day_end = local_day_bounds_utc(date)

    exam_ids_today = [
        row[0]
        for row in db.query(ExamAttempt.exam_id)
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .filter(
            Exam.class_id == class_id,
            ExamAttempt.status.in_([AttemptStatus.submitted, AttemptStatus.auto_submitted]),
            ExamAttempt.submitted_at >= day_start,
            ExamAttempt.submitted_at < day_end,
        )
        .distinct()
    ]
    exams = (
        db.query(Exam).filter(Exam.id.in_(exam_ids_today)).order_by(Exam.start_at).all() if exam_ids_today else []
    )

    exam_outs: list[DailyResultsExamOut] = []
    # One {student_id: score} map per exam, same order as exam_outs — a
    # student's row is built by indexing into every map at their id, so a
    # missing entry (didn't take that particular exam) naturally becomes
    # None rather than a misleading 0.
    per_exam_scores: list[dict[int, float]] = []
    student_names: dict[int, str] = {}
    for exam in exams:
        subject = db.get(Subject, exam.subject_id)
        question_count = db.query(Question).filter_by(exam_id=exam.id).count()
        exam_outs.append(
            DailyResultsExamOut(
                exam_id=exam.id,
                exam_title=exam.title,
                subject_name=subject.name if subject else "",
                end_at=exam.end_at,
                question_count=question_count,
                max_score=float(exam.total_points or 0),
            )
        )
        rows = db.query(ExamRanking).filter_by(exam_id=exam.id).all()
        score_map: dict[int, float] = {}
        for r in rows:
            score_map[r.student_id] = float(r.score)
            student_names.setdefault(r.student_id, db.get(Student, r.student_id).user.full_name)
        per_exam_scores.append(score_map)

    unranked = []
    for student_id, full_name in student_names.items():
        scores = [scores_for_exam.get(student_id) for scores_for_exam in per_exam_scores]
        # Percent over only the exams this student actually took — summing
        # raw points across differently-weighted exams (e.g. a 20-point exam
        # and a 40-point exam) wouldn't be a fair combined number, same
        # reasoning as ranking_service.compute_overall_ranking.
        earned = sum(s for s in scores if s is not None)
        possible = sum(exam_outs[i].max_score for i, s in enumerate(scores) if s is not None)
        percent = round(earned / possible * 100, 2) if possible > 0 else 0.0
        unranked.append((student_id, full_name, scores, percent))
    unranked.sort(key=lambda row: row[3], reverse=True)

    student_outs: list[DailyStudentRowOut] = []
    prev_percent: float | None = None
    rank = 0
    for i, (student_id, full_name, scores, percent) in enumerate(unranked):
        if percent != prev_percent:
            rank = i + 1
        prev_percent = percent
        student_outs.append(
            DailyStudentRowOut(rank=rank, student_id=student_id, full_name=full_name, scores=scores, percent=percent)
        )

    return DailyClassResultsOut(
        class_id=klass.id, class_name=klass.display_name, date=resolved_date, exams=exam_outs, students=student_outs
    )
