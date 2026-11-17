"""A student's learning dynamics: every graded exam of the school year, any
subject, nazorat and chorak, on one percent scale."""

from datetime import date, datetime, timedelta, timezone

from app.models.attempt import AttemptSectionScore, AttemptStatus, ExamAttempt, StudentAnswer
from app.models.exam import Exam, ExamSection, ExamStatus, ExamType
from app.models.user import TeacherClassSubject
from app.services import quarter_service as qs
from app.tests.factories import (
    add_mcq_question,
    make_admin,
    make_class,
    make_exam,
    make_student,
    make_subject,
    make_teacher,
)

YEAR = qs.school_year_start_year(qs.school_today())


def _login(client, username, password="secret123", class_id=None):
    body = {"username": username, "password": password}
    if class_id is not None:
        body["class_id"] = class_id
    resp = client.post("/api/v1/auth/login", json=body)
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _utc(day: date, hour=9):
    # school time is UTC+5
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc) - timedelta(hours=5)


def _result(db, student, exam, score, max_score, day: date):
    attempt = ExamAttempt(
        exam_id=exam.id,
        student_id=student.id,
        status=AttemptStatus.submitted,
        score=score,
        max_score=max_score,
        started_at=_utc(day),
        submitted_at=_utc(day, 10),
    )
    db.add(attempt)
    db.flush()
    return attempt


def _nazorat(db, klass, subject, day: date, title=None):
    exam = make_exam(db, klass, subject, status=ExamStatus.scheduled, start_at=_utc(day, 8), end_at=_utc(day, 20))
    if title:
        exam.title = title
    return exam


def test_percent_scale_baseline_current_and_delta_per_subject(client, db_session):
    klass, kimyo, tarix = make_class(db_session), make_subject(db_session, name="Kimyo"), make_subject(db_session, name="Tarix")
    ali = make_student(db_session, klass, username="ali", full_name="Ali")
    # Kimyo: 50 -> 60 -> 80 -> 90 (4 results: baseline = mean of first two, current = mean of last two)
    for i, (score, mx) in enumerate([(10, 20), (12, 20), (16, 20), (18, 20)]):
        day = date(YEAR, 9, 10) + timedelta(days=7 * i)
        _result(db_session, ali, _nazorat(db_session, klass, kimyo, day), score, mx, day)
    # Tarix: one result only
    _result(db_session, ali, _nazorat(db_session, klass, tarix, date(YEAR, 10, 1)), 15, 30, date(YEAR, 10, 1))
    db_session.commit()

    body = client.get("/api/v1/student/me/dynamics", headers=_login(client, "ali", class_id=klass.id)).json()

    by_name = {s["subject_name"]: s for s in body["subjects"]}
    assert (by_name["Kimyo"]["baseline_percent"], by_name["Kimyo"]["current_percent"], by_name["Kimyo"]["delta"]) == (55.0, 85.0, 30.0)
    assert by_name["Kimyo"]["average_percent"] == 70.0
    assert (by_name["Tarix"]["current_percent"], by_name["Tarix"]["delta"]) == (50.0, None)  # one result: no story yet
    assert [p["percent"] for p in body["points"] if p["subject_name"] == "Kimyo"] == [50.0, 60.0, 80.0, 90.0]
    # overall: every subject counts once; only subjects with a change feed the delta
    assert body["overall"]["current_percent"] == round((85 + 50) / 2, 1)
    assert body["overall"]["delta"] == 30.0
    assert body["insights"]["most_improved"]["subject_name"] == "Kimyo"
    assert body["insights"]["strongest"]["subject_name"] == "Kimyo"
    assert body["insights"]["weakest"]["subject_name"] == "Tarix"


