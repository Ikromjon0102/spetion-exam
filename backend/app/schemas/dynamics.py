from pydantic import BaseModel


class DynamicsPointOut(BaseModel):
    """One graded result in one subject: a whole nazorat exam, or one subject
    block of a chorak exam."""

    exam_id: int
    exam_title: str
    exam_type: str  # "nazorat" | "chorak"
    subject_id: int
    subject_name: str
    date: str  # YYYY-MM-DD, school-local day it was handed in
    quarter: int
    score: float
    max_score: float
    percent: float
    # the class's average on the same exam/block, in percent; None when fewer
    # than 3 students sat it (an average of one or two would expose them)
    class_percent: float | None = None
    # a written answer is still waiting for the teacher: the score may change
    provisional: bool = False


class DynamicsMissedOut(BaseModel):
    exam_id: int
    exam_title: str
    exam_type: str
    subject_name: str | None = None
    date: str


class DynamicsSubjectOut(BaseModel):
    subject_id: int
    subject_name: str
    exams_count: int
    average_percent: float
    baseline_percent: float  # mean of the first results ("yil boshi")
    current_percent: float  # mean of the latest results ("hozir")
    delta: float | None = None  # current - baseline; None with fewer than 2 results
    class_percent: float | None = None


class DynamicsQuarterOut(BaseModel):
    number: int
    start_date: str
    end_date: str
    exams_count: int
    percent: float | None = None  # None: no result in this chorak (yet)
    rank: int | None = None  # staff only
    rank_of: int | None = None


class DynamicsOverallOut(BaseModel):
    exams_count: int
    baseline_percent: float | None = None
    current_percent: float | None = None
    delta: float | None = None
    average_percent: float | None = None
    class_percent: float | None = None
    rank: int | None = None  # staff only
    rank_of: int | None = None


class DynamicsInsightOut(BaseModel):
    subject_id: int
    subject_name: str
    value: float  # a percent (strongest/weakest) or a delta (improved/declined)


class DynamicsInsightsOut(BaseModel):
    strongest: DynamicsInsightOut | None = None
    weakest: DynamicsInsightOut | None = None
    most_improved: DynamicsInsightOut | None = None
    most_declined: DynamicsInsightOut | None = None


class DynamicsOut(BaseModel):
    student_id: int
    full_name: str
    class_name: str
    school_year_start: int  # 2026 = the 2026/27 school year
    available_school_years: list[int]
    show_rank: bool  # False for a student looking at their own page
    overall: DynamicsOverallOut
    subjects: list[DynamicsSubjectOut]
    quarters: list[DynamicsQuarterOut]
    points: list[DynamicsPointOut]
    missed: list[DynamicsMissedOut]
    insights: DynamicsInsightsOut
