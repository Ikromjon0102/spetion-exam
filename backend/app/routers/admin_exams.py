"""Teacher/admin exam authoring: upload, parse status, review/edit, publish,
monitoring. See docs/spec.md sections 2-4.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.storage import download_exam_file, upload_exam_file, upload_question_image
from app.db.base import get_db
from app.dependencies import get_current_user, require_role
from app.models.attempt import AttemptStatus, ExamAttempt, StudentAnswer
from app.models.exam import (
    Exam,
    ExamStatus,
    ExamUpload,
    Question,
    QuestionOption,
    QuestionSource,
    QuestionType,
    UploadFileType,
    UploadStatus,
)
from app.models.org import Class
from app.models.user import Student, Subject, TeacherClassSubject, User, UserRole
from app.schemas.exam import (
    AttemptAnswerOverrideIn,
    AttemptAnswerReviewOut,
    AttemptMonitorOut,
    ExamCreate,
    ExamDetailOut,
    ExamDuplicateIn,
    ExamOut,
    ExamUpdate,
    ExamUploadOut,
    QuestionCreate,
    QuestionOptionOut,
    QuestionOptionUpdate,
    QuestionOut,
    QuestionUpdate,
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


def _exam_out(db: Session, exam: Exam) -> ExamOut:
    subject = db.get(Subject, exam.subject_id)
    klass = db.get(Class, exam.class_id)
    return ExamOut(
        id=exam.id,
        title=exam.title,
        subject_id=exam.subject_id,
        subject_name=subject.name if subject else "",
        class_id=exam.class_id,
        class_name=klass.display_name if klass else "",
        status=exam.status.value,
        start_at=exam.start_at,
        end_at=exam.end_at,
        duration_minutes=exam.duration_minutes,
        total_points=float(exam.total_points) if exam.total_points is not None else None,
        question_count=len(exam.questions),
        needs_review_count=sum(1 for q in exam.questions if q.needs_review),
        can_edit=not exam_service.has_attempts(db, exam),
    )


def _get_exam_or_404(db: Session, exam_id: int) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imtihon topilmadi")
    return exam


def _upload_out(db: Session, upload: ExamUpload) -> ExamUploadOut:
    exam = db.query(Exam).filter_by(exam_upload_id=upload.id).first()
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
    subject_id: int = Form(...),
    class_id: int = Form(...),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ("pdf", "docx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Faqat PDF yoki DOCX qabul qilinadi")

    exam_service.ensure_can_author_exam(db, user, class_id, subject_id)

    file_bytes = await file.read()
    storage_key = upload_exam_file(file_bytes, file.filename)

    upload = ExamUpload(
        uploaded_by_id=user.id,
        original_filename=file.filename,
        file_type=UploadFileType(ext),
        storage_key=storage_key,
        status=UploadStatus.pending,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    # .delay(), not celery_app.send_task(name, ...) — send_task-by-name
    # always opens a broker connection even under task_always_eager (a
    # Celery quirk), while calling the task object's own apply_async/delay
    # correctly short-circuits to an in-process call in eager dev mode.
    parse_exam_upload.delay(upload.id, subject_id, class_id, title)

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
        status=ExamStatus.draft,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return _exam_out(db, exam)


@router.get("", response_model=list[ExamOut])
def list_exams(
    exam_status: str | None = None,
    class_id: int | None = None,
    subject_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    query = db.query(Exam)
    if exam_status:
        query = query.filter(Exam.status == ExamStatus(exam_status))
    if class_id:
        query = query.filter(Exam.class_id == class_id)
    if subject_id:
        query = query.filter(Exam.subject_id == subject_id)
    exams = query.order_by(Exam.created_at.desc()).all()

    if user.role == UserRole.teacher:
        if user.teacher is None:
            return []
        allowed_pairs = {
            (a.class_id, a.subject_id)
            for a in db.query(TeacherClassSubject).filter_by(teacher_id=user.teacher.id)
        }
        exams = [e for e in exams if (e.class_id, e.subject_id) in allowed_pairs]

    return [_exam_out(db, e) for e in exams]


@router.get("/{exam_id}", response_model=ExamDetailOut)
def get_exam_detail(
    exam_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    base = _exam_out(db, exam)
    questions = [_question_out(q) for q in exam.questions]
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
    exam_service.ensure_can_manage_exam(db, user, source)

    target_class_ids = [cid for cid in dict.fromkeys(body.class_ids) if cid != source.class_id]
    if not target_class_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Kamida bitta boshqa sinf tanlang"
        )

    created: list[Exam] = []
    for class_id in target_class_ids:
        exam_service.ensure_can_author_exam(db, user, class_id, source.subject_id)

        new_exam = Exam(
            title=source.title,
            subject_id=source.subject_id,
            class_id=class_id,
            created_by_id=user.id,
            exam_upload_id=None,
            status=ExamStatus.draft,
            start_at=source.start_at,
            end_at=source.end_at,
            duration_minutes=source.duration_minutes,
            shuffle_questions=source.shuffle_questions,
            shuffle_options=source.shuffle_options,
        )
        db.add(new_exam)
        db.flush()

        for q in source.questions:
            new_question = Question(
                exam_id=new_exam.id,
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
    return [_exam_out(db, exam) for exam in created]


@router.put("/{exam_id}", response_model=ExamOut)
def update_exam(
    exam_id: int,
    body: ExamUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    exam_service.ensure_no_attempts(db, exam)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(exam, field, value)
    db.commit()
    db.refresh(exam)
    return _exam_out(db, exam)


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

    question = Question(
        exam_id=exam.id,
        order_index=len(exam.questions),
        question_type=QuestionType(body.question_type),
        prompt_text=body.prompt_text,
        points=body.points,
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

    for field, value in body.model_dump(exclude_unset=True).items():
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
    db.delete(question)
    db.flush()
    exam_service.recompute_total_points(db, exam)
    db.commit()


@router.post("/{exam_id}/publish", response_model=ExamOut)
def publish_exam_endpoint(
    exam_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    exam = exam_service.publish_exam(db, exam)
    return _exam_out(db, exam)


@router.post("/{exam_id}/close", response_model=ExamOut)
def close_exam(
    exam_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)
    if exam.status not in (ExamStatus.scheduled, ExamStatus.active):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu imtihonni yopib bo'lmaydi")
    exam.status = ExamStatus.closed
    db.commit()
    db.refresh(exam)
    return _exam_out(db, exam)


@router.get("/{exam_id}/attempts", response_model=list[AttemptMonitorOut])
def list_attempts(
    exam_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    exam = _get_exam_or_404(db, exam_id)
    exam_service.ensure_can_manage_exam(db, user, exam)

    students = db.query(Student).filter_by(class_id=exam.class_id).all()
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
                if s.id in attempts_by_student and attempts_by_student[s.id].score is not None
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
    out = []
    for q in sorted(exam.questions, key=lambda q: q.order_index):
        answer = answers_by_question.get(q.id)
        option_texts = {o.id: o.option_text for o in q.options}
        out.append(
            AttemptAnswerReviewOut(
                question_id=q.id,
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
