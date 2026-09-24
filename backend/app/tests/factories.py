"""Minimal object-creation helpers shared by the test modules."""

from datetime import date

from app.core.security import hash_password
from app.models.exam import Exam, ExamStatus, Question, QuestionOption, QuestionType
from app.models.org import AcademicYear, Class, School
from app.models.user import Student, Subject, Teacher, User, UserRole

_counter = {"n": 0}


def _next(prefix: str) -> str:
    _counter["n"] += 1
    return f"{prefix}{_counter['n']}"


def make_class(db, label: str | None = None, grade_level: int = 9) -> Class:
    school = School(name=_next("School"))
    db.add(school)
    db.flush()
    year = AcademicYear(
        school_id=school.id,
        label="2025-2026",
        start_date=date(2025, 9, 1),
        end_date=date(2026, 6, 1),
        is_current=True,
    )
    db.add(year)
    db.flush()
    label = label or _next("L")
    klass = Class(
        school_id=school.id,
        academic_year_id=year.id,
        grade_level=grade_level,
        label=label,
        display_name=f"{grade_level}-{label}",
    )
    db.add(klass)
    db.flush()
    return klass


def make_subject(db, name: str | None = None) -> Subject:
    subject = Subject(name=name or _next("Subject"))
    db.add(subject)
    db.flush()
    return subject


def make_user(db, role: UserRole, username: str | None = None, password: str = "secret123", full_name: str = "Test User") -> User:
    user = User(username=username or _next("user"), password_hash=hash_password(password), role=role, full_name=full_name)
    db.add(user)
    db.flush()
    return user


def make_student(
    db, klass: Class, username: str | None = None, student_code: str | None = None, full_name: str = "Talaba"
) -> Student:
    user = make_user(db, UserRole.student, username=username, full_name=full_name)
    student = Student(user_id=user.id, class_id=klass.id, student_code=student_code or _next("SC"))
    db.add(student)
    db.flush()
    return student


def make_teacher(db, subject: Subject | None = None, username: str | None = None) -> Teacher:
    user = make_user(db, UserRole.teacher, username=username, full_name="Ustoz")
    teacher = Teacher(user_id=user.id, subject_id=subject.id if subject else None)
    db.add(teacher)
    db.flush()
    return teacher


def make_admin(db, username: str | None = None) -> User:
    return make_user(db, UserRole.admin, username=username, full_name="Admin")


def make_exam(
    db,
    klass: Class,
    subject: Subject,
    status: ExamStatus = ExamStatus.draft,
    duration_minutes: int = 30,
    start_at=None,
    end_at=None,
    created_by: User | None = None,
) -> Exam:
    exam = Exam(
        title=_next("Imtihon"),
        subject_id=subject.id,
        class_id=klass.id,
        created_by_id=created_by.id if created_by else make_admin(db).id,
        status=status,
        duration_minutes=duration_minutes,
        start_at=start_at,
        end_at=end_at,
    )
    db.add(exam)
    db.flush()
    return exam


def add_mcq_question(
    db, exam: Exam, correct_index: int = 0, order_index: int = 0, needs_review: bool = False, points: float = 1
) -> Question:
    question = Question(
        exam_id=exam.id,
        order_index=order_index,
        question_type=QuestionType.mcq,
        prompt_text=f"Savol {order_index + 1}?",
        points=points,
        needs_review=needs_review,
    )
    db.add(question)
    db.flush()
    for i in range(4):
        db.add(
            QuestionOption(
                question_id=question.id, order_index=i, option_text=f"Variant {chr(65 + i)}", is_correct=(i == correct_index)
            )
        )
    db.flush()
    db.refresh(question)
    return question
