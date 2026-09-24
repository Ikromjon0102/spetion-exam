from datetime import datetime

from pydantic import BaseModel


class AttemptOptionOut(BaseModel):
    id: int
    order_index: int
    option_text: str


class AttemptQuestionOut(BaseModel):
    id: int
    order_index: int
    question_type: str
    prompt_text: str
    prompt_image_key: str | None = None
    points: float
    options: list[AttemptOptionOut] = []
    selected_option_id: int | None = None
    answer_text: str | None = None


class ExamListItemOut(BaseModel):
    id: int
    title: str
    subject_name: str
    start_at: datetime | None = None
    end_at: datetime | None = None
    duration_minutes: int
    window_state: str  # "upcoming" | "active" | "closed"
    my_attempt_status: str | None = None


class AttemptStateOut(BaseModel):
    attempt_id: int
    exam_id: int
    exam_title: str
    deadline_at: datetime
    duration_minutes: int
    questions: list[AttemptQuestionOut]


class AnswerIn(BaseModel):
    selected_option_id: int | None = None
    answer_text: str | None = None


class SubmitResultOut(BaseModel):
    score: float
    max_score: float
    submitted_at: datetime


class ResultQuestionOut(BaseModel):
    question_id: int
    prompt_text: str
    points: float
    selected_option_id: int | None = None
    correct_option_id: int | None = None
    is_correct: bool | None = None
    points_awarded: float | None = None


class ExamResultOut(BaseModel):
    exam_id: int
    exam_title: str
    score: float
    max_score: float
    percent: float
    questions: list[ResultQuestionOut]


class RankingEntryOut(BaseModel):
    rank_in_class: int
    student_id: int
    full_name: str
    score: float
    is_me: bool


class SubjectHistoryPointOut(BaseModel):
    exam_id: int
    exam_title: str
    score: float
    max_score: float
    date: datetime


class SubjectHistoryOut(BaseModel):
    subject_id: int
    subject_name: str
    exams_taken_count: int
    average_percent: float | None = None
    trend: str | None = None
    timeline: list[SubjectHistoryPointOut]
