"""Org management: classes, subjects, students (incl. bulk import),
teachers + teacher_class_subjects assignment. See docs/spec.md section 2.
"""

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import get_db
from app.dependencies import require_role
from app.models.attempt import ExamAttempt
from app.models.exam import Exam
from app.models.org import AcademicYear, Class, School
from app.models.user import Student, Subject, Teacher, TeacherClassSubject, User, UserRole
from app.schemas.admin_management import (
    ClassCreate,
    ClassDetailOut,
    ClassOut,
    ClassPasswordResetRequest,
    ClassPasswordResetResult,
    ClassSubjectAssignmentOut,
    ClassUpdate,
    StudentBulkImportRequest,
    StudentBulkImportResult,
    StudentBulkImportRow,
    StudentCreate,
    StudentOut,
    StudentUpdate,
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
    TeacherAssignmentOut,
    TeacherClassSubjectCreate,
    TeacherCreate,
    TeacherOut,
    TeacherUpdate,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin-management"])

# Shared temp password for bulk-created student accounts — same pattern as
# scripts/seed_school_data.py's teacher import. Each student changes it
# themselves via POST /auth/change-password.
DEFAULT_STUDENT_PASSWORD = "Spetion2026!"


def _slugify_username(full_name: str) -> str:
    s = full_name.lower().replace("'", "").replace("’", "")
    s = re.sub(r"\s+", ".", s.strip())
    s = re.sub(r"[^a-z0-9.]", "", s)
    return s or "student"


def _class_out(db: Session, klass: Class) -> ClassOut:
    homeroom = db.get(Teacher, klass.homeroom_teacher_id) if klass.homeroom_teacher_id else None
    return ClassOut(
        id=klass.id,
        grade_level=klass.grade_level,
        label=klass.label,
        display_name=klass.display_name,
        homeroom_teacher_id=klass.homeroom_teacher_id,
        homeroom_teacher_name=homeroom.user.full_name if homeroom else None,
    )


def _teacher_has_link_to_class(db: Session, teacher_id: int, class_id: int) -> bool:
    return (
        db.query(TeacherClassSubject).filter_by(teacher_id=teacher_id, class_id=class_id).first() is not None
    )


def _ensure_class_view_access(db: Session, user: User, class_id: int) -> Class:
    """Admin can view any class. A teacher can view a class only if they
    teach a subject there or are its homeroom teacher — not the whole
    school's rosters."""
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sinf topilmadi")
    if user.role == UserRole.admin:
        return klass
    if user.role == UserRole.teacher and user.teacher is not None and (
        klass.homeroom_teacher_id == user.teacher.id or _teacher_has_link_to_class(db, user.teacher.id, class_id)
    ):
        return klass
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu sinfga kirish huquqingiz yo'q")


def _ensure_class_homeroom(db: Session, user: User, class_id: int) -> Class:
    """Admin can manage any class's roster. A teacher can manage a
    roster only for the class they are the homeroom ("sinf rahbari") of."""
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sinf topilmadi")
    if user.role == UserRole.admin:
        return klass
    if user.role == UserRole.teacher and user.teacher is not None and klass.homeroom_teacher_id == user.teacher.id:
        return klass
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Faqat shu sinf rahbari yoki admin o'zgartira oladi"
    )


def _student_out(db: Session, student: Student) -> StudentOut:
    klass = db.get(Class, student.class_id)
    return StudentOut(
        id=student.id,
        user_id=student.user_id,
        username=student.user.username,
        full_name=student.user.full_name,
        class_id=student.class_id,
        class_name=klass.display_name if klass else "",
        student_code=student.student_code,
        is_active=student.user.is_active,
    )


def _teacher_out(teacher: Teacher) -> TeacherOut:
    return TeacherOut(
        id=teacher.id,
        user_id=teacher.user_id,
        username=teacher.user.username,
        full_name=teacher.user.full_name,
        subject_id=teacher.subject_id,
        is_active=teacher.user.is_active,
    )


