from pydantic import BaseModel


class ClassScopeOut(BaseModel):
    """What the viewer is allowed to see of this class. A subject teacher
    sees only the subjects they teach to it; the homeroom teacher and an admin
    see every subject."""

    all_subjects: bool
    subject_ids: list[int] = []


class ClassResultColumnOut(BaseModel):
    """One exam in one subject (a chorak exam gives one column per subject)."""

    exam_id: int
    exam_title: str
    exam_type: str
    subject_id: int
    subject_name: str
    date: str
    max_score: float
    taken: int  # how many students have a graded result in it
    class_percent: float | None = None


class ClassResultCellOut(BaseModel):
    score: float
    max_score: float
    percent: float


class ClassResultRowOut(BaseModel):
    student_id: int
    full_name: str
    cells: list[ClassResultCellOut | None]  # index-aligned to `columns`
    percent: float | None = None  # earned / possible over the cells present
    rank: int | None = None  # None while the student has no result in range


class ClassResultsOut(BaseModel):
    class_id: int
    class_name: str
    start_date: str
    end_date: str
    scope: ClassScopeOut
    columns: list[ClassResultColumnOut]
    students: list[ClassResultRowOut]
    class_percent: float | None = None


class ClassDynSubjectOut(BaseModel):
    subject_id: int
    subject_name: str
    exams_count: int
    baseline_percent: float
    current_percent: float
    average_percent: float
    delta: float | None = None


class ClassDynStudentOut(BaseModel):
    student_id: int
    full_name: str
    exams_count: int
    average_percent: float | None = None
    baseline_percent: float | None = None
    current_percent: float | None = None
    delta: float | None = None
    rank: int | None = None


class ClassDynQuarterOut(BaseModel):
    number: int
    start_date: str
    end_date: str
    exams_count: int
    percent: float | None = None


class ClassDynBandsOut(BaseModel):
    """How many students are now below 50%, 50-70%, 70% and up."""

    low: int
    middle: int
    high: int


class ClassDynamicsOut(BaseModel):
    class_id: int
    class_name: str
    school_year_start: int
    available_school_years: list[int]
    scope: ClassScopeOut
    students_count: int
    exams_count: int
    baseline_percent: float | None = None
    current_percent: float | None = None
    delta: float | None = None
    average_percent: float | None = None
    bands: ClassDynBandsOut
    subjects: list[ClassDynSubjectOut]
    quarters: list[ClassDynQuarterOut]
    timeline: list[ClassResultColumnOut]  # every exam/subject of the year, by date
    students: list[ClassDynStudentOut]
