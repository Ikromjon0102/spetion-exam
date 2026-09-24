"""Student-facing endpoints: exam list, start/answer/submit, result, ranking,
subject history. See docs/spec.md section 2 ("Student") and section 3
(lifecycle steps 6-9).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.timeutil import aware
from app.db.base import get_db
from app.dependencies import get_current_student
from app.models.attempt import AttemptStatus, ExamAttempt
from app.models.exam import Exam, ExamStatus
from app.models.ranking import ExamRanking, StudentSubjectStats
from app.models.user import Student, Subject
from app.schemas.admin_management import SubjectOut
from app.schemas.attempt import (
    AnswerIn,
    AttemptOptionOut,
    AttemptQuestionOut,
    AttemptStateOut,
    ExamListItemOut,
    ExamResultOut,
    RankingEntryOut,
    ResultQuestionOut,
    SubjectHistoryOut,
    SubjectHistoryPointOut,
    SubmitResultOut,
)
from app.services import attempt_service

router = APIRouter(prefix="/api/v1/student", tags=["student"])


def _window_state(exam: Exam) -> str:
    now = datetime.now(timezone.utc)
    if not exam.start_at or not exam.end_at or now < aware(exam.start_at):
        return "upcoming"
    if now < aware(exam.end_at):
        return "active"
    return "closed"


def _attempt_state_out(db: Session, exam: Exam, attempt: ExamAttempt) -> AttemptStateOut:
    answers_by_question = {a.question_id: a for a in attempt.answers}
    questions_out = []
    for q in attempt_service.get_ordered_questions(exam, attempt):
        answer = answers_by_question.get(q.id)
        questions_out.append(
            AttemptQuestionOut(
                id=q.id,
                order_index=q.order_index,
                question_type=q.question_type.value,
                prompt_text=q.prompt_text,
                prompt_image_key=q.prompt_image_key,
                points=float(q.points),
                options=[
                    AttemptOptionOut(id=o.id, order_index=o.order_index, option_text=o.option_text)
                    for o in attempt_service.get_ordered_options(attempt, q)
                ],
                selected_option_id=answer.selected_option_id if answer else None,
                answer_text=answer.answer_text if answer else None,
            )
        )
    return AttemptStateOut(
        attempt_id=attempt.id,
        exam_id=exam.id,
        exam_title=exam.title,
        deadline_at=attempt.deadline_at,
        duration_minutes=exam.duration_minutes,
        questions=questions_out,
    )


def _get_exam_for_student(db: Session, exam_id: int, student: Student) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None or exam.class_id != student.class_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imtihon topilmadi")
    return exam


@router.get("/me/exams", response_model=list[ExamListItemOut])
def list_my_exams(db: Session = Depends(get_db), student: Student = Depends(get_current_student)):
    exams = (
        db.query(Exam)
        .filter(
            Exam.class_id == student.class_id,
            Exam.status.in_([ExamStatus.scheduled, ExamStatus.active, ExamStatus.closed]),
        )
        .order_by(Exam.start_at)
        .all()
    )
    attempts = {
        a.exam_id: a
        for a in db.query(ExamAttempt).filter(
            ExamAttempt.student_id == student.id, ExamAttempt.exam_id.in_([e.id for e in exams])
        )
    }

    result = []
    for exam in exams:
        subject = db.get(Subject, exam.subject_id)
        attempt = attempts.get(exam.id)
        result.append(
            ExamListItemOut(
                id=exam.id,
                title=exam.title,
                subject_name=subject.name if subject else "",
                start_at=exam.start_at,
                end_at=exam.end_at,
                duration_minutes=exam.duration_minutes,
                window_state=_window_state(exam),
                my_attempt_status=attempt.status.value if attempt else None,
            )
        )
    return result


@router.post("/exams/{exam_id}/start", response_model=AttemptStateOut)
def start_exam(exam_id: int, db: Session = Depends(get_db), student: Student = Depends(get_current_student)):
    exam = _get_exam_for_student(db, exam_id, student)
    attempt = attempt_service.start_attempt(db, exam, student)
    return _attempt_state_out(db, exam, attempt)


@router.get("/exams/{exam_id}/attempt", response_model=AttemptStateOut)
def get_my_attempt(exam_id: int, db: Session = Depends(get_db), student: Student = Depends(get_current_student)):
    exam = _get_exam_for_student(db, exam_id, student)
    attempt = db.query(ExamAttempt).filter_by(exam_id=exam_id, student_id=student.id).first()
    if attempt is None or attempt.status != AttemptStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faol urinish topilmadi")
    return _attempt_state_out(db, exam, attempt)


@router.put("/exams/{exam_id}/answers/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def submit_answer(
    exam_id: int,
    question_id: int,
    body: AnswerIn,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    attempt = db.query(ExamAttempt).filter_by(exam_id=exam_id, student_id=student.id).first()
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Urinish topilmadi")
    attempt_service.record_answer(db, attempt, question_id, body.selected_option_id, body.answer_text)


@router.post("/exams/{exam_id}/submit", response_model=SubmitResultOut)
def submit_exam(exam_id: int, db: Session = Depends(get_db), student: Student = Depends(get_current_student)):
    attempt = db.query(ExamAttempt).filter_by(exam_id=exam_id, student_id=student.id).first()
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Urinish topilmadi")
    attempt = attempt_service.submit_attempt(db, attempt.id)
    return SubmitResultOut(
        score=float(attempt.score or 0), max_score=float(attempt.max_score or 0), submitted_at=attempt.submitted_at
    )


@router.get("/exams/{exam_id}/result", response_model=ExamResultOut)
def get_result(exam_id: int, db: Session = Depends(get_db), student: Student = Depends(get_current_student)):
    exam = _get_exam_for_student(db, exam_id, student)
    attempt = db.query(ExamAttempt).filter_by(exam_id=exam_id, student_id=student.id).first()
    if attempt is None or attempt.status not in (AttemptStatus.submitted, AttemptStatus.auto_submitted):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Natija hali mavjud emas")

    correct_by_question = {q.id: next((o.id for o in q.options if o.is_correct), None) for q in exam.questions}
    answers_by_question = {a.question_id: a for a in attempt.answers}

    # Iterate exam.questions (in order_index order), not attempt.answers — a
    # question the student never answered has no StudentAnswer row at all,
    # and must still show up as "no answer, 0 pts" rather than silently
    # vanishing from the result.
    questions_out = []
    for question in exam.questions:
        answer = answers_by_question.get(question.id)
        questions_out.append(
            ResultQuestionOut(
                question_id=question.id,
                prompt_text=question.prompt_text,
                points=float(question.points),
                selected_option_id=answer.selected_option_id if answer else None,
                correct_option_id=correct_by_question.get(question.id),
                is_correct=answer.is_correct if answer else False,
                points_awarded=float(answer.points_awarded) if answer and answer.points_awarded is not None else 0.0,
            )
        )

    max_score = float(attempt.max_score or 0)
    score = float(attempt.score or 0)
    return ExamResultOut(
        exam_id=exam.id,
        exam_title=exam.title,
        score=score,
        max_score=max_score,
        percent=round(100 * score / max_score, 2) if max_score else 0.0,
        questions=questions_out,
    )


@router.get("/exams/{exam_id}/ranking", response_model=list[RankingEntryOut])
def get_exam_ranking(exam_id: int, db: Session = Depends(get_db), student: Student = Depends(get_current_student)):
    _get_exam_for_student(db, exam_id, student)
    rows = db.query(ExamRanking).filter_by(exam_id=exam_id).order_by(ExamRanking.rank_in_class).all()
    return [
        RankingEntryOut(
            rank_in_class=r.rank_in_class,
            student_id=r.student_id,
            full_name=db.get(Student, r.student_id).user.full_name,
            score=float(r.score),
            is_me=(r.student_id == student.id),
        )
        for r in rows
    ]


@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db), _student: Student = Depends(get_current_student)):
    """Read-only subject list so the profile page can discover which
    subjects to fetch history for — /admin/subjects is teacher/admin-only."""
    return db.query(Subject).order_by(Subject.name).all()


@router.get("/me/subjects/{subject_id}/history", response_model=SubjectHistoryOut)
def get_subject_history(
    subject_id: int, db: Session = Depends(get_db), student: Student = Depends(get_current_student)
):
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fan topilmadi")

    stats = db.query(StudentSubjectStats).filter_by(student_id=student.id, subject_id=subject_id).first()
    attempts = (
        db.query(ExamAttempt)
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .filter(
            ExamAttempt.student_id == student.id,
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
