"""Fixtures for tests that must prove behavior against a real Postgres
instance, per docs/PROCESS.md ("Integration tests run against a real
Dockerized Postgres instance, not mocks"). Skips cleanly — doesn't fail —
when no Postgres is reachable, so `make test` still works for a contributor
who hasn't started the db; CI brings one up explicitly (see ci.yml).
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg2://clincode:clincode@localhost:5432/clincode_test"
)


def _postgres_available() -> bool:
    try:
        engine = create_engine(TEST_DATABASE_URL)
        with engine.connect():
            pass
        engine.dispose()
        return True
    except Exception:
        return False


requires_postgres = pytest.mark.skipif(
    not _postgres_available(),
    reason=f"Postgres not reachable at {TEST_DATABASE_URL}; start it to run integration tests",
)


@pytest.fixture()
def pg_session():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def pg_client(pg_session):
    def override_get_db():
        yield pg_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