def _assignment_out(db: Session, link: TeacherClassSubject) -> TeacherAssignmentOut | None:
    klass = db.get(Class, link.class_id)
    subject = db.get(Subject, link.subject_id)
    if klass is None or subject is None:
        return None
    return TeacherAssignmentOut(
        id=link.id, class_id=klass.id, class_name=klass.display_name, subject_id=subject.id, subject_name=subject.name
    )


def _get_or_create_default_context(db: Session) -> tuple[School, AcademicYear]:
    """v1 is single-tenant/single-year (docs/spec.md section 1.1) — classes
    are created against "the" school and "the" current academic year
    without the admin needing to manage those separately. Lazily creates
    them on first use, mirroring scripts/seed_school_data.py."""
    school = db.query(School).first()
    if school is None:
        school = School(name="Spetion School")
        db.add(school)
        db.flush()

    year = db.query(AcademicYear).filter_by(school_id=school.id, is_current=True).first()
    if year is None:
        today = date.today()
        start_year = today.year if today.month >= 8 else today.year - 1
        year = AcademicYear(
            school_id=school.id,
            label=f"{start_year}-{start_year + 1}",
            start_date=date(start_year, 9, 1),
            end_date=date(start_year + 1, 6, 30),
            is_current=True,
        )
        db.add(year)
        db.flush()

    return school, year


@router.get("/classes", response_model=list[ClassOut])
def list_classes(db: Session = Depends(get_db), _user: User = Depends(require_role("admin", "teacher"))):
    classes = db.query(Class).order_by(Class.grade_level, Class.label).all()
    return [_class_out(db, c) for c in classes]


@router.post("/classes", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(
    body: ClassCreate, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))
):
    school, year = _get_or_create_default_context(db)
    existing = (
        db.query(Class)
        .filter_by(academic_year_id=year.id, grade_level=body.grade_level, label=body.label)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu sinf allaqachon mavjud")
    klass = Class(
        school_id=school.id,
        academic_year_id=year.id,
        grade_level=body.grade_level,
        label=body.label,
        display_name=body.display_name,
    )
    db.add(klass)
    db.commit()
    db.refresh(klass)
    return _class_out(db, klass)


@router.get("/classes/{class_id}", response_model=ClassDetailOut)
def get_class_detail(
    class_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("admin", "teacher"))
):
    klass = _ensure_class_view_access(db, user, class_id)
    homeroom = db.get(Teacher, klass.homeroom_teacher_id) if klass.homeroom_teacher_id else None
    student_count = db.query(Student).filter_by(class_id=klass.id).count()
    can_manage = user.role == UserRole.admin or (
        user.teacher is not None and klass.homeroom_teacher_id == user.teacher.id
    )
    links = db.query(TeacherClassSubject).filter_by(class_id=klass.id).all()
    assignments = []
    for link in links:
        subject = db.get(Subject, link.subject_id)
        teacher = db.get(Teacher, link.teacher_id)
        if subject is None or teacher is None:
            continue
        assignments.append(
            ClassSubjectAssignmentOut(
                subject_id=subject.id,
                subject_name=subject.name,
                teacher_id=teacher.id,
                teacher_name=teacher.user.full_name,
            )
        )
    return ClassDetailOut(
        id=klass.id,
        grade_level=klass.grade_level,
        label=klass.label,
        display_name=klass.display_name,
        homeroom_teacher_id=klass.homeroom_teacher_id,
        homeroom_teacher_name=homeroom.user.full_name if homeroom else None,
        student_count=student_count,
        can_manage_students=can_manage,
        subject_assignments=sorted(assignments, key=lambda a: a.subject_name),
    )


