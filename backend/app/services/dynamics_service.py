"""One student's learning dynamics across every graded exam of a school year:
nazorat and chorak, any subject, on one comparable scale (percent).

A chorak exam contributes one result per subject block (the block's own
score/max), a nazorat exam one result. Everything is percent so a 20-point
quiz and a 93-point block line up. Nothing is guessed: an exam the student
missed is listed separately, never counted as 0.

"Yil boshi -> hozir": per subject, `baseline` is the mean of the first
results and `current` the mean of the latest ones (see _edge_mean), so a
single easy or hard exam doesn't decide the story.
"""

from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.timeutil import SCHOOL_UTC_OFFSET, aware
from app.models.attempt import AttemptSectionScore, AttemptStatus, ExamAttempt, StudentAnswer
from app.models.exam import Exam, ExamStatus, ExamType
from app.models.org import Class
from app.models.user import Student, Subject, User
from app.schemas.dynamics import (
    DynamicsInsightOut,
    DynamicsInsightsOut,
    DynamicsMissedOut,
    DynamicsOut,
    DynamicsOverallOut,
    DynamicsPointOut,
    DynamicsQuarterOut,
    DynamicsSubjectOut,
)
from app.services import quarter_service

GRADED = (AttemptStatus.submitted, AttemptStatus.auto_submitted)
# a class average built from fewer results than this would point at individuals
MIN_CLASS_SAMPLE = 3
# a change smaller than this (percentage points) is noise, not a story
NOTABLE_DELTA = 3.0


def _local_day(dt: datetime) -> date:
    return (aware(dt) + SCHOOL_UTC_OFFSET).date()


def _pct(score, max_score) -> float:
    return round(100 * float(score) / float(max_score), 1) if max_score and float(max_score) > 0 else 0.0


def _edge_mean(values: list[float]) -> tuple[float, float]:
    """(baseline, current) of a chronological list: the mean of the first k
    and of the last k results, k = 1 for up to three results and 2 beyond."""
    k = 2 if len(values) >= 4 else 1
    return sum(values[:k]) / k, sum(values[-k:]) / k


def _year_window(year: int):
    return quarter_service.utc_bounds(date(year, 9, 1), date(year + 1, 9, 1))


def _graded_results(db: Session, student_ids: list[int], lo: datetime, hi: datetime):
    """Every graded result of these students inside [lo, hi), as dicts —
    one per nazorat exam and one per chorak block."""
    attempts = (
        db.query(ExamAttempt, Exam)
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .filter(
            ExamAttempt.student_id.in_(student_ids),
            ExamAttempt.status.in_(GRADED),
            ExamAttempt.score.isnot(None),
            ExamAttempt.submitted_at >= lo,
            ExamAttempt.submitted_at < hi,
        )
        .all()
    )
    chorak_attempt_ids = [a.id for a, e in attempts if e.exam_type == ExamType.chorak.value]
    sections: dict[int, list[AttemptSectionScore]] = defaultdict(list)
    if chorak_attempt_ids:
        for sc in db.query(AttemptSectionScore).filter(AttemptSectionScore.attempt_id.in_(chorak_attempt_ids)):
            sections[sc.attempt_id].append(sc)

    results = []
    for attempt, exam in attempts:
        day = _local_day(attempt.submitted_at)
        base = {
            "student_id": attempt.student_id,
            "attempt_id": attempt.id,
            "exam_id": exam.id,
            "exam_title": exam.title,
            "exam_type": exam.exam_type,
            "date": day,
        }
        if exam.exam_type == ExamType.chorak.value:
            # Two blocks of one subject (asosiy + majburiy) are ONE result.
            merged: dict[int, dict] = {}
            for sc in sections.get(attempt.id, []):
                got = merged.get(sc.subject_id)
                if got is None:
                    merged[sc.subject_id] = {**base, "subject_id": sc.subject_id, "section_id": sc.section_id,
                                             "score": float(sc.score), "max_score": float(sc.max_score)}
                else:
                    got["score"] = round(got["score"] + float(sc.score), 2)
                    got["max_score"] = round(got["max_score"] + float(sc.max_score), 2)
            results.extend(merged.values())
        elif attempt.max_score and float(attempt.max_score) > 0:
            results.append({**base, "subject_id": exam.subject_id, "section_id": None,
                            "score": float(attempt.score), "max_score": float(attempt.max_score)})
    return results


