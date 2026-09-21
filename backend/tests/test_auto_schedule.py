"""自動スケジューリング（Phase 12）のテスト。

配置の規則は LLM ではなく ScheduleService が持つため、ここで固める。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.models.calendar_event import CalendarEvent
from app.models.enums import TaskPriority
from app.models.task import Task
from app.models.user import User
from app.services.schedule_service import ScheduleConstraints, ScheduleService

JST = ZoneInfo("Asia/Tokyo")


def at(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=JST)


@pytest.fixture
def service(db: Session) -> ScheduleService:
    return ScheduleService(db)


def add_task(
    db: Session,
    user: User,
    title: str,
    minutes: int | None = 60,
    due: str | None = None,
    priority: TaskPriority = TaskPriority.MEDIUM,
) -> Task:
    task = Task(
        user_id=user.id,
        title=title,
        estimated_minutes=minutes,
        due_date=at(due) if due else None,
        priority=priority,
    )
    db.add(task)
    db.flush()
    return task


def plan(service: ScheduleService, user: User, start: str, end: str, **kw):
    return service.generate_schedule(
        user, period_start=at(start), period_end=at(end), **kw
    )


def placed(result) -> list[str]:
    return [
        f"{i.title} {i.start_at.astimezone(JST):%m/%d %H:%M}-{i.end_at.astimezone(JST):%H:%M}"
        for i in result.items
    ]


def test_places_tasks_into_free_time(
    service: ScheduleService, user: User, db: Session
) -> None:
    add_task(db, user, "ES作成", minutes=120)

    result = plan(service, user, "2026-09-22 00:00", "2026-09-23 00:00")

    assert placed(result) == ["ES作成 09/22 09:00-11:00"]
    assert result.skipped == []


def test_avoids_existing_events(
    service: ScheduleService, user: User, db: Session
) -> None:
    db.add(
        CalendarEvent(
            user_id=user.id,
            title="面接",
            start_at=at("2026-09-22 09:00"),
            end_at=at("2026-09-22 11:00"),
        )
    )
    add_task(db, user, "ES作成", minutes=120)

    result = plan(service, user, "2026-09-22 00:00", "2026-09-23 00:00")
    assert placed(result) == ["ES作成 09/22 11:00-13:00"]


def test_orders_by_due_date_then_priority(
    service: ScheduleService, user: User, db: Session
) -> None:
    """期限が近い順 → 優先度が高い順（開発手順15）。"""
    add_task(db, user, "期限なし低", minutes=60, priority=TaskPriority.LOW)
    add_task(db, user, "後の期限", minutes=60, due="2026-09-30 23:59")
    add_task(db, user, "近い期限低", minutes=60, due="2026-09-23 23:59", priority=TaskPriority.LOW)
    add_task(db, user, "近い期限高", minutes=60, due="2026-09-23 12:00", priority=TaskPriority.HIGH)

    result = plan(service, user, "2026-09-22 00:00", "2026-09-23 00:00")

    assert [i.title for i in result.items] == [
        "近い期限高",
        "近い期限低",
        "後の期限",
        "期限なし低",
    ]


def test_same_due_date_prefers_higher_priority(
    service: ScheduleService, user: User, db: Session
) -> None:
    add_task(db, user, "低", minutes=60, due="2026-09-25 23:59", priority=TaskPriority.LOW)
    add_task(db, user, "高", minutes=60, due="2026-09-25 23:59", priority=TaskPriority.HIGH)

    result = plan(service, user, "2026-09-22 00:00", "2026-09-23 00:00")
    assert [i.title for i in result.items] == ["高", "低"]


def test_respects_daily_limit(
    service: ScheduleService, user: User, db: Session
) -> None:
    """1日に入れる作業時間の上限を超えない（既定6時間）。"""
    for i in range(5):
        add_task(db, user, f"タスク{i}", minutes=120)

    result = plan(service, user, "2026-09-22 00:00", "2026-09-23 00:00")

    assert len(result.items) == 3  # 2時間 × 3 = 6時間が上限
    assert sum(i.minutes for i in result.items) == 360
    assert all("上限" in s.reason for s in result.skipped)


def test_spreads_over_multiple_days(
    service: ScheduleService, user: User, db: Session
) -> None:
    for i in range(5):
        add_task(db, user, f"タスク{i}", minutes=120)

    result = plan(service, user, "2026-09-22 00:00", "2026-09-24 00:00")

    days = {i.start_at.astimezone(JST).date().day for i in result.items}
    assert days == {22, 23}
    assert len(result.items) == 5
    assert result.skipped == []


def test_skips_task_without_estimate(
    service: ScheduleService, user: User, db: Session
) -> None:
    add_task(db, user, "見積もりなし", minutes=None)

    result = plan(service, user, "2026-09-22 00:00", "2026-09-23 00:00")

    assert result.items == []
    assert result.skipped[0].reason == "所要時間が未設定です"


def test_skips_task_that_cannot_meet_its_due_date(
    service: ScheduleService, user: User, db: Session
) -> None:
    add_task(db, user, "間に合わない", minutes=120, due="2026-09-22 10:00")

    result = plan(service, user, "2026-09-22 00:00", "2026-09-23 00:00")

    assert result.items == []
    assert "期限までに" in result.skipped[0].reason


def test_skips_task_longer_than_any_gap(
    service: ScheduleService, user: User, db: Session
) -> None:
    db.add(
        CalendarEvent(
            user_id=user.id,
            title="ふさがっている",
            start_at=at("2026-09-22 10:00"),
            end_at=at("2026-09-22 21:00"),
        )
    )
    add_task(db, user, "長い作業", minutes=180)

    result = plan(service, user, "2026-09-22 00:00", "2026-09-23 00:00")

    assert result.items == []
    assert "空き時間" in result.skipped[0].reason


def test_only_targets_specified_tasks(
    service: ScheduleService, user: User, db: Session
) -> None:
    target = add_task(db, user, "対象", minutes=60)
    add_task(db, user, "対象外", minutes=60)

    result = plan(
        service, user, "2026-09-22 00:00", "2026-09-23 00:00", task_ids=[target.id]
    )

    assert [i.title for i in result.items] == ["対象"]


def test_completed_tasks_are_not_scheduled(
    service: ScheduleService, user: User, db: Session
) -> None:
    from app.models.enums import TaskStatus

    task = add_task(db, user, "完了済み", minutes=60)
    task.status = TaskStatus.DONE
    db.flush()

    result = plan(service, user, "2026-09-22 00:00", "2026-09-23 00:00")
    assert result.items == []


def test_plan_reports_the_applied_rule(service: ScheduleService, user: User) -> None:
    result = plan(
        service,
        user,
        "2026-09-22 00:00",
        "2026-09-23 00:00",
        constraints=ScheduleConstraints(exclude_weekends=True),
    )
    assert "土日を除く" in result.rule
    assert "1日あたり最大6時間" in result.rule


def test_nothing_is_saved_by_generating_a_plan(
    service: ScheduleService, user: User, db: Session
) -> None:
    """提案の段階では予定を作らない（要件定義書 19）。"""
    add_task(db, user, "ES作成", minutes=120)

    plan(service, user, "2026-09-22 00:00", "2026-09-23 00:00")

    assert db.query(CalendarEvent).count() == 0


# ----------------------------------------------- Tool 経由（提案 → 承認 → 登録）


def registry_for(db: Session, user: User):
    from app.services.tool_registry import ToolRegistry

    return ToolRegistry(db, user)


def tool_call(name: str, **arguments):
    from app.llm.base import ToolCall

    return ToolCall(id="c1", name=name, arguments=arguments)


def test_generate_schedule_asks_for_confirmation(
    db: Session, user: User
) -> None:
    add_task(db, user, "ES作成", minutes=120)
    registry = registry_for(db, user)

    outcome = registry.execute(
        tool_call(
            "generate_schedule",
            period_start="2026-09-22T00:00",
            period_end="2026-09-23T00:00",
        )
    )

    assert outcome.pending is not None
    assert outcome.pending.tool == "apply_schedule"
    assert "ES作成" in outcome.pending.description
    assert "09:00〜11:00" in outcome.pending.description
    # 提案しただけでは登録されない
    assert outcome.mutated is False
    assert db.query(CalendarEvent).count() == 0


def test_confirmed_schedule_creates_events(db: Session, user: User) -> None:
    task = add_task(db, user, "ES作成", minutes=120)
    registry = registry_for(db, user)

    proposal = registry.execute(
        tool_call(
            "generate_schedule",
            period_start="2026-09-22T00:00",
            period_end="2026-09-23T00:00",
        )
    )
    applied = registry.execute(
        tool_call("apply_schedule", **proposal.pending.arguments), confirmed=True
    )

    assert applied.mutated is True
    assert applied.content["created"] == 1

    events = db.query(CalendarEvent).all()
    assert len(events) == 1
    assert events[0].title == "ES作成"
    # 作業時間としてタスクに紐づく
    assert events[0].task_id == task.id


def test_plan_without_candidates_does_not_ask_for_confirmation(
    db: Session, user: User
) -> None:
    add_task(db, user, "見積もりなし", minutes=None)
    registry = registry_for(db, user)

    outcome = registry.execute(
        tool_call(
            "generate_schedule",
            period_start="2026-09-22T00:00",
            period_end="2026-09-23T00:00",
        )
    )

    assert outcome.pending is None
    assert outcome.content["scheduled"] == 0
    assert outcome.content["skipped"][0]["reason"] == "所要時間が未設定です"


def test_apply_schedule_rejects_other_users_task(
    db: Session, user: User
) -> None:
    other = User(name="他人", email="other-apply@example.com")
    db.add(other)
    db.flush()
    foreign = Task(user_id=other.id, title="他人のタスク", estimated_minutes=60)
    db.add(foreign)
    db.flush()

    registry = registry_for(db, user)
    outcome = registry.execute(
        tool_call(
            "apply_schedule",
            items=[
                {
                    "task_id": foreign.id,
                    "start_at": "2026-09-22T09:00",
                    "end_at": "2026-09-22T10:00",
                }
            ],
        ),
        confirmed=True,
    )

    assert outcome.is_error is True
    assert db.query(CalendarEvent).count() == 0


def test_confirmed_schedule_reply_is_concise(client, db: Session, user: User) -> None:
    """承認後の返答は件数だけを短く返す（案の全文を繰り返さない）。"""
    from app.api.deps import ConversationServiceDep, get_chat_service
    from app.main import app
    from app.services.chat_service import ChatService
    from tests.fakes import FakeProvider

    def factory(conversations: ConversationServiceDep) -> ChatService:
        return ChatService(FakeProvider(), conversations)

    app.dependency_overrides[get_chat_service] = factory
    try:
        task = client.post(
            "/tasks", json={"title": "ES作成", "estimated_minutes": 120}
        ).json()
        conversation_id = client.post("/chat", json={"message": "準備"}).json()[
            "conversation_id"
        ]

        body = client.post(
            "/chat/confirm",
            json={
                "conversation_id": conversation_id,
                "tool": "apply_schedule",
                "arguments": {
                    "items": [
                        {
                            "task_id": task["id"],
                            "start_at": "2026-09-22T09:00",
                            "end_at": "2026-09-22T11:00",
                        }
                    ]
                },
                "description": "以下の予定を登録します。\n\n9/22(火)\n  09:00〜11:00 ES作成",
            },
        ).json()

        assert body["reply"] == "1件の予定を登録しました。"
        assert body["mutated"] is True
        assert len(client.get("/events").json()) == 1
    finally:
        app.dependency_overrides.pop(get_chat_service, None)