@router.put("/classes/{class_id}", response_model=ClassOut)
def update_class(
    class_id: int, body: ClassUpdate, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))
):
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sinf topilmadi")
    if body.grade_level is not None:
        klass.grade_level = body.grade_level
    if body.label is not None:
        klass.label = body.label
    if body.display_name is not None:
        klass.display_name = body.display_name
    if "homeroom_teacher_id" in body.model_fields_set:
        if body.homeroom_teacher_id is not None and db.get(Teacher, body.homeroom_teacher_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="O'qituvchi topilmadi")
        klass.homeroom_teacher_id = body.homeroom_teacher_id
    db.commit()
    db.refresh(klass)
    return _class_out(db, klass)


@router.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(
    class_id: int, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))
):
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sinf topilmadi")
    if db.query(Student).filter_by(class_id=class_id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu sinfda o'quvchilar bor — avval ularni boshqa sinfga o'tkazing yoki o'chiring",
        )
    if db.query(Exam).filter_by(class_id=class_id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bu sinf uchun imtihonlar mavjud, o'chirib bo'lmaydi"
        )
    db.query(TeacherClassSubject).filter_by(class_id=class_id).delete()
    db.delete(klass)
    db.commit()
    return None


@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db), _user: User = Depends(require_role("admin", "teacher"))):
    return db.query(Subject).order_by(Subject.name).all()


@router.post("/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(
    body: SubjectCreate, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))
):
    if db.query(Subject).filter_by(name=body.name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu fan allaqachon mavjud")
    subject = Subject(**body.model_dump())
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.put("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(
    subject_id: int, body: SubjectUpdate, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))
):
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fan topilmadi")
    if body.name is not None:
        if db.query(Subject).filter(Subject.name == body.name, Subject.id != subject_id).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu fan nomi band")
        subject.name = body.name
    if "code" in body.model_fields_set:
        subject.code = body.code
    db.commit()
    db.refresh(subject)
    return subject


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: int, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))
):
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fan topilmadi")
    if db.query(Exam).filter_by(subject_id=subject_id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bu fan bo'yicha imtihonlar mavjud, o'chirib bo'lmaydi"
        )
    if db.query(TeacherClassSubject).filter_by(subject_id=subject_id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu fan o'qituvchilarga biriktirilgan — avval biriktirishlarni o'chiring",
        )
    # A teacher's "asosiy fan" (main subject) is just a label, not a real
    # assignment — clear it rather than blocking the delete on it.
    for teacher in db.query(Teacher).filter_by(subject_id=subject_id).all():
        teacher.subject_id = None
    db.delete(subject)
    db.commit()
    return None


@router.get("/students", response_model=list[StudentOut])
def list_students(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "teacher")),
):
    if user.role == UserRole.teacher:
        # Never leak the whole school's roster to a teacher — only classes
        # they can view: their homeroom, or any class they teach a subject
        # in (read-only for the latter; _ensure_class_homeroom is the
        # separate, stricter check the mutating endpoints use).
        if user.teacher is None:
            return []
        if class_id is not None:
            _ensure_class_view_access(db, user, class_id)
            class_ids = [class_id]
        else:
            homeroom_ids = {c.id for c in db.query(Class).filter_by(homeroom_teacher_id=user.teacher.id).all()}
            taught_ids = {
                link.class_id for link in db.query(TeacherClassSubject).filter_by(teacher_id=user.teacher.id).all()
            }
            class_ids = list(homeroom_ids | taught_ids)
        if not class_ids:
            return []
        query = db.query(Student).filter(Student.class_id.in_(class_ids))
    else:
        query = db.query(Student)
        if class_id is not None:
            query = query.filter_by(class_id=class_id)
    return [_student_out(db, s) for s in query.all()]


