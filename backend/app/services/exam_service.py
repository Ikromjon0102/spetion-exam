"""Exam authoring authorization + lifecycle transitions: draft -> review -> scheduled.

publish_exam(db, exam) enforces, server-side (never trust the frontend to
have checked this):
  - every question.needs_review is False
  - every mcq question has at least 2 options with exactly 1 is_correct=True
    (originally a hard "exactly 4" — relaxed on the user's explicit request
    so True/False, 3-option, 5-option etc. all work; a single correct
    answer is still required either way, that part wasn't up for debate)
  - exam.start_at < exam.end_at
  - exam.duration_minutes <= (end_at - start_at) in minutes
  - at least 1 question exists
On success: status='scheduled', published_at=now(), total_points recomputed.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.timeutil import aware
from app.models.attempt import AttemptStatus, ExamAttempt
from app.models.exam import Exam, ExamStatus, Question, QuestionType
from app.models.org import Class
from app.models.user import Subject, TeacherClassSubject, User, UserRole


def ensure_can_author_exam(db: Session, user: User, class_id: int, subject_id: int) -> None:
    """Raises 403 unless `user` is an admin, or a teacher assigned to teach
    `subject_id` to `class_id` via teacher_class_subjects."""
    if user.role == UserRole.admin:
        return
    if user.role != UserRole.teacher or user.teacher is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ruxsat yo'q")
    assigned = (
        db.query(TeacherClassSubject)
        .filter_by(teacher_id=user.teacher.id, class_id=class_id, subject_id=subject_id)
        .first()
    )
    if assigned is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu sinf/fan uchun ruxsatingiz yo'q",
        )


def ensure_can_manage_exam(db: Session, user: User, exam: Exam) -> None:
    """May `user` open this exam at all (see it, its questions, its attempts)?
    A nazorat exam: admin, or the teacher of its (class, subject). A chorak
    exam: admin, or a teacher of at least one of its blocks — what such a
    teacher may then *change* is narrower, see ensure_can_edit_section and
    ensure_exam_owner."""
    if not exam.is_chorak:
        ensure_can_author_exam(db, user, exam.class_id, exam.subject_id)
        return
    if user.role == UserRole.admin:
        return
    if not editable_section_ids(db, user, exam):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu imtihon uchun ruxsatingiz yo'q")


def editable_section_ids(db: Session, user: User, exam: Exam) -> set[int]:
    """The blocks of a chorak exam `user` may write questions for: all of
    them for an admin, for a teacher only the blocks whose subject they teach
    to the exam's class."""
    if user.role == UserRole.admin:
        return {s.id for s in exam.sections}
    if user.role != UserRole.teacher or user.teacher is None:
        return set()
    taught = {
        row[0]
        for row in db.query(TeacherClassSubject.subject_id).filter_by(
            teacher_id=user.teacher.id, class_id=exam.class_id
        )
    }
    return {s.id for s in exam.sections if s.subject_id in taught}


def results_scope(db: Session, user: User, exam: Exam) -> set[int] | None:
    """Whose results of this exam `user` may see. None = everything (the
    total and every block): any exam's manager for a nazorat exam; the admin
    or the class's homeroom teacher for a chorak one. A set = only those
    blocks of a chorak exam (a block's teacher sees their own subject, not
    the whole paper). Raises 403 when there is nothing they may see."""
    if not exam.is_chorak:
        ensure_can_manage_exam(db, user, exam)
        return None
    if user.role == UserRole.admin:
        return None
    if user.role == UserRole.teacher and user.teacher is not None:
        klass = db.get(Class, exam.class_id)
        if klass is not None and klass.homeroom_teacher_id == user.teacher.id:
            return None
        own = editable_section_ids(db, user, exam)
        if own:
            return own
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu imtihon natijalari uchun ruxsatingiz yo'q")


def ensure_exam_owner(db: Session, user: User, exam: Exam) -> None:
    """Exam-wide actions — schedule, publish, close, delete, duplicate,
    archive. On a chorak exam these belong to the admin alone: no single
    block's teacher owns the whole paper."""
    if exam.is_chorak:
        if user.role != UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Choraklik imtihonni faqat administrator boshqaradi",
            )
        return
    ensure_can_manage_exam(db, user, exam)


