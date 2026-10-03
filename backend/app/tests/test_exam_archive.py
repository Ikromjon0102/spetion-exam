"""Archiving old exams, plus the filtering/paging that makes a list of 100+
exams a week usable.

A school that sits ~5 exams per class every Saturday ends up with 100 new
exams a week; the flat list could only ever grow. Archive is a *flag*
(Exam.archived_at), deliberately not a status: status keeps its meaning for
the sweep, grading and the student list, restoring loses nothing, and the
graded attempts that feed rankings, stats and the student portfolio are never
touched.
"""

from datetime import datetime, timedelta, timezone

from app.models.exam import ExamStatus
from app.models.ranking import StudentSubjectStats
from app.models.user import TeacherClassSubject
from app.services import attempt_service, exam_service
from app.services.exam_service import publish_exam
from app.tests.factories import (
    add_mcq_question,
    make_admin,
    make_class,
    make_exam,
    make_student,
    make_subject,
    make_teacher,
)

NOW = lambda: datetime.now(timezone.utc)  # noqa: E731


def _login(client, username, class_id=None):
    body = {"username": username, "password": "secret123"}
    if class_id is not None:
        body["class_id"] = class_id
    resp = client.post("/api/v1/auth/login", json=body)
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _admin(client, db_session, username="arch_admin"):
    make_admin(db_session, username=username)
    db_session.commit()
    return _login(client, username)


def _exam(db, klass, subject, *, phase, days_ago_ended=0, author=None):
    """An exam in the requested phase. `finished` ended `days_ago_ended` days ago."""
    now = NOW()
    if phase == "draft":
        return make_exam(db, klass, subject, created_by=author)
    if phase == "upcoming":
        times = dict(start_at=now + timedelta(days=1), end_at=now + timedelta(days=1, hours=2))
    elif phase == "live":
        times = dict(start_at=now - timedelta(minutes=10), end_at=now + timedelta(hours=1))
    else:
        end = now - timedelta(days=days_ago_ended, hours=1)
        times = dict(start_at=end - timedelta(hours=2), end_at=end)
    return make_exam(db, klass, subject, status=ExamStatus.scheduled, created_by=author, **times)


def _ids(resp):
    return [e["id"] for e in resp.json()]


def test_archive_hides_from_working_list_and_restore_brings_it_back(client, db_session):
    klass, subject = make_class(db_session), make_subject(db_session)
    headers = _admin(client, db_session)
    old = _exam(db_session, klass, subject, phase="finished", days_ago_ended=10)
    db_session.commit()

    assert _ids(client.get("/api/v1/admin/exams", headers=headers)) == [old.id]

    resp = client.post("/api/v1/admin/exams/archive", json={"exam_ids": [old.id]}, headers=headers)
    assert resp.status_code == 200 and resp.json() == {"changed": [old.id], "skipped": []}
    assert _ids(client.get("/api/v1/admin/exams", headers=headers)) == []
    archived = client.get("/api/v1/admin/exams?archived=true", headers=headers)
    assert _ids(archived) == [old.id] and archived.json()[0]["archived_at"] is not None

    resp = client.post("/api/v1/admin/exams/restore", json={"exam_ids": [old.id]}, headers=headers)
    assert resp.json()["changed"] == [old.id]
    assert _ids(client.get("/api/v1/admin/exams", headers=headers)) == [old.id]
    assert _ids(client.get("/api/v1/admin/exams?archived=true", headers=headers)) == []


def test_archiving_never_touches_graded_results(client, db_session):
    klass, subject = make_class(db_session), make_subject(db_session)
    student = make_student(db_session, klass, username="arch_graded")
    headers = _admin(client, db_session)
    now = NOW()
    exam = make_exam(db_session, klass, subject, start_at=now - timedelta(hours=1), end_at=now + timedelta(hours=2))
    add_mcq_question(db_session, exam, correct_index=0, points=1)
    db_session.commit()
    publish_exam(db_session, exam)
    attempt = attempt_service.start_attempt(db_session, exam, student)
    attempt_service.record_answer(db_session, attempt, exam.questions[0].id, exam.questions[0].options[0].id, None)
    attempt_service.submit_attempt(db_session, attempt.id)
    exam.start_at, exam.end_at = now - timedelta(days=9), now - timedelta(days=8)  # the window is long over
    db_session.commit()

    assert client.post("/api/v1/admin/exams/archive", json={"exam_ids": [exam.id]}, headers=headers).json()["changed"] == [exam.id]

    stats = db_session.query(StudentSubjectStats).filter_by(student_id=student.id, subject_id=subject.id).one()
    assert float(stats.total_points_earned) == 1.0 and stats.exams_taken_count == 1
    # ...and the student's portfolio still lists it, archived or not
    student_headers = _login(client, "arch_graded", klass.id)
    history = client.get(f"/api/v1/student/me/subjects/{subject.id}/history", headers=student_headers).json()
    assert [p["exam_id"] for p in history["timeline"]] == [exam.id]


