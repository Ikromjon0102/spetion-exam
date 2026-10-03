from pydantic import BaseModel


class LiveExamOut(BaseModel):
    exam_id: int
    title: str
    subject_name: str
    class_name: str
    total: int
    submitted: int
    in_progress: int
    not_started: int


class ClassStudentCountOut(BaseModel):
    class_id: int
    class_name: str
    count: int


class DashboardCountsOut(BaseModel):
    classes: int
    subjects: int
    students: int
    teachers: int


class DashboardOut(BaseModel):
    live: list[LiveExamOut]
    # Admin-only; None for a teacher (the school-wide numbers would leak every
    # other class's data, same rule as the other school-wide endpoints).
    counts: DashboardCountsOut | None = None
    students_per_class: list[ClassStudentCountOut] | None = None
