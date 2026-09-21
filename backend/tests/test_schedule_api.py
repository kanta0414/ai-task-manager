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
