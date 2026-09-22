from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metrics_without_generated_file() -> None:
    settings.api_key = "test-key"

    response = client.get(
        "/api/v1/metrics",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    assert "status" in response.json()
