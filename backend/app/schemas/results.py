from datetime import datetime

from pydantic import BaseModel


class ClassRankingRowOut(BaseModel):
    rank_in_class: int
    student_id: int
    full_name: str
    score: float
    percentile: float | None = None


class ClassRankingOut(BaseModel):
    exam_id: int
    exam_title: str
    rankings: list[ClassRankingRowOut]


class StudentPerformanceSubjectOut(BaseModel):
    subject_id: int
    subject_name: str
    exams_taken_count: int
    average_percent: float | None = None
    trend: str | None = None
    last_exam_at: datetime | None = None


class StudentPerformanceOut(BaseModel):
    student_id: int
    full_name: str
    subjects: list[StudentPerformanceSubjectOut]


class ClassSubjectExamPointOut(BaseModel):
    exam_id: int
    exam_title: str
    average_score: float
    max_score: float
    start_at: datetime | None = None


class ClassSubjectPerformanceOut(BaseModel):
    class_id: int
    subject_id: int
    exams: list[ClassSubjectExamPointOut]


class OverallRankingRowOut(BaseModel):
    rank: int
    student_id: int
    full_name: str
    class_id: int
    class_name: str
    exams_taken_count: int
    average_percent: float


class OverallRankingOut(BaseModel):
    scope: str  # "class" | "grade" | "school"
    class_id: int | None = None
    class_name: str | None = None
    grade_level: int | None = None
    rankings: list[OverallRankingRowOut]


class DailyResultsExamOut(BaseModel):
    exam_id: int
    exam_title: str
    subject_name: str
    end_at: datetime | None = None


class DailyStudentRowOut(BaseModel):
    rank: int
    student_id: int
    full_name: str
    # Aligned index-for-index with DailyClassResultsOut.exams — None means
    # this student has no ExamRanking row for that particular exam (didn't
    # take it / not yet graded), rendered as a dash rather than a 0 so it
    # isn't mistaken for a zero score.
    scores: list[float | None]
    total: float


class DailyClassResultsOut(BaseModel):
    class_id: int
    class_name: str
    date: str
    exams: list[DailyResultsExamOut]
    students: list[DailyStudentRowOut]
