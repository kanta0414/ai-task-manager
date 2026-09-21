import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import ConversationServiceDep, get_chat_service
from app.llm.base import ChatResult
from app.main import app
from app.models.conversation import Conversation, Message
from app.models.enums import MessageRole
from app.models.user import User
from app.services.chat_service import ChatService
from tests.fakes import FakeProvider


@pytest.fixture(autouse=True)
def fake_llm():
    provider = FakeProvider([ChatResult(content="はい", provider="fake", model="fake-model")] * 10)

    def factory(conversations: ConversationServiceDep) -> ChatService:
        return ChatService(provider, conversations)

    app.dependency_overrides[get_chat_service] = factory
    yield provider
    app.dependency_overrides.pop(get_chat_service, None)


def test_messages_are_persisted(client: TestClient) -> None:
    body = client.post("/chat", json={"message": "今日のタスクを教えて"}).json()

    detail = client.get(f"/conversations/{body['conversation_id']}").json()
    assert [(m["role"], m["content"]) for m in detail["messages"]] == [
        ("user", "今日のタスクを教えて"),
        ("assistant", "はい"),
    ]


def test_stored_user_message_has_no_injected_timestamp(client: TestClient) -> None:
    """LLM へ渡す現在日時は保存しない（表示にも次回の履歴にも不要）。"""
    body = client.post("/chat", json={"message": "こんにちは"}).json()

    detail = client.get(f"/conversations/{body['conversation_id']}").json()
    assert detail["messages"][0]["content"] == "こんにちは"


def test_title_comes_from_the_first_message(client: TestClient) -> None:
    body = client.post("/chat", json={"message": "明日の予定を教えて"}).json()
    client.post(
        "/chat",
        json={"message": "ありがとう", "conversation_id": body["conversation_id"]},
    )

    listed = client.get("/conversations").json()
    assert listed[0]["title"] == "明日の予定を教えて"


def test_long_title_is_truncated(client: TestClient) -> None:
    client.post("/chat", json={"message": "あ" * 80})
    assert listed_title(client).endswith("…")
    assert len(listed_title(client)) == 40


def listed_title(client: TestClient) -> str:
    return client.get("/conversations").json()[0]["title"]


def test_conversations_are_listed_recent_first(client: TestClient) -> None:
    first = client.post("/chat", json={"message": "ひとつめ"}).json()
    second = client.post("/chat", json={"message": "ふたつめ"}).json()

    listed = client.get("/conversations").json()
    assert [c["id"] for c in listed][:2] == [
        second["conversation_id"],
        first["conversation_id"],
    ]


def test_delete_conversation(client: TestClient) -> None:
    body = client.post("/chat", json={"message": "消す会話"}).json()
    conversation_id = body["conversation_id"]

    assert client.delete(f"/conversations/{conversation_id}").status_code == 204
    assert client.get(f"/conversations/{conversation_id}").status_code == 404


def test_deleting_conversation_removes_messages(
    client: TestClient, db: Session
) -> None:
    body = client.post("/chat", json={"message": "消す会話"}).json()
    conversation_id = body["conversation_id"]

    client.delete(f"/conversations/{conversation_id}")

    remaining = (
        db.query(Message).filter(Message.conversation_id == conversation_id).count()
    )
    assert remaining == 0


def test_other_users_conversation_is_not_accessible(
    client: TestClient, db: Session
) -> None:
    other = User(name="他人", email="other-conv@example.com")
    db.add(other)
    db.flush()
    conversation = Conversation(user_id=other.id, title="他人の会話")
    db.add(conversation)
    db.flush()
    db.add(
        Message(
            conversation_id=conversation.id, role=MessageRole.USER, content="ひみつ"
        )
    )
    db.commit()

    assert client.get(f"/conversations/{conversation.id}").status_code == 404
    assert client.delete(f"/conversations/{conversation.id}").status_code == 404
    assert client.get("/conversations").json() == []
    # 他人の会話IDを指定して会話を続けることもできない
    res = client.post(
        "/chat", json={"message": "続き", "conversation_id": conversation.id}
    )
    assert res.status_code == 404
