import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.api.deps import ConversationServiceDep, get_chat_service
from app.core.exceptions import LLMError, LLMUnavailableError
from app.llm.base import ChatResult, ToolCall
from app.main import app
from app.models.user import User
from app.services.chat_service import ChatService, build_system_prompt
from tests.fakes import FakeProvider


def use_provider(provider: FakeProvider) -> None:
    """差し替え側も FastAPI の依存解決を通し、テスト用DBセッションを共有する。"""

    def factory(conversations: ConversationServiceDep) -> ChatService:
        return ChatService(provider, conversations)

    app.dependency_overrides[get_chat_service] = factory


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.pop(get_chat_service, None)


def reply(content: str = "", *calls: ToolCall) -> ChatResult:
    return ChatResult(
        content=content, provider="fake", model="fake-model", tool_calls=tuple(calls)
    )


# --------------------------------------------------------------- 会話の基本


def test_chat_returns_reply(client: TestClient) -> None:
    use_provider(FakeProvider())

    body = client.post("/chat", json={"message": "こんにちは"}).json()
    assert body["reply"] == "こんにちは"
    assert body["executed_tools"] == []
    assert body["mutated"] is False
    assert body["pending_action"] is None


def test_conversation_continues_across_requests(client: TestClient) -> None:
    """2回目の発言で、直前のやり取りが LLM に渡ること（要件22）。"""
    provider = FakeProvider(
        [
            reply("18時から20時に変更しました。"),
            reply("19時から21時に変更しました。"),
        ]
    )
    use_provider(provider)

    first = client.post(
        "/chat", json={"message": "明日の企業研究を18時からにして"}
    ).json()
    conversation_id = first["conversation_id"]

    client.post(
        "/chat",
        json={"message": "やっぱり19時からにして", "conversation_id": conversation_id},
    )

    sent = provider.calls[1]
    assert [m.role for m in sent] == ["user", "assistant", "user"]
    assert "明日の企業研究を18時からにして" in sent[0].content
    assert sent[1].content == "18時から20時に変更しました。"
    assert sent[-1].content.endswith("やっぱり19時からにして")


def test_new_conversation_is_created_without_id(client: TestClient) -> None:
    use_provider(FakeProvider())

    first = client.post("/chat", json={"message": "こんにちは"}).json()
    second = client.post("/chat", json={"message": "こんにちは"}).json()

    assert first["conversation_id"] != second["conversation_id"]


def test_unknown_conversation_returns_404(client: TestClient) -> None:
    use_provider(FakeProvider())
    res = client.post("/chat", json={"message": "hi", "conversation_id": 999999})
    assert res.status_code == 404


def test_chat_truncates_long_history(client: TestClient) -> None:
    """トークン量を抑えるため、LLM に渡すのは直近20件まで。"""
    provider = FakeProvider([reply(f"返答{i}") for i in range(20)])
    use_provider(provider)

    conversation_id = None
    for i in range(15):
        body = client.post(
            "/chat", json={"message": f"発言{i}", "conversation_id": conversation_id}
        ).json()
        conversation_id = body["conversation_id"]

    sent = provider.calls[-1]
    assert len(sent) == 21  # 直近20件 + 今回の発言
    assert sent[-1].content.endswith("発言14")


def test_chat_rejects_empty_message(client: TestClient) -> None:
    use_provider(FakeProvider())
    assert client.post("/chat", json={"message": ""}).status_code == 422


# ------------------------------------------------------------ Tool Calling


def test_tools_are_offered_to_the_model(client: TestClient) -> None:
    provider = FakeProvider()
    use_provider(provider)

    client.post("/chat", json={"message": "こんにちは"})

    names = {spec.name for spec in provider.received_tools}
    assert "create_task" in names
    assert "search_tasks" in names


