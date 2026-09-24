"""Admin-facing results/ranking views: class leaderboard, cross-subject
student performance, class-subject performance trend. See docs/spec.md
sections 1.4 and 2.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.dependencies import require_role
from app.models.exam import Exam
from app.models.ranking import ExamRanking, StudentSubjectStats
from app.models.user import Student, Subject, User
from app.schemas.results import (
    ClassRankingOut,
    ClassRankingRowOut,
    ClassSubjectExamPointOut,
    ClassSubjectPerformanceOut,
    StudentPerformanceOut,
    StudentPerformanceSubjectOut,
)

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
    student_id: int, db: Session = Depends(get_db), _user: User = Depends(require_role("teacher", "admin"))
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="O'quvchi topilmadi")

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
