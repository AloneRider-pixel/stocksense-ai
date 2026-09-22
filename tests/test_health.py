from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metrics_requires_authentication() -> None:
    response = client.get("/api/v1/metrics")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