def ensure_can_edit_section(db: Session, user: User, exam: Exam, section_id: int | None) -> None:
    """Question-level edits. On a nazorat exam this is just
    ensure_can_manage_exam; on a chorak exam the question's block must be one
    of the user's own."""
    if not exam.is_chorak:
        ensure_can_manage_exam(db, user, exam)
        return
    if section_id is None or section_id not in editable_section_ids(db, user, exam):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu blok sizga biriktirilmagan")


def section_problem(section, questions: list[Question]) -> str | None:
    """Why a block isn't finished yet, or None if it is: the agreed number of
    questions, all reviewed, each well-formed."""
    if len(questions) != section.question_count:
        return f"{section.question_count} ta savol kerak, hozir {len(questions)} ta"
    for i, q in enumerate(questions, start=1):
        if q.needs_review:
            return f"{i}-savol hali tekshirilmagan"
        problem = _question_problem(q)
        if problem:
            return f"{i}-savol: {problem}"
    return None


def _question_problem(q: Question) -> str | None:
    if q.question_type == QuestionType.mcq:
        if len(q.options) < 2:
            return "kamida 2 ta variant bo'lishi kerak"
        if sum(1 for o in q.options if o.is_correct) != 1:
            return "aynan 1 ta to'g'ri javob bo'lishi kerak"
    elif q.question_type == QuestionType.short_answer:
        if not (q.reference_answer or "").strip():
            return "namunaviy javob kiritilmagan"
    return None


_STARTED_STATUSES = (AttemptStatus.in_progress, AttemptStatus.submitted, AttemptStatus.auto_submitted)


def exam_phase(exam: Exam, now: datetime | None = None) -> str:
    """Where an exam is in its life, derived from its time window — never read
    off Exam.status alone, which stays "scheduled" long after the window has
    closed (only a manual close ever sets "closed"). One of: draft, upcoming,
    live, finished. The SQL twin is admin_exams._phase_clause; keep in step."""
    now = now or datetime.now(timezone.utc)
    if exam.status in (ExamStatus.draft, ExamStatus.review):
        return "draft"
    if exam.status in (ExamStatus.closed, ExamStatus.archived):
        return "finished"
    if exam.start_at is None or exam.end_at is None:
        return "upcoming"
    if now < aware(exam.start_at):
        return "upcoming"
    if now < aware(exam.end_at):
        return "live"
    return "finished"


def archive_block_reason(exam: Exam, now: datetime | None = None) -> str | None:
    """None if the exam may be archived. A draft or a finished exam can; one
    that is still to come or running cannot (close or delete it instead)."""
    if exam.archived_at is not None:
        return "already_archived"
    if exam_phase(exam, now) not in ("draft", "finished"):
        return "not_finished"
    return None


def exam_ids_with_attempts(db: Session, exam_ids: list[int]) -> set[int]:
    """Batched form of has_attempts — which of these exams have a started
    attempt — so a list endpoint needs one query, not one per exam."""
    if not exam_ids:
        return set()
    rows = (
        db.query(ExamAttempt.exam_id)
        .filter(ExamAttempt.exam_id.in_(exam_ids), ExamAttempt.status.in_(_STARTED_STATUSES))
        .distinct()
    )
    return {row[0] for row in rows}


def has_attempts(db: Session, exam: Exam) -> bool:
    """True only if a student actually opened the exam.

    The lifecycle sweep (mark_expired_unstarted) creates an ExamAttempt row
    for every enrolled student once exam.end_at passes, even ones who never
    called /start — status=expired_unstarted (or a never-touched
    not_started row). Those rows must NOT count here, or an exam nobody
    ever took becomes permanently unelidable/unediable the moment its
    window closes."""
    return exam.id in exam_ids_with_attempts(db, [exam.id])


def ensure_no_attempts(db: Session, exam: Exam) -> None:
    """Question/option edits, schedule-field edits (duration/start/end/
    shuffle), and whole-exam deletion all share one rule: allowed on a
    draft *and* on an already-published (scheduled/active) exam, right up
    until the moment any student actually starts it. A started attempt
    snapshots the question/option order and, once submitted, its score —
    changing or removing the exam out from under that would desync a
    student's view or destroy a recorded grade, so this is the one hard
    line for all three operations."""
    if has_attempts(db, exam):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu imtihonni allaqachon boshlagan o'quvchilar bor, endi uni o'zgartirib yoki o'chirib bo'lmaydi",
        )


