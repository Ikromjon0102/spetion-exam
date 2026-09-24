from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExamUploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    original_filename: str
    file_type: str
    status: str
    parse_error: str | None = None
    created_at: datetime
    exam_id: int | None = None


class ExamCreate(BaseModel):
    title: str
    subject_id: int
    class_id: int
    exam_upload_id: int | None = None


class ExamUpdate(BaseModel):
    title: str | None = None
    duration_minutes: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    shuffle_questions: bool | None = None
    shuffle_options: bool | None = None


class QuestionOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_index: int
    option_text: str
    is_correct: bool


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_index: int
    question_type: str
    prompt_text: str
    prompt_image_key: str | None = None
    points: float
    source: str
    needs_review: bool
    options: list[QuestionOptionOut] = []


class ExamOut(BaseModel):
    id: int
    title: str
    subject_id: int
    subject_name: str
    class_id: int
    class_name: str
    status: str
    start_at: datetime | None = None
    end_at: datetime | None = None
    duration_minutes: int
    total_points: float | None = None
    question_count: int
    needs_review_count: int
    can_edit: bool


class ExamDetailOut(ExamOut):
    questions: list[QuestionOut] = []


class QuestionOptionUpdate(BaseModel):
    option_text: str | None = None
    is_correct: bool | None = None


class QuestionUpdate(BaseModel):
    prompt_text: str | None = None
    points: float | None = None
    needs_review: bool | None = None
    order_index: int | None = None


class QuestionOptionCreate(BaseModel):
    option_text: str
    is_correct: bool = False


class QuestionCreate(BaseModel):
    question_type: str = "mcq"
    prompt_text: str
    points: float = 1
    options: list[QuestionOptionCreate] = []


class AttemptMonitorOut(BaseModel):
    student_id: int
    full_name: str
    status: str
    started_at: datetime | None = None
    deadline_at: datetime | None = None
    submitted_at: datetime | None = None
    score: float | None = None
