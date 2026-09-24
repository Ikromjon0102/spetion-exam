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

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


def aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