def recompute_total_points(db: Session, exam: Exam) -> None:
    # A direct query, not exam.questions — that in-memory collection can be
    # stale right after this same request added/removed a question (the
    # child's exam_id FK was set directly, not via the relationship, so the
    # parent's loaded collection doesn't auto-update).
    total = db.query(func.sum(Question.points)).filter_by(exam_id=exam.id).scalar()
    # Rounded: block weights are decimals (3.1, 2.1, 1.1) and thirty of them
    # summed as floats come out as 93.00000000000001.
    exam.total_points = round(float(total), 2) if total else None


def publish_exam(db: Session, exam: Exam) -> Exam:
    if exam.status not in (ExamStatus.draft, ExamStatus.review):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu imtihon allaqachon chop etilgan")

    if not exam.questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kamida 1 ta savol bo'lishi kerak")

    for q in exam.questions:
        if q.needs_review:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Savol #{q.order_index + 1} hali tekshirilmagan (needs_review)",
            )
        if q.question_type == QuestionType.mcq:
            if len(q.options) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Savol #{q.order_index + 1} kamida 2 ta variantga ega bo'lishi kerak",
                )
            correct_count = sum(1 for o in q.options if o.is_correct)
            if correct_count != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Savol #{q.order_index + 1} aynan 1 ta to'g'ri javobga ega bo'lishi kerak",
                )
        elif q.question_type == QuestionType.short_answer:
            # AI grading compares the student's answer against THIS, never
            # against the prompt alone — without it there's nothing to grade
            # against, so publish must not be allowed to skip it.
            if not (q.reference_answer or "").strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Savol #{q.order_index + 1} uchun namunaviy javob kiritilmagan",
                )

    if exam.is_chorak:
        if not exam.sections:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Imtihonda blok yo'q")
        names = dict(db.query(Subject.id, Subject.name).filter(Subject.id.in_([s.subject_id for s in exam.sections])))
        for section in exam.sections:
            label = names.get(section.subject_id, "")
            questions = [q for q in exam.questions if q.section_id == section.id]
            problem = section_problem(section, questions)
            if problem:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label} bloki: {problem}")
            if section.ready_at is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label} bloki hali tayyor deb belgilanmagan"
                )
            # The block's weight is the single source of truth for points.
            for q in questions:
                q.points = section.points_per_question
        if any(q.section_id is None for q in exam.questions):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Blokka biriktirilmagan savol bor")
        db.flush()

    if exam.start_at is None or exam.end_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Boshlanish va tugash vaqti belgilanmagan")
    if exam.start_at >= exam.end_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tugash vaqti boshlanishdan keyin bo'lishi kerak")
    window_minutes = (exam.end_at - exam.start_at).total_seconds() / 60
    if exam.duration_minutes > window_minutes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Davomiylik boshlanish va tugash orasidagi vaqtdan uzun bo'lmasligi kerak",
        )

    recompute_total_points(db, exam)
    exam.status = ExamStatus.scheduled
    exam.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(exam)
    return exam


def section_labels(sections, names: dict[int, str]) -> dict[int, str]:
    """{section_id: label} for the blocks of ONE chorak exam. A subject is
    normally one block ("Kimyo"), but a direction may sit the same subject as
    both an asosiy and a majburiy block (economics: Matematika 30x... and
    Matematika 10x...). Then the two would be indistinguishable on every tab,
    column and table, so those blocks get the kind appended:
    "Matematika (asosiy)" / "Matematika (majburiy)". Compute it over the
    exam's FULL block list — a block teacher's filtered view must still show
    the same label as everyone else."""
    count: dict[int, int] = {}
    for s in sections:
        count[s.subject_id] = count.get(s.subject_id, 0) + 1
    return {
        s.id: (
            f"{names.get(s.subject_id, '')} ({s.kind})"
            if count[s.subject_id] > 1
            else names.get(s.subject_id, "")
        )
        for s in sections
    }
