import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models import *  # noqa: F401,F403


TEST_DATABASE_URL = (
    "postgresql+psycopg://"
    "payflow_user:payflow_password"
    "@localhost:5434/"
    "payflow_test_db"
)


@pytest.fixture
def db():
    engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()