import pytest
from sqlalchemy.orm import Session

from app.llm.base import ToolCall
from app.models.task import Task
from app.models.user import User
from app.services.tool_registry import ToolRegistry


@pytest.fixture
def registry(db: Session, user: User) -> ToolRegistry:
    return ToolRegistry(db, user)


def call(name: str, **arguments) -> ToolCall:
    return ToolCall(id="call_1", name=name, arguments=arguments)


def test_specs_cover_mvp_task_tools(registry: ToolRegistry) -> None:
    names = {spec.name for spec in registry.specs()}
    assert {
        "create_task",
        "get_task",
        "search_tasks",
        "update_task",
        "complete_task",
        "delete_task",
    } <= names


def test_tool_count_stays_small(registry: ToolRegistry) -> None:
    """Tool が増えすぎると LLM の選択精度が落ちるため、MVP では11個に抑える。"""
    assert len(registry.specs()) == 11


def test_specs_have_no_json_schema_refs(registry: ToolRegistry) -> None:
    """$ref を残すと受け付けないプロバイダがあるため、実体に展開されていること。"""
    for spec in registry.specs():
        serialized = str(spec.input_schema)
        assert "$ref" not in serialized
        assert "$defs" not in serialized
        assert spec.description


def test_create_task(registry: ToolRegistry) -> None:
    outcome = registry.execute(
        call("create_task", title="SPIの勉強", due_date="2026-09-30T23:59", priority="high")
    )

    assert outcome.is_error is False
    assert outcome.mutated is True
    assert outcome.content["title"] == "SPIの勉強"
    assert outcome.content["priority"] == "high"
    # オフセット無しの日時は日本時間として解釈される
    assert outcome.content["due_date"].endswith("+09:00")


def test_create_task_rejects_invalid_arguments(registry: ToolRegistry) -> None:
    """LLM が誤った引数を出しても例外にせず、修正を促す結果を返す。"""
    outcome = registry.execute(call("create_task", title=""))

    assert outcome.is_error is True
    assert "引数が不正" in outcome.content["error"]
    assert outcome.content["details"][0]["field"] == "title"


def test_unknown_tool_returns_error(registry: ToolRegistry) -> None:
    outcome = registry.execute(call("drop_database"))
    assert outcome.is_error is True
    assert "ツールはありません" in outcome.content["error"]


def test_search_tasks(registry: ToolRegistry) -> None:
    registry.execute(call("create_task", title="企業研究", description="業界分析"))
    registry.execute(call("create_task", title="SPIの勉強"))

    outcome = registry.execute(call("search_tasks", keyword="業界"))
    assert outcome.content["count"] == 1
    assert outcome.content["tasks"][0]["title"] == "企業研究"
    assert outcome.mutated is False


def test_search_tasks_by_due_range(registry: ToolRegistry) -> None:
    registry.execute(call("create_task", title="今週", due_date="2026-09-22T12:00"))
    registry.execute(call("create_task", title="来月", due_date="2026-10-22T12:00"))

    outcome = registry.execute(
        call("search_tasks", due_from="2026-09-21T00:00", due_to="2026-09-27T23:59")
    )
    assert [t["title"] for t in outcome.content["tasks"]] == ["今週"]


def test_update_task(registry: ToolRegistry) -> None:
    created = registry.execute(call("create_task", title="ES作成")).content

    outcome = registry.execute(
        call("update_task", task_id=created["id"], due_date="2026-10-05T18:00")
    )
    assert outcome.mutated is True
    assert outcome.content["due_date"].startswith("2026-10-05")
    assert outcome.content["title"] == "ES作成"


def test_update_missing_task_returns_error(registry: ToolRegistry) -> None:
    outcome = registry.execute(call("update_task", task_id=999999, title="x"))
    assert outcome.is_error is True
    assert "見つかりません" in outcome.content["error"]


def test_complete_task(registry: ToolRegistry) -> None:
    created = registry.execute(call("create_task", title="面接対策")).content

    outcome = registry.execute(call("complete_task", task_id=created["id"]))
    assert outcome.content["status"] == "done"


def test_delete_requires_confirmation(registry: ToolRegistry) -> None:
    """削除は承認を得るまで実行しない（要件定義書 24）。"""
    created = registry.execute(call("create_task", title="消される予定")).content

    outcome = registry.execute(call("delete_task", task_id=created["id"]))

    assert outcome.pending is not None
    assert outcome.pending.tool == "delete_task"
    assert "消される予定" in outcome.pending.description
    assert "消される予定" in outcome.pending.done_message
    assert outcome.mutated is False
    # まだ残っている
    assert registry.execute(call("get_task", task_id=created["id"])).is_error is False


def test_delete_executes_after_confirmation(registry: ToolRegistry) -> None:
    created = registry.execute(call("create_task", title="消される予定")).content

    outcome = registry.execute(call("delete_task", task_id=created["id"]), confirmed=True)

    assert outcome.content["deleted"] is True
    assert outcome.mutated is True
    assert registry.execute(call("get_task", task_id=created["id"])).is_error is True


def test_confirmation_checks_existence_first(registry: ToolRegistry) -> None:
    """存在しないIDなら、確認ダイアログを出す前にエラーを返す。"""
    outcome = registry.execute(call("delete_task", task_id=999999))
    assert outcome.pending is None
    assert outcome.is_error is True


