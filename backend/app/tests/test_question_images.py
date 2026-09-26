"""Covers pasting a screenshot straight into a question prompt or option
instead of typing it (e.g. a formula too complex/slow to retype, or fixing
a garbled OCR result) — the user's own follow-up idea after seeing OCR
struggle with real math notation. Question.prompt_image_key existed in the
schema from the start but was never actually wired up to anything; this is
its first real usage.
"""

import base64
import io

from app.services.exam_service import publish_exam
from app.tests.factories import add_mcq_question, make_admin, make_class, make_exam, make_subject

# A minimal valid 1x1 transparent PNG, just enough for pdfplumber-free
# validation (content-type + size checks) — no real parsing happens here.
_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _login(client, username, password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_headers(client, db_session, username="image_admin"):
    make_admin(db_session, username=username)
    db_session.commit()
    return {"Authorization": f"Bearer {_login(client, username)}"}


def _png_file():
    return {"file": ("screenshot.png", io.BytesIO(_PNG_BYTES), "image/png")}


def test_teacher_can_paste_image_for_question_prompt_and_clear_it(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    question = add_mcq_question(db_session, exam, needs_review=False)
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.post(
        f"/api/v1/admin/exams/{exam.id}/questions/{question.id}/prompt-image",
        headers=headers,
        files=_png_file(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["prompt_image_key"] is not None
    assert body["prompt_image_key"].startswith("question-images/")
    # prompt_text is untouched — the image is an alternative display, not a replacement of the row
    assert body["prompt_text"] == question.prompt_text

    image_resp = client.get(f"/api/v1/admin/exams/uploads/image/{body['prompt_image_key']}", headers=headers)
    assert image_resp.status_code == 200
    assert image_resp.headers["content-type"] == "image/png"
    assert image_resp.content == _PNG_BYTES

    cleared = client.delete(f"/api/v1/admin/exams/{exam.id}/questions/{question.id}/prompt-image", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["prompt_image_key"] is None


def test_teacher_can_paste_image_for_an_option(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    question = add_mcq_question(db_session, exam, needs_review=False)
    option = question.options[0]
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.post(
        f"/api/v1/admin/exams/{exam.id}/questions/{question.id}/options/{option.id}/image",
        headers=headers,
        files=_png_file(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["option_image_key"] is not None
    assert body["is_correct"] == option.is_correct  # untouched by the image upload

    cleared = client.delete(
        f"/api/v1/admin/exams/{exam.id}/questions/{question.id}/options/{option.id}/image", headers=headers
    )
    assert cleared.status_code == 200
    assert cleared.json()["option_image_key"] is None


def test_rejects_non_image_files_and_files_over_the_size_limit(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    question = add_mcq_question(db_session, exam, needs_review=False)
    db_session.commit()
    headers = _admin_headers(client, db_session)

    not_an_image = client.post(
        f"/api/v1/admin/exams/{exam.id}/questions/{question.id}/prompt-image",
        headers=headers,
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert not_an_image.status_code == 400

    too_big = client.post(
        f"/api/v1/admin/exams/{exam.id}/questions/{question.id}/prompt-image",
        headers=headers,
        files={"file": ("big.png", io.BytesIO(b"x" * (9 * 1024 * 1024)), "image/png")},
    )
    assert too_big.status_code == 400


def test_image_upload_blocked_once_a_student_starts_the_exam(client, db_session):
    from datetime import datetime, timedelta, timezone

    from app.models.attempt import AttemptStatus, ExamAttempt
    from app.tests.factories import make_student

    klass = make_class(db_session)
    subject = make_subject(db_session)
    start = datetime.now(timezone.utc)
    exam = make_exam(db_session, klass, subject, start_at=start, end_at=start + timedelta(hours=2))
    question = add_mcq_question(db_session, exam, needs_review=False)
    publish_exam(db_session, exam)
    student = make_student(db_session, klass)
    db_session.add(ExamAttempt(exam_id=exam.id, student_id=student.id, status=AttemptStatus.in_progress))
    db_session.commit()
    headers = _admin_headers(client, db_session)

    resp = client.post(
        f"/api/v1/admin/exams/{exam.id}/questions/{question.id}/prompt-image",
        headers=headers,
        files=_png_file(),
    )
    assert resp.status_code == 409


def test_image_endpoint_requires_auth_but_not_a_specific_role(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    question = add_mcq_question(db_session, exam, needs_review=False)
    db_session.commit()
    admin_headers = _admin_headers(client, db_session)

    upload = client.post(
        f"/api/v1/admin/exams/{exam.id}/questions/{question.id}/prompt-image",
        headers=admin_headers,
        files=_png_file(),
    )
    key = upload.json()["prompt_image_key"]

    anonymous = client.get(f"/api/v1/admin/exams/uploads/image/{key}")
    assert anonymous.status_code == 401