def _class_averages(db: Session, results: list[dict]) -> dict[tuple[int, int], float]:
    """{(exam_id, subject_id): class average percent} for the exams in
    `results`, over every graded attempt of the exam (only where the sample
    is big enough to stay anonymous)."""
    exam_ids = {r["exam_id"] for r in results}
    if not exam_ids:
        return {}
    pool: dict[tuple[int, int], list[float]] = defaultdict(list)
    nazorat_ids = {r["exam_id"] for r in results if r["exam_type"] == ExamType.nazorat.value}
    chorak_ids = exam_ids - nazorat_ids
    if nazorat_ids:
        for exam_id, subject_id, score, max_score in (
            db.query(ExamAttempt.exam_id, Exam.subject_id, ExamAttempt.score, ExamAttempt.max_score)
            .join(Exam, Exam.id == ExamAttempt.exam_id)
            .filter(ExamAttempt.exam_id.in_(nazorat_ids), ExamAttempt.status.in_(GRADED), ExamAttempt.score.isnot(None))
        ):
            if max_score and float(max_score) > 0:
                pool[(exam_id, subject_id)].append(_pct(score, max_score))
    if chorak_ids:
        per_student: dict[tuple[int, int, int], list[float]] = defaultdict(lambda: [0.0, 0.0])
        for exam_id, student_id, subject_id, score, max_score in db.query(
            AttemptSectionScore.exam_id, AttemptSectionScore.student_id, AttemptSectionScore.subject_id,
            AttemptSectionScore.score, AttemptSectionScore.max_score,
        ).filter(AttemptSectionScore.exam_id.in_(chorak_ids)):
            acc = per_student[(exam_id, student_id, subject_id)]
            acc[0] += float(score)
            acc[1] += float(max_score)
        for (exam_id, _student, subject_id), (score, max_score) in per_student.items():
            pool[(exam_id, subject_id)].append(_pct(score, max_score))
    return {k: round(sum(v) / len(v), 1) for k, v in pool.items() if len(v) >= MIN_CLASS_SAMPLE}


def _ranks(db: Session, klass_id: int, quarters, lo, hi, year: int):
    """(overall {student_id: rank}, by_quarter {n: {student_id: rank}}, size
    of each) for one class over the school year, by points earned / points
    possible — the same logic as the school's overall ranking, never an
    average of averages. Staff only."""
    classmates = [
        s.id for s in db.query(Student).join(User, User.id == Student.user_id)
        .filter(Student.class_id == klass_id, User.is_active.is_(True))
    ]
    totals: dict[int | None, dict[int, list[float]]] = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    for r in _graded_results(db, classmates, lo, hi):
        quarter = quarter_service.quarter_of(quarters, r["date"])
        for key in (None, quarter):
            acc = totals[key][r["student_id"]]
            acc[0] += r["score"]
            acc[1] += r["max_score"]

    def rank(per_student: dict[int, list[float]]) -> dict[int, tuple[int, int]]:
        scored = sorted(
            ((sid, 100 * e / p) for sid, (e, p) in per_student.items() if p > 0), key=lambda x: x[1], reverse=True
        )
        out, current, previous = {}, 0, None
        for i, (sid, value) in enumerate(scored, start=1):
            value = round(value, 2)
            if value != previous:
                current = i
            out[sid] = (current, len(scored))
            previous = value
        return out

    return rank(totals[None]), {n: rank(totals[n]) for n in (1, 2, 3, 4)}


