from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import CalendarEvent, Task, TaskPriority, TaskStatus, User


def _user(db) -> User:
    user = User(name="かんた", email=f"test{id(db)}@example.com")
    db.add(user)
    db.flush()
    return user


def test_task_defaults(db) -> None:
    """status / priority / created_at の既定値が入ること。"""
    user = _user(db)
    task = Task(user_id=user.id, title="ES作成")
    db.add(task)
    db.flush()
    db.refresh(task)

    assert task.status is TaskStatus.TODO
    assert task.priority is TaskPriority.MEDIUM
    assert task.created_at is not None
    assert task.completed_at is None


def test_task_fields_round_trip(db) -> None:
    """期限・所要時間・優先度が保存・取得できること。"""
    user = _user(db)
    due = datetime(2026, 9, 30, 23, 59, tzinfo=UTC)
    task = Task(
        user_id=user.id,
        title="SPIの勉強",
        description="非言語分野",
        priority=TaskPriority.HIGH,
        due_date=due,
        estimated_minutes=120,
    )
    db.add(task)
    db.flush()

    saved = db.get(Task, task.id)
    assert saved is not None
    assert saved.due_date == due
    assert saved.estimated_minutes == 120
    assert saved.priority is TaskPriority.HIGH
    # timezone-aware で戻ること（LLM の日時解釈のずれを防ぐ前提）
    assert saved.due_date.tzinfo is not None


def test_event_linked_to_task(db) -> None:
    """予定をタスクの作業時間として紐づけられること。"""
    user = _user(db)
    task = Task(user_id=user.id, title="企業研究")
    db.add(task)
    db.flush()

    start = datetime(2026, 9, 21, 14, 0, tzinfo=UTC)
    event = CalendarEvent(
        user_id=user.id,
        task_id=task.id,
        title="企業研究",
        start_at=start,
        end_at=start + timedelta(hours=2),
    )
    db.add(event)
    db.flush()

    assert event.task is task
    assert task.events == [event]


def test_event_requires_end_after_start(db) -> None:
    """終了が開始より前の予定は DB レベルで拒否されること。"""
    user = _user(db)
    start = datetime(2026, 9, 21, 16, 0, tzinfo=UTC)
    db.add(
        CalendarEvent(
            user_id=user.id,
            title="不正な予定",
            start_at=start,
            end_at=start - timedelta(hours=1),
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_estimated_minutes_must_be_positive(db) -> None:
    user = _user(db)
    db.add(Task(user_id=user.id, title="不正なタスク", estimated_minutes=0))
    with pytest.raises(IntegrityError):
        db.flush()


def test_email_is_unique(db) -> None:
    db.add(User(name="A", email="dup@example.com"))
    db.flush()
    db.add(User(name="B", email="dup@example.com"))
    with pytest.raises(IntegrityError):
        db.flush()
