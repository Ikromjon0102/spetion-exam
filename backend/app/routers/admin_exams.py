"""Teacher/admin exam authoring: upload, parse status, review/edit, publish,
monitoring. See docs/spec.md sections 2-4.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi import Response as FastAPIResponse
from fastapi.responses import Response
from sqlalchemy import and_, case, exists, false, func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.storage import download_exam_file, upload_exam_file, upload_question_image
from app.db.base import get_db
from app.dependencies import get_current_user, require_role
from app.models.attempt import AttemptStatus, ExamAttempt, StudentAnswer
from app.models.exam import (
    Exam,
    ExamSection,
    ExamStatus,
    ExamType,
    ExamUpload,
    Question,
    QuestionOption,
    QuestionSource,
    QuestionType,
    UploadFileType,
    UploadStatus,
)
from app.models.org import Class
from app.models.user import Student, Subject, Teacher, TeacherClassSubject, User, UserRole
from app.schemas.exam import (
    AttemptAnswerOverrideIn,
    AttemptAnswerReviewOut,
    AttemptMonitorOut,
    ArchiveOldIn,
    ExamBulkResultOut,
    ExamBulkSkippedOut,
    ExamCreate,
    ExamDetailOut,
    ExamDuplicateIn,
    ExamIdsIn,
    ExamOut,
    ExamsSummaryOut,
    FacetOut,
    ExamUpdate,
    ExamUploadOut,
    QuestionCreate,
    QuestionOptionOut,
    QuestionOptionUpdate,
    QuestionOut,
    QuestionUpdate,
    SectionOut,
)
from app.services import exam_service, grading_service, ranking_service
from app.tasks.parsing_tasks import parse_exam_upload

router = APIRouter(prefix="/api/v1/admin/exams", tags=["admin-exams"])


def _question_out(question: Question) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        order_index=question.order_index,
        question_type=question.question_type.value,
        prompt_text=question.prompt_text,
        prompt_image_key=question.prompt_image_key,
        points=float(question.points),
        source=question.source.value,
        needs_review=question.needs_review,
        parse_confidence=question.parse_confidence,
        reference_answer=question.reference_answer,
        section_id=question.section_id,
        options=[
            QuestionOptionOut(
                id=o.id,
                order_index=o.order_index,
                option_text=o.option_text,
                option_image_key=o.option_image_key,
                is_correct=o.is_correct,
            )
            for o in question.options
        ],
    )


def _section_outs(db: Session, exams: list[Exam], user: User | None) -> dict[int, list[SectionOut]]:
    """The blocks of every chorak exam in `exams`, keyed by exam id, with each
    block's progress — built with a fixed number of queries for the whole
    list, like _exam_outs itself."""
    chorak = [e for e in exams if e.is_chorak]
    if not chorak:
        return {}
    exam_ids = [e.id for e in chorak]
    sections = (
        db.query(ExamSection).filter(ExamSection.exam_id.in_(exam_ids)).order_by(ExamSection.order_index).all()
    )
    subject_names = dict(db.query(Subject.id, Subject.name).filter(Subject.id.in_({s.subject_id for s in sections})))
    counts = {
        row.section_id: (row.total, int(row.pending))
        for row in db.query(
            Question.section_id,
            func.count(Question.id).label("total"),
            func.coalesce(func.sum(case((Question.needs_review.is_(True), 1), else_=0)), 0).label("pending"),
        )
        .filter(Question.exam_id.in_(exam_ids), Question.section_id.isnot(None))
        .group_by(Question.section_id)
    }
    class_ids = {e.class_id for e in chorak}
    teachers: dict[tuple[int, int], list[str]] = {}
    for class_id, subject_id, name in (
        db.query(TeacherClassSubject.class_id, TeacherClassSubject.subject_id, User.full_name)
        .join(Teacher, Teacher.id == TeacherClassSubject.teacher_id)
        .join(User, User.id == Teacher.user_id)
        .filter(TeacherClassSubject.class_id.in_(class_ids))
    ):
        teachers.setdefault((class_id, subject_id), []).append(name)

    is_admin = user is None or user.role == UserRole.admin
    taught: set[tuple[int, int]] = set()
    if not is_admin and user.teacher is not None:
        taught = {
            (a.class_id, a.subject_id) for a in db.query(TeacherClassSubject).filter_by(teacher_id=user.teacher.id)
        }
    class_of = {e.id: e.class_id for e in chorak}
    out: dict[int, list[SectionOut]] = {}
    for section in sections:
        class_id = class_of[section.exam_id]
        total, pending = counts.get(section.id, (0, 0))
        out.setdefault(section.exam_id, []).append(
            SectionOut(
                id=section.id,
                subject_id=section.subject_id,
                subject_name=subject_names.get(section.subject_id, ""),
                kind=section.kind,
                order_index=section.order_index,
                question_count=section.question_count,
                points_per_question=float(section.points_per_question),
                actual_count=total,
                needs_review_count=pending,
                is_ready=section.ready_at is not None,
                can_edit=is_admin or (class_id, section.subject_id) in taught,
                teacher_names=sorted(teachers.get((class_id, section.subject_id), [])),
            )
        )
    return out


def _exam_outs(db: Session, exams: list[Exam], user: User | None = None) -> list[ExamOut]:
    """Builds the ExamOut rows for a whole list with a fixed number of
    queries. This used to be one function per exam that issued a query each
    for the subject, the class, the full question collection (just to count
    it) and the attempt check — ~5 round trips per row, which is what made
    the exam list crawl once the school had dozens of exams.

    `user` decides the per-user flags (which blocks of a chorak exam they may
    edit, whether they hold the exam-wide actions); None means "as an admin"."""
    if not exams:
        return []
    exam_ids = [e.id for e in exams]
    subject_names = {
        row.id: row.name
        for row in db.query(Subject.id, Subject.name).filter(Subject.id.in_({e.subject_id for e in exams}))
    }
    class_names = {
        row.id: row.display_name
        for row in db.query(Class.id, Class.display_name).filter(Class.id.in_({e.class_id for e in exams}))
    }
    question_counts = {
        row.exam_id: (row.total, row.pending)
        for row in db.query(
            Question.exam_id,
            func.count(Question.id).label("total"),
            func.coalesce(func.sum(case((Question.needs_review.is_(True), 1), else_=0)), 0).label("pending"),
        )
        .filter(Question.exam_id.in_(exam_ids))
        .group_by(Question.exam_id)
    }
    started = exam_service.exam_ids_with_attempts(db, exam_ids)
    sections_by_exam = _section_outs(db, exams, user)
    is_admin = user is None or user.role == UserRole.admin

    now = datetime.now(timezone.utc)
    out = []
    for exam in exams:
        total, pending = question_counts.get(exam.id, (0, 0))
        sections = sections_by_exam.get(exam.id, [])
        if exam.is_chorak and not is_admin:
            # A block's teacher is told about their own blocks only.
            own = [s for s in sections if s.can_edit]
            total = sum(s.actual_count for s in own)
            pending = sum(s.needs_review_count for s in own)
        out.append(
            ExamOut(
                id=exam.id,
                title=exam.title,
                subject_id=exam.subject_id,
                subject_name=(
                    ", ".join(s.subject_name for s in sections)
                    if exam.is_chorak
                    else subject_names.get(exam.subject_id, "")
                ),
                class_id=exam.class_id,
                class_name=class_names.get(exam.class_id, ""),
                status=exam.status.value,
                start_at=exam.start_at,
                end_at=exam.end_at,
                duration_minutes=exam.duration_minutes,
                total_points=float(exam.total_points) if exam.total_points is not None else None,
                question_count=total,
                needs_review_count=int(pending),
                expected_question_count=(
                    sum(s.question_count for s in sections) if exam.is_chorak else exam.expected_question_count
                ),
                phase=exam_service.exam_phase(exam, now),
                archived_at=exam.archived_at,
                can_archive=exam_service.archive_block_reason(exam, now) is None,
                can_edit=exam.id not in started,
                exam_type=exam.exam_type,
                quarter=exam.quarter,
                sections=sections,
                can_administer=is_admin or not exam.is_chorak,
            )
        )
    return out


def _exam_out(db: Session, exam: Exam, user: User | None = None) -> ExamOut:
    return _exam_outs(db, [exam], user)[0]


def _get_exam_or_404(db: Session, exam_id: int) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imtihon topilmadi")
    return exam


def _upload_out(db: Session, upload: ExamUpload) -> ExamUploadOut:
    exam = (
        db.get(Exam, upload.target_exam_id)
        if upload.target_exam_id is not None
        else db.query(Exam).filter_by(exam_upload_id=upload.id).first()
    )
    return ExamUploadOut(
        id=upload.id,
        original_filename=upload.original_filename,
        file_type=upload.file_type.value,
        status=upload.status.value,
        parse_error=upload.parse_error,
        created_at=upload.created_at,
        exam_id=exam.id if exam else None,
    )


@router.post("/uploads", response_model=ExamUploadOut, status_code=status.HTTP_202_ACCEPTED)
async def create_upload(
    file: UploadFile = File(...),
    subject_id: int | None = Form(None),
    class_id: int | None = Form(None),
    title: str | None = Form(None),
    expected_question_count: int | None = Form(None),
    exam_id: int | None = Form(None),
    section_id: int | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    """Either a new exam from a file (subject_id + class_id), or — with
    exam_id + section_id — the file's questions imported into one block of an
    existing chorak exam."""
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ("pdf", "docx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Faqat PDF yoki DOCX qabul qilinadi")

    if exam_id is not None:
        target = _get_exam_or_404(db, exam_id)
        section = next((s for s in target.sections if s.id == section_id), None)
        if section is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blok topilmadi")
        exam_service.ensure_can_edit_section(db, user, target, section.id)
        exam_service.ensure_no_attempts(db, target)
        subject_id, class_id = section.subject_id, target.class_id
    elif subject_id is None or class_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Sinf va fan ko'rsatilmagan")
    else:
        exam_service.ensure_can_author_exam(db, user, class_id, subject_id)

    file_bytes = await file.read()
    storage_key = upload_exam_file(file_bytes, file.filename)

    upload = ExamUpload(
        uploaded_by_id=user.id,
        original_filename=file.filename,
        file_type=UploadFileType(ext),
        storage_key=storage_key,
        status=UploadStatus.pending,
        target_exam_id=exam_id,
        target_section_id=section_id if exam_id is not None else None,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    # .delay(), not celery_app.send_task(name, ...) — send_task-by-name
    # always opens a broker connection even under task_always_eager (a
    # Celery quirk), while calling the task object's own apply_async/delay
    # correctly short-circuits to an in-process call in eager dev mode.
    parse_exam_upload.delay(upload.id, subject_id, class_id, title, expected_question_count)

    return _upload_out(db, upload)


@router.get("/uploads/{upload_id}", response_model=ExamUploadOut)
def get_upload_status(
    upload_id: int, db: Session = Depends(get_db), _user: User = Depends(require_role("teacher", "admin"))
):
    upload = db.get(ExamUpload, upload_id)
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Yuklama topilmadi")
    return _upload_out(db, upload)


@router.post("", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
def create_exam(
    body: ExamCreate, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    exam_service.ensure_can_author_exam(db, user, body.class_id, body.subject_id)
    exam = Exam(
        title=body.title,
        subject_id=body.subject_id,
        class_id=body.class_id,
        created_by_id=user.id,
        exam_upload_id=body.exam_upload_id,
        expected_question_count=body.expected_question_count,
        status=ExamStatus.draft,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return _exam_out(db, exam, user)


def visible_exams_query(db: Session, user: User):
    """Every exam `user` may see, as a query so callers can filter, count and
    page in SQL: all of them for an admin, only the (class, subject) pairs they
    teach for a teacher. Shared by the exam list, its folder counts, the bulk
    archive actions and the dashboard so they can never disagree about scope."""
    query = db.query(Exam)
    if user.role == UserRole.teacher:
        pairs = (
            [(a.class_id, a.subject_id) for a in db.query(TeacherClassSubject).filter_by(teacher_id=user.teacher.id)]
            if user.teacher is not None
            else []
        )
        if not pairs:
            return query.filter(false())
        # A nazorat exam belongs to its (class, subject); a chorak exam is
        # visible to the teacher of any one of its blocks.
        own_nazorat = and_(
            Exam.exam_type == ExamType.nazorat.value,
            or_(*[and_(Exam.class_id == c, Exam.subject_id == s) for c, s in pairs]),
        )
        own_block = and_(
            Exam.exam_type == ExamType.chorak.value,
            exists().where(
                and_(
                    ExamSection.exam_id == Exam.id,
                    or_(*[and_(Exam.class_id == c, ExamSection.subject_id == s) for c, s in pairs]),
                )
            ),
        )
        query = query.filter(or_(own_nazorat, own_block))
    return query


def _phase_clause(phase: str, now: datetime):
    """SQL twin of exam_service.exam_phase — keep the two in step."""
    live_statuses = [ExamStatus.scheduled, ExamStatus.active]
    if phase == "draft":
        return Exam.status.in_([ExamStatus.draft, ExamStatus.review])
    if phase == "upcoming":
        return and_(Exam.status.in_(live_statuses), or_(Exam.start_at.is_(None), Exam.start_at > now))
    if phase == "live":
        return and_(Exam.status.in_(live_statuses), Exam.start_at <= now, Exam.end_at > now)
    if phase == "finished":
        return or_(
            Exam.status.in_([ExamStatus.closed, ExamStatus.archived]),
            and_(Exam.status.in_(live_statuses), Exam.start_at.isnot(None), Exam.end_at <= now),
        )
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Noma'lum holat")


def _newest_first():
    # Drafts have no start yet — place them by when they were created.
    return func.coalesce(Exam.start_at, Exam.created_at).desc()


def visible_exams(
    db: Session,
    user: User,
    exam_status: str | None = None,
    class_id: int | None = None,
    subject_id: int | None = None,
) -> list[Exam]:
    """The non-archived exams `user` may see, newest first (the dashboard's
    view of "my exams")."""
    query = visible_exams_query(db, user).filter(Exam.archived_at.is_(None))
    if exam_status:
        query = query.filter(Exam.status == ExamStatus(exam_status))
    if class_id:
        query = query.filter(Exam.class_id == class_id)
    if subject_id:
        query = query.filter(Exam.subject_id == subject_id)
    return query.order_by(_newest_first(), Exam.id.desc()).all()


@router.get("", response_model=list[ExamOut])
def list_exams(
    response: FastAPIResponse,
    exam_status: str | None = None,
    class_id: int | None = None,
    subject_id: int | None = None,
    phase: str | None = None,
    q: str | None = None,
    needs_review: bool = False,
    archived: bool = False,
    exam_type: str | None = None,
    limit: int | None = Query(None, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    """Filterable, pageable list. `archived=false` (the default) is the working
    view; `archived=true` is the archive. The unpaged total is returned in the
    X-Total-Count header so the body stays a plain list. Omitting `limit`
    returns everything that matches (the dashboard relies on that)."""
    query = visible_exams_query(db, user)
    query = query.filter(Exam.archived_at.isnot(None) if archived else Exam.archived_at.is_(None))
    if exam_status:
        query = query.filter(Exam.status == ExamStatus(exam_status))
    if class_id:
        query = query.filter(Exam.class_id == class_id)
    if subject_id:
        query = query.filter(Exam.subject_id == subject_id)
    if phase:
        query = query.filter(_phase_clause(phase, datetime.now(timezone.utc)))
    if exam_type:
        query = query.filter(Exam.exam_type == exam_type)
    if q and q.strip():
        query = query.filter(Exam.title.ilike(f"%{q.strip()}%"))
    if needs_review:
        query = query.filter(exists().where(and_(Question.exam_id == Exam.id, Question.needs_review.is_(True))))

    response.headers["X-Total-Count"] = str(query.count())
    query = query.order_by(_newest_first(), Exam.id.desc()).offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return _exam_outs(db, query.all(), user)


@router.get("/summary", response_model=ExamsSummaryOut)
def exams_summary(
    archived: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    """The "folders": how many exams per subject and per class in the working
    view (or the archive), plus the size of both tabs. Counted in SQL over the
    exams this user may see."""
    base = visible_exams_query(db, user)
    current = base.filter(Exam.archived_at.is_(None)).count()
    archived_total = base.filter(Exam.archived_at.isnot(None)).count()
    scoped = base.filter(Exam.archived_at.isnot(None) if archived else Exam.archived_at.is_(None))

    def facets(column, model, name_column) -> list[FacetOut]:
        rows = scoped.with_entities(column, func.count(Exam.id)).group_by(column).all()
        names = (
            dict(db.query(model.id, name_column).filter(model.id.in_([r[0] for r in rows])).all()) if rows else {}
        )
        return sorted(
            (FacetOut(id=r[0], name=names.get(r[0], ""), count=r[1]) for r in rows),
            key=lambda f: f.name.lower(),
        )

    return ExamsSummaryOut(
        current=current,
        archived=archived_total,
        subjects=facets(Exam.subject_id, Subject, Subject.name),
        classes=facets(Exam.class_id, Class, Class.display_name),
    )


def _bulk_archive_change(db: Session, user: User, exam_ids: list[int], *, archive: bool) -> ExamBulkResultOut:
    """Archive or restore several exams, each checked on its own: one that
    can't be changed (no access, still running, wrong state) is reported back
    as skipped instead of failing the whole batch. Only the archived_at flag
    moves — attempts, rankings and student stats are never touched."""
    now = datetime.now(timezone.utc)
    found = {e.id: e for e in db.query(Exam).filter(Exam.id.in_(exam_ids)).all()}
    changed: list[int] = []
    skipped: list[ExamBulkSkippedOut] = []
    for exam_id in dict.fromkeys(exam_ids):
        exam = found.get(exam_id)
        if exam is None:
            skipped.append(ExamBulkSkippedOut(exam_id=exam_id, reason="not_found"))
            continue
        try:
            exam_service.ensure_exam_owner(db, user, exam)
        except HTTPException:
            skipped.append(ExamBulkSkippedOut(exam_id=exam_id, reason="forbidden"))
            continue
        if archive:
            reason = exam_service.archive_block_reason(exam, now)
            if reason is not None:
                skipped.append(ExamBulkSkippedOut(exam_id=exam_id, reason=reason))
                continue
            exam.archived_at = now
        else:
            if exam.archived_at is None:
                skipped.append(ExamBulkSkippedOut(exam_id=exam_id, reason="not_archived"))
                continue
            exam.archived_at = None
        changed.append(exam_id)
    db.commit()
    return ExamBulkResultOut(changed=changed, skipped=skipped)


@router.post("/archive", response_model=ExamBulkResultOut)
def archive_exams(
    body: ExamIdsIn, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    return _bulk_archive_change(db, user, body.exam_ids, archive=True)


@router.post("/restore", response_model=ExamBulkResultOut)
def restore_exams(
    body: ExamIdsIn, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    return _bulk_archive_change(db, user, body.exam_ids, archive=False)


@router.post("/archive-old", response_model=ExamBulkResultOut)
def archive_old_exams(
    body: ArchiveOldIn, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    """Archives every exam the caller can see whose window ended more than
    `days` days ago — the weekly "clear last week's out of the way" action."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=body.days)
    ids = [
        e.id
        for e in visible_exams_query(db, user).filter(
            Exam.archived_at.is_(None),
            Exam.status.in_([ExamStatus.scheduled, ExamStatus.active, ExamStatus.closed]),
            Exam.end_at.isnot(None),
            Exam.end_at < cutoff,
        )
    ]
    if not ids:
        return ExamBulkResultOut(changed=[])
    return _bulk_archive_change(db, user, ids, archive=True)


