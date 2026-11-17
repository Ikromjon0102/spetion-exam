"""The four chorak date ranges and the exam list's "this chorak" filter."""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.exam import Exam
from app.services import quarter_service as qs
from app.tests.factories import make_admin, make_class, make_exam, make_subject, make_teacher
from app.models.user import TeacherClassSubject

DEFAULT = [qs.Quarter(n, (v[0], v[1]), (v[2], v[3])) for n, v in sorted(qs.DEFAULTS.items())]


def _login(client, username, password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.parametrize(
    "day, expected",
    [
        (date(2026, 9, 1), 1),
        (date(2026, 11, 5), 1),
        (date(2026, 11, 6), 2),
        (date(2026, 12, 31), 2),  # crosses New Year
        (date(2027, 1, 11), 2),
        (date(2027, 1, 12), 3),
        (date(2027, 4, 7), 3),
        (date(2027, 4, 8), 4),
        (date(2027, 7, 1), 4),
        (date(2027, 8, 15), 4),  # summer belongs to the last chorak of that school year
        (date(2026, 8, 20), 4),  # ...i.e. of the school year before 2026/27
    ],
)
def test_default_quarter_of_a_date(day, expected):
    assert qs.quarter_of(DEFAULT, day) == expected


def test_school_year_start():
    assert qs.school_year_start_year(date(2026, 9, 1)) == 2026
    assert qs.school_year_start_year(date(2027, 8, 31)) == 2026
    assert qs.school_year_start_year(date(2027, 1, 1)) == 2026


def test_a_gap_between_quarters_goes_to_the_earlier_one():
    # chorak 1 ends 5 Nov, chorak 2 only starts 10 Nov: 6-9 Nov is a holiday
    quarters = [
        qs.Quarter(1, (9, 1), (11, 5)),
        qs.Quarter(2, (11, 10), (1, 11)),
        qs.Quarter(3, (1, 12), (4, 7)),
        qs.Quarter(4, (4, 8), (7, 1)),
    ]
    assert qs.quarter_of(quarters, date(2026, 11, 7)) == 1
    assert qs.quarter_of(quarters, date(2026, 11, 10)) == 2


def test_validation_rejects_overlap_reversed_and_impossible_dates():
    ok = dict(qs.DEFAULTS)
    qs.validate(ok)
    with pytest.raises(ValueError):
        qs.validate({**ok, 1: (9, 1, 11, 20)})  # overlaps chorak 2
    with pytest.raises(ValueError):
        qs.validate({**ok, 3: (4, 7, 1, 12)})  # ends before it starts
    with pytest.raises(ValueError):
        qs.validate({**ok, 4: (2, 29, 7, 1)})  # not a date in most years
    with pytest.raises(ValueError):
        qs.validate({1: ok[1], 2: ok[2], 3: ok[3]})  # one missing


def test_get_quarters_defaults_for_staff_and_save_is_admin_only(client, db_session):
    make_admin(db_session, username="boss")
    subject = make_subject(db_session)
    klass = make_class(db_session)
    teacher = make_teacher(db_session, subject=subject, username="ustoz")
    db_session.add(TeacherClassSubject(teacher_id=teacher.id, class_id=klass.id, subject_id=subject.id))
    db_session.commit()
    boss, ustoz = _login(client, "boss"), _login(client, "ustoz")

    body = client.get("/api/v1/admin/quarters", headers=ustoz).json()
    assert body["is_default"] is True
    assert [q["number"] for q in body["quarters"]] == [1, 2, 3, 4]
    assert body["quarters"][1]["start_date"].endswith("-11-06")
    assert body["quarters"][1]["end_date"].endswith("-01-11")
    assert body["current_number"] in (1, 2, 3, 4)

    payload = {
        "quarters": [
            {"number": 1, "start_date": "2026-09-02", "end_date": "2026-11-01"},
            {"number": 2, "start_date": "2026-11-09", "end_date": "2027-01-10"},
            {"number": 3, "start_date": "2027-01-11", "end_date": "2027-04-04"},
            {"number": 4, "start_date": "2027-04-05", "end_date": "2027-06-30"},
        ]
    }
    assert client.put("/api/v1/admin/quarters", headers=ustoz, json=payload).status_code == 403
    saved = client.put("/api/v1/admin/quarters", headers=boss, json=payload)
    assert saved.status_code == 200
    assert saved.json()["is_default"] is False
    assert saved.json()["quarters"][0]["start_date"].endswith("-09-02")

    bad = {"quarters": [*payload["quarters"][:3], {"number": 4, "start_date": "2027-04-01", "end_date": "2027-06-30"}]}
    resp = client.put("/api/v1/admin/quarters", headers=boss, json=bad)
    assert resp.status_code == 400 and "3-chorak" in resp.json()["detail"]
    duplicate = {"quarters": [payload["quarters"][0]] * 4}
    assert client.put("/api/v1/admin/quarters", headers=boss, json=duplicate).status_code == 400


def _exam_on(db, klass, subject, day: date, hour=9, **kw):
    # school time is UTC+5
    start = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc) - timedelta(hours=5)
    return make_exam(db, klass, subject, start_at=start, end_at=start + timedelta(hours=3), **kw)


