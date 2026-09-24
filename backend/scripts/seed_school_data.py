"""One-off import of the real school timetable (seed_data/spetion_school_data.json)
into classes, subjects, teachers and teacher_class_subjects — this is what
authorizes a teacher to author/publish exams for a given class+subject (see
exam_service.ensure_can_author_exam).

Run from backend/ with the venv active:
    python -m scripts.seed_school_data

Idempotent: safe to re-run — matches existing rows by name/grade+label
instead of inserting duplicates. Every newly-created teacher account gets
the same placeholder password (DEFAULT_PASSWORD below); change it before
handing out real logins.
"""

import json
import re
from datetime import date
from pathlib import Path

from app.core.security import hash_password
from app.db.base import Base, SessionLocal, engine
from app.models.org import AcademicYear, Class, School
from app.models.user import Subject, Teacher, TeacherClassSubject, User, UserRole

DATA_PATH = Path(__file__).resolve().parent.parent / "seed_data" / "spetion_school_data.json"
DEFAULT_PASSWORD = "Spetion2026!"


def slugify_username(full_name: str) -> str:
    s = full_name.lower().replace("'", "").replace("’", "")
    s = re.sub(r"\s+", ".", s.strip())
    s = re.sub(r"[^a-z0-9.]", "", s)
    return s or "teacher"


def parse_class_name(name: str) -> tuple[int, str]:
    m = re.match(r"^(\d+)-?\s*(.*)$", name)
    if not m:
        raise ValueError(f"Can't parse a grade level out of class name {name!r}")
    grade_level = int(m.group(1))
    label = m.group(2).strip() or name
    return grade_level, label


def get_or_create_school(db, name: str) -> School:
    school = db.query(School).filter_by(name=name).first()
    if school is None:
        school = School(name=name)
        db.add(school)
        db.flush()
    return school


def get_or_create_academic_year(db, school: School) -> AcademicYear:
    year = db.query(AcademicYear).filter_by(school_id=school.id, is_current=True).first()
    if year is None:
        year = AcademicYear(
            school_id=school.id,
            label="2025-2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
            is_current=True,
        )
        db.add(year)
        db.flush()
    return year


def get_or_create_class(db, school: School, year: AcademicYear, name: str) -> Class:
    grade_level, label = parse_class_name(name)
    klass = (
        db.query(Class)
        .filter_by(academic_year_id=year.id, grade_level=grade_level, label=label)
        .first()
    )
    if klass is None:
        klass = Class(
            school_id=school.id,
            academic_year_id=year.id,
            grade_level=grade_level,
            label=label,
            display_name=name,
        )
        db.add(klass)
        db.flush()
    return klass


def get_or_create_subject(db, name: str) -> Subject:
    subject = db.query(Subject).filter_by(name=name).first()
    if subject is None:
        subject = Subject(name=name)
        db.add(subject)
        db.flush()
    return subject


def get_or_create_teacher(db, full_name: str, used_usernames: set[str]) -> Teacher:
    user = db.query(User).filter_by(full_name=full_name, role=UserRole.teacher).first()
    if user is not None:
        used_usernames.add(user.username)
        return user.teacher

    base = slugify_username(full_name)
    username = base
    suffix = 2
    while username in used_usernames or db.query(User).filter_by(username=username).first() is not None:
        username = f"{base}{suffix}"
        suffix += 1
    used_usernames.add(username)

    user = User(
        username=username,
        password_hash=hash_password(DEFAULT_PASSWORD),
        role=UserRole.teacher,
        full_name=full_name,
    )
    db.add(user)
    db.flush()
    teacher = Teacher(user_id=user.id)
    db.add(teacher)
    db.flush()
    return teacher


def main() -> None:
    Base.metadata.create_all(engine)
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    db = SessionLocal()
    used_usernames: set[str] = set()

    try:
        school = get_or_create_school(db, data["school"])
        year = get_or_create_academic_year(db, school)

        classes = {c["name"]: get_or_create_class(db, school, year, c["name"]) for c in data["classes"]}
        subjects = {name: get_or_create_subject(db, name) for name in data["subjects"]}
        teachers = {name: get_or_create_teacher(db, name, used_usernames) for name in data["teachers"]}
        db.commit()

        seen: set[tuple[str, str, str]] = set()
        created = 0
        for entry in data["schedule"]:
            key = (entry["teacher"], entry["class"], entry["subject"])
            if key in seen:
                continue
            seen.add(key)

            teacher = teachers.get(entry["teacher"])
            klass = classes.get(entry["class"])
            subject = subjects.get(entry["subject"])
            if not (teacher and klass and subject):
                print(f"SKIP (noma'lum bog'lanish): {key}")
                continue

            exists = (
                db.query(TeacherClassSubject)
                .filter_by(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id)
                .first()
            )
            if exists is None:
                db.add(TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id))
                created += 1
        db.commit()

        print(f"Maktab: {school.name}")
        print(f"Sinflar: {len(classes)}, fanlar: {len(subjects)}, o'qituvchilar: {len(teachers)}")
        print(f"Yangi teacher_class_subjects yozuvlari: {created} (jami noyob birikma: {len(seen)})")
        print(f"Barcha yangi o'qituvchi hisoblari uchun vaqtinchalik parol: {DEFAULT_PASSWORD}")
        print("MUHIM: bu parolni birinchi kirishdan keyin albatta almashtiring.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
