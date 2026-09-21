from fastapi.testclient import TestClient


def test_free_time_endpoint(client: TestClient) -> None:
    client.post(
        "/events",
        json={
            "title": "会議",
            "start_at": "2026-09-22T13:00:00+09:00",
            "end_at": "2026-09-22T15:00:00+09:00",
        },
    )

    body = client.get(
        "/schedule/free-time",
        params={
            "period_start": "2026-09-22T00:00:00+09:00",
            "period_end": "2026-09-23T00:00:00+09:00",
            "minutes_needed": 60,
        },
    ).json()

    assert body["count"] == 2
    assert body["rule"] == "9:00〜22:00 の範囲で探索"
    assert [s["minutes"] for s in body["slots"]] == [240, 420]


def test_free_time_endpoint_excludes_weekends(client: TestClient) -> None:
    body = client.get(
        "/schedule/free-time",
        params={
            "period_start": "2026-09-26T00:00:00+09:00",
            "period_end": "2026-09-28T00:00:00+09:00",
            "minutes_needed": 60,
            "exclude_weekends": True,
        },
    ).json()

    assert body["count"] == 0
    assert "土日を除く" in body["rule"]


def test_free_time_endpoint_rejects_inverted_period(client: TestClient) -> None:
    res = client.get(
        "/schedule/free-time",
        params={
            "period_start": "2026-09-23T00:00:00+09:00",
            "period_end": "2026-09-22T00:00:00+09:00",
            "minutes_needed": 60,
        },
    )
    assert res.status_code == 422


def test_plan_endpoint_previews_without_saving(client: TestClient) -> None:
    client.post("/tasks", json={"title": "ES作成", "estimated_minutes": 120})

    body = client.get(
        "/schedule/plan",
        params={
            "period_start": "2026-09-22T00:00:00+09:00",
            "period_end": "2026-09-23T00:00:00+09:00",
        },
    ).json()

    assert [i["title"] for i in body["items"]] == ["ES作成"]
    assert body["items"][0]["start_at"] == "2026-09-22T09:00:00+09:00"
    assert "1日あたり最大6時間" in body["rule"]
    # 提案しただけで予定は作られない
    assert client.get("/events").json() == []


def test_plan_endpoint_reports_skipped_tasks(client: TestClient) -> None:
    client.post("/tasks", json={"title": "見積もりなし"})

    body = client.get(
        "/schedule/plan",
        params={
            "period_start": "2026-09-22T00:00:00+09:00",
            "period_end": "2026-09-23T00:00:00+09:00",
        },
    ).json()

    assert body["items"] == []
    assert body["skipped"][0]["reason"] == "所要時間が未設定です"