def test_chorak_blocks_become_one_result_per_subject_and_quarters_are_filled(client, db_session):
    klass, kimyo, bio = make_class(db_session), make_subject(db_session, name="Kimyo"), make_subject(db_session, name="Biologiya")
    ali = make_student(db_session, klass, username="ali", full_name="Ali")
    chorak = make_exam(db_session, klass, kimyo, status=ExamStatus.scheduled, start_at=_utc(date(YEAR, 11, 20)), end_at=_utc(date(YEAR, 11, 21)))
    chorak.exam_type = ExamType.chorak.value
    sec_k = ExamSection(exam_id=chorak.id, subject_id=kimyo.id, order_index=0, question_count=30, points_per_question=3.1)
    sec_b = ExamSection(exam_id=chorak.id, subject_id=bio.id, order_index=1, question_count=30, points_per_question=2.1)
    db_session.add_all([sec_k, sec_b])
    db_session.flush()
    attempt = _result(db_session, ali, chorak, 83.7 + 31.5, 156, date(YEAR, 11, 20))
    db_session.add_all(
        [
            AttemptSectionScore(attempt_id=attempt.id, section_id=sec_k.id, exam_id=chorak.id, student_id=ali.id, subject_id=kimyo.id, score=83.7, max_score=93, correct_count=27, question_count=30),
            AttemptSectionScore(attempt_id=attempt.id, section_id=sec_b.id, exam_id=chorak.id, student_id=ali.id, subject_id=bio.id, score=31.5, max_score=63, correct_count=15, question_count=30),
        ]
    )
    db_session.commit()

    body = client.get("/api/v1/student/me/dynamics", headers=_login(client, "ali", class_id=klass.id)).json()

    assert sorted((p["subject_name"], p["percent"], p["exam_type"]) for p in body["points"]) == [
        ("Biologiya", 50.0, "chorak"),
        ("Kimyo", 90.0, "chorak"),
    ]
    assert body["overall"]["exams_count"] == 1  # one exam, two subject results
    assert all(p["quarter"] == 2 for p in body["points"])  # 20 Nov is chorak 2
    quarters = {q["number"]: q for q in body["quarters"]}
    assert quarters[2]["percent"] == round(100 * 115.2 / 156, 1) and quarters[2]["exams_count"] == 1
    assert quarters[1]["percent"] is None and quarters[1]["exams_count"] == 0
    assert quarters[2]["start_date"].endswith("-11-06") and quarters[2]["end_date"].endswith("-01-11")


def test_class_average_only_when_enough_students_sat_it(client, db_session):
    klass, kimyo = make_class(db_session), make_subject(db_session, name="Kimyo")
    ali = make_student(db_session, klass, username="ali", full_name="Ali")
    others = [make_student(db_session, klass, username=f"s{i}", full_name=f"S{i}") for i in range(2)]
    small = _nazorat(db_session, klass, kimyo, date(YEAR, 9, 15))
    big = _nazorat(db_session, klass, kimyo, date(YEAR, 9, 22))
    _result(db_session, ali, small, 10, 20, date(YEAR, 9, 15))
    _result(db_session, others[0], small, 20, 20, date(YEAR, 9, 15))  # 2 students: too few to average
    _result(db_session, ali, big, 10, 20, date(YEAR, 9, 22))
    _result(db_session, others[0], big, 20, 20, date(YEAR, 9, 22))
    _result(db_session, others[1], big, 15, 20, date(YEAR, 9, 22))  # 3 students: shown
    db_session.commit()

    points = client.get("/api/v1/student/me/dynamics", headers=_login(client, "ali", class_id=klass.id)).json()["points"]

    assert [p["class_percent"] for p in points] == [None, round((50 + 100 + 75) / 3, 1)]


def test_a_student_never_gets_a_rank_but_staff_do(client, db_session):
    klass, kimyo = make_class(db_session), make_subject(db_session, name="Kimyo")
    ali = make_student(db_session, klass, username="ali", full_name="Ali")
    vali = make_student(db_session, klass, username="vali", full_name="Vali")
    gap = make_student(db_session, klass, username="gap", full_name="Gap")
    exam = _nazorat(db_session, klass, kimyo, date(YEAR, 11, 20))
    _result(db_session, ali, exam, 20, 20, date(YEAR, 11, 20))
    _result(db_session, vali, exam, 20, 20, date(YEAR, 11, 20))  # ties Ali for first
    _result(db_session, gap, exam, 10, 20, date(YEAR, 11, 20))
    make_admin(db_session, username="boss")
    db_session.commit()

    own = client.get("/api/v1/student/me/dynamics", headers=_login(client, "ali", class_id=klass.id)).json()
    assert own["show_rank"] is False
    assert own["overall"]["rank"] is None and all(q["rank"] is None for q in own["quarters"])

    staff = client.get(f"/api/v1/admin/students/{gap.id}/dynamics", headers=_login(client, "boss")).json()
    assert staff["show_rank"] is True
    assert (staff["overall"]["rank"], staff["overall"]["rank_of"]) == (3, 3)
    ali_staff = client.get(f"/api/v1/admin/students/{ali.id}/dynamics", headers=_login(client, "boss")).json()
    assert ali_staff["overall"]["rank"] == 1  # RANK(): the tie shares first place
    assert {q["number"]: q["rank"] for q in ali_staff["quarters"]}[2] == 1


