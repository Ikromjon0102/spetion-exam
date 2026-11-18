"""A whole class's results: one table over a date range, and the class's
dynamics across a school year ("yil boshida / hozir").

Who sees what is decided in ONE place, `visible_subject_ids`: an admin and the
class's homeroom teacher see every subject; any other teacher of the class
sees only the subjects they teach to it. Everything here is computed over the
visible subjects only, so a subject teacher's totals, ranks and averages never
include a colleague's subject.
"""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.attempt import ExamAttempt
from app.models.exam import Exam
from app.models.org import Class
from app.models.user import Student, Subject, TeacherClassSubject, User, UserRole
from app.schemas.class_results import (
    ClassDynamicsOut,
    ClassDynBandsOut,
    ClassDynQuarterOut,
    ClassDynStudentOut,
    ClassDynSubjectOut,
    ClassResultCellOut,
    ClassResultColumnOut,
    ClassResultRowOut,
    ClassResultsOut,
    ClassScopeOut,
)
from app.services import dynamics_service, quarter_service
from app.services.dynamics_service import GRADED, NOTABLE_DELTA, _edge_mean, _graded_results, _local_day, _pct, _year_window


def visible_subject_ids(db: Session, user: User, klass: Class) -> set[int] | None:
    """None = every subject; otherwise the subject ids this teacher teaches to
    the class. The caller has already passed _ensure_class_view_access."""
    if user.role == UserRole.admin:
        return None
    teacher = user.teacher
    if teacher is None:
        return set()
    if klass.homeroom_teacher_id == teacher.id:
        return None
    return {
        row[0]
        for row in db.query(TeacherClassSubject.subject_id).filter_by(teacher_id=teacher.id, class_id=klass.id)
    }


def _scope_out(visible: set[int] | None) -> ClassScopeOut:
    return ClassScopeOut(all_subjects=visible is None, subject_ids=sorted(visible or []))


def _class_student_ids(db: Session, class_id: int) -> dict[int, str]:
    return {
        s.id: s.user.full_name
        for s in db.query(Student).join(User, User.id == Student.user_id).filter(
            Student.class_id == class_id, User.is_active.is_(True)
        )
    }


def _rank(per_student: dict[int, list[float]]) -> dict[int, int]:
    """RANK() by earned / possible, ties share a rank."""
    scored = sorted(((sid, 100 * e / p) for sid, (e, p) in per_student.items() if p > 0), key=lambda x: x[1], reverse=True)
    out, current, previous = {}, 0, None
    for i, (sid, value) in enumerate(scored, start=1):
        value = round(value, 2)
        if value != previous:
            current = i
        out[sid] = current
        previous = value
    return out


def _columns(results: list[dict], names: dict[int, str]) -> list[ClassResultColumnOut]:
    groups: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for r in results:
        groups[(r["exam_id"], r["subject_id"])].append(r)
    columns = []
    for (exam_id, subject_id), rows in groups.items():
        first = rows[0]
        percents = [_pct(r["score"], r["max_score"]) for r in rows]
        columns.append(
            ClassResultColumnOut(
                exam_id=exam_id,
                exam_title=first["exam_title"],
                exam_type=first["exam_type"],
                subject_id=subject_id,
                subject_name=names.get(subject_id, ""),
                date=min(r["date"] for r in rows).isoformat(),
                max_score=round(max(r["max_score"] for r in rows), 2),
                taken=len(rows),
                class_percent=round(sum(percents) / len(percents), 1),
            )
        )
    columns.sort(key=lambda c: (c.date, c.exam_id, c.subject_id))
    return columns


def build_class_results(
    db: Session, klass: Class, visible: set[int] | None, start: date | None, end: date | None, school_year: int | None
) -> ClassResultsOut:
    today = quarter_service.school_today()
    year = school_year if school_year is not None else quarter_service.school_year_start_year(today)
    if start is None or end is None:
        start, end = date(year, 9, 1), date(year + 1, 8, 31)
    if end < start:
        start, end = end, start
    lo, hi = quarter_service.utc_bounds(start, end + timedelta(days=1))

    students = _class_student_ids(db, klass.id)
    results = [
        r for r in _graded_results(db, list(students), lo, hi) if visible is None or r["subject_id"] in visible
    ]
    names = dict(db.query(Subject.id, Subject.name).filter(Subject.id.in_({r["subject_id"] for r in results}))) if results else {}
    columns = _columns(results, names)
    index = {(c.exam_id, c.subject_id): i for i, c in enumerate(columns)}

    cells: dict[int, list[ClassResultCellOut | None]] = {sid: [None] * len(columns) for sid in students}
    totals: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in results:
        i = index[(r["exam_id"], r["subject_id"])]
        cells[r["student_id"]][i] = ClassResultCellOut(
            score=round(r["score"], 2), max_score=round(r["max_score"], 2), percent=_pct(r["score"], r["max_score"])
        )
        totals[r["student_id"]][0] += r["score"]
        totals[r["student_id"]][1] += r["max_score"]

    ranks = _rank(totals)
    rows = []
    for sid, name in students.items():
        earned, possible = totals[sid] if sid in totals else (0.0, 0.0)
        rows.append(
            ClassResultRowOut(
                student_id=sid,
                full_name=name,
                cells=cells[sid],
                percent=round(100 * earned / possible, 1) if possible > 0 else None,
                rank=ranks.get(sid),
            )
        )
    rows.sort(key=lambda r: (r.rank is None, r.rank or 0, r.full_name.lower()))
    all_percents = [_pct(r["score"], r["max_score"]) for r in results]
    return ClassResultsOut(
        class_id=klass.id,
        class_name=klass.display_name,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        scope=_scope_out(visible),
        columns=columns,
        students=rows,
        class_percent=round(sum(all_percents) / len(all_percents), 1) if all_percents else None,
    )


