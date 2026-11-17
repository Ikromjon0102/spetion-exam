"""Student-facing endpoints: exam list, start/answer/submit, result, ranking,
subject history. See docs/spec.md section 2 ("Student") and section 3
(lifecycle steps 6-9).
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.timeutil import aware
from app.db.base import get_db
from app.dependencies import get_current_student
from sqlalchemy import func

from app.models.attempt import AttemptSectionScore, AttemptStatus, ExamAttempt
from app.models.exam import Exam, ExamSection, ExamStatus, Question
from app.models.ranking import ExamRanking, StudentSubjectStats
from app.models.user import Student, Subject
from app.schemas.admin_management import SubjectOut
from app.schemas.attempt import (
    AnswerIn,
    AttemptOptionOut,
    AttemptQuestionOut,
    AttemptSectionOut,
    AttemptStateOut,
    ExamListItemOut,
    ExamResultOut,
    RankingEntryOut,
    ResultQuestionOut,
    ResultSectionOut,
    SubjectHistoryOut,
    SubjectHistoryPointOut,
    SubmitResultOut,
)
from app.schemas.dynamics import DynamicsOut
from app.services import attempt_service, dynamics_service, ranking_service

router = APIRouter(prefix="/api/v1/student", tags=["student"])


def _window_state(exam: Exam) -> str:
    now = datetime.now(timezone.utc)
    if not exam.start_at or not exam.end_at or now < aware(exam.start_at):
        return "upcoming"
    if now < aware(exam.end_at):
        return "active"
    return "closed"


def _section_outs(db: Session, exams: list[Exam]) -> dict[int, list[AttemptSectionOut]]:
    """Blocks of the chorak exams among `exams`, keyed by exam id (one query
    for the sections, one for the subject names)."""
    ids = [e.id for e in exams if e.is_chorak]
    if not ids:
        return {}
    sections = db.query(ExamSection).filter(ExamSection.exam_id.in_(ids)).order_by(ExamSection.order_index).all()
    names = dict(db.query(Subject.id, Subject.name).filter(Subject.id.in_({s.subject_id for s in sections})))
    out: dict[int, list[AttemptSectionOut]] = {}
    for s in sections:
        out.setdefault(s.exam_id, []).append(
            AttemptSectionOut(
                id=s.id,
                subject_name=names.get(s.subject_id, ""),
                kind=s.kind,
                question_count=s.question_count,
                points_per_question=float(s.points_per_question),
            )
        )
    return out


def _attempt_state_out(db: Session, exam: Exam, attempt: ExamAttempt) -> AttemptStateOut:
    answers_by_question = {a.question_id: a for a in attempt.answers}
    questions_out = []
    for q in attempt_service.get_ordered_questions(exam, attempt):
        answer = answers_by_question.get(q.id)
        questions_out.append(
            AttemptQuestionOut(
                id=q.id,
                section_id=q.section_id,
                order_index=q.order_index,
                question_type=q.question_type.value,
                prompt_text=q.prompt_text,
                prompt_image_key=q.prompt_image_key,
                points=float(q.points),
                options=[
                    AttemptOptionOut(
                        id=o.id, order_index=o.order_index, option_text=o.option_text, option_image_key=o.option_image_key
                    )
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
        exam_type=exam.exam_type,
        sections=_section_outs(db, [exam]).get(exam.id, []),
        questions=questions_out,
    )


def _get_exam_for_student(db: Session, exam_id: int, student: Student) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None or exam.class_id != student.class_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imtihon topilmadi")
    return exam


# A class sitting several exams every week would otherwise show a student a
# list that only ever grows. By default the list is what is happening or
# recent; the full history is one tap away (include_old) and always on the
# profile/portfolio, which is built from graded attempts and does not depend on
# this list (or on whether staff have archived the exam).
RECENT_EXAM_DAYS = 30


@router.get("/me/exams", response_model=list[ExamListItemOut])
def list_my_exams(
    include_old: bool = False,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    query = db.query(Exam).filter(
        Exam.class_id == student.class_id,
        Exam.status.in_([ExamStatus.scheduled, ExamStatus.active, ExamStatus.closed]),
    )
    if not include_old:
        cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_EXAM_DAYS)
        query = query.filter(or_(Exam.end_at.is_(None), Exam.end_at >= cutoff))
    exams = query.all()
    # What needs the student now comes first: running, then upcoming (soonest
    # first), then finished (most recent first).
    order = {"active": 0, "upcoming": 1, "closed": 2}
    exams.sort(
        key=lambda e: (
            order.get(_window_state(e), 3),
            (aware(e.start_at).timestamp() if e.start_at else 0) * (1 if _window_state(e) != "closed" else -1),
        )
    )
    attempts = {
        a.exam_id: a
        for a in db.query(ExamAttempt).filter(
            ExamAttempt.student_id == student.id, ExamAttempt.exam_id.in_([e.id for e in exams])
        )
    }

    return _list_items(db, exams, attempts)


def _list_items(db: Session, exams: list[Exam], attempts: dict[int, ExamAttempt]) -> list[ExamListItemOut]:
    if not exams:
        return []
    subject_names = dict(db.query(Subject.id, Subject.name).filter(Subject.id.in_({e.subject_id for e in exams})))
    question_counts = dict(
        db.query(Question.exam_id, func.count(Question.id))
        .filter(Question.exam_id.in_([e.id for e in exams]))
        .group_by(Question.exam_id)
    )
    sections = _section_outs(db, exams)
    result = []
    for exam in exams:
        attempt = attempts.get(exam.id)
        exam_sections = sections.get(exam.id, [])
        result.append(
            ExamListItemOut(
                id=exam.id,
                title=exam.title,
                subject_name=(
                    ", ".join(s.subject_name for s in exam_sections)
                    if exam.is_chorak
                    else subject_names.get(exam.subject_id, "")
                ),
                start_at=exam.start_at,
                end_at=exam.end_at,
                duration_minutes=exam.duration_minutes,
                window_state=_window_state(exam),
                my_attempt_status=attempt.status.value if attempt else None,
                exam_type=exam.exam_type,
                question_count=question_counts.get(exam.id, 0),
                total_points=float(exam.total_points) if exam.total_points is not None else None,
                my_deadline_at=(
                    attempt.deadline_at if attempt and attempt.status == AttemptStatus.in_progress else None
                ),
                sections=exam_sections,
            )
        )
    return result


@router.get("/exams/{exam_id}/info", response_model=ExamListItemOut)
def get_exam_info(exam_id: int, db: Session = Depends(get_db), student: Student = Depends(get_current_student)):
    """What the "before you start" screen shows: how long, how many questions,
    which blocks. Reading it never starts the clock — only POST .../start does."""
    exam = _get_exam_for_student(db, exam_id, student)
    if exam.status not in (ExamStatus.scheduled, ExamStatus.active, ExamStatus.closed):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imtihon topilmadi")
    attempt = db.query(ExamAttempt).filter_by(exam_id=exam_id, student_id=student.id).first()
    return _list_items(db, [exam], {exam.id: attempt} if attempt else {})[0]


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

    # Hide which option was correct/selected while the exam window is still
    # open (now < exam.end_at) — otherwise a student who finishes early can
    # read off the answer key and pass it to classmates who haven't taken
    # it yet. ✓/✕ and points still show either way, since those alone don't
    # reveal any option's content. Once the window has closed for everyone,
    # the real text is shown (see get_result's ExamResultOut construction).
    now = datetime.now(timezone.utc)
    answers_revealed = exam.end_at is None or now >= aware(exam.end_at)

    correct_by_question = {q.id: next((o.id for o in q.options if o.is_correct), None) for q in exam.questions}
    options_by_question = {q.id: {o.id: o.option_text for o in q.options} for q in exam.questions}
    answers_by_question = {a.question_id: a for a in attempt.answers}

    # Iterate in the same per-attempt shuffled order the student actually saw
    # while taking the exam (attempt.question_order), not exam.questions'
    # fixed order_index — otherwise "Savol 1" here can be a totally
    # different question than "Savol 1" during the exam, which looks like
    # answers went missing when really they're just further down the list.
    # A question the student never answered has no StudentAnswer row at
    # all, and must still show up as "no answer, 0 pts" rather than
    # silently vanishing from the result.
    questions_out = []
    for question in attempt_service.get_ordered_questions(exam, attempt):
        answer = answers_by_question.get(question.id)
        option_texts = options_by_question.get(question.id, {})
        selected_option_id = answer.selected_option_id if answer else None
        correct_option_id = correct_by_question.get(question.id)
        questions_out.append(
            ResultQuestionOut(
                question_id=question.id,
                section_id=question.section_id,
                question_type=question.question_type.value,
                prompt_text=question.prompt_text,
                points=float(question.points),
                selected_option_id=selected_option_id,
                selected_option_text=(
                    option_texts.get(selected_option_id)
                    if answers_revealed and selected_option_id
                    else None
                ),
                correct_option_id=correct_option_id,
                correct_option_text=(
                    option_texts.get(correct_option_id) if answers_revealed and correct_option_id else None
                ),
                answer_text=answer.answer_text if answer else None,
                ai_feedback=(answer.ai_feedback if answer and answers_revealed else None),
                is_correct=answer.is_correct if answer else False,
                points_awarded=float(answer.points_awarded) if answer and answer.points_awarded is not None else 0.0,
                pending_review=bool(answer and answer.graded_by == "pending"),
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
        answers_revealed=answers_revealed,
        reveal_at=exam.end_at if not answers_revealed else None,
        exam_type=exam.exam_type,
        sections=_result_sections(db, exam, attempt),
        questions=questions_out,
    )


def _result_sections(db: Session, exam: Exam, attempt: ExamAttempt) -> list[ResultSectionOut]:
    if not exam.is_chorak:
        return []
    scores = {sc.section_id: sc for sc in db.query(AttemptSectionScore).filter_by(attempt_id=attempt.id)}
    info = {s.id: s for s in _section_outs(db, [exam]).get(exam.id, [])}
    out = []
    for section in exam.sections:
        sc = scores.get(section.id)
        out.append(
            ResultSectionOut(
                section_id=section.id,
                subject_name=info[section.id].subject_name,
                kind=section.kind,
                score=float(sc.score) if sc else 0.0,
                max_score=float(sc.max_score) if sc else round(section.question_count * float(section.points_per_question), 2),
                correct_count=sc.correct_count if sc else 0,
                question_count=sc.question_count if sc else section.question_count,
            )
        )
    return out


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


@router.get("/me/dynamics", response_model=DynamicsOut)
def get_my_dynamics(
    school_year: int | None = None, db: Session = Depends(get_db), student: Student = Depends(get_current_student)
):
    """The student's own learning dynamics. No class rank here on purpose —
    a place in the class is for teachers, not a number for a child to be
    measured by."""
    return dynamics_service.build_dynamics(db, student, school_year, include_rank=False)


@router.get("/me/subjects/{subject_id}/history", response_model=SubjectHistoryOut)
def get_subject_history(
    subject_id: int, db: Session = Depends(get_db), student: Student = Depends(get_current_student)
):
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fan topilmadi")

    stats = db.query(StudentSubjectStats).filter_by(student_id=student.id, subject_id=subject_id).first()
    timeline = [
        SubjectHistoryPointOut(
            exam_id=r.exam_id,
            exam_title=r.exam_title,
            exam_type=r.exam_type,
            score=r.score,
            max_score=r.max_score,
            date=r.submitted_at,
        )
        for r in ranking_service.subject_results(db, student.id, subject_id)
    ]

    return SubjectHistoryOut(
        subject_id=subject_id,
        subject_name=subject.name,
        exams_taken_count=stats.exams_taken_count if stats else 0,
        average_percent=float(stats.average_percent) if stats and stats.average_percent is not None else None,
        trend=stats.trend.value if stats and stats.trend else None,
        timeline=timeline,
    )
