import re
from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator


def _normalize_name(v: str | None) -> str | None:
    """Collapses internal whitespace runs (not just leading/trailing) to a
    single space. A plain .strip() alone leaves a name like "Abdukarimova
    \tShahnoza" intact when it was pasted from Excel — the tab renders as a
    large, ugly gap everywhere the name is displayed. Applied at the schema
    boundary so every entry point (single add, edit, bulk import) is covered
    once, rather than duplicating this in each router function."""
    if v is None:
        return v
    return re.sub(r"\s+", " ", v.strip())


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str | None = None


class SubjectCreate(BaseModel):
    name: str
    code: str | None = None


class SubjectUpdate(BaseModel):
    name: str | None = None
    code: str | None = None


class ClassCreate(BaseModel):
    # school_id/academic_year_id are not exposed — v1 is single-tenant/
    # single-year (see docs/spec.md section 1.1), so the backend resolves
    # (or lazily creates) "the" school + current academic year itself.
    grade_level: int
    label: str
    display_name: str


class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    grade_level: int
    label: str
    display_name: str
    homeroom_teacher_id: int | None = None
    homeroom_teacher_name: str | None = None


class ClassUpdate(BaseModel):
    grade_level: int | None = None
    label: str | None = None
    display_name: str | None = None
    # None here is ambiguous between "not provided" and "unassign" — routers
    # check `"homeroom_teacher_id" in body.model_fields_set` to tell them apart.
    homeroom_teacher_id: int | None = None


class ClassSubjectAssignmentOut(BaseModel):
    subject_id: int
    subject_name: str
    teacher_id: int
    teacher_name: str


class ClassDetailOut(BaseModel):
    id: int
    grade_level: int
    label: str
    display_name: str
    homeroom_teacher_id: int | None = None
    homeroom_teacher_name: str | None = None
    student_count: int
    can_manage_students: bool
    subject_assignments: list[ClassSubjectAssignmentOut]


class StudentCreate(BaseModel):
    username: str
    password: str
    full_name: str
    class_id: int
    student_code: str
    phone: str | None = None
    enrolled_at: date | None = None

    _clean_full_name = field_validator("full_name")(_normalize_name)


class StudentOut(BaseModel):
    id: int
    user_id: int
    username: str
    full_name: str
    class_id: int
    class_name: str
    student_code: str
    is_active: bool


class StudentUpdate(BaseModel):
    full_name: str | None = None
    class_id: int | None = None
    is_active: bool | None = None

    _clean_full_name = field_validator("full_name")(_normalize_name)


class StudentBulkImportRequest(BaseModel):
    class_id: int
    # One full name per line, pasted straight from an Excel roster column —
    # username/password/student_code are all auto-generated server-side so
    # the admin never has to invent 400 of each by hand.
    full_names: list[str]

    @field_validator("full_names")
    @classmethod
    def _clean_full_names(cls, v: list[str]) -> list[str]:
        return [_normalize_name(name) or "" for name in v]


class StudentBulkImportRow(BaseModel):
    full_name: str
    username: str
    password: str


class StudentBulkImportResult(BaseModel):
    created: list[StudentBulkImportRow]
    errors: list[str]


class ClassPasswordResetRequest(BaseModel):
    new_password: str


class ClassPasswordResetResult(BaseModel):
    updated_count: int


class TeacherCreate(BaseModel):
    username: str
    password: str
    full_name: str
    subject_id: int | None = None
    phone: str | None = None

    _clean_full_name = field_validator("full_name")(_normalize_name)


class TeacherOut(BaseModel):
    id: int
    user_id: int
    username: str
    full_name: str
    subject_id: int | None = None
    is_active: bool


class TeacherUpdate(BaseModel):
    full_name: str | None = None
    subject_id: int | None = None
    is_active: bool | None = None

    _clean_full_name = field_validator("full_name")(_normalize_name)


class TeacherAssignmentOut(BaseModel):
    id: int
    class_id: int
    class_name: str
    subject_id: int
    subject_name: str


class TeacherClassSubjectCreate(BaseModel):
    teacher_id: int
    class_id: int
    subject_id: int


class TeacherClassSubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    teacher_id: int
    class_id: int
    subject_id: int
