"""Covers parse_confidence propagating from the parser all the way to the
Question row and the review API response. Previously the parser's
confidence signal (ParsedQuestion.confidence) was computed but dropped on
the floor at materialization time — only visible in ExamUpload's
diagnostic-only raw_parse_debug, never to the teacher reviewing the exam.
The user asked for it to be surfaced so a low-confidence parsed question
gets extra scrutiny.
"""

from app.models.exam import ExamUpload, UploadFileType, UploadStatus
from app.parsers.base import ParsedOption, ParsedQuestion
from app.services import parsing_service
from app.tests.factories import make_admin, make_class, make_subject


def _login(client, username, password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_process_upload_persists_parse_confidence_per_question(client, db_session, monkeypatch):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    admin = make_admin(db_session, username="confidence_admin")
    db_session.commit()

    upload = ExamUpload(
        uploaded_by_id=admin.id,
        original_filename="test.docx",
        file_type=UploadFileType.docx,
        storage_key="fake-key",
        status=UploadStatus.pending,
    )
    db_session.add(upload)
    db_session.commit()

    monkeypatch.setattr(parsing_service, "download_exam_file", lambda key: b"irrelevant")
    fake_questions = [
        ParsedQuestion(
            prompt="Aniq savol",
            confidence="high",
            options=[
                ParsedOption("A", is_correct=True),
                ParsedOption("B"),
                ParsedOption("C"),
                ParsedOption("D"),
            ],
        ),
        ParsedQuestion(prompt="Noaniq savol", confidence="low", options=[]),
    ]
    monkeypatch.setattr(parsing_service._PARSERS["docx"], "parse", lambda file_bytes: fake_questions)

    exam = parsing_service.process_upload(db_session, upload, subject_id=subject.id, class_id=klass.id)

    persisted = {q.prompt_text: q.parse_confidence for q in exam.questions}
    assert persisted == {"Aniq savol": "high", "Noaniq savol": "low"}

    token = _login(client, "confidence_admin")
    resp = client.get(f"/api/v1/admin/exams/{exam.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    by_prompt = {q["prompt_text"]: q["parse_confidence"] for q in resp.json()["questions"]}
    assert by_prompt == {"Aniq savol": "high", "Noaniq savol": "low"}


def test_manually_added_question_has_no_parse_confidence(client, db_session):
    from app.tests.factories import make_exam

    klass = make_class(db_session)
    subject = make_subject(db_session)
    admin = make_admin(db_session, username="manual_q_admin")
    exam = make_exam(db_session, klass, subject, created_by=admin)
    db_session.commit()
    token = _login(client, "manual_q_admin")

    resp = client.post(
        f"/api/v1/admin/exams/{exam.id}/questions",
        json={
            "prompt_text": "Qo'lda qo'shilgan savol",
            "points": 1,
            "options": [
                {"option_text": "A", "is_correct": True},
                {"option_text": "B", "is_correct": False},
                {"option_text": "C", "is_correct": False},
                {"option_text": "D", "is_correct": False},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["parse_confidence"] is None
