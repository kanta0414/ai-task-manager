"""タスク分解（Phase 13）のテスト。

分解の中身は LLM が考えるが、登録は承認を経てからにする（要件定義書 20）。
"""

import pytest
from sqlalchemy.orm import Session

from app.llm.base import ToolCall
from app.models.enums import TaskPriority
from app.models.task import Task
from app.models.user import User
from app.services.tool_registry import ToolRegistry


@pytest.fixture
def registry(db: Session, user: User) -> ToolRegistry:
    return ToolRegistry(db, user)


def call(name: str, **arguments) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments)


def make_parent(registry: ToolRegistry, **overrides) -> dict:
    payload = {"title": "ES作成", "priority": "high"} | overrides
    return registry.execute(call("create_task", **payload)).content


def test_decomposition_asks_for_confirmation(registry: ToolRegistry, db: Session) -> None:
    parent = make_parent(registry)

    outcome = registry.execute(
        call(
            "create_subtasks",
            parent_task_id=parent["id"],
            subtasks=[
                {"title": "企業研究", "estimated_minutes": 60},
                {"title": "志望動機作成"},
            ],
        )
    )

    assert outcome.pending is not None
    assert "ES作成" in outcome.pending.description
    assert "1. 企業研究（60分）" in outcome.pending.description
    assert "2. 志望動機作成" in outcome.pending.description
    assert outcome.mutated is False
    # 承認前は登録されない
    assert db.query(Task).count() == 1


def test_confirmed_decomposition_creates_subtasks(
    registry: ToolRegistry, db: Session
) -> None:
    parent = make_parent(registry, due_date="2026-10-01T23:59")

    outcome = registry.execute(
        call(
            "create_subtasks",
            parent_task_id=parent["id"],
            subtasks=[{"title": "企業研究"}, {"title": "自己PR作成"}],
        ),
        confirmed=True,
    )

    assert outcome.mutated is True
    assert outcome.message == "2個のタスクを登録しました。"

    subtasks = db.query(Task).filter(Task.parent_task_id == parent["id"]).all()
    assert [t.title for t in subtasks] == ["企業研究", "自己PR作成"]
    # 期限と優先度は親から引き継ぐ
    assert all(t.due_date == subtasks[0].due_date for t in subtasks)
    assert all(t.priority is TaskPriority.HIGH for t in subtasks)


def test_subtask_can_override_inherited_values(
    registry: ToolRegistry, db: Session
) -> None:
    parent = make_parent(registry, due_date="2026-10-01T23:59")

    registry.execute(
        call(
            "create_subtasks",
            parent_task_id=parent["id"],
            subtasks=[{"title": "先に終わらせる", "due_date": "2026-09-25T18:00"}],
        ),
        confirmed=True,
    )

    subtask = db.query(Task).filter(Task.parent_task_id == parent["id"]).one()
    assert subtask.due_date.isoformat().startswith("2026-09-25")


def test_unknown_parent_is_rejected_before_confirmation(
    registry: ToolRegistry,
) -> None:
    outcome = registry.execute(
        call("create_subtasks", parent_task_id=999999, subtasks=[{"title": "x"}])
    )
    assert outcome.pending is None
    assert outcome.is_error is True


def test_other_users_task_cannot_be_decomposed(
    registry: ToolRegistry, db: Session, user: User
) -> None:
    other = User(name="他人", email="other-sub@example.com")
    db.add(other)
    db.flush()
    foreign = Task(user_id=other.id, title="他人のタスク")
    db.add(foreign)
    db.commit()

    outcome = registry.execute(
        call("create_subtasks", parent_task_id=foreign.id, subtasks=[{"title": "x"}])
    )
    assert outcome.is_error is True


def test_too_many_subtasks_are_rejected(registry: ToolRegistry) -> None:
    parent = make_parent(registry)
    outcome = registry.execute(
        call(
            "create_subtasks",
            parent_task_id=parent["id"],
            subtasks=[{"title": f"作業{i}"} for i in range(20)],
        )
    )
    assert outcome.is_error is True
    assert "引数が不正" in outcome.content["error"]


def test_deleting_parent_keeps_subtasks(registry: ToolRegistry, db: Session) -> None:
    """親を消しても小タスクは単独のタスクとして残る。"""
    parent = make_parent(registry)
    registry.execute(
        call(
            "create_subtasks",
            parent_task_id=parent["id"],
            subtasks=[{"title": "企業研究"}],
        ),
        confirmed=True,
    )

    registry.execute(call("delete_task", task_id=parent["id"]), confirmed=True)

    remaining = db.query(Task).all()
    assert [t.title for t in remaining] == ["企業研究"]
    assert remaining[0].parent_task_id is None
