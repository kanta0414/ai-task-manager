from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.calendar_event import CalendarEvent
from app.models.user import User


def _create(client: TestClient, **overrides) -> dict:
    payload = {
        "title": "企業研究",
        "start_at": "2026-09-21T14:00:00+09:00",
        "end_at": "2026-09-21T16:00:00+09:00",
    } | overrides
    res = client.post("/events", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def _create_task(client: TestClient, title: str = "ES作成") -> dict:
    res = client.post("/tasks", json={"title": title})
    assert res.status_code == 201
    return res.json()


def test_create_event(client: TestClient) -> None:
    body = _create(client, location="自宅", description="業界分析")
    assert body["title"] == "企業研究"
    assert body["start_at"] == "2026-09-21T14:00:00+09:00"
    assert body["end_at"] == "2026-09-21T16:00:00+09:00"
    assert body["location"] == "自宅"
    assert body["task_id"] is None


def test_create_event_linked_to_task(client: TestClient) -> None:
    task = _create_task(client)
    body = _create(client, task_id=task["id"])
    assert body["task_id"] == task["id"]


def test_create_event_rejects_end_before_start(client: TestClient) -> None:
    res = client.post(
        "/events",
        json={
            "title": "逆転",
            "start_at": "2026-09-21T16:00:00+09:00",
            "end_at": "2026-09-21T14:00:00+09:00",
        },
    )
    assert res.status_code == 422
    assert "終了時刻" in res.json()["detail"]


def test_create_event_rejects_too_long(client: TestClient) -> None:
    res = client.post(
        "/events",
        json={
            "title": "長すぎる",
            "start_at": "2026-09-21T00:00:00+09:00",
            "end_at": "2026-09-23T00:00:00+09:00",
        },
    )
    assert res.status_code == 422


def test_create_event_rejects_unknown_task(client: TestClient) -> None:
    res = client.post(
        "/events",
        json={
            "title": "不明なタスク紐付け",
            "start_at": "2026-09-21T14:00:00+09:00",
            "end_at": "2026-09-21T15:00:00+09:00",
            "task_id": 999999,
        },
    )
    assert res.status_code == 404


def test_get_and_missing_event(client: TestClient) -> None:
    created = _create(client)
    assert client.get(f"/events/{created['id']}").status_code == 200
    assert client.get("/events/999999").status_code == 404


def test_update_event_time(client: TestClient) -> None:
    """「明日の企業研究を18時からに変更」に相当する操作。"""
    created = _create(client)
    res = client.patch(
        f"/events/{created['id']}",
        json={
            "start_at": "2026-09-21T18:00:00+09:00",
            "end_at": "2026-09-21T20:00:00+09:00",
        },
    )
    assert res.status_code == 200
    assert res.json()["start_at"] == "2026-09-21T18:00:00+09:00"


def test_update_validates_against_existing_values(client: TestClient) -> None:
    """開始だけを終了より後ろへ動かす更新は拒否されること。"""
    created = _create(client)
    res = client.patch(
        f"/events/{created['id']}", json={"start_at": "2026-09-21T17:00:00+09:00"}
    )
    assert res.status_code == 422


def test_delete_event(client: TestClient) -> None:
    created = _create(client)
    assert client.delete(f"/events/{created['id']}").status_code == 204
    assert client.get(f"/events/{created['id']}").status_code == 404


def test_search_by_period_includes_overlapping(client: TestClient) -> None:
    """検索期間をまたぐ予定も取得できること（カレンダー表示で欠けないため）。"""
    _create(
        client,
        title="またぎ",
        start_at="2026-09-21T23:00:00+09:00",
        end_at="2026-09-22T01:00:00+09:00",
    )
    _create(client, title="範囲外", start_at="2026-09-25T10:00:00+09:00",
            end_at="2026-09-25T11:00:00+09:00")

    found = client.get(
        "/events",
        params={"from": "2026-09-22T00:00:00+09:00", "to": "2026-09-23T00:00:00+09:00"},
    ).json()
    assert [e["title"] for e in found] == ["またぎ"]


def test_search_sorted_by_start(client: TestClient) -> None:
    _create(client, title="後", start_at="2026-09-21T16:00:00+09:00",
            end_at="2026-09-21T17:00:00+09:00")
    _create(client, title="先", start_at="2026-09-21T09:00:00+09:00",
            end_at="2026-09-21T10:00:00+09:00")

    titles = [e["title"] for e in client.get("/events").json()]
    assert titles == ["先", "後"]


def test_search_by_task_id(client: TestClient) -> None:
    task = _create_task(client)
    _create(client, title="紐付きあり", task_id=task["id"])
    _create(client, title="紐付きなし", start_at="2026-09-22T14:00:00+09:00",
            end_at="2026-09-22T15:00:00+09:00")

    found = client.get("/events", params={"task_id": task["id"]}).json()
    assert [e["title"] for e in found] == ["紐付きあり"]


def test_deleting_task_keeps_event_and_clears_link(client: TestClient) -> None:
    """タスクを削除しても、そのために確保した予定は残り紐付けだけ外れる。"""
    task = _create_task(client)
    event = _create(client, task_id=task["id"])

    assert client.delete(f"/tasks/{task['id']}").status_code == 204

    body = client.get(f"/events/{event['id']}").json()
    assert body["task_id"] is None


def test_other_users_event_is_not_accessible(client: TestClient, db: Session) -> None:
    other = User(name="他人", email="other-event@example.com")
    db.add(other)
    db.flush()
    event = CalendarEvent(
        user_id=other.id,
        title="他人の予定",
        start_at="2026-09-21T14:00:00+09:00",
        end_at="2026-09-21T15:00:00+09:00",
    )
    db.add(event)
    db.commit()

    assert client.get(f"/events/{event.id}").status_code == 404
    assert client.delete(f"/events/{event.id}").status_code == 404
    assert client.get("/events").json() == []