def test_exam_list_filters_by_chorak_and_defaults_to_the_current_school_year(client, db_session):
    make_admin(db_session, username="boss")
    klass, subject = make_class(db_session), make_subject(db_session)
    year = qs.school_year_start_year(qs.school_today())
    q1 = _exam_on(db_session, klass, subject, date(year, 10, 1))
    q2_new_year = _exam_on(db_session, klass, subject, date(year + 1, 1, 5))
    q2_early = _exam_on(db_session, klass, subject, date(year, 11, 6), hour=0)  # 00:00 local = previous UTC day
    q3 = _exam_on(db_session, klass, subject, date(year + 1, 2, 1))
    last_year = _exam_on(db_session, klass, subject, date(year - 1, 10, 1))
    draft = make_exam(db_session, klass, subject)  # no start: judged by created_at (now)
    db_session.commit()
    boss = _login(client, "boss")

    def ids(**params):
        return {e["id"] for e in client.get("/api/v1/admin/exams", headers=boss, params=params).json()}

    # the draft has no start date, so it sits in whichever chorak TODAY is in
    today_quarter = qs.quarter_of(DEFAULT, qs.school_today())

    def expected(number, *exams):
        return {e.id for e in exams} | ({draft.id} if number == today_quarter else set())

    assert ids(quarter=1) == expected(1, q1)
    assert ids(quarter=2) == expected(2, q2_new_year, q2_early)
    assert ids(quarter=3) == expected(3, q3)
    assert ids(quarter=4) == expected(4)
    assert ids(quarter=1, school_year=year - 1) == {last_year.id}
    assert ids() == {q1.id, q2_new_year.id, q2_early.id, q3.id, last_year.id, draft.id}  # no filter: nothing hidden


def test_folder_counts_follow_the_selected_chorak(client, db_session):
    make_admin(db_session, username="boss")
    klass, subject = make_class(db_session), make_subject(db_session, name="Kimyo")
    year = qs.school_year_start_year(qs.school_today())
    _exam_on(db_session, klass, subject, date(year, 10, 1))
    _exam_on(db_session, klass, subject, date(year, 10, 2))
    _exam_on(db_session, klass, subject, date(year + 1, 2, 1))
    db_session.commit()
    boss = _login(client, "boss")

    q1 = client.get("/api/v1/admin/exams/summary", headers=boss, params={"quarter": 1}).json()
    assert q1["current"] == 2
    assert [(s["name"], s["count"]) for s in q1["subjects"]] == [("Kimyo", 2)]
    all_time = client.get("/api/v1/admin/exams/summary", headers=boss).json()
    assert all_time["current"] == 3


def test_a_saved_calendar_moves_an_exam_between_quarters(client, db_session):
    make_admin(db_session, username="boss")
    klass, subject = make_class(db_session), make_subject(db_session)
    year = qs.school_year_start_year(qs.school_today())
    exam = _exam_on(db_session, klass, subject, date(year, 11, 7))  # chorak 2 by default
    db_session.commit()
    boss = _login(client, "boss")
    assert exam.id in {e["id"] for e in client.get("/api/v1/admin/exams", headers=boss, params={"quarter": 2}).json()}

    payload = {
        "quarters": [
            {"number": 1, "start_date": f"{year}-09-01", "end_date": f"{year}-11-10"},
            {"number": 2, "start_date": f"{year}-11-11", "end_date": f"{year + 1}-01-11"},
            {"number": 3, "start_date": f"{year + 1}-01-12", "end_date": f"{year + 1}-04-07"},
            {"number": 4, "start_date": f"{year + 1}-04-08", "end_date": f"{year + 1}-07-01"},
        ]
    }
    assert client.put("/api/v1/admin/quarters", headers=boss, json=payload).status_code == 200
    assert exam.id in {e["id"] for e in client.get("/api/v1/admin/exams", headers=boss, params={"quarter": 1}).json()}
    assert exam.id not in {e["id"] for e in client.get("/api/v1/admin/exams", headers=boss, params={"quarter": 2}).json()}
