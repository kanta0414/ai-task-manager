"""通知と定期実行（Phase 15）のテスト。

ブローカーを動かさずに済むよう、処理の中身は Service に置いている。
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.calendar_event import CalendarEvent
from app.models.enums import NotificationKind, TaskStatus
from app.models.notification import Notification
from app.models.task import Task
from app.models.user import User
from app.services.notification_service import NotificationService

JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")


def at(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=JST)


@pytest.fixture
def service(db: Session) -> NotificationService:
    return NotificationService(db)


def add_event(db: Session, user: User, title: str, start: str, end: str, task: Task | None = None):
    event = CalendarEvent(
        user_id=user.id,
        title=title,
        start_at=at(start),
        end_at=at(end),
        task_id=task.id if task else None,
    )
    db.add(event)
    db.flush()
    return event


# ------------------------------------------------------------- リマインダー


def test_reminder_is_created_for_upcoming_event(
    service: NotificationService, user: User, db: Session
) -> None:
    add_event(db, user, "面接", "2026-09-22 14:00", "2026-09-22 15:00")

    created = service.send_due_reminders(at("2026-09-22 13:40"))

    assert created == 1
    notification = db.query(Notification).one()
    assert notification.kind is NotificationKind.REMINDER
    assert notification.title == "まもなく開始: 面接"
    assert "14:00" in notification.body


def test_reminder_is_not_created_too_early(
    service: NotificationService, user: User, db: Session
) -> None:
    add_event(db, user, "面接", "2026-09-22 14:00", "2026-09-22 15:00")

    assert service.send_due_reminders(at("2026-09-22 12:00")) == 0


def test_reminder_is_not_created_for_started_event(
    service: NotificationService, user: User, db: Session
) -> None:
    """既に始まっている予定は通知しない。"""
    add_event(db, user, "面接", "2026-09-22 14:00", "2026-09-22 15:00")

    assert service.send_due_reminders(at("2026-09-22 14:30")) == 0


def test_reminder_is_sent_only_once(
    service: NotificationService, user: User, db: Session
) -> None:
    """5分おきに実行されても通知は増えない。"""
    add_event(db, user, "面接", "2026-09-22 14:00", "2026-09-22 15:00")

    assert service.send_due_reminders(at("2026-09-22 13:40")) == 1
    assert service.send_due_reminders(at("2026-09-22 13:45")) == 0
    assert service.send_due_reminders(at("2026-09-22 13:50")) == 0
    assert db.query(Notification).count() == 1


def test_reminders_are_per_user(
    service: NotificationService, user: User, db: Session
) -> None:
    other = User(name="他人", email="other-notify@example.com")
    db.add(other)
    db.flush()
    add_event(db, user, "自分の面接", "2026-09-22 14:00", "2026-09-22 15:00")
    db.add(
        CalendarEvent(
            user_id=other.id,
            title="他人の面接",
            start_at=at("2026-09-22 14:00"),
            end_at=at("2026-09-22 15:00"),
        )
    )
    db.flush()

    service.send_due_reminders(at("2026-09-22 13:40"))

    mine = db.query(Notification).filter(Notification.user_id == user.id).all()
    assert [n.title for n in mine] == ["まもなく開始: 自分の面接"]


# ------------------------------------------------------------ 朝のまとめ


def test_daily_digest_lists_todays_events_and_due_tasks(
    service: NotificationService, user: User, db: Session
) -> None:
    add_event(db, user, "面接", "2026-09-22 14:00", "2026-09-22 15:00")
    db.add(
        Task(user_id=user.id, title="ES提出", due_date=at("2026-09-22 18:00"))
    )
    db.add(Task(user_id=user.id, title="来週の課題", due_date=at("2026-09-29 18:00")))
    db.flush()

    created = service.create_daily_digest(at("2026-09-22 07:00"))

    assert created == 1
    body = db.query(Notification).one().body
    assert "14:00 面接" in body
    assert "ES提出" in body
    assert "来週の課題" not in body


def test_daily_digest_is_skipped_when_nothing_scheduled(
    service: NotificationService, user: User
) -> None:
    assert service.create_daily_digest(at("2026-09-22 07:00")) == 0


def test_daily_digest_is_created_once_per_day(
    service: NotificationService, user: User, db: Session
) -> None:
    add_event(db, user, "面接", "2026-09-22 14:00", "2026-09-22 15:00")

    assert service.create_daily_digest(at("2026-09-22 07:00")) == 1
    assert service.create_daily_digest(at("2026-09-22 07:05")) == 0
    # 翌日は別の通知
    add_event(db, user, "面談", "2026-09-23 10:00", "2026-09-23 11:00")
    assert service.create_daily_digest(at("2026-09-23 07:00")) == 1


# --------------------------------------------------------- 夜のやり残し確認


def test_unfinished_work_is_reported(
    service: NotificationService, user: User, db: Session
) -> None:
    task = Task(user_id=user.id, title="ES作成", status=TaskStatus.TODO)
    db.add(task)
    db.flush()
    add_event(db, user, "ES作成", "2026-09-22 10:00", "2026-09-22 12:00", task)

    created = service.flag_unfinished_work(at("2026-09-22 23:00"))

    assert created == 1
    notification = db.query(Notification).one()
    assert notification.kind is NotificationKind.UNFINISHED
    assert "1件" in notification.title
    assert "ES作成" in notification.body


def test_finished_work_is_not_reported(
    service: NotificationService, user: User, db: Session
) -> None:
    task = Task(user_id=user.id, title="ES作成", status=TaskStatus.DONE)
    db.add(task)
    db.flush()
    add_event(db, user, "ES作成", "2026-09-22 10:00", "2026-09-22 12:00", task)

    assert service.flag_unfinished_work(at("2026-09-22 23:00")) == 0


def test_yesterdays_leftovers_are_not_repeated(
    service: NotificationService, user: User, db: Session
) -> None:
    """その日のぶんだけを対象にする（古いやり残しを毎晩蒸し返さない）。"""
    task = Task(user_id=user.id, title="古い作業", status=TaskStatus.TODO)
    db.add(task)
    db.flush()
    add_event(db, user, "古い作業", "2026-09-20 10:00", "2026-09-20 12:00", task)

    assert service.flag_unfinished_work(at("2026-09-22 23:00")) == 0


# ------------------------------------------------------------------- API


def test_notifications_api(client: TestClient, db: Session, user: User) -> None:
    add_event(db, user, "面接", "2026-09-22 14:00", "2026-09-22 15:00")
    NotificationService(db).send_due_reminders(at("2026-09-22 13:40"))

    listed = client.get("/notifications").json()
    assert len(listed) == 1
    assert listed[0]["read_at"] is None

    read = client.post(f"/notifications/{listed[0]['id']}/read").json()
    assert read["read_at"] is not None

    assert client.get("/notifications", params={"unread_only": True}).json() == []


def test_other_users_notification_cannot_be_read(
    client: TestClient, db: Session
) -> None:
    other = User(name="他人", email="other-read@example.com")
    db.add(other)
    db.flush()
    notification = Notification(
        user_id=other.id,
        kind=NotificationKind.REMINDER,
        title="他人の通知",
        dedup_key="x",
    )
    db.add(notification)
    db.commit()

    assert client.get("/notifications").json() == []
    assert client.post(f"/notifications/{notification.id}/read").status_code == 404
