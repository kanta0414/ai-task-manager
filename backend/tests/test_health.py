from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_health_db(client: TestClient) -> None:
    res = client.get("/health/db")
    assert res.status_code == 200
    assert res.json()["database"] == "connected"
