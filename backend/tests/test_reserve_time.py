"""タスクの作業時間を確保する機能のテスト。"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.calendar_event import CalendarEvent
from app.models.user import User

JST = ZoneInfo("Asia/Tokyo")


def next_weekday_at(hour: int, days_ahead: int = 1) -> datetime:
    """翌日以降の指定時刻（稼働時間内に収まるよう調整）。"""
    return (datetime.now(JST) + timedelta(days=days_ahead)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


def test_reserves_time_and_links_to_the_task(
    client: TestClient, db: Session, user: User
) -> None:
    due = next_weekday_at(22, days_ahead=3)
    task = client.post(
        "/tasks",
        json={
            "title": "ES作成",
            "estimated_minutes": 120,
            "due_date": f"{due:%Y-%m-%dT%H:%M:%S}+09:00",
        },
    ).json()

    body = client.post(f"/tasks/{task['id']}/schedule").json()

    assert body["task_id"] == task["id"]
    assert body["minutes"] == 120

    events = db.query(CalendarEvent).filter(CalendarEvent.task_id == task["id"]).all()
    assert len(events) == 1
    assert events[0].title == "ES作成"


def test_reserved_time_is_in_the_future(client: TestClient, user: User) -> None:
    due = next_weekday_at(22, days_ahead=3)
    task = client.post(
        "/tasks",
        json={
            "title": "ES作成",
            "estimated_minutes": 60,
            "due_date": f"{due:%Y-%m-%dT%H:%M:%S}+09:00",
        },
    ).json()

    body = client.post(f"/tasks/{task['id']}/schedule").json()

    assert datetime.fromisoformat(body["start_at"]) > datetime.now(UTC)


def test_requires_estimated_minutes(client: TestClient) -> None:
    """所要時間が無いと置けないので、理由を返して失敗させる。"""
    task = client.post("/tasks", json={"title": "見積もりなし"}).json()

    res = client.post(f"/tasks/{task['id']}/schedule")

    assert res.status_code == 422
    assert "所要時間" in res.json()["detail"]


def test_rejects_task_whose_due_date_has_passed(client: TestClient) -> None:
    past = datetime.now(JST) - timedelta(days=1)
    task = client.post(
        "/tasks",
        json={
            "title": "期限切れ",
            "estimated_minutes": 60,
            "due_date": f"{past:%Y-%m-%dT%H:%M:%S}+09:00",
        },
    ).json()

    res = client.post(f"/tasks/{task['id']}/schedule")

    assert res.status_code == 422
    assert "期限" in res.json()["detail"]


def test_unknown_task_returns_404(client: TestClient) -> None:
    assert client.post("/tasks/999999/schedule").status_code == 404


def test_avoids_existing_events(client: TestClient, db: Session, user: User) -> None:
    """既に埋まっている時間は避ける。"""
    day = next_weekday_at(9, days_ahead=1)
    db.add(
        CalendarEvent(
            user_id=user.id,
            title="終日ふさがり",
            start_at=day,
            end_at=day.replace(hour=21),
        )
    )
    db.commit()

    due = next_weekday_at(22, days_ahead=3)
    task = client.post(
        "/tasks",
        json={
            "title": "ES作成",
            "estimated_minutes": 120,
            "due_date": f"{due:%Y-%m-%dT%H:%M:%S}+09:00",
        },
    ).json()

    body = client.post(f"/tasks/{task['id']}/schedule").json()

    # ふさがっている日は避け、別の時間に置かれる
    start = datetime.fromisoformat(body["start_at"]).astimezone(JST)
    assert not (day <= start < day.replace(hour=21))
