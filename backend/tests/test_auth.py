"""認証（Phase 16）のテスト。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app
from app.models.user import User


@pytest.fixture
def anon(db: Session):
    """ログインしていない状態のクライアント。

    他のテストは get_current_user を差し替えているため、ここでは外す。
    """
    from app.db.session import get_db

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def register(client: TestClient, email: str = "new@example.com", password: str = "password123"):
    return client.post(
        "/auth/register",
        json={"name": "かんた", "email": email, "password": password},
    )


# ------------------------------------------------------------ パスワード


def test_password_is_hashed_and_verifiable() -> None:
    hashed = hash_password("password123")
    assert hashed != "password123"
    assert verify_password("password123", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_long_and_multibyte_passwords_work() -> None:
    """bcrypt の72バイト制限を回避できていること。

    日本語は1文字3バイトなので、そのまま渡すと24文字で頭打ちになる。
    """
    long_japanese = "ぱすわーど" * 30  # 450バイト相当
    hashed = hash_password(long_japanese)

    assert verify_password(long_japanese, hashed) is True
    # 先頭が同じでも末尾が違えば不一致になる（切り捨てられていない証拠）
    assert verify_password(long_japanese + "x", hashed) is False


def test_verify_rejects_user_without_password() -> None:
    assert verify_password("anything", None) is False
    assert verify_password("anything", "") is False


# ------------------------------------------------------------ トークン


def test_token_round_trip() -> None:
    assert decode_access_token(create_access_token(42)) == 42


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(42)
    assert decode_access_token(token[:-2] + "xx") is None
    assert decode_access_token("でたらめ") is None


# ------------------------------------------------------------ 登録・ログイン


def test_register_creates_user_and_logs_in(anon: TestClient) -> None:
    res = register(anon)

    assert res.status_code == 201
    assert res.json()["email"] == "new@example.com"
    assert "password" not in res.text and "hash" not in res.text
    # そのままログイン状態になる
    assert anon.get("/auth/me").json()["email"] == "new@example.com"


def test_duplicate_email_is_rejected(anon: TestClient) -> None:
    register(anon)
    res = register(anon)

    assert res.status_code == 409
    assert "既に登録" in res.json()["detail"]


def test_short_password_is_rejected(anon: TestClient) -> None:
    assert register(anon, password="short").status_code == 422


def test_invalid_email_is_rejected(anon: TestClient) -> None:
    assert register(anon, email="メールではない").status_code == 422


def test_login_and_logout(anon: TestClient) -> None:
    register(anon)
    anon.post("/auth/logout")
    assert anon.get("/auth/me").status_code == 401

    res = anon.post(
        "/auth/login", json={"email": "new@example.com", "password": "password123"}
    )
    assert res.status_code == 200
    assert anon.get("/auth/me").status_code == 200


def test_wrong_password_is_rejected(anon: TestClient) -> None:
    register(anon)
    res = anon.post(
        "/auth/login", json={"email": "new@example.com", "password": "ちがう"}
    )
    assert res.status_code == 401


def test_unknown_email_gives_the_same_error(anon: TestClient) -> None:
    """登録済みかどうかを応答から判別できないようにする。"""
    register(anon)
    unknown = anon.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "password123"}
    )
    wrong = anon.post(
        "/auth/login", json={"email": "new@example.com", "password": "ちがう"}
    )

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_session_cookie_is_protected(anon: TestClient) -> None:
    """Cookie は JavaScript から読めず、他サイトからは送られない設定であること。"""
    res = register(anon)
    cookie = res.headers["set-cookie"].lower()

    assert "httponly" in cookie
    assert "samesite=lax" in cookie


# ------------------------------------------------------- 未ログイン時の遮断


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/tasks"),
        ("post", "/tasks"),
        ("get", "/events"),
        ("get", "/conversations"),
        ("get", "/notifications"),
        ("post", "/chat"),
        ("get", "/auth/me"),
    ],
)
def test_endpoints_require_login(anon: TestClient, method: str, path: str) -> None:
    assert getattr(anon, method)(path).status_code == 401


def test_health_does_not_require_login(anon: TestClient) -> None:
    assert anon.get("/health").status_code == 200


# --------------------------------------------------------------- データ分離


def test_users_only_see_their_own_data(anon: TestClient, db: Session) -> None:
    register(anon, email="a@example.com")
    anon.post("/tasks", json={"title": "Aさんのタスク"})
    anon.post("/auth/logout")

    register(anon, email="b@example.com")
    assert anon.get("/tasks").json() == []

    anon.post("/tasks", json={"title": "Bさんのタスク"})
    assert [t["title"] for t in anon.get("/tasks").json()] == ["Bさんのタスク"]


def test_session_of_deleted_user_is_rejected(anon: TestClient, db: Session) -> None:
    register(anon, email="gone@example.com")
    user = db.query(User).filter(User.email == "gone@example.com").one()
    db.delete(user)
    db.commit()

    assert anon.get("/auth/me").status_code == 401