def test_only_drafts_and_finished_exams_can_be_archived(client, db_session):
    klass, subject = make_class(db_session), make_subject(db_session)
    headers = _admin(client, db_session)
    author = make_admin(db_session, username="arch_author")
    draft = _exam(db_session, klass, subject, phase="draft", author=author)
    upcoming = _exam(db_session, klass, subject, phase="upcoming", author=author)
    live = _exam(db_session, klass, subject, phase="live", author=author)
    finished = _exam(db_session, klass, subject, phase="finished", days_ago_ended=1, author=author)
    db_session.commit()

    body = client.post(
        "/api/v1/admin/exams/archive",
        json={"exam_ids": [draft.id, upcoming.id, live.id, finished.id, 999999]},
        headers=headers,
    ).json()

    assert sorted(body["changed"]) == sorted([draft.id, finished.id])
    reasons = {s["exam_id"]: s["reason"] for s in body["skipped"]}
    assert reasons == {upcoming.id: "not_finished", live.id: "not_finished", 999999: "not_found"}

    # archiving twice / restoring something never archived are reported, not errors
    again = client.post("/api/v1/admin/exams/archive", json={"exam_ids": [finished.id]}, headers=headers).json()
    assert again["changed"] == [] and again["skipped"][0]["reason"] == "already_archived"
    nope = client.post("/api/v1/admin/exams/restore", json={"exam_ids": [live.id]}, headers=headers).json()
    assert nope["changed"] == [] and nope["skipped"][0]["reason"] == "not_archived"


def test_teachers_archive_and_restore_only_their_own_exams(client, db_session):
    mine_class, other_class = make_class(db_session), make_class(db_session)
    subject = make_subject(db_session)
    teacher = make_teacher(db_session, subject=subject, username="arch_teacher")
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=mine_class.id, subject_id=subject.id))
    mine = _exam(db_session, mine_class, subject, phase="finished", days_ago_ended=3)
    theirs = _exam(db_session, other_class, subject, phase="finished", days_ago_ended=3)
    db_session.commit()
    headers = _login(client, "arch_teacher")

    body = client.post("/api/v1/admin/exams/archive", json={"exam_ids": [mine.id, theirs.id]}, headers=headers).json()
    assert body["changed"] == [mine.id]
    assert body["skipped"] == [{"exam_id": theirs.id, "reason": "forbidden"}]

    # the teacher can see and restore their own archived exam, and nobody else's
    assert _ids(client.get("/api/v1/admin/exams?archived=true", headers=headers)) == [mine.id]
    assert client.post("/api/v1/admin/exams/restore", json={"exam_ids": [mine.id]}, headers=headers).json()["changed"] == [mine.id]


def test_archive_old_only_takes_exams_finished_longer_ago_than_the_cutoff(client, db_session):
    klass, subject = make_class(db_session), make_subject(db_session)
    headers = _admin(client, db_session)
    author = make_admin(db_session, username="arch_author2")
    stale = _exam(db_session, klass, subject, phase="finished", days_ago_ended=20, author=author)
    recent = _exam(db_session, klass, subject, phase="finished", days_ago_ended=2, author=author)
    live = _exam(db_session, klass, subject, phase="live", author=author)
    draft = _exam(db_session, klass, subject, phase="draft", author=author)
    db_session.commit()

    body = client.post("/api/v1/admin/exams/archive-old", json={"days": 14}, headers=headers).json()

    assert body["changed"] == [stale.id]
    assert sorted(_ids(client.get("/api/v1/admin/exams", headers=headers))) == sorted([recent.id, live.id, draft.id])
    assert client.post("/api/v1/admin/exams/archive-old", json={"days": 14}, headers=headers).json()["changed"] == []
    assert client.post("/api/v1/admin/exams/archive-old", json={"days": 0}, headers=headers).status_code == 422


def test_phase_is_derived_from_the_window_and_the_filter_agrees_with_it(client, db_session):
    klass, subject = make_class(db_session), make_subject(db_session)
    headers = _admin(client, db_session)
    author = make_admin(db_session, username="arch_author3")
    made = {p: _exam(db_session, klass, subject, phase=p, author=author) for p in ("draft", "upcoming", "live", "finished")}
    db_session.commit()

    listed = {e["id"]: e["phase"] for e in client.get("/api/v1/admin/exams", headers=headers).json()}
    assert listed == {made[p].id: p for p in made}
    assert all(exam_service.exam_phase(made[p]) == p for p in made)
    for p in made:
        assert _ids(client.get(f"/api/v1/admin/exams?phase={p}", headers=headers)) == [made[p].id]
    assert client.get("/api/v1/admin/exams?phase=nonsense", headers=headers).status_code == 422

    can_archive = {e["id"]: e["can_archive"] for e in client.get("/api/v1/admin/exams", headers=headers).json()}
    assert can_archive == {made["draft"].id: True, made["upcoming"].id: False, made["live"].id: False, made["finished"].id: True}


