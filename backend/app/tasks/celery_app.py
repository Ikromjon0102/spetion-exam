from celery import Celery

from app.config import settings

celery_app = Celery("spetion_exam", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_always_eager = settings.celery_eager

celery_app.conf.beat_schedule = {
    "auto-submit-sweep": {
        "task": "app.tasks.exam_lifecycle_tasks.auto_submit_expired_attempts",
        "schedule": 20.0,  # seconds — the "safety net" from docs/spec.md section 3 step 7
    },
    "flip-expired-unstarted": {
        "task": "app.tasks.exam_lifecycle_tasks.mark_expired_unstarted",
        "schedule": 60.0,
    },
}

# Registers the tasks in this process too (not just the worker's), so
# celery_eager + send_task-by-name can find and run them without a worker.
from app.tasks import exam_lifecycle_tasks, parsing_tasks  # noqa: E402, F401