def _mean_of_subjects(per_subject: dict[int, list[float]]) -> tuple[float | None, float | None]:
    """(baseline, current) with an equal say for every subject — as the
    student's own dynamics page does."""
    if not per_subject:
        return None, None
    edges = [_edge_mean(values) for values in per_subject.values()]
    return (
        round(sum(b for b, _ in edges) / len(edges), 1),
        round(sum(c for _, c in edges) / len(edges), 1),
    )


def build_class_dynamics(db: Session, klass: Class, visible: set[int] | None, school_year: int | None) -> ClassDynamicsOut:
    today = quarter_service.school_today()
    year = school_year if school_year is not None else quarter_service.school_year_start_year(today)
    quarters, _ = quarter_service.get_quarters(db)
    lo, hi = _year_window(year)

    students = _class_student_ids(db, klass.id)
    results = sorted(
        (r for r in _graded_results(db, list(students), lo, hi) if visible is None or r["subject_id"] in visible),
        key=lambda r: (r["date"], r["exam_id"]),
    )
    names = dict(db.query(Subject.id, Subject.name).filter(Subject.id.in_({r["subject_id"] for r in results}))) if results else {}
    timeline = _columns(results, names)

    # ---- the class per subject: the average of each exam, first -> latest
    by_subject_cols: dict[int, list[ClassResultColumnOut]] = defaultdict(list)
    for c in timeline:
        by_subject_cols[c.subject_id].append(c)
    subjects, class_series = [], {}
    for subject_id, cols in by_subject_cols.items():
        values = [c.class_percent for c in cols if c.class_percent is not None]
        baseline, current = _edge_mean(values)
        class_series[subject_id] = values
        subjects.append(
            ClassDynSubjectOut(
                subject_id=subject_id,
                subject_name=cols[0].subject_name,
                exams_count=len(cols),
                baseline_percent=round(baseline, 1),
                current_percent=round(current, 1),
                average_percent=round(sum(values) / len(values), 1),
                delta=round(current - baseline, 1) if len(values) >= 2 else None,
            )
        )
    subjects.sort(key=lambda s: s.subject_name.lower())
    base, cur = _mean_of_subjects(class_series)
    multi = [s for s in subjects if s.delta is not None]
    delta = round(sum(s.delta for s in multi) / len(multi), 1) if multi else None

    # ---- each student, the same way
    per_student: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    totals: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in results:
        per_student[r["student_id"]][r["subject_id"]].append(_pct(r["score"], r["max_score"]))
        totals[r["student_id"]][0] += r["score"]
        totals[r["student_id"]][1] += r["max_score"]
    ranks = _rank(totals)
    student_rows = []
    for sid, name in students.items():
        per_subject = per_student.get(sid, {})
        b, c = _mean_of_subjects(per_subject)
        counted = sum(len(v) for v in per_subject.values())
        earned, possible = totals[sid] if sid in totals else (0.0, 0.0)
        multi_subjects = [v for v in per_subject.values() if len(v) >= 2]
        student_rows.append(
            ClassDynStudentOut(
                student_id=sid,
                full_name=name,
                exams_count=counted,
                average_percent=round(100 * earned / possible, 1) if possible > 0 else None,
                baseline_percent=b,
                current_percent=c,
                delta=(
                    round(sum(_edge_mean(v)[1] - _edge_mean(v)[0] for v in multi_subjects) / len(multi_subjects), 1)
                    if multi_subjects
                    else None
                ),
                rank=ranks.get(sid),
            )
        )
    student_rows.sort(key=lambda s: (s.rank is None, s.rank or 0, s.full_name.lower()))

    bands = ClassDynBandsOut(
        low=sum(1 for s in student_rows if s.current_percent is not None and s.current_percent < 50),
        middle=sum(1 for s in student_rows if s.current_percent is not None and 50 <= s.current_percent < 70),
        high=sum(1 for s in student_rows if s.current_percent is not None and s.current_percent >= 70),
    )

    quarter_out = []
    for q in quarters:
        start, end = quarter_service.quarter_dates(q, year)
        in_q = [r for r in results if quarter_service.quarter_of(quarters, r["date"]) == q.number]
        possible = sum(r["max_score"] for r in in_q)
        quarter_out.append(
            ClassDynQuarterOut(
                number=q.number,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                exams_count=len({(r["exam_id"], r["subject_id"]) for r in in_q}),
                percent=_pct(sum(r["score"] for r in in_q), possible) if possible else None,
            )
        )

    years = {year}
    for (submitted_at,) in db.query(ExamAttempt.submitted_at).join(Exam, Exam.id == ExamAttempt.exam_id).filter(
        Exam.class_id == klass.id, ExamAttempt.status.in_(GRADED), ExamAttempt.submitted_at.isnot(None)
    ):
        years.add(quarter_service.school_year_start_year(_local_day(submitted_at)))

    all_percents = [_pct(r["score"], r["max_score"]) for r in results]
    return ClassDynamicsOut(
        class_id=klass.id,
        class_name=klass.display_name,
        school_year_start=year,
        available_school_years=sorted(years),
        scope=_scope_out(visible),
        students_count=len(students),
        exams_count=len(timeline),
        baseline_percent=base,
        current_percent=cur,
        delta=delta,
        average_percent=round(sum(all_percents) / len(all_percents), 1) if all_percents else None,
        bands=bands,
        subjects=subjects,
        quarters=quarter_out,
        timeline=timeline,
        students=student_rows,
    )
