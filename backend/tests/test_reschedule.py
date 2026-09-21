"""未完了タスクの再配置（Phase 14）のテスト。"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.llm.base import ToolCall
from app.models.calendar_event import CalendarEvent
from app.models.enums import TaskStatus
from app.models.task import Task
from app.models.user import User
from app.services.schedule_service import ScheduleService
from app.services.tool_registry import ToolRegistry

JST = ZoneInfo("Asia/Tokyo")


def at(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=JST)


@pytest.fixture
def service(db: Session) -> ScheduleService:
    return ScheduleService(db)


def add_work(
    db: Session,
    user: User,
    title: str,
    start: str,
    end: str,
    *,
    done: bool = False,
    due: str | None = None,
) -> tuple[Task, CalendarEvent]:
    task = Task(
        user_id=user.id,
        title=title,
        status=TaskStatus.DONE if done else TaskStatus.TODO,
        due_date=at(due) if due else None,
    )
    db.add(task)
    db.flush()
    event = CalendarEvent(
        user_id=user.id, title=title, start_at=at(start), end_at=at(end), task_id=task.id
    )
    db.add(event)
    db.flush()
    return task, event


def test_moves_unfinished_work_forward(
    service: ScheduleService, user: User, db: Session
) -> None:
    add_work(db, user, "ES作成", "2026-09-21 10:00", "2026-09-21 12:00")

    plan = service.reschedule_unfinished(
        user, now=at("2026-09-21 18:00"), period_end=at("2026-09-23 00:00")
    )

    assert len(plan.items) == 1
    item = plan.items[0]
    assert item.title == "ES作成"
    assert item.previous_start_at == at("2026-09-21 10:00")
    # 現在(18:00)以降の空きへ移る
    assert item.start_at >= at("2026-09-21 18:00")
    assert item.minutes == 120


def test_completed_work_is_left_alone(
    service: ScheduleService, user: User, db: Session
) -> None:
    add_work(db, user, "終わった作業", "2026-09-21 10:00", "2026-09-21 12:00", done=True)

    plan = service.reschedule_unfinished(
        user, now=at("2026-09-21 18:00"), period_end=at("2026-09-23 00:00")
    )
    assert plan.items == []


def test_future_work_is_not_touched(
    service: ScheduleService, user: User, db: Session
) -> None:
    add_work(db, user, "これからの作業", "2026-09-22 10:00", "2026-09-22 12:00")

    plan = service.reschedule_unfinished(
        user, now=at("2026-09-21 18:00"), period_end=at("2026-09-23 00:00")
    )
    assert plan.items == []


def test_events_without_task_are_ignored(
    service: ScheduleService, user: User, db: Session
) -> None:
    """タスクに紐づかない予定（面接など）は作業ではないので動かさない。"""
    db.add(
        CalendarEvent(
            user_id=user.id,
            title="面接",
            start_at=at("2026-09-21 10:00"),
            end_at=at("2026-09-21 11:00"),
        )
    )
    db.flush()

    plan = service.reschedule_unfinished(
        user, now=at("2026-09-21 18:00"), period_end=at("2026-09-23 00:00")
    )
    assert plan.items == []


def test_period_start_can_push_to_tomorrow(
    service: ScheduleService, user: User, db: Session
) -> None:
    """「明日以降に回して」を表現できる。"""
    add_work(db, user, "ES作成", "2026-09-21 10:00", "2026-09-21 12:00")

    plan = service.reschedule_unfinished(
        user,
        now=at("2026-09-21 18:00"),
        period_start=at("2026-09-22 00:00"),
        period_end=at("2026-09-23 00:00"),
    )

    assert plan.items[0].start_at >= at("2026-09-22 00:00")


def test_cannot_move_into_the_past(
    service: ScheduleService, user: User, db: Session
) -> None:
    add_work(db, user, "ES作成", "2026-09-21 10:00", "2026-09-21 12:00")

    plan = service.reschedule_unfinished(
        user,
        now=at("2026-09-21 18:00"),
        period_start=at("2026-09-20 00:00"),
        period_end=at("2026-09-23 00:00"),
    )

    assert all(item.start_at >= at("2026-09-21 18:00") for item in plan.items)


def test_reports_work_that_cannot_be_moved(
    service: ScheduleService, user: User, db: Session
) -> None:
    add_work(
        db, user, "間に合わない", "2026-09-21 10:00", "2026-09-21 12:00",
        due="2026-09-21 12:00",
    )

    plan = service.reschedule_unfinished(
        user, now=at("2026-09-21 18:00"), period_end=at("2026-09-23 00:00")
    )

    assert plan.items == []
    assert "期限" in plan.skipped[0].reason


def test_does_not_change_anything_by_planning(
    service: ScheduleService, user: User, db: Session
) -> None:
    _, event = add_work(db, user, "ES作成", "2026-09-21 10:00", "2026-09-21 12:00")

    service.reschedule_unfinished(
        user, now=at("2026-09-21 18:00"), period_end=at("2026-09-23 00:00")
    )

    db.refresh(event)
    assert event.start_at == at("2026-09-21 10:00")
    assert db.query(CalendarEvent).count() == 1


# ------------------------------------------------------------ Tool 経由


def past_and_future() -> tuple[str, str, str]:
    """「昨日の作業」と「これから2週間」を実時刻を基準に作る。

    Tool 経由では現在時刻がサーバー側で決まるため、テストも実時刻に合わせる。
    """
    from datetime import timedelta

    now = datetime.now(JST)
    yesterday = now - timedelta(days=1)
    return (
        f"{yesterday:%Y-%m-%d} 10:00",
        f"{yesterday:%Y-%m-%d} 12:00",
        f"{now + timedelta(days=14):%Y-%m-%dT00:00}",
    )


def test_reschedule_tool_asks_for_confirmation(db: Session, user: User) -> None:
    start, end, period_end = past_and_future()
    add_work(db, user, "ES作成", start, end)
    registry = ToolRegistry(db, user)

    outcome = registry.execute(
        ToolCall(
            id="c1",
            name="reschedule_unfinished",
            arguments={"period_end": period_end},
        )
    )

    assert outcome.pending is not None
    assert outcome.pending.tool == "apply_reschedule"
    assert "ES作成" in outcome.pending.description
    assert "→" in outcome.pending.description
    assert db.query(CalendarEvent).count() == 1


def test_confirmed_reschedule_replaces_the_event(db: Session, user: User) -> None:
    start, end, period_end = past_and_future()
    task, old_event = add_work(db, user, "ES作成", start, end)
    old_start = old_event.start_at
    registry = ToolRegistry(db, user)

    proposal = registry.execute(
        ToolCall(
            id="c1",
            name="reschedule_unfinished",
            arguments={"period_end": period_end},
        )
    )
    applied = registry.execute(
        ToolCall(
            id="c2",
            name="apply_reschedule",
            arguments=proposal.pending.arguments,
        ),
        confirmed=True,
    )

    assert applied.mutated is True
    assert applied.message == "1件の予定を組み直しました。"

    events = db.query(CalendarEvent).all()
    assert len(events) == 1  # 古い予定は消えて新しい予定に入れ替わる
    assert events[0].id != old_event.id
    assert events[0].task_id == task.id
    # 元の予定より後ろで、かつ15分単位に切り上げられている
    assert events[0].start_at > old_start
    assert events[0].start_at.minute % 15 == 0
    assert events[0].start_at.second == 0


def test_nothing_to_reschedule_does_not_ask(db: Session, user: User) -> None:
    _, _, period_end = past_and_future()
    registry = ToolRegistry(db, user)

    outcome = registry.execute(
        ToolCall(
            id="c1",
            name="reschedule_unfinished",
            arguments={"period_end": period_end},
        )
    )

    assert outcome.pending is None
    assert outcome.content["rescheduled"] == 0


def test_rounds_proposal_to_quarter_hours() -> None:
    """「17:09:48から」のような提案にしない。"""
    from app.services.schedule_service import round_up_to_quarter

    assert round_up_to_quarter(at("2026-09-21 17:09")) == at("2026-09-21 17:15")
    assert round_up_to_quarter(at("2026-09-21 17:15")) == at("2026-09-21 17:15")
    assert round_up_to_quarter(at("2026-09-21 17:50")) == at("2026-09-21 18:00")
    assert round_up_to_quarter(at("2026-09-21 23:55")) == at("2026-09-22 00:00")


def test_proposal_uses_the_users_timezone(db: Session, user: User) -> None:
    """返す日時は JST で表す。

    UTC のまま返すと、LLM が時差込みの数字をそのまま読み上げてしまう。
    """
    from datetime import timedelta

    now = datetime.now(JST)
    yesterday = now - timedelta(days=1)
    add_work(
        db,
        user,
        "ES作成",
        f"{yesterday:%Y-%m-%d} 10:00",
        f"{yesterday:%Y-%m-%d} 12:00",
    )

    service = ScheduleService(db)
    plan = service.reschedule_unfinished(
        user, now=datetime.now(ZoneInfo("UTC")), period_end=now + timedelta(days=7)
    )

    assert plan.items
    offsets = {item.start_at.utcoffset() for item in plan.items}
    assert offsets == {timedelta(hours=9)}
