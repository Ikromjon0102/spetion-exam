from datetime import datetime

from pydantic import BaseModel


class AttemptOptionOut(BaseModel):
    id: int
    order_index: int
    option_text: str
    option_image_key: str | None = None


class AttemptSectionOut(BaseModel):
    """One block of a chorak exam as the student sees it."""

    id: int
    subject_name: str
    kind: str
    question_count: int
    points_per_question: float


class AttemptQuestionOut(BaseModel):
    id: int
    section_id: int | None = None
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
    exam_type: str = "nazorat"
    question_count: int = 0
    total_points: float | None = None
    # the student's own deadline once they have started (for "resume")
    my_deadline_at: datetime | None = None
    sections: list[AttemptSectionOut] = []


class AttemptStateOut(BaseModel):
    attempt_id: int
    exam_id: int
    exam_title: str
    deadline_at: datetime
    duration_minutes: int
    exam_type: str = "nazorat"
    sections: list[AttemptSectionOut] = []
    questions: list[AttemptQuestionOut]


class AnswerIn(BaseModel):
    selected_option_id: int | None = None
    answer_text: str | None = None


class SubmitResultOut(BaseModel):
    score: float
    max_score: float
    submitted_at: datetime


class ResultSectionOut(BaseModel):
    section_id: int
    subject_name: str
    kind: str
    score: float
    max_score: float
    correct_count: int
    question_count: int


class ResultQuestionOut(BaseModel):
    question_id: int
    section_id: int | None = None
    question_type: str
    prompt_text: str
    points: float
    selected_option_id: int | None = None
    selected_option_text: str | None = None
    correct_option_id: int | None = None
    correct_option_text: str | None = None
    # short_answer only — answer_text is always the student's own writing
    # (no reveal-gating needed), ai_feedback is gated the same way option
    # text is, since it can describe what the correct answer covers.
    answer_text: str | None = None
    ai_feedback: str | None = None
    is_correct: bool | None = None
    points_awarded: float | None = None


class ExamResultOut(BaseModel):
    exam_id: int
    exam_title: str
    score: float
    max_score: float
    percent: float
    answers_revealed: bool
    reveal_at: datetime | None = None
    exam_type: str = "nazorat"
    sections: list[ResultSectionOut] = []
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
    # "nazorat" | "chorak" — a chorak point is that subject's block only
    exam_type: str = "nazorat"
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
