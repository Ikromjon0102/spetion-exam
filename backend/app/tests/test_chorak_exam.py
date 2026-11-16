"""Choraklik (end-of-quarter) exams: one sitting made of subject blocks, each
block with its own points-per-question and its own teacher.

The shape under test is a scaled-down version of the real one (Kimyo 30x3.1,
Biologiya 30x2.1, three compulsory subjects 10x1.1 = 189 points): here
Kimyo 3x3.1 + Biologiya 2x2.1 + Tarix 2x1.1 = 15.7 points.
"""

from datetime import datetime, timedelta, timezone

from app.models.attempt import AttemptSectionScore
from app.models.exam import Exam, Question
from app.models.ranking import StudentSubjectStats
from app.models.user import TeacherClassSubject
from app.tests.factories import (
    add_mcq_question,
    make_admin,
    make_class,
    make_exam,
    make_student,
    make_subject,
    make_teacher,
)

API = "/api/v1/admin/exams"


def _login(client, username, password="secret123", class_id=None):
    body = {"username": username, "password": password}
    if class_id is not None:
        body["class_id"] = class_id
    resp = client.post("/api/v1/auth/login", json=body)
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _setup(client, db):
    """An admin, a class, three subjects each with its own teacher, a template
    and one chorak exam created from it. Returns a dict of the pieces."""
    make_admin(db, username="boss")
    klass = make_class(db, label="med", grade_level=10)
    kimyo, bio, tarix = (make_subject(db, name=n) for n in ("Kimyo", "Biologiya", "Tarix"))
    teachers = {}
    for name, subject in (("kimyo_t", kimyo), ("bio_t", bio), ("tarix_t", tarix)):
        teacher = make_teacher(db, subject=subject, username=name)
        db.add(TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id))
        teachers[name] = teacher
    db.commit()

    admin = _login(client, "boss")
    resp = client.post(
        f"{API}/templates",
        headers=admin,
        json={
            "name": "Tibbiyot",
            "sections": [
                {"subject_id": kimyo.id, "kind": "asosiy", "question_count": 3, "points_per_question": 3.1},
                {"subject_id": bio.id, "kind": "asosiy", "question_count": 2, "points_per_question": 2.1},
                {"subject_id": tarix.id, "kind": "majburiy", "question_count": 2, "points_per_question": 1.1},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    template = resp.json()

    now = datetime.now(timezone.utc)
    resp = client.post(
        f"{API}/chorak",
        headers=admin,
        json={
            "title": "1-chorak imtihoni",
            "template_id": template["id"],
            "class_ids": [klass.id],
            "quarter": 1,
            "start_at": (now - timedelta(minutes=5)).isoformat(),
            "end_at": (now + timedelta(hours=4)).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text
    exam = resp.json()[0]
    return {
        "admin": admin,
        "klass": klass,
        "subjects": {"kimyo": kimyo, "bio": bio, "tarix": tarix},
        "template": template,
        "exam": exam,
        "sections": {s["subject_name"]: s for s in exam["sections"]},
    }


def _mcq(section_id):
    return {
        "prompt_text": "Savol?",
        "section_id": section_id,
        "options": [
            {"option_text": "To'g'ri", "is_correct": True},
            {"option_text": "Xato 1", "is_correct": False},
            {"option_text": "Xato 2", "is_correct": False},
        ],
    }


def _fill_and_publish(client, ctx):
    """Every teacher writes their own block and marks it ready; admin publishes."""
    exam_id = ctx["exam"]["id"]
    for username, subject_name in (("kimyo_t", "Kimyo"), ("bio_t", "Biologiya"), ("tarix_t", "Tarix")):
        headers = _login(client, username)
        section = ctx["sections"][subject_name]
        for _ in range(section["question_count"]):
            resp = client.post(f"{API}/{exam_id}/questions", headers=headers, json=_mcq(section["id"]))
            assert resp.status_code == 201, resp.text
        resp = client.put(f"{API}/{exam_id}/sections/{section['id']}/ready", headers=headers, json={"ready": True})
        assert resp.status_code == 200, resp.text
    resp = client.post(f"{API}/{exam_id}/publish", headers=ctx["admin"])
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_template_reports_its_totals(client, db_session):
    ctx = _setup(client, db_session)
    assert ctx["template"]["total_questions"] == 7
    assert ctx["template"]["total_points"] == 15.7
    assert ctx["template"]["duration_minutes"] == 180


def test_real_school_layout_adds_up_to_189(client, db_session):
    make_admin(db_session, username="boss")
    ids = [make_subject(db_session, name=n).id for n in ("Kimyo", "Biologiya", "Ona tili", "Matematika", "Tarix")]
    db_session.commit()
    resp = client.post(
        f"{API}/templates",
        headers=_login(client, "boss"),
        json={
            "name": "Tibbiyot",
            "sections": [
                {"subject_id": ids[0], "question_count": 30, "points_per_question": 3.1},
                {"subject_id": ids[1], "question_count": 30, "points_per_question": 2.1},
                {"subject_id": ids[2], "kind": "majburiy", "question_count": 10, "points_per_question": 1.1},
                {"subject_id": ids[3], "kind": "majburiy", "question_count": 10, "points_per_question": 1.1},
                {"subject_id": ids[4], "kind": "majburiy", "question_count": 10, "points_per_question": 1.1},
            ],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["total_questions"] == 90
    assert resp.json()["total_points"] == 189


def test_template_rejects_a_repeated_subject_and_a_duplicate_name(client, db_session):
    ctx = _setup(client, db_session)
    kimyo = ctx["subjects"]["kimyo"].id
    section = {"subject_id": kimyo, "question_count": 5, "points_per_question": 1}
    resp = client.post(f"{API}/templates", headers=ctx["admin"], json={"name": "X", "sections": [section, section]})
    assert resp.status_code == 400
    resp = client.post(f"{API}/templates", headers=ctx["admin"], json={"name": "Tibbiyot", "sections": [section]})
    assert resp.status_code == 409


def test_only_admin_manages_templates_and_creates_chorak_exams(client, db_session):
    ctx = _setup(client, db_session)
    teacher = _login(client, "kimyo_t")
    assert client.get(f"{API}/templates", headers=teacher).status_code == 403
    resp = client.post(
        f"{API}/chorak",
        headers=teacher,
        json={"title": "X", "template_id": ctx["template"]["id"], "class_ids": [ctx["klass"].id]},
    )
    assert resp.status_code == 403


def test_created_exam_is_a_draft_with_the_templates_blocks(client, db_session):
    ctx = _setup(client, db_session)
    exam = ctx["exam"]
    assert exam["exam_type"] == "chorak"
    assert exam["status"] == "draft"
    assert exam["quarter"] == 1
    assert exam["duration_minutes"] == 180
    assert exam["expected_question_count"] == 7
    assert [s["subject_name"] for s in exam["sections"]] == ["Kimyo", "Biologiya", "Tarix"]
    assert [s["kind"] for s in exam["sections"]] == ["asosiy", "asosiy", "majburiy"]
    assert exam["sections"][0]["teacher_names"] == ["Ustoz"]
    assert all(not s["is_ready"] for s in exam["sections"])


def test_one_exam_per_class(client, db_session):
    ctx = _setup(client, db_session)
    other = make_class(db_session, label="huquq", grade_level=10)
    db_session.commit()
    resp = client.post(
        f"{API}/chorak",
        headers=ctx["admin"],
        json={"title": "2-chorak", "template_id": ctx["template"]["id"], "class_ids": [ctx["klass"].id, other.id]},
    )
    assert resp.status_code == 201
    assert sorted(e["class_id"] for e in resp.json()) == sorted([ctx["klass"].id, other.id])


def test_teacher_sees_the_exam_but_may_edit_only_their_own_block(client, db_session):
    ctx = _setup(client, db_session)
    exam_id = ctx["exam"]["id"]
    kimyo_t = _login(client, "kimyo_t")

    listed = client.get(API, headers=kimyo_t).json()
    assert [e["id"] for e in listed] == [exam_id]
    assert listed[0]["can_administer"] is False
    assert {s["subject_name"]: s["can_edit"] for s in listed[0]["sections"]} == {
        "Kimyo": True,
        "Biologiya": False,
        "Tarix": False,
    }

    own = client.post(f"{API}/{exam_id}/questions", headers=kimyo_t, json=_mcq(ctx["sections"]["Kimyo"]["id"]))
    assert own.status_code == 201
    # the block's weight, not whatever the request said
    assert own.json()["points"] == 3.1
    assert own.json()["section_id"] == ctx["sections"]["Kimyo"]["id"]

    foreign = client.post(f"{API}/{exam_id}/questions", headers=kimyo_t, json=_mcq(ctx["sections"]["Tarix"]["id"]))
    assert foreign.status_code == 403
    no_block = client.post(f"{API}/{exam_id}/questions", headers=kimyo_t, json=_mcq(None))
    assert no_block.status_code == 400


def test_teacher_reads_only_their_own_blocks_questions(client, db_session):
    ctx = _setup(client, db_session)
    exam_id = ctx["exam"]["id"]
    client.post(f"{API}/{exam_id}/questions", headers=_login(client, "kimyo_t"), json=_mcq(ctx["sections"]["Kimyo"]["id"]))
    bio = client.post(
        f"{API}/{exam_id}/questions", headers=_login(client, "bio_t"), json=_mcq(ctx["sections"]["Biologiya"]["id"])
    ).json()

    kimyo_t = _login(client, "kimyo_t")
    detail = client.get(f"{API}/{exam_id}", headers=kimyo_t).json()
    assert [q["section_id"] for q in detail["questions"]] == [ctx["sections"]["Kimyo"]["id"]]
    assert detail["question_count"] == 1
    assert len(client.get(f"{API}/{exam_id}", headers=ctx["admin"]).json()["questions"]) == 2

    # and cannot change or delete a colleague's question
    assert client.put(f"{API}/{exam_id}/questions/{bio['id']}", headers=kimyo_t, json={"prompt_text": "x"}).status_code == 403
    assert client.delete(f"{API}/{exam_id}/questions/{bio['id']}", headers=kimyo_t).status_code == 403


def test_a_teacher_of_no_block_cannot_open_the_exam(client, db_session):
    ctx = _setup(client, db_session)
    outsider_subject = make_subject(db_session, name="Musiqa")
    outsider = make_teacher(db_session, subject=outsider_subject, username="musiqa_t")
    db_session.add(
        TeacherClassSubject(teacher_id=outsider.id, class_id=ctx["klass"].id, subject_id=outsider_subject.id)
    )
    db_session.commit()
    headers = _login(client, "musiqa_t")
    assert client.get(API, headers=headers).json() == []
    assert client.get(f"{API}/{ctx['exam']['id']}", headers=headers).status_code == 403


def test_exam_wide_actions_are_admin_only(client, db_session):
    ctx = _setup(client, db_session)
    exam_id = ctx["exam"]["id"]
    teacher = _login(client, "kimyo_t")
    assert client.put(f"{API}/{exam_id}", headers=teacher, json={"duration_minutes": 10}).status_code == 403
    assert client.post(f"{API}/{exam_id}/publish", headers=teacher).status_code == 403
    assert client.delete(f"{API}/{exam_id}", headers=teacher).status_code == 403
    assert client.put(f"{API}/{exam_id}", headers=ctx["admin"], json={"duration_minutes": 170}).status_code == 200


def test_points_of_a_block_question_cannot_be_changed(client, db_session):
    ctx = _setup(client, db_session)
    exam_id = ctx["exam"]["id"]
    q = client.post(f"{API}/{exam_id}/questions", headers=ctx["admin"], json=_mcq(ctx["sections"]["Kimyo"]["id"])).json()
    resp = client.put(f"{API}/{exam_id}/questions/{q['id']}", headers=ctx["admin"], json={"points": 50})
    assert resp.status_code == 200
    assert resp.json()["points"] == 3.1


def test_block_is_ready_only_with_the_agreed_number_of_reviewed_questions(client, db_session):
    ctx = _setup(client, db_session)
    exam_id = ctx["exam"]["id"]
    section = ctx["sections"]["Biologiya"]  # needs 2
    bio_t = _login(client, "bio_t")
    ready = f"{API}/{exam_id}/sections/{section['id']}/ready"

    first = client.post(f"{API}/{exam_id}/questions", headers=bio_t, json=_mcq(section["id"])).json()
    assert client.put(ready, headers=bio_t, json={"ready": True}).status_code == 400  # 1 of 2

    client.post(f"{API}/{exam_id}/questions", headers=bio_t, json=_mcq(section["id"]))
    client.put(f"{API}/{exam_id}/questions/{first['id']}", headers=bio_t, json={"needs_review": True})
    assert client.put(ready, headers=bio_t, json={"ready": True}).status_code == 400  # one unreviewed

    client.put(f"{API}/{exam_id}/questions/{first['id']}", headers=bio_t, json={"needs_review": False})
    resp = client.put(ready, headers=bio_t, json={"ready": True})
    assert resp.status_code == 200
    assert {s["subject_name"]: s["is_ready"] for s in resp.json()["sections"]}["Biologiya"] is True

    # another block's teacher can't flip it; its own teacher can take it back
    assert client.put(ready, headers=_login(client, "kimyo_t"), json={"ready": False}).status_code == 403
    assert client.put(ready, headers=bio_t, json={"ready": False}).status_code == 200


def test_publish_needs_every_block_ready(client, db_session):
    ctx = _setup(client, db_session)
    exam_id = ctx["exam"]["id"]
    # only Kimyo is written and ready
    section = ctx["sections"]["Kimyo"]
    for _ in range(3):
        client.post(f"{API}/{exam_id}/questions", headers=ctx["admin"], json=_mcq(section["id"]))
    client.put(f"{API}/{exam_id}/sections/{section['id']}/ready", headers=ctx["admin"], json={"ready": True})
    resp = client.post(f"{API}/{exam_id}/publish", headers=ctx["admin"])
    assert resp.status_code == 400
    assert "Biologiya" in resp.json()["detail"]


def test_published_total_is_the_sum_of_the_block_weights(client, db_session):
    ctx = _setup(client, db_session)
    published = _fill_and_publish(client, ctx)
    assert published["status"] == "scheduled"
    assert published["total_points"] == 15.7
    assert published["question_count"] == 7


def _sit(client, db, ctx, username, correct_by_subject):
    """A student sits the exam, answering correctly the first N questions of
    each block (N from correct_by_subject) and wrongly the rest."""
    student = make_student(db, ctx["klass"], username=username, full_name=username)
    db.commit()
    headers = _login(client, username, class_id=ctx["klass"].id)
    exam_id = ctx["exam"]["id"]
    state = client.post(f"/api/v1/student/exams/{exam_id}/start", headers=headers).json()
    section_names = {s["id"]: s["subject_name"] for s in state["sections"]}
    seen: dict[str, int] = {}
    for q in state["questions"]:
        name = section_names[q["section_id"]]
        index = seen.get(name, 0)
        seen[name] = index + 1
        options = {o["option_text"]: o["id"] for o in q["options"]}
        pick = options["To'g'ri"] if index < correct_by_subject.get(name, 0) else options["Xato 1"]
        resp = client.put(
            f"/api/v1/student/exams/{exam_id}/answers/{q['id']}", headers=headers, json={"selected_option_id": pick}
        )
        assert resp.status_code == 204
    resp = client.post(f"/api/v1/student/exams/{exam_id}/submit", headers=headers)
    assert resp.status_code == 200, resp.text
    return student, headers, state, resp.json()


def test_student_gets_the_paper_block_by_block(client, db_session):
    ctx = _setup(client, db_session)
    _fill_and_publish(client, ctx)
    make_student(db_session, ctx["klass"], username="ali")
    db_session.commit()
    headers = _login(client, "ali", class_id=ctx["klass"].id)

    info = client.get(f"/api/v1/student/exams/{ctx['exam']['id']}/info", headers=headers).json()
    assert info["exam_type"] == "chorak"
    assert info["question_count"] == 7
    assert info["total_points"] == 15.7
    assert info["my_attempt_status"] is None  # reading the info starts nothing
    assert [s["subject_name"] for s in info["sections"]] == ["Kimyo", "Biologiya", "Tarix"]

    state = client.post(f"/api/v1/student/exams/{ctx['exam']['id']}/start", headers=headers).json()
    order = [s["id"] for s in state["sections"]]
    # shuffled inside a block, but the blocks stay in the paper's order
    assert [q["section_id"] for q in state["questions"]] == [order[0]] * 3 + [order[1]] * 2 + [order[2]] * 2


def test_grading_weights_each_block_and_rounds(client, db_session):
    ctx = _setup(client, db_session)
    _fill_and_publish(client, ctx)
    student, headers, _state, submitted = _sit(client, db_session, ctx, "ali", {"Kimyo": 2, "Biologiya": 1, "Tarix": 2})

    # 2 x 3.1 + 1 x 2.1 + 2 x 1.1 = 10.5 exactly, not 10.500000000000002
    assert submitted["score"] == 10.5
    assert submitted["max_score"] == 15.7

    result = client.get(f"/api/v1/student/exams/{ctx['exam']['id']}/result", headers=headers).json()
    assert result["exam_type"] == "chorak"
    assert [(s["subject_name"], s["score"], s["max_score"], s["correct_count"], s["question_count"]) for s in result["sections"]] == [
        ("Kimyo", 6.2, 9.3, 2, 3),
        ("Biologiya", 2.1, 4.2, 1, 2),
        ("Tarix", 2.2, 2.2, 2, 2),
    ]
    assert all(q["section_id"] is not None for q in result["questions"])
    assert db_session.query(AttemptSectionScore).filter_by(student_id=student.id).count() == 3


def test_each_block_counts_towards_its_own_subject(client, db_session):
    ctx = _setup(client, db_session)
    _fill_and_publish(client, ctx)
    student, headers, _state, _ = _sit(client, db_session, ctx, "ali", {"Kimyo": 3, "Biologiya": 0, "Tarix": 1})

    stats = {s.subject_id: s for s in db_session.query(StudentSubjectStats).filter_by(student_id=student.id)}
    kimyo, bio, tarix = (ctx["subjects"][k].id for k in ("kimyo", "bio", "tarix"))
    assert float(stats[kimyo].average_percent) == 100
    assert float(stats[bio].average_percent) == 0
    assert float(stats[tarix].average_percent) == 50
    assert float(stats[kimyo].total_points_possible) == 9.3

    history = client.get(f"/api/v1/student/me/subjects/{kimyo}/history", headers=headers).json()
    assert [(p["exam_type"], p["score"], p["max_score"]) for p in history["timeline"]] == [("chorak", 9.3, 9.3)]


def test_section_results_full_for_admin_own_block_for_its_teacher(client, db_session):
    ctx = _setup(client, db_session)
    _fill_and_publish(client, ctx)
    _sit(client, db_session, ctx, "ali", {"Kimyo": 3, "Biologiya": 2, "Tarix": 2})
    _sit(client, db_session, ctx, "vali", {"Kimyo": 0, "Biologiya": 2, "Tarix": 0})
    make_student(db_session, ctx["klass"], username="absent", full_name="absent")
    db_session.commit()
    url = f"{API}/{ctx['exam']['id']}/section-results"

    full = client.get(url, headers=ctx["admin"]).json()
    assert full["shows_total"] is True
    assert full["max_total"] == 15.7
    assert [s["subject_name"] for s in full["sections"]] == ["Kimyo", "Biologiya", "Tarix"]
    assert [(r["full_name"], r["rank"], r["scores"], r["total"]) for r in full["students"]] == [
        ("ali", 1, [9.3, 4.2, 2.2], 15.7),
        ("vali", 2, [0.0, 4.2, 0.0], 4.2),
        ("absent", None, [None, None, None], None),
    ]

    own = client.get(url, headers=_login(client, "bio_t")).json()
    assert own["shows_total"] is False
    assert [s["subject_name"] for s in own["sections"]] == ["Biologiya"]
    # ranked by their own block: both got 4.2, a shared 1st place; no totals
    assert [(r["full_name"], r["rank"], r["scores"], r["total"]) for r in own["students"][:2]] == [
        ("ali", 1, [4.2], None),
        ("vali", 1, [4.2], None),
    ]
    # the monitor list hides the paper's total from a block's teacher too
    monitor = client.get(f"{API}/{ctx['exam']['id']}/attempts", headers=_login(client, "bio_t")).json()
    assert all(row["score"] is None for row in monitor)
    assert client.get(f"/api/v1/admin/exams/{ctx['exam']['id']}/ranking", headers=_login(client, "bio_t")).json()["rankings"] == []


def test_homeroom_teacher_sees_the_whole_table_without_teaching_a_block(client, db_session):
    ctx = _setup(client, db_session)
    _fill_and_publish(client, ctx)
    _sit(client, db_session, ctx, "ali", {"Kimyo": 1})
    homeroom = make_teacher(db_session, username="rahbar")
    ctx["klass"].homeroom_teacher_id = homeroom.id
    db_session.commit()
    resp = client.get(f"{API}/{ctx['exam']['id']}/section-results", headers=_login(client, "rahbar"))
    assert resp.status_code == 200
    assert resp.json()["shows_total"] is True
    assert len(resp.json()["sections"]) == 3


def test_teacher_reviews_only_their_blocks_answers(client, db_session):
    ctx = _setup(client, db_session)
    _fill_and_publish(client, ctx)
    student, *_ = _sit(client, db_session, ctx, "ali", {"Kimyo": 1})
    url = f"{API}/{ctx['exam']['id']}/attempts/{student.id}/answers"
    rows = client.get(url, headers=_login(client, "tarix_t")).json()
    assert len(rows) == 2
    assert {r["section_id"] for r in rows} == {ctx["sections"]["Tarix"]["id"]}
    assert rows[0]["correct_option_text"] == "To'g'ri"
    assert len(client.get(url, headers=ctx["admin"]).json()) == 7


def test_overall_ranking_can_be_limited_to_one_kind_of_exam(client, db_session):
    ctx = _setup(client, db_session)
    _fill_and_publish(client, ctx)
    student, *_ = _sit(client, db_session, ctx, "ali", {"Kimyo": 3, "Biologiya": 2, "Tarix": 2})  # 100% chorak

    # plus a nazorat exam in Kimyo the same student fails outright
    now = datetime.now(timezone.utc)
    nazorat = make_exam(
        db_session, ctx["klass"], ctx["subjects"]["kimyo"], start_at=now - timedelta(minutes=1), end_at=now + timedelta(hours=1)
    )
    add_mcq_question(db_session, nazorat, correct_index=0)
    db_session.commit()
    assert client.post(f"{API}/{nazorat.id}/publish", headers=ctx["admin"]).status_code == 200
    headers = _login(client, "ali", class_id=ctx["klass"].id)
    client.post(f"/api/v1/student/exams/{nazorat.id}/start", headers=headers)
    client.post(f"/api/v1/student/exams/{nazorat.id}/submit", headers=headers)

    url = f"/api/v1/admin/classes/{ctx['klass'].id}/overall-ranking"

    def percent(params):
        rows = client.get(url, headers=ctx["admin"], params=params).json()["rankings"]
        return rows[0]["average_percent"] if rows else None

    assert percent({"exam_type": "chorak"}) == 100
    assert percent({"exam_type": "nazorat"}) == 0
    assert percent({}) == round(100 * 15.7 / 16.7, 2)
    assert client.get(url, headers=ctx["admin"], params={"exam_type": "x"}).status_code == 422


def test_daily_results_show_one_column_per_block(client, db_session):
    ctx = _setup(client, db_session)
    _fill_and_publish(client, ctx)
    _sit(client, db_session, ctx, "ali", {"Kimyo": 3, "Biologiya": 1})
    body = client.get(f"/api/v1/admin/classes/{ctx['klass'].id}/daily-results", headers=ctx["admin"]).json()
    assert [(e["subject_name"], e["max_score"]) for e in body["exams"]] == [
        ("Kimyo", 9.3),
        ("Biologiya", 4.2),
        ("Tarix", 2.2),
    ]
    assert body["students"][0]["scores"] == [9.3, 2.1, 0.0]


def test_duplicating_copies_the_blocks_and_resets_their_ready_state(client, db_session):
    ctx = _setup(client, db_session)
    _fill_and_publish(client, ctx)
    other = make_class(db_session, label="med2", grade_level=10)
    db_session.commit()
    resp = client.post(f"{API}/{ctx['exam']['id']}/duplicate", headers=ctx["admin"], json={"class_ids": [other.id]})
    assert resp.status_code == 200, resp.text
    copy = resp.json()[0]
    assert copy["exam_type"] == "chorak"
    assert copy["status"] == "draft"
    assert [(s["subject_name"], s["actual_count"], s["is_ready"]) for s in copy["sections"]] == [
        ("Kimyo", 3, False),
        ("Biologiya", 2, False),
        ("Tarix", 2, False),
    ]
    section_ids = {s["id"] for s in copy["sections"]}
    assert {q.section_id for q in db_session.query(Question).filter_by(exam_id=copy["id"])} == section_ids


def test_deleting_a_sat_exam_cleans_up_block_scores_and_stats(client, db_session):
    ctx = _setup(client, db_session)
    _fill_and_publish(client, ctx)
    student, *_ = _sit(client, db_session, ctx, "ali", {"Kimyo": 3})
    assert client.delete(f"{API}/{ctx['exam']['id']}", headers=ctx["admin"]).status_code == 204
    assert db_session.get(Exam, ctx["exam"]["id"]) is None
    assert db_session.query(AttemptSectionScore).count() == 0
    assert db_session.query(StudentSubjectStats).filter_by(student_id=student.id).count() == 0


def test_nazorat_exams_are_untouched(client, db_session):
    """The single-subject exam keeps working exactly as before: no blocks,
    per-question points, its own teacher owns it end to end."""
    subject = make_subject(db_session, name="Huquq")
    klass = make_class(db_session, label="huquq", grade_level=10)
    teacher = make_teacher(db_session, subject=subject, username="huquq_t")
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id))
    db_session.commit()
    headers = _login(client, "huquq_t")
    exam = client.post(API, headers=headers, json={"title": "Nazorat", "subject_id": subject.id, "class_id": klass.id}).json()
    assert exam["exam_type"] == "nazorat"
    assert exam["sections"] == []
    assert exam["can_administer"] is True
    q = client.post(
        f"{API}/{exam['id']}/questions", headers=headers, json={**_mcq(None), "points": 2.5}
    ).json()
    assert q["points"] == 2.5
    assert q["section_id"] is None


def test_a_file_is_imported_into_one_block_and_arrives_unreviewed(client, db_session, monkeypatch):
    """A teacher uploads their block's questions as a file: they land in that
    block only, worth the block's weight, all needing review — and a block
    that was marked ready is no longer ready."""
    from app.models.exam import ExamUpload, UploadFileType, UploadStatus
    from app.services import parsing_service
    from app.tests.test_parsers import _sample_docx_bytes

    ctx = _setup(client, db_session)
    exam_id = ctx["exam"]["id"]
    section = ctx["sections"]["Biologiya"]  # needs exactly the 2 the sample file holds
    teacher = db_session.query(TeacherClassSubject).filter_by(subject_id=ctx["subjects"]["bio"].id).one()

    upload = ExamUpload(
        uploaded_by_id=teacher.teacher_id,
        original_filename="bio.docx",
        file_type=UploadFileType.docx,
        storage_key="fake-key",
        status=UploadStatus.pending,
        target_exam_id=exam_id,
        target_section_id=section["id"],
    )
    db_session.add(upload)
    db_session.commit()
    monkeypatch.setattr(parsing_service, "download_exam_file", lambda key: _sample_docx_bytes())

    exam = parsing_service.process_upload(db_session, upload, subject_id=0, class_id=0)

    assert exam.id == exam_id
    assert upload.status == UploadStatus.parsed
    questions = db_session.query(Question).filter_by(exam_id=exam_id).all()
    assert len(questions) == 2
    assert {q.section_id for q in questions} == {section["id"]}
    assert all(q.needs_review for q in questions)
    assert {float(q.points) for q in questions} == {2.1}
    # no stray second exam was created for the file
    assert db_session.query(Exam).count() == 1

    # the upload endpoint itself refuses a block that isn't the caller's
    resp = client.post(
        f"{API}/uploads",
        headers=_login(client, "kimyo_t"),
        data={"exam_id": str(exam_id), "section_id": str(section["id"])},
        files={"file": ("x.docx", b"x", "application/octet-stream")},
    )
    assert resp.status_code == 403