@router.post("/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(
    body: StudentCreate, db: Session = Depends(get_db), user: User = Depends(require_role("admin", "teacher"))
):
    _ensure_class_homeroom(db, user, body.class_id)
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu username band")
    if db.query(Student).filter_by(student_code=body.student_code).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu student_code band")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=UserRole.student,
        full_name=body.full_name,
        phone=body.phone,
    )
    db.add(user)
    db.flush()
    student = Student(
        user_id=user.id,
        class_id=body.class_id,
        student_code=body.student_code,
        enrolled_at=body.enrolled_at,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return _student_out(db, student)


@router.put("/students/{student_id}", response_model=StudentOut)
def update_student(
    student_id: int,
    body: StudentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "teacher")),
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="O'quvchi topilmadi")
    _ensure_class_homeroom(db, user, student.class_id)
    if body.class_id is not None:
        if user.role != UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Faqat admin o'quvchini boshqa sinfga o'tkaza oladi"
            )
        student.class_id = body.class_id
    if body.full_name is not None:
        student.user.full_name = body.full_name
    if body.is_active is not None:
        student.user.is_active = body.is_active
    db.commit()
    db.refresh(student)
    return _student_out(db, student)


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("admin", "teacher"))
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="O'quvchi topilmadi")
    _ensure_class_homeroom(db, user, student.class_id)
    if db.query(ExamAttempt).filter_by(student_id=student_id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu o'quvchining imtihon natijalari mavjud — o'chirish o'rniga faolsizlantiring",
        )
    user_row = student.user
    db.delete(student)
    db.delete(user_row)
    db.commit()
    return None


@router.post("/students/bulk-import", response_model=StudentBulkImportResult)
def bulk_import_students(
    body: StudentBulkImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "teacher")),
):
    """Import a whole class roster from pasted full names — one line each,
    e.g. copy-pasted straight from an Excel column. Username and
    student_code are auto-generated and made unique; every created account
    gets DEFAULT_STUDENT_PASSWORD, which each student replaces themselves
    via POST /auth/change-password."""
    klass = _ensure_class_homeroom(db, user, body.class_id)

    existing_usernames = {row[0] for row in db.query(User.username).all()}
    code_prefix = re.sub(r"\s+", "", klass.display_name) or f"class{klass.id}"
    seq = db.query(Student).filter_by(class_id=klass.id).count()

    created: list[StudentBulkImportRow] = []
    errors: list[str] = []
    for raw_name in body.full_names:
        full_name = raw_name.strip()
        if not full_name:
            continue

        base_username = _slugify_username(full_name)
        username = base_username
        suffix = 2
        while username in existing_usernames:
            username = f"{base_username}{suffix}"
            suffix += 1
        existing_usernames.add(username)

        seq += 1
        student_code = f"{code_prefix}-{seq:03d}"
        while db.query(Student).filter_by(student_code=student_code).first():
            seq += 1
            student_code = f"{code_prefix}-{seq:03d}"

        user = User(
            username=username,
            password_hash=hash_password(DEFAULT_STUDENT_PASSWORD),
            role=UserRole.student,
            full_name=full_name,
        )
        db.add(user)
        db.flush()
        db.add(Student(user_id=user.id, class_id=klass.id, student_code=student_code))
        created.append(StudentBulkImportRow(full_name=full_name, username=username, password=DEFAULT_STUDENT_PASSWORD))

    db.commit()
    return StudentBulkImportResult(created=created, errors=errors)


@router.post("/classes/{class_id}/reset-password", response_model=ClassPasswordResetResult)
def reset_class_passwords(
    class_id: int,
    body: ClassPasswordResetRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "teacher")),
):
    """Set the same new password on every student currently in this class —
    e.g. after a bulk import, so the admin (or the class's homeroom
    teacher) can hand the whole class one memorable word (like
    "huquq2026") instead of 400 individual temp passwords. Each student can
    still change it themselves afterwards via POST /auth/change-password."""
    if len(body.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Yangi parol kamida 6 belgidan iborat bo'lishi kerak"
        )
    _ensure_class_homeroom(db, user, class_id)

    students = db.query(Student).filter_by(class_id=class_id).all()
    new_hash = hash_password(body.new_password)
    for student in students:
        student.user.password_hash = new_hash
    db.commit()
    return ClassPasswordResetResult(updated_count=len(students))


