"""Choraklik (end-of-quarter) exams: one sitting made of subject blocks, like
the national university entrance test — e.g. Kimyo 30 x 3.1, Biologiya
30 x 2.1, three compulsory subjects 10 x 1.1 each = 189 points, 3 hours.

  - Templates: the reusable block layout per direction, admin-only.
  - Creating a chorak exam: admin picks a template and classes; one draft
    exam with its blocks is created per class.
  - Each block is then filled in by the teacher who teaches that subject to
    that class (the ordinary question endpoints in admin_exams.py, scoped per
    block), who marks it ready here. The admin publishes once all are ready.
  - Block-by-block results.

Registered before admin_exams.router so "/exams/chorak" and
"/exams/templates" are not swallowed by its "/exams/{exam_id}".
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.db.base import get_db
from app.dependencies import require_role
from app.models.attempt import AttemptSectionScore, AttemptStatus, ExamAttempt
from app.models.exam import (
    Exam,
    ExamSection,
    ExamStatus,
    ExamTemplate,
    ExamTemplateSection,
    ExamType,
    Question,
)
from app.models.org import Class
from app.models.user import Student, Subject, User
from app.routers.admin_exams import _exam_out, _exam_outs, _get_exam_or_404
from app.schemas.exam import (
    ChorakCreateIn,
    ExamOut,
    SectionReadyIn,
    SectionResultColumnOut,
    SectionResultRowOut,
    SectionResultsOut,
    TemplateIn,
    TemplateOut,
    TemplateSectionOut,
)
from app.services import exam_service

router = APIRouter(prefix="/api/v1/admin/exams", tags=["admin-chorak"])


def _template_out(db: Session, template: ExamTemplate) -> TemplateOut:
    names = dict(
        db.query(Subject.id, Subject.name).filter(Subject.id.in_([s.subject_id for s in template.sections]))
    )
    return TemplateOut(
        id=template.id,
        name=template.name,
        duration_minutes=template.duration_minutes,
        total_questions=sum(s.question_count for s in template.sections),
        total_points=round(sum(s.question_count * float(s.points_per_question) for s in template.sections), 2),
        sections=[
            TemplateSectionOut(
                id=s.id,
                subject_id=s.subject_id,
                subject_name=names.get(s.subject_id, ""),
                kind=s.kind,
                order_index=s.order_index,
                question_count=s.question_count,
                points_per_question=float(s.points_per_question),
            )
            for s in template.sections
        ],
    )


def _check_template_body(db: Session, body: TemplateIn, template_id: int | None) -> None:
    subject_ids = [s.subject_id for s in body.sections]
    if len(set(subject_ids)) != len(subject_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bitta fan ikki marta qo'shilgan")
    known = {row[0] for row in db.query(Subject.id).filter(Subject.id.in_(subject_ids))}
    if known != set(subject_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noma'lum fan")
    clash = db.query(ExamTemplate).filter(ExamTemplate.name == body.name.strip())
    if template_id is not None:
        clash = clash.filter(ExamTemplate.id != template_id)
    if clash.first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu nomdagi shablon allaqachon bor")


def _set_template_sections(template: ExamTemplate, body: TemplateIn) -> None:
    template.sections = [
        ExamTemplateSection(
            subject_id=s.subject_id,
            order_index=i,
            kind=s.kind,
            question_count=s.question_count,
            points_per_question=s.points_per_question,
        )
        for i, s in enumerate(body.sections)
    ]


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))):
    return [_template_out(db, t) for t in db.query(ExamTemplate).order_by(ExamTemplate.name)]


@router.post("/templates", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(body: TemplateIn, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))):
    _check_template_body(db, body, None)
    template = ExamTemplate(name=body.name.strip(), duration_minutes=body.duration_minutes)
    _set_template_sections(template, body)
    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_out(db, template)


@router.put("/templates/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: int, body: TemplateIn, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))
):
    """Changing a template never touches exams already created from it — an
    exam copies the blocks at creation time."""
    template = db.get(ExamTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shablon topilmadi")
    _check_template_body(db, body, template_id)
    template.name = body.name.strip()
    template.duration_minutes = body.duration_minutes
    _set_template_sections(template, body)
    db.commit()
    db.refresh(template)
    return _template_out(db, template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: int, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))):
    template = db.get(ExamTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shablon topilmadi")
    db.delete(template)
    db.commit()


@router.post("/chorak", response_model=list[ExamOut], status_code=status.HTTP_201_CREATED)
def create_chorak_exams(
    body: ChorakCreateIn, db: Session = Depends(get_db), user: User = Depends(require_role("admin"))
):
    """One draft chorak exam per chosen class, each with its own copy of the
    template's blocks. Nothing is published: the blocks still have to be
    written by their teachers."""
    template = db.get(ExamTemplate, body.template_id)
    if template is None or not template.sections:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shablon topilmadi")
    class_ids = list(dict.fromkeys(body.class_ids))
    found = {row[0] for row in db.query(Class.id).filter(Class.id.in_(class_ids))}
    if found != set(class_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sinf topilmadi")
    if body.start_at and body.end_at and body.start_at >= body.end_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Tugash vaqti boshlanishdan keyin bo'lishi kerak"
        )

    created: list[Exam] = []
    for class_id in class_ids:
        exam = Exam(
            title=body.title.strip(),
            subject_id=template.sections[0].subject_id,
            class_id=class_id,
            created_by_id=user.id,
            status=ExamStatus.draft,
            exam_type=ExamType.chorak.value,
            quarter=body.quarter,
            start_at=body.start_at,
            end_at=body.end_at,
            duration_minutes=body.duration_minutes or template.duration_minutes,
            expected_question_count=sum(s.question_count for s in template.sections),
        )
        exam.sections = [
            ExamSection(
                subject_id=s.subject_id,
                order_index=s.order_index,
                kind=s.kind,
                question_count=s.question_count,
                points_per_question=s.points_per_question,
            )
            for s in template.sections
        ]
        db.add(exam)
        created.append(exam)
    db.commit()
    for exam in created:
        db.refresh(exam)
    return _exam_outs(db, created, user)


@router.put("/{exam_id}/sections/{section_id}/ready", response_model=ExamOut)
def set_section_ready(
    exam_id: int,
    section_id: int,
    body: SectionReadyIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
):
    """The block's teacher (or an admin) declares the block finished — only
    accepted when it really is (the agreed number of questions, all reviewed
    and well-formed) — or takes that back to keep working on it."""
    exam = _get_exam_or_404(db, exam_id)
    section = next((s for s in exam.sections if s.id == section_id), None)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blok topilmadi")
    exam_service.ensure_can_edit_section(db, user, exam, section.id)
    if exam.status not in (ExamStatus.draft, ExamStatus.review):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Imtihon allaqachon e'lon qilingan")

    if body.ready:
        questions = db.query(Question).filter_by(exam_id=exam.id, section_id=section.id).all()
        problem = exam_service.section_problem(section, questions)
        if problem:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=problem)
        section.ready_at = datetime.now(timezone.utc)
    else:
        section.ready_at = None
    db.commit()
    db.refresh(exam)
    return _exam_out(db, exam, user)


@router.get("/{exam_id}/section-results", response_model=SectionResultsOut)
def get_section_results(
    exam_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))
):
    """The chorak result table: one row per student, one column per block,
    the total and the rank in class. The admin and the class's homeroom
    teacher see all of it; a block's teacher sees their own block(s) only."""
    exam = _get_exam_or_404(db, exam_id)
    if not exam.is_chorak:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu choraklik imtihon emas")
    scope = exam_service.results_scope(db, user, exam)
    sections = [s for s in exam.sections if scope is None or s.id in scope]

    names = dict(db.query(Subject.id, Subject.name).filter(Subject.id.in_([s.subject_id for s in sections])))
    klass = db.get(Class, exam.class_id)
    students = db.query(Student).options(joinedload(Student.user)).filter_by(class_id=exam.class_id).all()
    attempts = {a.student_id: a for a in db.query(ExamAttempt).filter_by(exam_id=exam.id)}
    scores: dict[tuple[int, int], AttemptSectionScore] = {
        (sc.student_id, sc.section_id): sc for sc in db.query(AttemptSectionScore).filter_by(exam_id=exam.id)
    }

    graded = (AttemptStatus.submitted, AttemptStatus.auto_submitted)
    rows = []
    for student in students:
        attempt = attempts.get(student.id)
        done = attempt is not None and attempt.status in graded and attempt.score is not None
        rows.append(
            SectionResultRowOut(
                student_id=student.id,
                full_name=student.user.full_name,
                status=attempt.status.value if attempt else "not_started",
                scores=[
                    float(scores[(student.id, s.id)].score) if (student.id, s.id) in scores else None
                    for s in sections
                ],
                correct_counts=[
                    scores[(student.id, s.id)].correct_count if (student.id, s.id) in scores else None
                    for s in sections
                ],
                total=float(attempt.score) if done and scope is None else None,
            )
        )

    # Ranked by the whole paper for a full viewer, by the visible blocks'
    # sum for a block's teacher. RANK() semantics, as everywhere else.
    def sort_value(row: SectionResultRowOut) -> float | None:
        if scope is None:
            return row.total
        seen = [v for v in row.scores if v is not None]
        return round(sum(seen), 2) if seen else None

    ranked = sorted((r for r in rows if sort_value(r) is not None), key=sort_value, reverse=True)
    rank, previous = 0, None
    for i, row in enumerate(ranked, start=1):
        value = sort_value(row)
        if value != previous:
            rank = i
        row.rank = rank
        previous = value
    unranked = sorted((r for r in rows if sort_value(r) is None), key=lambda r: r.full_name)

    return SectionResultsOut(
        exam_id=exam.id,
        exam_title=exam.title,
        class_name=klass.display_name if klass else "",
        max_total=float(exam.total_points or 0),
        shows_total=scope is None,
        sections=[
            SectionResultColumnOut(
                section_id=s.id,
                subject_name=names.get(s.subject_id, ""),
                kind=s.kind,
                max_score=round(s.question_count * float(s.points_per_question), 2),
                question_count=s.question_count,
            )
            for s in sections
        ],
        students=ranked + unranked,
    )