def test_filters_search_and_paging(client, db_session):
    klass_a, klass_b = make_class(db_session), make_class(db_session)
    math, physics = make_subject(db_session, name="Matematika"), make_subject(db_session, name="Fizika")
    headers = _admin(client, db_session)
    author = make_admin(db_session, username="arch_author4")
    exams = [_exam(db_session, klass_a if i % 2 else klass_b, math if i < 4 else physics, phase="finished", days_ago_ended=i, author=author) for i in range(6)]
    exams[0].title = "Algebra choraklik"
    add_mcq_question(db_session, exams[1], needs_review=True)
    db_session.commit()

    page1 = client.get("/api/v1/admin/exams?limit=4", headers=headers)
    page2 = client.get("/api/v1/admin/exams?limit=4&offset=4", headers=headers)
    assert page1.headers["X-Total-Count"] == "6" and len(page1.json()) == 4 and len(page2.json()) == 2
    assert not set(_ids(page1)) & set(_ids(page2))
    # newest first: days_ago_ended=0 is the most recent window
    assert _ids(page1)[0] == exams[0].id

    assert sorted(_ids(client.get(f"/api/v1/admin/exams?subject_id={physics.id}", headers=headers))) == sorted([exams[4].id, exams[5].id])
    assert _ids(client.get("/api/v1/admin/exams?q=algebra", headers=headers)) == [exams[0].id]
    assert _ids(client.get("/api/v1/admin/exams?needs_review=true", headers=headers)) == [exams[1].id]
    assert client.get(f"/api/v1/admin/exams?class_id={klass_a.id}", headers=headers).headers["X-Total-Count"] == "3"


def test_summary_counts_the_folders_for_each_tab(client, db_session):
    klass = make_class(db_session)
    math, physics = make_subject(db_session, name="Matematika"), make_subject(db_session, name="Fizika")
    headers = _admin(client, db_session)
    author = make_admin(db_session, username="arch_author5")
    a = _exam(db_session, klass, math, phase="finished", days_ago_ended=1, author=author)
    _exam(db_session, klass, math, phase="finished", days_ago_ended=2, author=author)
    _exam(db_session, klass, physics, phase="finished", days_ago_ended=3, author=author)
    db_session.commit()
    client.post("/api/v1/admin/exams/archive", json={"exam_ids": [a.id]}, headers=headers)

    working = client.get("/api/v1/admin/exams/summary", headers=headers).json()
    assert (working["current"], working["archived"]) == (2, 1)
    assert {s["name"]: s["count"] for s in working["subjects"]} == {"Matematika": 1, "Fizika": 1}

    archive = client.get("/api/v1/admin/exams/summary?archived=true", headers=headers).json()
    assert {s["name"]: s["count"] for s in archive["subjects"]} == {"Matematika": 1}
    assert [c["count"] for c in archive["classes"]] == [1]


def test_student_list_shows_recent_and_current_first_and_old_on_request(client, db_session):
    klass, subject = make_class(db_session), make_subject(db_session)
    make_student(db_session, klass, username="arch_student")
    author = make_admin(db_session, username="arch_author6")
    old = _exam(db_session, klass, subject, phase="finished", days_ago_ended=60, author=author)
    recent = _exam(db_session, klass, subject, phase="finished", days_ago_ended=3, author=author)
    live = _exam(db_session, klass, subject, phase="live", author=author)
    upcoming = _exam(db_session, klass, subject, phase="upcoming", author=author)
    db_session.commit()
    headers = _login(client, "arch_student", klass.id)

    default = client.get("/api/v1/student/me/exams", headers=headers).json()
    assert [e["id"] for e in default] == [live.id, upcoming.id, recent.id]
    everything = client.get("/api/v1/student/me/exams?include_old=true", headers=headers).json()
    assert [e["id"] for e in everything] == [live.id, upcoming.id, recent.id, old.id]


def test_archived_exam_stays_in_the_students_list_and_portfolio(client, db_session):
    """Archive is a staff-side tidy-up; it must not take a recent exam away from
    the students who sat it."""
    klass, subject = make_class(db_session), make_subject(db_session)
    make_student(db_session, klass, username="arch_student2")
    headers = _admin(client, db_session, username="arch_admin_b")
    exam = _exam(db_session, klass, subject, phase="finished", days_ago_ended=2, author=make_admin(db_session, username="arch_author7"))
    db_session.commit()
    client.post("/api/v1/admin/exams/archive", json={"exam_ids": [exam.id]}, headers=headers)

    student_headers = _login(client, "arch_student2", klass.id)
    assert [e["id"] for e in client.get("/api/v1/student/me/exams", headers=student_headers).json()] == [exam.id]