@router.get("/teachers", response_model=list[TeacherOut])
def list_teachers(db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))):
    return [_teacher_out(t) for t in db.query(Teacher).all()]


@router.post("/teachers", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
def create_teacher(
    body: TeacherCreate, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))
):
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu username band")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=UserRole.teacher,
        full_name=body.full_name,
        phone=body.phone,
    )
    db.add(user)
    db.flush()
    teacher = Teacher(user_id=user.id, subject_id=body.subject_id)
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return _teacher_out(teacher)


@router.put("/teachers/{teacher_id}", response_model=TeacherOut)
def update_teacher(
    teacher_id: int,
    body: TeacherUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin")),
):
    teacher = db.get(Teacher, teacher_id)
    if teacher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="O'qituvchi topilmadi")
    if body.full_name is not None:
        teacher.user.full_name = body.full_name
    if body.subject_id is not None:
        teacher.subject_id = body.subject_id
    if body.is_active is not None:
        teacher.user.is_active = body.is_active
    db.commit()
    db.refresh(teacher)
    return _teacher_out(teacher)


@router.delete("/teachers/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(
    teacher_id: int, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))
):
    teacher = db.get(Teacher, teacher_id)
    if teacher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="O'qituvchi topilmadi")
    if db.query(Exam).filter_by(created_by_id=teacher.user_id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu o'qituvchi imtihon yaratgan — o'chirib bo'lmaydi",
        )
    db.query(TeacherClassSubject).filter_by(teacher_id=teacher_id).delete()
    for klass in db.query(Class).filter_by(homeroom_teacher_id=teacher_id).all():
        klass.homeroom_teacher_id = None
    user_row = teacher.user
    db.delete(teacher)
    db.delete(user_row)
    db.commit()
    return None


@router.get("/teachers/me/assignments", response_model=list[TeacherAssignmentOut])
def list_my_assignments(db: Session = Depends(get_db), user: User = Depends(require_role("teacher", "admin"))):
    """A teacher's own (class, subject) pairs from teacher_class_subjects —
    lets the exam-upload UI show only what this teacher is actually
    authorized to create exams for. Admin has no restriction, so this is
    empty for admin; the frontend falls back to the unrestricted class/
    subject pickers in that case."""
    if user.role != UserRole.teacher or user.teacher is None:
        return []
    rows = db.query(TeacherClassSubject).filter_by(teacher_id=user.teacher.id).all()
    return [out for r in rows if (out := _assignment_out(db, r)) is not None]


@router.get("/teachers/{teacher_id}/assignments", response_model=list[TeacherAssignmentOut])
def list_teacher_assignments(
    teacher_id: int, db: Session = Depends(get_db), _user: User = Depends(require_role("admin"))
):
    rows = db.query(TeacherClassSubject).filter_by(teacher_id=teacher_id).all()
    return [out for r in rows if (out := _assignment_out(db, r)) is not None]


@router.post(
    "/teachers/{teacher_id}/class-subjects",
    response_model=TeacherAssignmentOut,
    status_code=status.HTTP_201_CREATED,
)
def assign_teacher_class_subject(
    teacher_id: int,
    body: TeacherClassSubjectCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin")),
):
    if teacher_id != body.teacher_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="teacher_id mos kelmadi")
    existing = db.query(TeacherClassSubject).filter_by(
        teacher_id=body.teacher_id, class_id=body.class_id, subject_id=body.subject_id
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu biriktirish allaqachon mavjud")
    link = TeacherClassSubject(**body.model_dump())
    db.add(link)
    db.commit()
    db.refresh(link)
    out = _assignment_out(db, link)
    assert out is not None
    return out


@router.delete("/teachers/{teacher_id}/class-subjects/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_teacher_class_subject(
    teacher_id: int,
    link_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("admin")),
):
    link = db.get(TeacherClassSubject, link_id)
    if link is None or link.teacher_id != teacher_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Biriktirish topilmadi")
    db.delete(link)
    db.commit()
    return None
