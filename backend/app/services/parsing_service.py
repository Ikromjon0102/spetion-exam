"""Orchestrates app.parsers.{docx_parser,pdf_parser} from the Celery task:
downloads the file from S3, extracts ParsedQuestion list, writes
raw_parse_debug onto the ExamUpload, then materializes Exam (status=draft)
+ Question/QuestionOption rows (needs_review=True always) in the same
transaction so the teacher's next GET already sees editable rows.

exam_uploads has no subject_id/class_id of its own (see docs/spec.md
section 1.2) — the admin picks the target subject/class/title at upload
time and they're threaded through as task args rather than stored on the
upload row.
"""

from sqlalchemy.orm import Session

from app.core.storage import download_exam_file
from app.models.exam import (
    Exam,
    ExamStatus,
    ExamUpload,
    Question,
    QuestionOption,
    QuestionSource,
    UploadStatus,
)
from app.parsers.base import BaseParser
from app.parsers.docx_parser import DocxParser
from app.parsers.pdf_parser import PdfParser

_PARSERS: dict[str, BaseParser] = {
    "docx": DocxParser(),
    "pdf": PdfParser(),
}


def process_upload(
    db: Session,
    upload: ExamUpload,
    subject_id: int,
    class_id: int,
    title: str | None = None,
) -> Exam:
    upload.status = UploadStatus.parsing
    db.commit()

    try:
        file_bytes = download_exam_file(upload.storage_key)
        parser = _PARSERS[upload.file_type.value]
        parsed_questions = parser.parse(file_bytes)
    except Exception as exc:
        upload.status = UploadStatus.parse_failed
        upload.parse_error = str(exc)
        db.commit()
        raise

    upload.raw_parse_debug = {
        "question_count": len(parsed_questions),
        "questions": [
            {
                "prompt": q.prompt,
                "confidence": q.confidence,
                "options": [{"text": o.text, "is_correct": o.is_correct} for o in q.options],
            }
            for q in parsed_questions
        ],
    }

    exam = Exam(
        title=title or upload.original_filename.rsplit(".", 1)[0],
        subject_id=subject_id,
        class_id=class_id,
        created_by_id=upload.uploaded_by_id,
        exam_upload_id=upload.id,
        status=ExamStatus.draft,
    )
    db.add(exam)
    db.flush()

    for order_index, parsed_q in enumerate(parsed_questions):
        question = Question(
            exam_id=exam.id,
            order_index=order_index,
            prompt_text=parsed_q.prompt,
            source=QuestionSource.parsed,
            needs_review=True,
        )
        db.add(question)
        db.flush()
        for opt_index, parsed_opt in enumerate(parsed_q.options):
            db.add(
                QuestionOption(
                    question_id=question.id,
                    order_index=opt_index,
                    option_text=parsed_opt.text,
                    is_correct=parsed_opt.is_correct,
                )
            )

    upload.status = UploadStatus.parsed
    db.commit()
    db.refresh(exam)
    return exam
