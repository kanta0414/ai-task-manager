import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User

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


@pytest.fixture
def user(db: Session) -> User:
    """テスト用の「現在のユーザー」。"""
    user = User(name="テストユーザー", email="owner@example.com", timezone="Asia/Tokyo")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client(db: Session, user: User) -> Generator[TestClient, None, None]:
    """DB と現在のユーザーをテスト用に差し替えた API クライアント。"""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
