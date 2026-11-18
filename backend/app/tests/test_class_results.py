"""A whole class's results (a table over a date range) and the class's
dynamics across the school year — and who may see which subject."""

from datetime import date, timedelta

from app.models.exam import ExamStatus
from app.models.user import TeacherClassSubject
from app.tests.factories import make_admin, make_class, make_student, make_subject, make_teacher
from app.tests.test_dynamics import YEAR, _login, _nazorat, _result


def _setup(client, db):
    """Class 10A: three students, Kimyo (4 exams) and Tarix (1 exam). Kimyo's
    teacher, Tarix's teacher, the homeroom teacher (teaches nothing there) and
    an outsider (teaches in another class)."""
    make_admin(db, username="boss")
    klass, other = make_class(db, label="A", grade_level=10), make_class(db, label="B", grade_level=10)
    kimyo, tarix = make_subject(db, name="Kimyo"), make_subject(db, name="Tarix")
    students = {n: make_student(db, klass, username=n, full_name=n.title()) for n in ("ali", "vali", "gani")}
    teachers = {}
    for name, subject, target in (("kimyo_t", kimyo, klass), ("tarix_t", tarix, klass), ("outsider", kimyo, other)):
        teacher = make_teacher(db, subject=subject, username=name)
        db.add(TeacherClassSubject(teacher_id=teacher.id, class_id=target.id, subject_id=subject.id))
        teachers[name] = teacher
    homeroom = make_teacher(db, subject=None, username="homeroom")
    klass.homeroom_teacher_id = homeroom.id
    db.flush()

    # Kimyo: Ali 50 -> 60 -> 80 -> 90, Vali 70 flat, Gani missed the 3rd exam
    days = [date(YEAR, 9, 10) + timedelta(days=7 * i) for i in range(4)]
    plan = {
        "ali": [10, 12, 16, 18],
        "vali": [14, 14, 14, 14],
        "gani": [8, 10, None, 12],
    }
    for i, day in enumerate(days):
        exam = _nazorat(db, klass, kimyo, day, title=f"Kimyo {i + 1}")
        for name, scores in plan.items():
            if scores[i] is not None:
                _result(db, students[name], exam, scores[i], 20, day)
    tarix_day = date(YEAR, 10, 20)
    tarix_exam = _nazorat(db, klass, tarix, tarix_day, title="Tarix 1")
    for name, score in (("ali", 10), ("vali", 20), ("gani", 5)):
        _result(db, students[name], tarix_exam, score, 20, tarix_day)
    db.commit()
    return {"klass": klass, "other": other, "days": days, "tarix_day": tarix_day}


def _get(client, user, path, **params):
    return client.get(f"/api/v1/admin/classes{path}", headers=_login(client, user), params=params)


def test_admin_sees_every_subject_in_one_table(client, db_session):
    ctx = _setup(client, db_session)
    body = _get(client, "boss", f"/{ctx['klass'].id}/results").json()

    assert body["scope"]["all_subjects"] is True
    assert [(c["exam_title"], c["subject_name"]) for c in body["columns"]] == [
        ("Kimyo 1", "Kimyo"),
        ("Kimyo 2", "Kimyo"),
        ("Kimyo 3", "Kimyo"),
        ("Kimyo 4", "Kimyo"),
        ("Tarix 1", "Tarix"),
    ]
    rows = {r["full_name"]: r for r in body["students"]}
    assert [c["percent"] if c else None for c in rows["Ali"]["cells"]] == [50.0, 60.0, 80.0, 90.0, 50.0]
    assert [c is None for c in rows["Gani"]["cells"]] == [False, False, True, False, False]  # missed, not 0
    # total = points earned / possible over what each student took
    assert rows["Ali"]["percent"] == round(100 * (10 + 12 + 16 + 18 + 10) / 100, 1)
    assert rows["Gani"]["percent"] == round(100 * (8 + 10 + 12 + 5) / 80, 1)
    assert [r["full_name"] for r in body["students"]] == ["Vali", "Ali", "Gani"]
    assert [r["rank"] for r in body["students"]] == [1, 2, 3]
    assert body["columns"][0]["taken"] == 3 and body["columns"][2]["taken"] == 2


def test_the_date_range_limits_the_columns(client, db_session):
    ctx = _setup(client, db_session)
    # only the first two Kimyo exams
    body = _get(
        client, "boss", f"/{ctx['klass'].id}/results", start=ctx["days"][0].isoformat(), end=ctx["days"][1].isoformat()
    ).json()
    assert [c["exam_title"] for c in body["columns"]] == ["Kimyo 1", "Kimyo 2"]
    assert (body["start_date"], body["end_date"]) == (ctx["days"][0].isoformat(), ctx["days"][1].isoformat())
    # a single day (the end day is inclusive)
    one = _get(client, "boss", f"/{ctx['klass'].id}/results", start=ctx["tarix_day"].isoformat(), end=ctx["tarix_day"].isoformat()).json()
    assert [c["exam_title"] for c in one["columns"]] == ["Tarix 1"]
    # a day with nothing: an empty but valid table, every student listed unranked
    empty = _get(client, "boss", f"/{ctx['klass'].id}/results", start="2020-01-01", end="2020-01-02").json()
    assert empty["columns"] == [] and len(empty["students"]) == 3 and all(r["rank"] is None for r in empty["students"])