def test_access_scoping_for_the_staff_endpoint(client, db_session):
    klass, other_class, kimyo = make_class(db_session), make_class(db_session), make_subject(db_session)
    ali = make_student(db_session, klass, username="ali", full_name="Ali")
    mine = make_teacher(db_session, subject=kimyo, username="mine")
    db_session.add(TeacherClassSubject(teacher_id=mine.id, class_id=klass.id, subject_id=kimyo.id))
    stranger = make_teacher(db_session, subject=kimyo, username="stranger")
    db_session.add(TeacherClassSubject(teacher_id=stranger.id, class_id=other_class.id, subject_id=kimyo.id))
    db_session.commit()
    url = f"/api/v1/admin/students/{ali.id}/dynamics"

    assert client.get(url, headers=_login(client, "mine")).status_code == 200
    assert client.get(url, headers=_login(client, "stranger")).status_code == 403
    assert client.get(url, headers=_login(client, "ali", class_id=klass.id)).status_code == 403  # a student can't use it
    assert client.get("/api/v1/admin/students/9999/dynamics", headers=_login(client, "mine")).status_code == 404


def test_school_year_filter_and_available_years(client, db_session):
    klass, kimyo = make_class(db_session), make_subject(db_session, name="Kimyo")
    ali = make_student(db_session, klass, username="ali", full_name="Ali")
    _result(db_session, ali, _nazorat(db_session, klass, kimyo, date(YEAR - 1, 10, 5)), 10, 20, date(YEAR - 1, 10, 5))
    _result(db_session, ali, _nazorat(db_session, klass, kimyo, date(YEAR, 10, 5)), 18, 20, date(YEAR, 10, 5))
    db_session.commit()
    headers = _login(client, "ali", class_id=klass.id)

    now = client.get("/api/v1/student/me/dynamics", headers=headers).json()
    assert [p["percent"] for p in now["points"]] == [90.0]
    assert now["available_school_years"] == [YEAR - 1, YEAR]
    last = client.get("/api/v1/student/me/dynamics", headers=headers, params={"school_year": YEAR - 1}).json()
    assert [p["percent"] for p in last["points"]] == [50.0] and last["school_year_start"] == YEAR - 1


def test_missed_exams_are_listed_not_counted_as_zero(client, db_session):
    klass, kimyo = make_class(db_session), make_subject(db_session, name="Kimyo")
    ali = make_student(db_session, klass, username="ali", full_name="Ali")
    sat = _nazorat(db_session, klass, kimyo, date(YEAR, 9, 12), title="Sat it")
    missed = _nazorat(db_session, klass, kimyo, date(YEAR, 9, 19), title="Missed it")
    _result(db_session, ali, sat, 10, 20, date(YEAR, 9, 12))
    db_session.commit()

    body = client.get("/api/v1/student/me/dynamics", headers=_login(client, "ali", class_id=klass.id)).json()

    assert [m["exam_title"] for m in body["missed"]] == ["Missed it"]
    assert [p["exam_title"] for p in body["points"]] == ["Sat it"]
    assert body["subjects"][0]["average_percent"] == 50.0  # the missed one did not drag it to 25


def test_a_result_waiting_for_the_teacher_is_marked_provisional(client, db_session):
    klass, kimyo = make_class(db_session), make_subject(db_session, name="Kimyo")
    ali = make_student(db_session, klass, username="ali", full_name="Ali")
    exam = _nazorat(db_session, klass, kimyo, date(YEAR, 9, 12))
    question = add_mcq_question(db_session, exam)
    attempt = _result(db_session, ali, exam, 10, 20, date(YEAR, 9, 12))
    db_session.add(StudentAnswer(attempt_id=attempt.id, question_id=question.id, points_awarded=0, graded_by="pending"))
    db_session.commit()

    points = client.get("/api/v1/student/me/dynamics", headers=_login(client, "ali", class_id=klass.id)).json()["points"]

    assert points[0]["provisional"] is True


def test_a_student_with_no_results_gets_an_empty_page_not_an_error(client, db_session):
    klass = make_class(db_session)
    make_student(db_session, klass, username="new", full_name="New")
    db_session.commit()

    body = client.get("/api/v1/student/me/dynamics", headers=_login(client, "new", class_id=klass.id)).json()

    assert body["points"] == [] and body["subjects"] == []
    assert body["overall"]["current_percent"] is None
    assert len(body["quarters"]) == 4 and all(q["percent"] is None for q in body["quarters"])
    assert body["insights"]["strongest"] is None
