"""One cheap endpoint behind the staff dashboard.

The dashboard used to download the whole school's classes, subjects, students
and teachers just to show four counts and a bar chart, then — only after all
of that finished — fetch every live exam's roster to count who is taking it.
Two sequential waves of heavy requests, each paying the full network round
trip to a distant server, is what the "Yuklanmoqda..." wait was made of. The
numbers are all cheap aggregates, so they are computed in the database here.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.timeutil import aware
from app.db.base import get_db
from app.dependencies import require_role
from app.models.attempt import AttemptStatus, ExamAttempt
from app.models.exam import ExamStatus
from app.models.org import Class
from app.models.user import Student, Subject, Teacher, User, UserRole
from app.routers.admin_exams import visible_exams
from app.schemas.dashboard import (
    ClassStudentCountOut,
    DashboardCountsOut,
    DashboardOut,
    LiveExamOut,
)

router = APIRouter(prefix="/api/v1/admin", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))):
    now = datetime.now(timezone.utc)
    # "Live" is computed from the window, never from Exam.status (which
    # never becomes "active" — see the dashboard notes in CLAUDE.md).
    live_exams = [
        e
        for e in visible_exams(db, user)
        if e.status in (ExamStatus.scheduled, ExamStatus.active)
        and e.start_at
        and e.end_at
        and aware(e.start_at) <= now < aware(e.end_at)
    ]

    class_sizes = dict(db.query(Student.class_id, func.count(Student.id)).group_by(Student.class_id).all())

    by_exam: dict[int, dict[str, int]] = {e.id: {} for e in live_exams}
    if live_exams:
        rows = (
            db.query(ExamAttempt.exam_id, ExamAttempt.status, func.count(ExamAttempt.id))
            .filter(ExamAttempt.exam_id.in_(list(by_exam)))
            .group_by(ExamAttempt.exam_id, ExamAttempt.status)
        )
        for exam_id, attempt_status, n in rows:
            by_exam[exam_id][attempt_status.value] = n

    subject_names = dict(db.query(Subject.id, Subject.name).all())
    class_names = dict(db.query(Class.id, Class.display_name).all())

    live = []
    for exam in live_exams:
        counts = by_exam[exam.id]
        total = class_sizes.get(exam.class_id, 0)
        submitted = counts.get(AttemptStatus.submitted.value, 0) + counts.get(AttemptStatus.auto_submitted.value, 0)
        in_progress = counts.get(AttemptStatus.in_progress.value, 0)
        expired = counts.get(AttemptStatus.expired_unstarted.value, 0)
        live.append(
            LiveExamOut(
                exam_id=exam.id,
                title=exam.title,
                subject_name=subject_names.get(exam.subject_id, ""),
                class_name=class_names.get(exam.class_id, ""),
                total=total,
                submitted=submitted,
                in_progress=in_progress,
                not_started=max(total - submitted - in_progress - expired, 0),
            )
        )

    if user.role != UserRole.admin:
        return DashboardOut(live=live)

    per_class = sorted(
        (
            ClassStudentCountOut(class_id=cid, class_name=class_names.get(cid, ""), count=n)
            for cid, n in class_sizes.items()
            if n > 0
        ),
        key=lambda c: c.count,
        reverse=True,
    )
    return DashboardOut(
        live=live,
        counts=DashboardCountsOut(
            classes=len(class_names),
            subjects=len(subject_names),
            students=sum(class_sizes.values()),
            teachers=db.query(func.count(Teacher.id)).scalar() or 0,
        ),
        students_per_class=per_class,
    )