def test_a_subject_teacher_sees_only_their_subject_the_homeroom_teacher_sees_all(client, db_session):
    ctx = _setup(client, db_session)
    cid = ctx["klass"].id

    kimyo = _get(client, "kimyo_t", f"/{cid}/results").json()
    assert kimyo["scope"] == {"all_subjects": False, "subject_ids": kimyo["scope"]["subject_ids"]}
    assert {c["subject_name"] for c in kimyo["columns"]} == {"Kimyo"}
    # totals and ranks are over Kimyo alone — Tarix points never leak into them
    rows = {r["full_name"]: r for r in kimyo["students"]}
    assert rows["Ali"]["percent"] == round(100 * (10 + 12 + 16 + 18) / 80, 1)
    assert rows["Ali"]["cells"][-1] is not None and len(rows["Ali"]["cells"]) == 4

    tarix = _get(client, "tarix_t", f"/{cid}/results").json()
    assert {c["subject_name"] for c in tarix["columns"]} == {"Tarix"}

    homeroom = _get(client, "homeroom", f"/{cid}/results").json()
    assert homeroom["scope"]["all_subjects"] is True
    assert {c["subject_name"] for c in homeroom["columns"]} == {"Kimyo", "Tarix"}


def test_only_people_connected_to_the_class_may_open_it(client, db_session):
    ctx = _setup(client, db_session)
    cid = ctx["klass"].id
    assert _get(client, "outsider", f"/{cid}/results").status_code == 403
    assert _get(client, "outsider", f"/{cid}/dynamics").status_code == 403
    student = client.get(f"/api/v1/admin/classes/{cid}/results", headers=_login(client, "ali", class_id=cid))
    assert student.status_code == 403


def test_class_dynamics_first_results_against_the_latest(client, db_session):
    ctx = _setup(client, db_session)
    body = _get(client, "boss", f"/{ctx['klass'].id}/dynamics").json()

    assert body["students_count"] == 3 and body["school_year_start"] == YEAR
    kimyo = next(s for s in body["subjects"] if s["subject_name"] == "Kimyo")
    # class average per exam: 1st (50+70+40)/3, 2nd (60+70+50)/3, 3rd (80+70)/2, 4th (90+70+60)/3
    assert kimyo["exams_count"] == 4
    # (each exam's average is rounded to 0.1 before the edge mean, so allow 0.1)
    assert abs(kimyo["baseline_percent"] - ((160 / 3) + (180 / 3)) / 2) <= 0.1
    assert abs(kimyo["current_percent"] - (75 + (220 / 3)) / 2) <= 0.1
    assert abs(kimyo["delta"] - (kimyo["current_percent"] - kimyo["baseline_percent"])) <= 0.15
    tarix = next(s for s in body["subjects"] if s["subject_name"] == "Tarix")
    assert tarix["delta"] is None  # one exam: no story yet

    students = {s["full_name"]: s for s in body["students"]}
    assert students["Ali"]["delta"] == 30.0  # Kimyo 55 -> 85; Tarix has one result and doesn't feed the change
    assert students["Vali"]["delta"] == 0.0
    assert students["Ali"]["baseline_percent"] == round((55 + 50) / 2, 1)
    assert sum(body["bands"].values()) == 3
    assert [t["exam_title"] for t in body["timeline"]] == ["Kimyo 1", "Kimyo 2", "Kimyo 3", "Kimyo 4", "Tarix 1"]
    assert body["quarters"][0]["exams_count"] >= 1


def test_class_dynamics_are_scoped_to_the_viewers_subjects(client, db_session):
    ctx = _setup(client, db_session)
    body = _get(client, "tarix_t", f"/{ctx['klass'].id}/dynamics").json()
    assert [s["subject_name"] for s in body["subjects"]] == ["Tarix"]
    assert [t["subject_name"] for t in body["timeline"]] == ["Tarix"]
    assert body["scope"]["all_subjects"] is False
    home = _get(client, "homeroom", f"/{ctx['klass'].id}/dynamics").json()
    assert {s["subject_name"] for s in home["subjects"]} == {"Kimyo", "Tarix"}


def test_daily_results_follow_the_same_subject_scope(client, db_session):
    ctx = _setup(client, db_session)
    day = ctx["tarix_day"].isoformat()
    admin = _get(client, "boss", f"/{ctx['klass'].id}/daily-results", date=day).json()
    assert [e["subject_name"] for e in admin["exams"]] == ["Tarix"]
    # the Tarix teacher sees it; the Kimyo teacher has no Tarix column on that day
    assert [e["subject_name"] for e in _get(client, "tarix_t", f"/{ctx['klass'].id}/daily-results", date=day).json()["exams"]] == ["Tarix"]
    assert _get(client, "kimyo_t", f"/{ctx['klass'].id}/daily-results", date=day).json()["exams"] == []
    assert [e["subject_name"] for e in _get(client, "homeroom", f"/{ctx['klass'].id}/daily-results", date=day).json()["exams"]] == ["Tarix"]
