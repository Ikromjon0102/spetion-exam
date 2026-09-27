"""Shared datetime helper + column type.

Postgres TIMESTAMPTZ always round-trips timezone-aware; sqlite (used for
local dev without Docker, and in tests) silently drops the UTC offset on
read-back. Left uncorrected this breaks in two ways: a naive DB value
compared against a fresh datetime.now(timezone.utc) raises TypeError, and a
naive value serialized to JSON has no offset/Z suffix, which browsers then
parse as *local* time instead of UTC (turning e.g. a deadline_at that's
really 17:10 UTC into "17:10 in whatever timezone the browser is in",
silently corrupting the exam timer).

UTCDateTime fixes this at the source — use it instead of
sqlalchemy.DateTime(timezone=True) on every datetime column — so values are
guaranteed tz-aware in Python regardless of backend. `aware()` remains as a
defense-in-depth guard at comparison sites.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator

# Single-tenant v1: the one school this runs for is in Uzbekistan, which
# doesn't observe DST, so a fixed offset is safe (no zoneinfo/tzdata dep).
SCHOOL_UTC_OFFSET = timedelta(hours=5)


def aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def local_day_bounds_utc(date_str: str | None = None) -> tuple[str, datetime, datetime]:
    """Resolves a "YYYY-MM-DD" calendar day in the school's local timezone
    into a [start, end) UTC datetime range, for filtering "today's exams"
    without pushing timezone math onto the frontend. `date_str` omitted
    defaults to today in that local timezone. Returns (resolved_date_str,
    start_utc, end_utc)."""
    school_tz = timezone(SCHOOL_UTC_OFFSET)
    day = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else datetime.now(school_tz).date()
    start_local = datetime(day.year, day.month, day.day, tzinfo=school_tz)
    end_local = start_local + timedelta(days=1)
    return day.isoformat(), start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
