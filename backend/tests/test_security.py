"""セキュリティ上の性質を固定するテスト（Phase 19）。

監査で見つかった穴を塞いだあと、同じ穴が再発しないようにする。
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message
from app.models.enums import MessageRole
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.common import MAX_DESCRIPTION


def test_conversation_messages_are_scoped_to_the_owner(
    db: Session, user: User
) -> None:
    """会話IDを知っていても、他人の発言は読めない。"""
    other = User(name="他人", email="other-sec@example.com")
    db.add(other)
    db.flush()
    conversation = Conversation(user_id=other.id, title="他人の会話")
    db.add(conversation)
    db.flush()
    db.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="ひみつの相談",
        )
    )
    db.flush()

    repo = ConversationRepository(db)

    assert repo.recent_messages(conversation.id, other.id, 20) != []
    assert repo.recent_messages(conversation.id, user.id, 20) == []


def test_task_description_has_an_upper_bound(client: TestClient) -> None:
    """DBの型は無制限なので、入口で歯止めをかける。"""
    ok = client.post(
        "/tasks", json={"title": "ok", "description": "あ" * MAX_DESCRIPTION}
    )
    assert ok.status_code == 201

    too_long = client.post(
        "/tasks", json={"title": "ng", "description": "あ" * (MAX_DESCRIPTION + 1)}
    )
    assert too_long.status_code == 422


def test_event_description_has_an_upper_bound(client: TestClient) -> None:
    res = client.post(
        "/events",
        json={
            "title": "ng",
            "start_at": "2026-09-22T10:00:00+09:00",
            "end_at": "2026-09-22T11:00:00+09:00",
            "description": "あ" * (MAX_DESCRIPTION + 1),
        },
    )
    assert res.status_code == 422


def test_oversized_request_is_rejected(client: TestClient) -> None:
    """Pydantic の検証は本文を読み込んだ後に効くため、その手前で落とす。"""
    res = client.post(
        "/tasks", json={"title": "x", "description": "a" * 1_100_000}
    )
    assert res.status_code == 413


def test_cors_does_not_allow_credentials(client: TestClient) -> None:
    """Cookie を使っていないので資格情報は許可しない。"""
    res = client.options(
        "/tasks",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-credentials" not in res.headers


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    res = client.options(
        "/tasks",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in res.headers


def test_llm_tools_cannot_reach_the_database_directly() -> None:
    """Tool の実装が Service 以外からDBを触っていないこと（要件 32.2）。"""
    import inspect

    from app.services import tool_registry

    source = inspect.getsource(tool_registry)
    for forbidden in ("select(", "text(", "self.db.execute", "session.execute"):
        assert forbidden not in source, f"ToolRegistry が {forbidden} を使っている"
