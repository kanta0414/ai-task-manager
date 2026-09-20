from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_chat_service
from app.core.exceptions import LLMError, LLMUnavailableError
from app.llm.base import ChatMessage, ChatResult, LLMProvider
from app.main import app
from app.models.user import User
from app.services.chat_service import ChatService, build_system_prompt


class FakeProvider(LLMProvider):
    """実際のLLMを呼ばずに Service / API を検証するための差し替え。"""

    name = "fake"
    model = "fake-model"

    def __init__(self, *, available: bool = True, error: Exception | None = None):
        self.available = available
        self.error = error
        self.received_messages: list[ChatMessage] = []
        self.received_system = ""

    def chat(self, messages: list[ChatMessage], system: str) -> ChatResult:
        if self.error:
            raise self.error
        self.received_messages = messages
        self.received_system = system
        return ChatResult(content="こんにちは", provider=self.name, model=self.model)

    def is_available(self) -> bool:
        return self.available


@pytest.fixture
def fake_provider():
    provider = FakeProvider()
    app.dependency_overrides[get_chat_service] = lambda: ChatService(provider)
    yield provider
    app.dependency_overrides.pop(get_chat_service, None)


def test_chat_returns_reply(client: TestClient, fake_provider: FakeProvider) -> None:
    res = client.post("/chat", json={"message": "こんにちは"})
    assert res.status_code == 200
    assert res.json() == {
        "reply": "こんにちは",
        "provider": "fake",
        "model": "fake-model",
    }


def test_chat_passes_history_then_new_message(
    client: TestClient, fake_provider: FakeProvider
) -> None:
    client.post(
        "/chat",
        json={
            "message": "やっぱり19時からにして",
            "history": [
                {"role": "user", "content": "明日の企業研究を18時からにして"},
                {"role": "assistant", "content": "18時から20時に変更しました。"},
            ],
        },
    )

    roles = [m.role for m in fake_provider.received_messages]
    assert roles == ["user", "assistant", "user"]
    assert fake_provider.received_messages[-1].content == "やっぱり19時からにして"


def test_chat_truncates_long_history(
    client: TestClient, fake_provider: FakeProvider
) -> None:
    """トークン量を抑えるため直近20件までに切り詰める。"""
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"発言{i}"}
        for i in range(30)
    ]
    client.post("/chat", json={"message": "最新", "history": history})

    # 直近20件 + 今回の発言
    assert len(fake_provider.received_messages) == 21
    assert fake_provider.received_messages[0].content == "発言10"


def test_chat_rejects_empty_message(client: TestClient, fake_provider) -> None:
    assert client.post("/chat", json={"message": ""}).status_code == 422


def test_chat_returns_503_when_llm_unavailable(client: TestClient) -> None:
    provider = FakeProvider(error=LLMUnavailableError("Ollama に接続できません。"))
    app.dependency_overrides[get_chat_service] = lambda: ChatService(provider)

    res = client.post("/chat", json={"message": "こんにちは"})
    assert res.status_code == 503
    assert "Ollama" in res.json()["detail"]

    app.dependency_overrides.pop(get_chat_service, None)


def test_chat_returns_502_on_llm_error(client: TestClient) -> None:
    provider = FakeProvider(error=LLMError("モデルがエラーを返しました"))
    app.dependency_overrides[get_chat_service] = lambda: ChatService(provider)

    assert client.post("/chat", json={"message": "hi"}).status_code == 502

    app.dependency_overrides.pop(get_chat_service, None)


def test_status_reports_availability(
    client: TestClient, fake_provider: FakeProvider
) -> None:
    body = client.get("/chat/status").json()
    assert body == {
        "provider": "fake",
        "model": "fake-model",
        "available": True,
        "hint": None,
    }


def test_status_includes_hint_when_unavailable(client: TestClient) -> None:
    from app.llm.ollama import OllamaProvider

    provider = OllamaProvider(base_url="http://127.0.0.1:1", model="qwen3:8b")
    app.dependency_overrides[get_chat_service] = lambda: ChatService(provider)

    body = client.get("/chat/status").json()
    assert body["available"] is False
    assert "ollama pull" in body["hint"]

    app.dependency_overrides.pop(get_chat_service, None)


def test_system_prompt_contains_current_datetime() -> None:
    """相対的な日時表現を解釈させるため、現在日時が必ず含まれること。"""
    user = User(name="かんた", email="p@example.com", timezone="Asia/Tokyo")
    prompt = build_system_prompt(user)

    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    assert f"{now:%Y-%m-%d}" in prompt
    assert "Asia/Tokyo" in prompt
    assert "かんた" in prompt


def test_system_prompt_uses_user_timezone() -> None:
    user = User(name="海外ユーザー", email="ny@example.com", timezone="America/New_York")
    assert "America/New_York" in build_system_prompt(user)
