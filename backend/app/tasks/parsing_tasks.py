"""Celery task: parse_exam_upload(upload_id). Never runs inline in the
request — see docs/spec.md section 3 step 2. Calls
app.services.parsing_service to do the actual work.
"""

from app.db.base import SessionLocal
from app.models.exam import ExamUpload
from app.services import parsing_service
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.parsing_tasks.parse_exam_upload")
def parse_exam_upload(upload_id: int, subject_id: int, class_id: int, title: str | None = None) -> None:
    db = SessionLocal()
    try:
        upload = db.get(ExamUpload, upload_id)
        if upload is None:
            return
        parsing_service.process_upload(db, upload, subject_id=subject_id, class_id=class_id, title=title)
    finally:
        db.close()
