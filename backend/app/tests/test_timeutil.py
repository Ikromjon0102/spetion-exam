"""Regression test for the bug a live smoke test caught: a datetime that
round-trips through sqlite loses its UTC offset, which (a) breaks Python
comparisons against datetime.now(timezone.utc) and (b) gets serialized to
the frontend without a Z/offset suffix, which browsers then misread as
local time — silently corrupting the exam deadline countdown. UTCDateTime
fixes this at the column-type level; this test forces a real DB round-trip
(session.expire_all()) so it actually exercises that fix, unlike the app's
other sqlite-backed tests which use expire_on_commit=False and therefore
never re-read the value from disk.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.timeutil import UTCDateTime


def test_utc_datetime_round_trips_aware_even_on_sqlite():
    Base = declarative_base()

    class Sample(Base):
        __tablename__ = "sample_utc_datetime"
        id = Column(Integer, primary_key=True)
        at = Column(UTCDateTime)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    original = datetime(2026, 9, 22, 17, 0, 0, tzinfo=timezone.utc)
    session.add(Sample(id=1, at=original))
    session.commit()
    session.expire_all()  # force the next access to hit a real SELECT

    reloaded = session.get(Sample, 1)
    assert reloaded.at.tzinfo is not None
    assert reloaded.at == original
    # would raise TypeError before the fix if this came back naive
    assert reloaded.at <= datetime.now(timezone.utc)
