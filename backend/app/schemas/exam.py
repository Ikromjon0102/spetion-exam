from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core import rich_text


def _clean_rich(value: str | None) -> str | None:
    """Question/option text may be rich HTML (see app.core.rich_text) — reduce
    it to the allow-list at the API boundary, whatever the client sent."""
    return rich_text.sanitize(value) if value is not None else None


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
    expected_question_count: int | None = None


class ExamDuplicateIn(BaseModel):
    # One new Exam (with its own copy of every question/option) is created
    # per class_id here — for a teacher giving the identical lesson/exam to
    # several parallel classes (e.g. 7B and 7R) without re-authoring or
    # re-uploading the same content per class.
    class_ids: list[int]


class ExamUpdate(BaseModel):
    title: str | None = None
    duration_minutes: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    shuffle_questions: bool | None = None
    shuffle_options: bool | None = None
    expected_question_count: int | None = None


class ExamIdsIn(BaseModel):
    exam_ids: list[int] = Field(min_length=1, max_length=500)


class ArchiveOldIn(BaseModel):
    days: int = Field(ge=1, le=3650)


class ExamBulkSkippedOut(BaseModel):
    exam_id: int
    # not_found | forbidden | already_archived | not_finished | not_archived
    reason: str


class ExamBulkResultOut(BaseModel):
    changed: list[int]
    skipped: list[ExamBulkSkippedOut] = []


class FacetOut(BaseModel):
    id: int
    name: str
    count: int


class ExamsSummaryOut(BaseModel):
    current: int
    archived: int
    # counts for the tab that was asked about, ignoring the other filters, so
    # the "folder" numbers don't jump around as you filter
    subjects: list[FacetOut]
    classes: list[FacetOut]


class QuestionOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_index: int
    option_text: str
    option_image_key: str | None = None
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
    parse_confidence: str | None = None
    reference_answer: str | None = None
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
    expected_question_count: int | None = None
    # draft | upcoming | live | finished — derived from the time window (see
    # exam_service.exam_phase), because Exam.status alone stays "scheduled"
    # for ever and made last week's exams look like they were still to come.
    phase: str = "draft"
    archived_at: datetime | None = None
    can_archive: bool = False
    can_edit: bool


class ExamDetailOut(ExamOut):
    questions: list[QuestionOut] = []


class QuestionOptionUpdate(BaseModel):
    option_text: str | None = None
    is_correct: bool | None = None

    _sanitize_option = field_validator("option_text")(_clean_rich)


class QuestionUpdate(BaseModel):
    prompt_text: str | None = None
    points: float | None = None
    needs_review: bool | None = None
    order_index: int | None = None
    reference_answer: str | None = None

    _sanitize_prompt = field_validator("prompt_text")(_clean_rich)


class QuestionOptionCreate(BaseModel):
    option_text: str
    is_correct: bool = False

    _sanitize_option = field_validator("option_text")(_clean_rich)


class QuestionCreate(BaseModel):
    question_type: str = "mcq"
    prompt_text: str
    points: float = 1
    reference_answer: str | None = None
    options: list[QuestionOptionCreate] = []

    _sanitize_prompt = field_validator("prompt_text")(_clean_rich)


class AttemptMonitorOut(BaseModel):
    student_id: int
    full_name: str
    status: str
    started_at: datetime | None = None
    deadline_at: datetime | None = None
    submitted_at: datetime | None = None
    score: float | None = None


class AttemptAnswerReviewOut(BaseModel):
    question_id: int
    question_type: str
    prompt_text: str
    points: float
    # short_answer only — the teacher's own model answer, shown alongside
    # the student's answer_text so they can judge the AI's grade.
    reference_answer: str | None = None
    selected_option_id: int | None = None
    selected_option_text: str | None = None
    answer_text: str | None = None
    is_correct: bool | None = None
    points_awarded: float | None = None
    ai_feedback: str | None = None
    graded_by: str | None = None


class AttemptAnswerOverrideIn(BaseModel):
    points_awarded: float