def test_tool_call_creates_task(client: TestClient) -> None:
    """LLM が create_task を選べば、通常UIと同じデータが作られる。"""
    provider = FakeProvider(
        [
            reply("", ToolCall(id="c1", name="create_task", arguments={"title": "ES作成"})),
            reply("タスク「ES作成」を追加しました。"),
        ]
    )
    use_provider(provider)

    body = client.post("/chat", json={"message": "ES作成のタスクを追加して"}).json()

    assert body["executed_tools"] == ["create_task"]
    assert body["mutated"] is True
    assert body["reply"] == "タスク「ES作成」を追加しました。"

    titles = [t["title"] for t in client.get("/tasks").json()]
    assert "ES作成" in titles


def test_tool_result_is_sent_back_to_the_model(client: TestClient) -> None:
    provider = FakeProvider(
        [
            reply("", ToolCall(id="c1", name="create_task", arguments={"title": "企業研究"})),
            reply("追加しました。"),
        ]
    )
    use_provider(provider)

    client.post("/chat", json={"message": "企業研究を追加して"})

    second_call = provider.calls[1]
    assert [m.role for m in second_call] == ["user", "assistant", "tool"]
    tool_message = second_call[-1]
    assert tool_message.tool_call_id == "c1"
    assert json.loads(tool_message.content)["title"] == "企業研究"
    assert tool_message.is_error is False


def test_invalid_tool_arguments_are_reported_to_the_model(client: TestClient) -> None:
    """引数エラーで落とさず、LLM に返して修正させる。"""
    provider = FakeProvider(
        [
            reply("", ToolCall(id="c1", name="create_task", arguments={"title": ""})),
            reply("", ToolCall(id="c2", name="create_task", arguments={"title": "やり直し"})),
            reply("追加しました。"),
        ]
    )
    use_provider(provider)

    body = client.post("/chat", json={"message": "追加して"}).json()

    error_message = provider.calls[1][-1]
    assert error_message.is_error is True
    assert "引数が不正" in json.loads(error_message.content)["error"]
    assert body["reply"] == "追加しました。"
    assert "やり直し" in [t["title"] for t in client.get("/tasks").json()]


def test_multiple_tool_calls_in_one_turn(client: TestClient) -> None:
    provider = FakeProvider(
        [
            reply(
                "",
                ToolCall(id="c1", name="create_task", arguments={"title": "A"}),
                ToolCall(id="c2", name="create_task", arguments={"title": "B"}),
            ),
            reply("2件追加しました。"),
        ]
    )
    use_provider(provider)

    body = client.post("/chat", json={"message": "AとBを追加して"}).json()

    assert body["executed_tools"] == ["create_task", "create_task"]
    titles = {t["title"] for t in client.get("/tasks").json()}
    assert {"A", "B"} <= titles


def test_tool_loop_has_an_upper_bound(client: TestClient) -> None:
    """ツール呼び出しが止まらない場合も必ず終了する。"""
    endless = [
        reply("", ToolCall(id=f"c{i}", name="search_tasks", arguments={}))
        for i in range(10)
    ]
    provider = FakeProvider(endless)
    use_provider(provider)

    body = client.post("/chat", json={"message": "延々と検索して"}).json()

    assert len(provider.calls) == 5
    assert "完了できませんでした" in body["reply"]


# --------------------------------------------------------------- 確認フロー


def test_delete_returns_pending_action_without_deleting(client: TestClient) -> None:
    created = client.post("/tasks", json={"title": "消される予定"}).json()
    provider = FakeProvider(
        [reply("", ToolCall(id="c1", name="delete_task", arguments={"task_id": created["id"]}))]
    )
    use_provider(provider)

    body = client.post("/chat", json={"message": "消される予定を削除して"}).json()

    assert body["pending_action"]["tool"] == "delete_task"
    assert "消される予定" in body["pending_action"]["description"]
    assert body["mutated"] is False
    assert client.get(f"/tasks/{created['id']}").status_code == 200