def build_dynamics(db: Session, student: Student, school_year: int | None, include_rank: bool) -> DynamicsOut:
    today = quarter_service.school_today()
    year = school_year if school_year is not None else quarter_service.school_year_start_year(today)
    quarters, _ = quarter_service.get_quarters(db)
    lo, hi = _year_window(year)

    results = sorted(_graded_results(db, [student.id], lo, hi), key=lambda r: (r["date"], r["exam_id"]))
    averages = _class_averages(db, results)
    names = dict(db.query(Subject.id, Subject.name).filter(Subject.id.in_({r["subject_id"] for r in results}))) if results else {}

    pending_attempts = {
        row[0]
        for row in db.query(StudentAnswer.attempt_id).filter(
            StudentAnswer.attempt_id.in_({r["attempt_id"] for r in results} or {-1}), StudentAnswer.graded_by == "pending"
        )
    }

    points = [
        DynamicsPointOut(
            exam_id=r["exam_id"],
            exam_title=r["exam_title"],
            exam_type=r["exam_type"],
            subject_id=r["subject_id"],
            subject_name=names.get(r["subject_id"], ""),
            date=r["date"].isoformat(),
            quarter=quarter_service.quarter_of(quarters, r["date"]),
            score=round(r["score"], 2),
            max_score=round(r["max_score"], 2),
            percent=_pct(r["score"], r["max_score"]),
            class_percent=averages.get((r["exam_id"], r["subject_id"])),
            provisional=r["attempt_id"] in pending_attempts,
        )
        for r in results
    ]

    # ---- per subject: from the first results to the latest
    by_subject: dict[int, list[DynamicsPointOut]] = defaultdict(list)
    for p in points:
        by_subject[p.subject_id].append(p)
    subjects: list[DynamicsSubjectOut] = []
    for subject_id, pts in by_subject.items():
        values = [p.percent for p in pts]
        baseline, current = _edge_mean(values)
        class_values = [p.class_percent for p in pts if p.class_percent is not None]
        subjects.append(
            DynamicsSubjectOut(
                subject_id=subject_id,
                subject_name=pts[0].subject_name,
                exams_count=len(pts),
                average_percent=round(sum(values) / len(values), 1),
                baseline_percent=round(baseline, 1),
                current_percent=round(current, 1),
                delta=round(current - baseline, 1) if len(values) >= 2 else None,
                class_percent=round(sum(class_values) / len(class_values), 1) if class_values else None,
            )
        )
    subjects.sort(key=lambda s: s.subject_name.lower())

    # ---- overall: an equal say for every subject, not for every exam
    with_delta = [s for s in subjects if s.delta is not None]
    all_values = [p.percent for p in points]
    class_all = [p.class_percent for p in points if p.class_percent is not None]
    overall = DynamicsOverallOut(
        exams_count=len({p.exam_id for p in points}),
        baseline_percent=round(sum(s.baseline_percent for s in with_delta) / len(with_delta), 1) if with_delta else None,
        current_percent=round(sum(s.current_percent for s in subjects) / len(subjects), 1) if subjects else None,
        delta=round(sum(s.delta for s in with_delta) / len(with_delta), 1) if with_delta else None,
        average_percent=round(sum(all_values) / len(all_values), 1) if all_values else None,
        class_percent=round(sum(class_all) / len(class_all), 1) if class_all else None,
    )

    # ---- by chorak
    ranks_overall: dict = {}
    ranks_quarter: dict = {}
    if include_rank:
        ranks_overall, ranks_quarter = _ranks(db, student.class_id, quarters, lo, hi, year)
        if student.id in ranks_overall:
            overall.rank, overall.rank_of = ranks_overall[student.id]
    quarter_out: list[DynamicsQuarterOut] = []
    for q in quarters:
        start, end = quarter_service.quarter_dates(q, year)
        in_q = [p for p in points if p.quarter == q.number]
        total_max = sum(p.max_score for p in in_q)
        rank = ranks_quarter.get(q.number, {}).get(student.id)
        quarter_out.append(
            DynamicsQuarterOut(
                number=q.number,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                exams_count=len({p.exam_id for p in in_q}),
                percent=_pct(sum(p.score for p in in_q), total_max) if total_max else None,
                rank=rank[0] if rank else None,
                rank_of=rank[1] if rank else None,
            )
        )

    # ---- exams the class sat that this student did not
    sat = {p.exam_id for p in points}
    start_utc, end_utc = lo, hi
    now = datetime.now(timezone.utc)
    missed_rows = (
        db.query(Exam)
        .filter(
            Exam.class_id == student.class_id,
            Exam.status.in_([ExamStatus.scheduled, ExamStatus.active, ExamStatus.closed]),
            Exam.start_at.isnot(None),
            Exam.start_at >= start_utc,
            Exam.start_at < end_utc,
            Exam.end_at < now,
        )
        .order_by(Exam.start_at)
        .all()
    )
    own_attempts = {
        row[0]
        for row in db.query(ExamAttempt.exam_id).filter(
            ExamAttempt.student_id == student.id, ExamAttempt.status.in_(GRADED)
        )
    }
    missed_subjects = dict(db.query(Subject.id, Subject.name).filter(Subject.id.in_({e.subject_id for e in missed_rows}))) if missed_rows else {}
    missed = [
        DynamicsMissedOut(
            exam_id=e.id,
            exam_title=e.title,
            exam_type=e.exam_type,
            subject_name=None if e.exam_type == ExamType.chorak.value else missed_subjects.get(e.subject_id),
            date=_local_day(e.start_at).isoformat(),
        )
        for e in missed_rows
        if e.id not in sat and e.id not in own_attempts
    ]

    # ---- the few sentences a parent reads first
    def insight(s: DynamicsSubjectOut, value: float) -> DynamicsInsightOut:
        return DynamicsInsightOut(subject_id=s.subject_id, subject_name=s.subject_name, value=round(value, 1))

    improved = max(with_delta, key=lambda s: s.delta, default=None)
    declined = min(with_delta, key=lambda s: s.delta, default=None)
    insights = DynamicsInsightsOut(
        strongest=insight(max(subjects, key=lambda s: s.current_percent), max(s.current_percent for s in subjects)) if subjects else None,
        weakest=insight(min(subjects, key=lambda s: s.current_percent), min(s.current_percent for s in subjects)) if len(subjects) > 1 else None,
        most_improved=insight(improved, improved.delta) if improved and improved.delta >= NOTABLE_DELTA else None,
        most_declined=insight(declined, declined.delta) if declined and declined.delta <= -NOTABLE_DELTA else None,
    )

    # school years this student has any result in (the page offers a switch)
    years = {year}
    for (submitted_at,) in db.query(ExamAttempt.submitted_at).filter(
        ExamAttempt.student_id == student.id, ExamAttempt.status.in_(GRADED), ExamAttempt.submitted_at.isnot(None)
    ):
        years.add(quarter_service.school_year_start_year(_local_day(submitted_at)))

    klass = db.get(Class, student.class_id)
    return DynamicsOut(
        student_id=student.id,
        full_name=student.user.full_name,
        class_name=klass.display_name if klass else "",
        school_year_start=year,
        available_school_years=sorted(years),
        show_rank=include_rank,
        overall=overall,
        subjects=subjects,
        quarters=quarter_out,
        points=points,
        missed=missed,
        insights=insights,
    )
