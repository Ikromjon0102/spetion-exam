import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import UTCDateTime
from app.db.base import Base


class UploadFileType(str, enum.Enum):
    pdf = "pdf"
    docx = "docx"


class UploadStatus(str, enum.Enum):
    pending = "pending"
    parsing = "parsing"
    parsed = "parsed"
    parse_failed = "parse_failed"


class ExamStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    scheduled = "scheduled"
    active = "active"
    closed = "closed"
    archived = "archived"


class QuestionType(str, enum.Enum):
    mcq = "mcq"
    short_answer = "short_answer"


class QuestionSource(str, enum.Enum):
    parsed = "parsed"
    manual = "manual"


class ExamUpload(Base):
    __tablename__ = "exam_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[UploadFileType] = mapped_column(Enum(UploadFileType))
    storage_key: Mapped[str] = mapped_column(String(500))
    status: Mapped[UploadStatus] = mapped_column(Enum(UploadStatus), default=UploadStatus.pending)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_parse_debug: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    exam_upload_id: Mapped[int | None] = mapped_column(ForeignKey("exam_uploads.id"), nullable=True)

    status: Mapped[ExamStatus] = mapped_column(Enum(ExamStatus), default=ExamStatus.draft)
    start_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    total_points: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=True)
    shuffle_options: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now())

    # cascade="all, delete-orphan" — without it, deleting an Exam row tries
    # to null out Question.exam_id (a NOT NULL column) instead of deleting
    # the rows, the exact same bug already found once on Question.options.
    questions: Mapped[list["Question"]] = relationship(
        back_populates="exam", order_by="Question.order_index", cascade="all, delete-orphan"
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType), default=QuestionType.mcq)
    prompt_text: Mapped[str] = mapped_column(Text)
    # A teacher pastes a screenshot (e.g. a formula too complex to retype,
    # or a scanned/OCR'd question that came through garbled) straight into
    # the prompt field instead of typing it. Set means "show this image
    # instead of prompt_text"; prompt_text may be empty in that case. This
    # column existed in the schema from the start but was never actually
    # read or rendered by any frontend component until the paste-image
    # feature wired it up — see admin_exams.py's image endpoints.
    prompt_image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    points: Mapped[float] = mapped_column(Numeric, default=1)
    source: Mapped[QuestionSource] = mapped_column(Enum(QuestionSource), default=QuestionSource.manual)
    # Always true for parser output. An exam can never be published while any
    # question still has this set — see Exam.publish validation in exam_service.
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True)
    # "high"/"low"/None — the parser's own confidence in this question (see
    # ParsedQuestion.confidence in app/parsers/base.py), null for manually
    # added questions. Surfaced in the review UI as a warning badge so a
    # teacher knows which parsed questions deserve extra scrutiny.
    parse_confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Required for question_type=short_answer (enforced in exam_service.
    # publish_exam) — the teacher's model answer. ai_grading_service compares
    # the student's answer_text against THIS, never against prompt_text
    # alone, so the AI never has to independently "know" the right answer.
    # Null/unused for mcq questions.
    reference_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    exam: Mapped["Exam"] = relationship(back_populates="questions")
    # delete-orphan: deleting a question must take its options with it — the
    # NOT NULL question_id FK on QuestionOption means SQLAlchemy's default
    # cascade (nulling the FK first) fails instead of deleting them.
    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question", order_by="QuestionOption.order_index", cascade="all, delete-orphan"
    )


class QuestionOption(Base):
    __tablename__ = "question_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    option_text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    # A teacher can paste a screenshot (e.g. a complex formula) straight
    # into an option field instead of typing it — see prompt_image_key
    # above for the same idea on the question itself. Set means "show this
    # image instead of option_text"; option_text may be empty in that case.
    option_image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    question: Mapped["Question"] = relationship(back_populates="options")
