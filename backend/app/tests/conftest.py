"""Tests run against an in-memory SQLite DB, not the dev Postgres instance
(no live Postgres in this environment). app.services.attempt_service
dispatches its ON CONFLICT upserts by bound dialect specifically so this
works — see attempt_service._insert().

expire_on_commit=False below works around a sqlite-only quirk: unlike
Postgres TIMESTAMPTZ, sqlite's DateTime(timezone=True) silently drops the
UTC offset on round-trip, so a post-commit attribute refresh would turn a
tz-aware datetime naive and break comparisons against datetime.now(utc).
Production (Postgres) doesn't need this and isn't affected.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registers all tables on Base.metadata
from app.db.base import Base, get_db
from app.main import app as fastapi_app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
