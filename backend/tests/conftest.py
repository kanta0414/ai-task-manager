import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

# 開発用DBを壊さないよう、テストは専用DB (…_test) に対して実行する
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", get_settings().database_url + "_test"
)


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_DATABASE_URL, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(engine) -> Generator[Session, None, None]:
    """テストごとにロールバックされるセッション。テスト間でデータが残らない。"""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        # IntegrityError のテストでは既にロールバック済みのことがある
        if transaction.is_active:
            transaction.rollback()
        connection.close()