def test_tools_cannot_touch_other_users_data(
    registry: ToolRegistry, db: Session
) -> None:
    other = User(name="他人", email="other-tool@example.com")
    db.add(other)
    db.flush()
    task = Task(user_id=other.id, title="他人のタスク")
    db.add(task)
    db.commit()

    assert registry.execute(call("get_task", task_id=task.id)).is_error is True
    assert registry.execute(call("update_task", task_id=task.id, title="x")).is_error is True
    assert registry.execute(call("delete_task", task_id=task.id)).is_error is True
    assert registry.execute(call("search_tasks")).content["count"] == 0


# ------------------------------------------------------------ カレンダーの Tool


def test_specs_cover_mvp_calendar_tools(registry: ToolRegistry) -> None:
    names = {spec.name for spec in registry.specs()}
    assert {
        "create_event",
        "get_event",
        "search_events",
        "update_event",
        "delete_event",
    } <= names


def test_create_event(registry: ToolRegistry) -> None:
    outcome = registry.execute(
        call(
            "create_event",
            title="企業研究",
            start_at="2026-09-21T14:00",
            end_at="2026-09-21T16:00",
        )
    )

    assert outcome.mutated is True
    assert outcome.content["start_at"] == "2026-09-21T14:00:00+09:00"
    assert outcome.content["end_at"] == "2026-09-21T16:00:00+09:00"


def test_create_event_rejects_inverted_period(registry: ToolRegistry) -> None:
    """LLM が終了を開始より前に出しても Service のルールで弾かれる。"""
    outcome = registry.execute(
        call(
            "create_event",
            title="逆転",
            start_at="2026-09-21T16:00",
            end_at="2026-09-21T14:00",
        )
    )
    assert outcome.is_error is True
    assert "終了時刻" in outcome.content["error"]


def test_create_event_linked_to_task(registry: ToolRegistry) -> None:
    task = registry.execute(call("create_task", title="企業研究")).content

    outcome = registry.execute(
        call(
            "create_event",
            title="企業研究",
            start_at="2026-09-21T14:00",
            end_at="2026-09-21T16:00",
            task_id=task["id"],
        )
    )
    assert outcome.content["task_id"] == task["id"]


def test_search_events_returns_overlapping(registry: ToolRegistry) -> None:
    registry.execute(
        call("create_event", title="またぎ", start_at="2026-09-21T23:00", end_at="2026-09-22T01:00")
    )
    registry.execute(
        call("create_event", title="範囲外", start_at="2026-09-25T10:00", end_at="2026-09-25T11:00")
    )

    outcome = registry.execute(
        call("search_events", period_start="2026-09-22T00:00", period_end="2026-09-23T00:00")
    )
    assert [e["title"] for e in outcome.content["events"]] == ["またぎ"]


def test_update_event_moves_time(registry: ToolRegistry) -> None:
    created = registry.execute(
        call("create_event", title="企業研究", start_at="2026-09-21T14:00", end_at="2026-09-21T16:00")
    ).content

    outcome = registry.execute(
        call(
            "update_event",
            event_id=created["id"],
            start_at="2026-09-21T18:00",
            end_at="2026-09-21T20:00",
        )
    )
    assert outcome.content["start_at"] == "2026-09-21T18:00:00+09:00"


def test_delete_event_requires_confirmation(registry: ToolRegistry) -> None:
    created = registry.execute(
        call("create_event", title="面接", start_at="2026-09-21T09:00", end_at="2026-09-21T10:00")
    ).content

    outcome = registry.execute(call("delete_event", event_id=created["id"]))

    assert outcome.pending is not None
    assert "面接" in outcome.pending.description
    assert "9/21 09:00" in outcome.pending.description
    assert registry.execute(call("get_event", event_id=created["id"])).is_error is False


def test_delete_event_executes_after_confirmation(registry: ToolRegistry) -> None:
    created = registry.execute(
        call("create_event", title="面接", start_at="2026-09-21T09:00", end_at="2026-09-21T10:00")
    ).content

    outcome = registry.execute(call("delete_event", event_id=created["id"]), confirmed=True)

    assert outcome.content["deleted"] is True
    assert registry.execute(call("get_event", event_id=created["id"])).is_error is True


def test_required_arguments_are_visible_to_the_model(registry: ToolRegistry) -> None:
    """必須引数がスキーマに含まれていること。

    ここが欠けると LLM は引数を組み立てられず、Tool Calling が成立しない。
    """
    specs = {spec.name: spec.input_schema for spec in registry.specs()}

    assert "title" in specs["create_task"]["properties"]
    assert specs["create_task"]["required"] == ["title"]

    event_properties = specs["create_event"]["properties"]
    assert {"title", "start_at", "end_at"} <= set(event_properties)
    assert set(specs["create_event"]["required"]) == {"title", "start_at", "end_at"}

    # すべてのツールで required が properties に含まれていること
    for name, schema in specs.items():
        properties = set(schema.get("properties", {}))
        missing = set(schema.get("required", [])) - properties
        assert not missing, f"{name} の必須引数 {missing} がスキーマに無い"