def test_confirm_executes_the_pending_action(client: TestClient) -> None:
    created = client.post("/tasks", json={"title": "消される予定"}).json()
    use_provider(FakeProvider())

    conversation_id = client.post("/chat", json={"message": "準備"}).json()[
        "conversation_id"
    ]
    body = client.post(
        "/chat/confirm",
        json={
            "conversation_id": conversation_id,
            "tool": "delete_task",
            "arguments": {"task_id": created["id"]},
            "description": "タスク「消される予定」を削除します。",
        },
    ).json()

    assert body["mutated"] is True
    assert "削除しました" in body["reply"]
    assert client.get(f"/tasks/{created['id']}").status_code == 404


def test_confirm_revalidates_arguments(client: TestClient) -> None:
    """クライアントが返してきた引数もそのままは信用しない。"""
    use_provider(FakeProvider())

    conversation_id = client.post("/chat", json={"message": "準備"}).json()[
        "conversation_id"
    ]
    body = client.post(
        "/chat/confirm",
        json={
            "conversation_id": conversation_id,
            "tool": "delete_task",
            "arguments": {"task_id": 999999},
            "description": "タスクを削除します。",
        },
    ).json()

    assert "実行できませんでした" in body["reply"]
    assert body["mutated"] is False


# ------------------------------------------------------------ エラーと状態


def test_chat_returns_503_when_llm_unavailable(client: TestClient) -> None:
    use_provider(FakeProvider(error=LLMUnavailableError("Ollama に接続できません。")))

    res = client.post("/chat", json={"message": "こんにちは"})
    assert res.status_code == 503
    assert "Ollama" in res.json()["detail"]


def test_chat_returns_502_on_llm_error(client: TestClient) -> None:
    use_provider(FakeProvider(error=LLMError("モデルがエラーを返しました")))
    assert client.post("/chat", json={"message": "hi"}).status_code == 502


def test_status_reports_availability(client: TestClient) -> None:
    use_provider(FakeProvider())
    body = client.get("/chat/status").json()
    assert body == {
        "provider": "fake",
        "model": "fake-model",
        "available": True,
        "hint": None,
    }


def test_status_includes_hint_when_unavailable(client: TestClient) -> None:
    from app.llm.ollama import OllamaProvider

    use_provider(OllamaProvider(base_url="http://127.0.0.1:1", model="llama3.2:3b"))  # type: ignore[arg-type]

    body = client.get("/chat/status").json()
    assert body["available"] is False
    assert "ollama pull" in body["hint"]


# --------------------------------------------------------- システムプロンプト


def test_current_datetime_is_sent_with_the_user_message(client: TestClient) -> None:
    """現在日時は利用者の発言側に付ける。

    システムプロンプトに入れると分が変わるたびに Tool 定義まで含む前半が
    別物になり、LLM のプロンプトキャッシュが効かなくなるため。
    """
    provider = FakeProvider()
    use_provider(provider)

    client.post("/chat", json={"message": "今日のタスクを教えて"})

    sent = provider.calls[0][-1].content
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    assert sent.startswith(f"[現在日時: {now:%Y-%m-%d}")
    assert sent.endswith("今日のタスクを教えて")
    # 固定部分に可変の日時が混ざっていないこと
    assert f"{now:%H:%M}" not in provider.received_system


def test_system_prompt_contains_stable_context() -> None:
    user = User(name="かんた", email="p@example.com", timezone="Asia/Tokyo")
    prompt = build_system_prompt(user)

    assert "Asia/Tokyo" in prompt
    assert "かんた" in prompt


def test_system_prompt_uses_user_timezone() -> None:
    user = User(name="海外ユーザー", email="ny@example.com", timezone="America/New_York")
    assert "America/New_York" in build_system_prompt(user)


def test_system_prompt_forbids_pretending_to_use_tools() -> None:
    user = User(name="かんた", email="p@example.com", timezone="Asia/Tokyo")
    prompt = build_system_prompt(user)
    assert "必ず提供されたツールを使う" in prompt


def test_system_prompt_shows_search_before_destructive_action() -> None:
    """観測された失敗（IDを推測して削除しようとする）への対策が入っていること。"""
    user = User(name="かんた", email="p@example.com", timezone="Asia/Tokyo")
    prompt = build_system_prompt(user)

    assert "search_tasks" in prompt
    assert "id を推測してはいけない" in prompt
