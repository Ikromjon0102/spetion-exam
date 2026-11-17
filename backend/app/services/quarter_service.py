"""The school year's four chorak (quarters) as date ranges, and which one a
date — or an exam — falls in.

The school year runs 1 Sep - 31 Aug, so every date belongs to the school year
that STARTED in `school_year_start_year(d)`. Quarters are stored as month/day
only (see SchoolQuarter) and resolved against that year: a month >= 9 is in
the starting calendar year, a month < 9 in the next one — which is how
chorak 2 (6 Nov - 11 Jan) crosses New Year without a special case.

An exam belongs to a quarter by the *effective* ranges, which absorb every
gap so no date is ever "in no quarter": chorak 1 reaches back to 1 Sep, each
later quarter runs until the next one starts (a holiday between two quarters
goes to the earlier one), and chorak 4 runs to 31 Aug (the summer). Drafts
with no start date use the day they were created.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.timeutil import SCHOOL_UTC_OFFSET
from app.models.org import SchoolQuarter

# number -> (start_month, start_day, end_month, end_day) — the school's own
# calendar, used until an admin saves different dates.
DEFAULTS: dict[int, tuple[int, int, int, int]] = {
    1: (9, 1, 11, 5),
    2: (11, 6, 1, 11),
    3: (1, 12, 4, 7),
    4: (4, 8, 7, 1),
}

_SCHOOL_YEAR_START = (9, 1)
# a non-leap pair of years, so validation never accepts a 29 Feb that doesn't
# exist in most years
_REF_YEAR = 2001


@dataclass(frozen=True)
class Quarter:
    number: int
    start: tuple[int, int]  # (month, day)
    end: tuple[int, int]


def get_quarters(db: Session) -> tuple[list[Quarter], bool]:
    """(the four quarters in order, is_default)."""
    rows = {r.number: r for r in db.query(SchoolQuarter).all()}
    if set(rows) == {1, 2, 3, 4}:
        return (
            [Quarter(n, (rows[n].start_month, rows[n].start_day), (rows[n].end_month, rows[n].end_day)) for n in (1, 2, 3, 4)],
            False,
        )
    return [Quarter(n, (v[0], v[1]), (v[2], v[3])) for n, v in sorted(DEFAULTS.items())], True


def school_today() -> date:
    return (datetime.now(timezone.utc) + SCHOOL_UTC_OFFSET).date()


def school_year_start_year(d: date) -> int:
    return d.year if d.month >= _SCHOOL_YEAR_START[0] else d.year - 1


def resolve(md: tuple[int, int], year: int) -> date:
    """A month/day inside the school year that starts in `year`."""
    return date(year if md[0] >= 9 else year + 1, md[0], md[1])


def quarter_dates(q: Quarter, year: int) -> tuple[date, date]:
    """The quarter's own first and last day in that school year."""
    return resolve(q.start, year), resolve(q.end, year)


def effective_range(quarters: list[Quarter], number: int, year: int) -> tuple[date, date]:
    """[start, end) in dates, gaps absorbed (see the module docstring)."""
    start = date(year, *_SCHOOL_YEAR_START) if number == 1 else resolve(quarters[number - 1].start, year)
    end = resolve(quarters[number].start, year) if number < 4 else date(year + 1, *_SCHOOL_YEAR_START)
    return start, end


def quarter_of(quarters: list[Quarter], d: date) -> int:
    year = school_year_start_year(d)
    for number in (1, 2, 3, 4):
        start, end = effective_range(quarters, number, year)
        if start <= d < end:
            return number
    return 4


def utc_bounds(start: date, end_exclusive: date) -> tuple[datetime, datetime]:
    """[start, end) local school days as UTC datetimes."""
    def to_utc(d: date) -> datetime:
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc) - SCHOOL_UTC_OFFSET

    return to_utc(start), to_utc(end_exclusive)


def validate(parsed: dict[int, tuple[int, int, int, int]]) -> None:
    """Raises ValueError(message, in Uzbek) unless the four ranges are real
    dates, each start <= its end, and each quarter ends before the next one
    starts."""
    if set(parsed) != {1, 2, 3, 4}:
        raise ValueError("To'rtala chorakning to'rttasi ham ko'rsatilishi kerak")
    ranges: dict[int, tuple[date, date]] = {}
    for number, (sm, sd, em, ed) in parsed.items():
        try:
            ranges[number] = (resolve((sm, sd), _REF_YEAR), resolve((em, ed), _REF_YEAR))
        except ValueError:
            raise ValueError(f"{number}-chorak: sana noto'g'ri (29-fevral qabul qilinmaydi)")
        if ranges[number][0] > ranges[number][1]:
            raise ValueError(f"{number}-chorak: tugash sanasi boshlanishidan oldin")
    for number in (1, 2, 3):
        if ranges[number][1] >= ranges[number + 1][0]:
            raise ValueError(f"{number}-chorak {number + 1}-chorak boshlanishidan oldin tugashi kerak")


def save_quarters(db: Session, parsed: dict[int, tuple[int, int, int, int]]) -> None:
    validate(parsed)
    db.query(SchoolQuarter).delete()
    for number, (sm, sd, em, ed) in sorted(parsed.items()):
        db.add(SchoolQuarter(number=number, start_month=sm, start_day=sd, end_month=em, end_day=ed))
    db.commit()