@router.get("/{exam_id}", response_model=ExamDetailOut)
def get_exam_detail(
    exam_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    base = _exam_out(db, exam, user)
    questions = exam.questions
    if exam.is_chorak:
        # A block's teacher gets their own blocks' questions, never a
        # colleague's — the other blocks are not theirs to read before the exam.
        own = exam_service.editable_section_ids(db, user, exam)
        questions = [q for q in questions if q.section_id in own]
    questions = [_question_out(q) for q in questions]
    return ExamDetailOut(**base.model_dump(), questions=questions)


@router.post("/{exam_id}/duplicate", response_model=list[ExamOut])
def duplicate_exam(
    exam_id: int,
    body: ExamDuplicateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    """A teacher who gives the identical lesson/exam to several parallel
    classes (e.g. 7B and 7R) shouldn't have to re-upload/re-author the same
    questions per class — copies this exam's full content (every question,
    every option, images by storage-key reference since the underlying
    files are immutable, schedule/shuffle settings) into one brand-new
    Exam per target class_id. Each new exam starts as a fresh draft (not
    auto-published) so the teacher can still double-check/adjust each
    copy's schedule before it goes live; needs_review carries over as-is,
    so a copy of an already-reviewed exam can be published immediately.
    Every target class is independently authorization-checked via
    ensure_can_author_exam — same rule as creating a fresh exam there,
    so a teacher can only duplicate into classes they actually teach this
    subject in (admin is unrestricted, as usual)."""
    source = _get_exam_or_404(db, exam_id)
    exam_service.ensure_exam_owner(db, user, source)

    target_class_ids = [cid for cid in dict.fromkeys(body.class_ids) if cid != source.class_id]
    if not target_class_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Kamida bitta boshqa sinf tanlang"
        )

    created: list[Exam] = []
    for class_id in target_class_ids:
        if not source.is_chorak:  # a chorak exam is admin-only, checked above
            exam_service.ensure_can_author_exam(db, user, class_id, source.subject_id)

        new_exam = Exam(
            title=source.title,
            subject_id=source.subject_id,
            class_id=class_id,
            created_by_id=user.id,
            exam_upload_id=None,
            expected_question_count=source.expected_question_count,
            status=ExamStatus.draft,
            start_at=source.start_at,
            end_at=source.end_at,
            duration_minutes=source.duration_minutes,
            shuffle_questions=source.shuffle_questions,
            shuffle_options=source.shuffle_options,
        )
        new_exam.exam_type = source.exam_type
        new_exam.quarter = source.quarter
        db.add(new_exam)
        db.flush()

        # A chorak exam's blocks come along; each copy's blocks start
        # "not ready" so that class's own teachers confirm them.
        section_map: dict[int, int] = {}
        for section in source.sections:
            new_section = ExamSection(
                exam_id=new_exam.id,
                subject_id=section.subject_id,
                order_index=section.order_index,
                kind=section.kind,
                question_count=section.question_count,
                points_per_question=section.points_per_question,
            )
            db.add(new_section)
            db.flush()
            section_map[section.id] = new_section.id

        for q in source.questions:
            new_question = Question(
                exam_id=new_exam.id,
                section_id=section_map.get(q.section_id) if q.section_id else None,
                order_index=q.order_index,
                question_type=q.question_type,
                prompt_text=q.prompt_text,
                prompt_image_key=q.prompt_image_key,
                points=q.points,
                source=q.source,
                needs_review=q.needs_review,
                parse_confidence=q.parse_confidence,
                reference_answer=q.reference_answer,
            )
            db.add(new_question)
            db.flush()
            for opt in q.options:
                db.add(
                    QuestionOption(
                        question_id=new_question.id,
                        order_index=opt.order_index,
                        option_text=opt.option_text,
                        is_correct=opt.is_correct,
                        option_image_key=opt.option_image_key,
                    )
                )

        db.flush()
        exam_service.recompute_total_points(db, new_exam)
        created.append(new_exam)

    db.commit()
    for exam in created:
        db.refresh(exam)
    return _exam_outs(db, created, user)


@router.put("/{exam_id}", response_model=ExamOut)
def update_exam(
    exam_id: int,
    body: ExamUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_exam_owner(db, user, exam)
    exam_service.ensure_no_attempts(db, exam)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(exam, field, value)
    db.commit()
    db.refresh(exam)
    return _exam_out(db, exam, user)


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    """Same block/allow rule as editing for a teacher: a draft, review, or
    already-scheduled/published exam can be deleted right up until a
    student actually starts it (ensure_no_attempts) — a started attempt's
    grade would otherwise vanish along with the exam. Admin gets an
    explicit override: real attempts are unwound first (one call to
    ranking_service.remove_attempt per student, which also fixes up
    ExamRanking/StudentSubjectStats — see that function's docstring) so
    admin can force-delete an exam even after students took it, e.g.
    cleaning up a mistakenly-published test exam. Cascades to the exam's
    own Question/QuestionOption rows (Exam.questions now has
    cascade="all, delete-orphan"); ExamUpload, if any, is left as-is —
    harmless once orphaned, same as elsewhere in this router."""
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_exam_owner(db, user, exam)
    if user.role == UserRole.admin:
        student_ids = [row[0] for row in db.query(ExamAttempt.student_id).filter_by(exam_id=exam.id).distinct()]
        for student_id in student_ids:
            ranking_service.remove_attempt(db, exam.id, student_id)
    else:
        exam_service.ensure_no_attempts(db, exam)
    db.delete(exam)
    db.commit()


@router.post("/{exam_id}/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
def add_question(
    exam_id: int,
    body: QuestionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    exam_service.ensure_no_attempts(db, exam)

    points = body.points
    section_id = None
    if exam.is_chorak:
        section = next((s for s in exam.sections if s.id == body.section_id), None)
        if section is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Savol qaysi blokka tegishli ekani ko'rsatilmagan")
        exam_service.ensure_can_edit_section(db, user, exam, section.id)
        section_id = section.id
        points = float(section.points_per_question)

    question = Question(
        exam_id=exam.id,
        section_id=section_id,
        order_index=len(exam.questions),
        question_type=QuestionType(body.question_type),
        prompt_text=body.prompt_text,
        points=points,
        reference_answer=body.reference_answer,
        source=QuestionSource.manual,
        needs_review=False,  # teacher-authored directly, nothing parsed to review
    )
    db.add(question)
    db.flush()
    for i, opt in enumerate(body.options):
        db.add(
            QuestionOption(question_id=question.id, order_index=i, option_text=opt.option_text, is_correct=opt.is_correct)
        )
    db.flush()
    exam_service.recompute_total_points(db, exam)
    db.commit()
    db.refresh(question)
    return _question_out(question)


@router.put("/{exam_id}/questions/{question_id}", response_model=QuestionOut)
def update_question(
    exam_id: int,
    question_id: int,
    body: QuestionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    exam_service.ensure_no_attempts(db, exam)

    question = db.get(Question, question_id)
    if question is None or question.exam_id != exam_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")
    exam_service.ensure_can_edit_section(db, user, exam, question.section_id)

    changes = body.model_dump(exclude_unset=True)
    if question.section_id is not None:
        # In a chorak block every question is worth the block's weight.
        changes.pop("points", None)
    for field, value in changes.items():
        setattr(question, field, value)
    db.flush()
    exam_service.recompute_total_points(db, exam)
    db.commit()
    db.refresh(question)
    return _question_out(question)


@router.put("/{exam_id}/questions/{question_id}/options/{option_id}", response_model=QuestionOptionOut)
def update_question_option(
    exam_id: int,
    question_id: int,
    option_id: int,
    body: QuestionOptionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    exam_service.ensure_no_attempts(db, exam)

    option = db.get(QuestionOption, option_id)
    if option is None or option.question_id != question_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant topilmadi")
    question = db.get(Question, question_id)
    if question is None or question.exam_id != exam_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")
    exam_service.ensure_can_edit_section(db, user, exam, question.section_id)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(option, field, value)
    db.commit()
    db.refresh(option)
    return QuestionOptionOut(
        id=option.id,
        order_index=option.order_index,
        option_text=option.option_text,
        option_image_key=option.option_image_key,
        is_correct=option.is_correct,
    )


_ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_MAX_IMAGE_BYTES = 8 * 1024 * 1024  # a pasted screenshot, not a scan dump
_IMAGE_MEDIA_TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}


async def _read_and_validate_image(file: UploadFile) -> bytes:
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Faqat rasm fayllari qabul qilinadi")
    file_bytes = await file.read()
    if len(file_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rasm juda katta (8MB dan oshmasin)")
    return file_bytes


def _option_out(option: QuestionOption) -> QuestionOptionOut:
    return QuestionOptionOut(
        id=option.id,
        order_index=option.order_index,
        option_text=option.option_text,
        option_image_key=option.option_image_key,
        is_correct=option.is_correct,
    )


@router.post("/{exam_id}/questions/{question_id}/prompt-image", response_model=QuestionOut)
async def set_question_prompt_image(
    exam_id: int,
    question_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    """A teacher pastes a screenshot (e.g. a formula too complex/slow to
    retype) straight into the prompt field instead of typing it — see
    Question.prompt_image_key. Doesn't touch prompt_text; the frontend
    shows the image instead of the text when this key is set, but the text
    (even if just left empty) is never overwritten here."""
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    exam_service.ensure_no_attempts(db, exam)

    question = db.get(Question, question_id)
    if question is None or question.exam_id != exam_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")
    exam_service.ensure_can_edit_section(db, user, exam, question.section_id)

    file_bytes = await _read_and_validate_image(file)
    question.prompt_image_key = upload_question_image(file_bytes, file.content_type)
    db.commit()
    db.refresh(question)
    return _question_out(question)


@router.delete("/{exam_id}/questions/{question_id}/prompt-image", response_model=QuestionOut)
def clear_question_prompt_image(
    exam_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    exam_service.ensure_no_attempts(db, exam)

    question = db.get(Question, question_id)
    if question is None or question.exam_id != exam_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")
    exam_service.ensure_can_edit_section(db, user, exam, question.section_id)
    question.prompt_image_key = None
    db.commit()
    db.refresh(question)
    return _question_out(question)


@router.post("/{exam_id}/questions/{question_id}/options/{option_id}/image", response_model=QuestionOptionOut)
async def set_option_image(
    exam_id: int,
    question_id: int,
    option_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    exam_service.ensure_no_attempts(db, exam)

    option = db.get(QuestionOption, option_id)
    if option is None or option.question_id != question_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant topilmadi")
    question = db.get(Question, question_id)
    if question is None or question.exam_id != exam_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")
    exam_service.ensure_can_edit_section(db, user, exam, question.section_id)

    file_bytes = await _read_and_validate_image(file)
    option.option_image_key = upload_question_image(file_bytes, file.content_type)
    db.commit()
    db.refresh(option)
    return _option_out(option)


@router.delete("/{exam_id}/questions/{question_id}/options/{option_id}/image", response_model=QuestionOptionOut)
def clear_option_image(
    exam_id: int,
    question_id: int,
    option_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    exam_service.ensure_no_attempts(db, exam)

    option = db.get(QuestionOption, option_id)
    if option is None or option.question_id != question_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant topilmadi")
    question = db.get(Question, question_id)
    if question is None or question.exam_id != exam_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")
    exam_service.ensure_can_edit_section(db, user, exam, question.section_id)
    option.option_image_key = None
    db.commit()
    db.refresh(option)
    return _option_out(option)


@router.get("/uploads/image/{key:path}")
def get_question_image(key: str, _user: User = Depends(get_current_user)):
    """Serves a pasted question/option image back for display. Behind
    plain auth (any logged-in role), not per-exam ownership-checked — same
    looseness as the rest of this app's authenticated-but-not-finely-scoped
    endpoints; the key itself is an unguessable UUID either way. <img> tags
    can't send an Authorization header, so the frontend fetches this as a
    blob and builds an object URL rather than using the URL directly as
    `src` — see AuthedImage.tsx."""
    if not key.startswith("question-images/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topilmadi")
    try:
        file_bytes = download_exam_file(key)
    except (FileNotFoundError, OSError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topilmadi")
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topilmadi")
    ext = key.rsplit(".", 1)[-1].lower()
    return Response(content=file_bytes, media_type=_IMAGE_MEDIA_TYPES.get(ext, "application/octet-stream"))


@router.delete("/{exam_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    exam_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    exam_service.ensure_no_attempts(db, exam)

    question = db.get(Question, question_id)
    if question is None or question.exam_id != exam_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")
    exam_service.ensure_can_edit_section(db, user, exam, question.section_id)
    db.delete(question)
    db.flush()
    exam_service.recompute_total_points(db, exam)
    db.commit()


@router.post("/{exam_id}/publish", response_model=ExamOut)
def publish_exam_endpoint(
    exam_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_exam_owner(db, user, exam)
    exam = exam_service.publish_exam(db, exam)
    return _exam_out(db, exam, user)


@router.post("/{exam_id}/close", response_model=ExamOut)
def close_exam(
    exam_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_exam_owner(db, user, exam)
    if exam.status not in (ExamStatus.scheduled, ExamStatus.active):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu imtihonni yopib bo'lmaydi")
    exam.status = ExamStatus.closed
    db.commit()
    db.refresh(exam)
    return _exam_out(db, exam, user)


@router.get("/{exam_id}/attempts", response_model=list[AttemptMonitorOut])
def list_attempts(
    exam_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    exam = _get_exam_or_404(db, exam_id)
    # A block's teacher sees who has sat a chorak exam but not the paper's
    # total — only their own block's scores (GET .../section-results).
    shows_total = exam_service.results_scope(db, user, exam) is None

    students = db.query(Student).options(joinedload(Student.user)).filter_by(class_id=exam.class_id).all()
    attempts_by_student = {a.student_id: a for a in db.query(ExamAttempt).filter_by(exam_id=exam_id)}

    return [
        AttemptMonitorOut(
            student_id=s.id,
            full_name=s.user.full_name,
            status=(attempts_by_student[s.id].status.value if s.id in attempts_by_student else "not_started"),
            started_at=attempts_by_student[s.id].started_at if s.id in attempts_by_student else None,
            deadline_at=attempts_by_student[s.id].deadline_at if s.id in attempts_by_student else None,
            submitted_at=attempts_by_student[s.id].submitted_at if s.id in attempts_by_student else None,
            score=(
                float(attempts_by_student[s.id].score)
                if shows_total and s.id in attempts_by_student and attempts_by_student[s.id].score is not None
                else None
            ),
        )
        for s in students
    ]


@router.get("/{exam_id}/attempts/{student_id}", response_model=AttemptMonitorOut)
def get_attempt_detail(
    exam_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)

    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="O'quvchi topilmadi")
    attempt = db.query(ExamAttempt).filter_by(exam_id=exam_id, student_id=student_id).first()
    return AttemptMonitorOut(
        student_id=student.id,
        full_name=student.user.full_name,
        status=(attempt.status.value if attempt else "not_started"),
        started_at=attempt.started_at if attempt else None,
        deadline_at=attempt.deadline_at if attempt else None,
        submitted_at=attempt.submitted_at if attempt else None,
        score=float(attempt.score) if attempt and attempt.score is not None else None,
    )


@router.delete("/{exam_id}/attempts/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attempt(
    exam_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """Admin-only (not teacher) — removes one student's attempt at this
    exam (e.g. a staff member's own test run), including its answers and
    ExamRanking row, and re-derives that student's StudentSubjectStats and
    the rest of the class's ranks from what's left. See
    ranking_service.remove_attempt for why this can't be a raw DB delete:
    those derived tables don't update themselves."""
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    if not ranking_service.remove_attempt(db, exam_id, student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bu o'quvchining urinishi topilmadi")


def _get_graded_attempt_or_404(db: Session, exam_id: int, student_id: int) -> ExamAttempt:
    attempt = db.query(ExamAttempt).filter_by(exam_id=exam_id, student_id=student_id).first()
    if attempt is None or attempt.status not in (AttemptStatus.submitted, AttemptStatus.auto_submitted):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bu urinish hali topshirilmagan")
    return attempt


@router.get("/{exam_id}/attempts/{student_id}/answers", response_model=list[AttemptAnswerReviewOut])
def get_attempt_answers(
    exam_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    """Per-question grading detail for one student's submitted attempt —
    backs the short-answer review UI (ExamReviewEditor's "Natijalarni
    tekshirish" tab): the teacher sees the student's answer_text, the AI's
    points_awarded/feedback, and the reference_answer it graded against, so
    they can judge the AI's call before overriding it. MCQ rows are
    included too (selected_option_text only, no AI fields) so the teacher
    doesn't need a second endpoint to see the whole attempt."""
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    attempt = _get_graded_attempt_or_404(db, exam_id, student_id)

    answers_by_question = {a.question_id: a for a in attempt.answers}
    questions = sorted(exam.questions, key=lambda q: q.order_index)
    if exam.is_chorak:
        own = exam_service.editable_section_ids(db, user, exam)
        questions = [q for q in questions if q.section_id in own]
    out = []
    for q in questions:
        answer = answers_by_question.get(q.id)
        option_texts = {o.id: o.option_text for o in q.options}
        out.append(
            AttemptAnswerReviewOut(
                question_id=q.id,
                section_id=q.section_id,
                correct_option_text=next((o.option_text for o in q.options if o.is_correct), None),
                question_type=q.question_type.value,
                prompt_text=q.prompt_text,
                points=float(q.points),
                reference_answer=q.reference_answer,
                selected_option_id=answer.selected_option_id if answer else None,
                selected_option_text=(
                    option_texts.get(answer.selected_option_id) if answer and answer.selected_option_id else None
                ),
                answer_text=answer.answer_text if answer else None,
                is_correct=answer.is_correct if answer else None,
                points_awarded=(
                    float(answer.points_awarded) if answer and answer.points_awarded is not None else None
                ),
                ai_feedback=answer.ai_feedback if answer else None,
                graded_by=answer.graded_by if answer else None,
            )
        )
    return out


@router.put(
    "/{exam_id}/attempts/{student_id}/answers/{question_id}",
    response_model=AttemptAnswerReviewOut,
)
def override_attempt_answer(
    exam_id: int,
    student_id: int,
    question_id: int,
    body: AttemptAnswerOverrideIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    """A teacher overrides one answer's points_awarded — the AI grade counts
    immediately on submit (see grading_service/ai_grading_service), but the
    user's explicit design lets a teacher go back and correct it afterward.
    Uses grading_service.recompute_score_from_answers (sums existing
    points_awarded), not grade_attempt, so this doesn't re-run AI grading
    over every other answer and silently discard past overrides."""
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    attempt = _get_graded_attempt_or_404(db, exam_id, student_id)

    question = db.get(Question, question_id)
    if question is None or question.exam_id != exam_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savol topilmadi")
    exam_service.ensure_can_edit_section(db, user, exam, question.section_id)
    if body.points_awarded < 0 or body.points_awarded > float(question.points):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ball 0 va {question.points} oralig'ida bo'lishi kerak",
        )

    answer = db.query(StudentAnswer).filter_by(attempt_id=attempt.id, question_id=question_id).first()
    if answer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bu savolga javob topilmadi")

    answer.points_awarded = body.points_awarded
    answer.is_correct = body.points_awarded >= float(question.points)
    answer.graded_by = "teacher"
    db.commit()
    db.refresh(answer)

    grading_service.recompute_score_from_answers(db, attempt)
    ranking_service.recompute_for_student(db, attempt.exam_id, attempt.student_id)

    option_texts = {o.id: o.option_text for o in question.options}
    return AttemptAnswerReviewOut(
        question_id=question.id,
        question_type=question.question_type.value,
        prompt_text=question.prompt_text,
        points=float(question.points),
        reference_answer=question.reference_answer,
        selected_option_id=answer.selected_option_id,
        selected_option_text=option_texts.get(answer.selected_option_id) if answer.selected_option_id else None,
        answer_text=answer.answer_text,
        is_correct=answer.is_correct,
        points_awarded=float(answer.points_awarded) if answer.points_awarded is not None else None,
        ai_feedback=answer.ai_feedback,
        graded_by=answer.graded_by,
    )
