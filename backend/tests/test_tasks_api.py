from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import User


def _create(client: TestClient, **overrides) -> dict:
    payload = {"title": "ES作成"} | overrides
    res = client.post("/tasks", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def test_create_task_minimal(client: TestClient) -> None:
    body = _create(client)
    assert body["title"] == "ES作成"
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["completed_at"] is None
    assert body["id"] > 0


def test_create_task_full(client: TestClient) -> None:
    body = _create(
        client,
        title="SPIの勉強",
        description="非言語分野",
        priority="high",
        due_date="2026-09-30T23:59:00+09:00",
        estimated_minutes=120,
    )
    assert body["priority"] == "high"
    assert body["estimated_minutes"] == 120
    assert body["due_date"].startswith("2026-09-30T")


def test_create_task_rejects_empty_title(client: TestClient) -> None:
    assert client.post("/tasks", json={"title": ""}).status_code == 422


def test_create_task_rejects_invalid_estimated_minutes(client: TestClient) -> None:
    res = client.post("/tasks", json={"title": "x", "estimated_minutes": 0})
    assert res.status_code == 422


def test_naive_due_date_is_interpreted_as_app_timezone(client: TestClient) -> None:
    """タイムゾーン無しの日時は Asia/Tokyo として解釈される。"""
    body = _create(client, due_date="2026-09-30T23:59:00")
    assert body["due_date"] == "2026-09-30T23:59:00+09:00"


def test_get_task(client: TestClient) -> None:
    created = _create(client)
    res = client.get(f"/tasks/{created['id']}")
    assert res.status_code == 200
    assert res.json()["id"] == created["id"]


def test_get_missing_task_returns_404(client: TestClient) -> None:
    res = client.get("/tasks/999999")
    assert res.status_code == 404
    assert "見つかりません" in res.json()["detail"]


def test_update_task(client: TestClient) -> None:
    created = _create(client)
    res = client.patch(
        f"/tasks/{created['id']}",
        json={"title": "ES作成（修正）", "due_date": "2026-10-05T18:00:00+09:00"},
    )
    assert res.status_code == 200
    assert res.json()["title"] == "ES作成（修正）"
    assert res.json()["due_date"].startswith("2026-10-05T")
    # 未指定の項目は変更されない
    assert res.json()["priority"] == "medium"


def test_update_can_clear_due_date(client: TestClient) -> None:
    created = _create(client, due_date="2026-09-30T23:59:00+09:00")
    res = client.patch(f"/tasks/{created['id']}", json={"due_date": None})
    assert res.json()["due_date"] is None


def test_complete_and_reopen(client: TestClient) -> None:
    created = _create(client)

    done = client.post(f"/tasks/{created['id']}/complete").json()
    assert done["status"] == "done"
    assert done["completed_at"] is not None

    reopened = client.post(f"/tasks/{created['id']}/reopen").json()
    assert reopened["status"] == "todo"
    assert reopened["completed_at"] is None


def test_status_update_syncs_completed_at(client: TestClient) -> None:
    """PATCH で status を done にしても completed_at が整合すること。"""
    created = _create(client)
    done = client.patch(f"/tasks/{created['id']}", json={"status": "done"}).json()
    assert done["completed_at"] is not None

    back = client.patch(f"/tasks/{created['id']}", json={"status": "in_progress"}).json()
    assert back["completed_at"] is None


def test_delete_task(client: TestClient) -> None:
    created = _create(client)
    assert client.delete(f"/tasks/{created['id']}").status_code == 204
    assert client.get(f"/tasks/{created['id']}").status_code == 404


def test_delete_missing_task_returns_404(client: TestClient) -> None:
    assert client.delete("/tasks/999999").status_code == 404


def test_search_filters_by_status(client: TestClient) -> None:
    _create(client, title="未完了")
    done = _create(client, title="完了済み")
    client.post(f"/tasks/{done['id']}/complete")

    titles = [t["title"] for t in client.get("/tasks", params={"status": "todo"}).json()]
    assert titles == ["未完了"]


def test_search_filters_by_keyword(client: TestClient) -> None:
    _create(client, title="企業研究", description="業界分析")
    _create(client, title="SPI")

    found = client.get("/tasks", params={"keyword": "業界"}).json()
    assert [t["title"] for t in found] == ["企業研究"]


def test_search_filters_by_due_range(client: TestClient) -> None:
    _create(client, title="今週", due_date="2026-09-22T12:00:00+09:00")
    _create(client, title="来月", due_date="2026-10-22T12:00:00+09:00")

    found = client.get(
        "/tasks",
        params={
            "due_from": "2026-09-21T00:00:00+09:00",
            "due_to": "2026-09-27T23:59:59+09:00",
        },
    ).json()
    assert [t["title"] for t in found] == ["今週"]


def test_search_sorts_by_due_date_with_nulls_last(client: TestClient) -> None:
    _create(client, title="期限なし")
    _create(client, title="後", due_date="2026-10-01T10:00:00+09:00")
    _create(client, title="先", due_date="2026-09-25T10:00:00+09:00")

    titles = [t["title"] for t in client.get("/tasks").json()]
    assert titles == ["先", "後", "期限なし"]


def test_search_sorts_by_priority_desc(client: TestClient) -> None:
    _create(client, title="低", priority="low")
    _create(client, title="高", priority="high")
    _create(client, title="中", priority="medium")

    titles = [
        t["title"]
        for t in client.get(
            "/tasks", params={"sort_by": "priority", "order": "desc"}
        ).json()
    ]
    assert titles == ["高", "中", "低"]


def test_search_pagination(client: TestClient) -> None:
    for i in range(3):
        _create(client, title=f"task{i}", due_date=f"2026-09-2{i + 1}T10:00:00+09:00")

    page = client.get("/tasks", params={"limit": 2, "offset": 1}).json()
    assert [t["title"] for t in page] == ["task1", "task2"]


def test_other_users_task_is_not_accessible(client: TestClient, db: Session) -> None:
    """他ユーザーのタスクは 404（存在を推測させない）。"""
    other = User(name="他人", email="other@example.com")
    db.add(other)
    db.flush()
    task = Task(user_id=other.id, title="他人のタスク")
    db.add(task)
    db.commit()

    assert client.get(f"/tasks/{task.id}").status_code == 404
    assert client.patch(f"/tasks/{task.id}", json={"title": "x"}).status_code == 404
    assert client.delete(f"/tasks/{task.id}").status_code == 404
    assert client.get("/tasks").json() == []


def test_completed_at_is_recent(client: TestClient) -> None:
    created = _create(client)
    done = client.post(f"/tasks/{created['id']}/complete").json()
    completed_at = datetime.fromisoformat(done["completed_at"])
    assert datetime.now(UTC) - completed_at < timedelta(minutes=1)
