from __future__ import annotations

import json

import fakeredis
import pytest

import app.api.routes as api_routes
from app.core.config import settings


@pytest.fixture()
def fake_cache(monkeypatch):
    monkeypatch.setattr(api_routes.cache, "client", fakeredis.FakeStrictRedis())
    return api_routes.cache


@pytest.fixture()
def stub_predictor(monkeypatch):
    class StubPredictor:
        @staticmethod
        def cache_key(symbol, history):
            return f"prediction:test:{symbol}:{len(history)}"

        @staticmethod
        def predict(symbol, history):
            return {
                "symbol": symbol,
                "predicted_close": 101.25,
                "expected_change_pct": 1.25,
                "model": "stub-model-v1",
                "cached": False,
            }

    monkeypatch.setattr(api_routes, "predictor", StubPredictor())
    return api_routes.predictor


def history_payload(length=12):
    return [
        {"date": f"2025-02-{day:02d}", "close": 100.0 + day, "volume": 1000}
        for day in range(1, length + 1)
    ]


def test_health(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "stocksense-ai"}


def test_stock_history_ingests_and_returns_bars(client, auth_headers, monkeypatch):
    headers, _ = auth_headers
    monkeypatch.setattr(settings, "market_data_provider", "csv")

    response = client.get("/api/v1/stocks/DEMO/history?limit=50", headers=headers)

    assert response.status_code == 200
    bars = response.json()
    assert len(bars) == 50
    assert all(bar["symbol"] == "DEMO" for bar in bars)
    assert bars == sorted(bars, key=lambda bar: bar["date"])
    assert all(bar["close"] > 0 for bar in bars)


def test_stock_history_serves_stored_rows_without_provider(
    client, auth_headers, monkeypatch
):
    headers, _ = auth_headers
    monkeypatch.setattr(settings, "market_data_provider", "csv")
    first = client.get("/api/v1/stocks/DEMO/history?limit=50", headers=headers)
    assert first.status_code == 200

    def failing_provider():
        raise AssertionError("provider should not be called for fresh stored data")

    monkeypatch.setattr(api_routes, "get_market_data_provider", failing_provider)
    second = client.get("/api/v1/stocks/DEMO/history?limit=50", headers=headers)

    assert second.status_code == 200
    assert second.json() == first.json()


def test_stock_history_unknown_symbol_returns_404(client, auth_headers, monkeypatch):
    headers, _ = auth_headers
    monkeypatch.setattr(settings, "market_data_provider", "csv")

    response = client.get("/api/v1/stocks/NOPE/history", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SYMBOL_NOT_FOUND"


def test_stock_history_requires_auth(client):
    response = client.get("/api/v1/stocks/DEMO/history")

    assert response.status_code == 401


def test_predict_returns_prediction_and_persists(
    client, auth_headers, stub_predictor, fake_cache
):
    headers, _ = auth_headers

    response = client.post(
        "/api/v1/predict",
        headers=headers,
        json={"symbol": "DEMO", "history": history_payload()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "DEMO"
    assert body["predicted_close"] == 101.25
    assert body["cached"] is False
    assert body["persisted"] is True


def test_predict_serves_cached_result_on_repeat(
    client, auth_headers, stub_predictor, fake_cache
):
    headers, _ = auth_headers
    payload = {"symbol": "DEMO", "history": history_payload()}
    first = client.post("/api/v1/predict", headers=headers, json=payload)
    assert first.json()["cached"] is False

    second = client.post("/api/v1/predict", headers=headers, json=payload)

    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert second.json()["persisted"] is False


def test_predict_requires_auth(client, stub_predictor):
    response = client.post(
        "/api/v1/predict",
        json={"symbol": "DEMO", "history": history_payload()},
    )

    assert response.status_code == 401


def test_predict_validates_history_length(client, auth_headers, stub_predictor):
    headers, _ = auth_headers

    response = client.post(
        "/api/v1/predict",
        headers=headers,
        json={"symbol": "DEMO", "history": history_payload(length=5)},
    )

    assert response.status_code == 422


def test_prediction_history_lists_user_predictions(
    client, auth_headers, stub_predictor, fake_cache
):
    headers, _ = auth_headers
    client.post(
        "/api/v1/predict",
        headers=headers,
        json={"symbol": "DEMO", "history": history_payload()},
    )

    response = client.get("/api/v1/predictions?symbol=demo", headers=headers)

    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    assert records[0]["symbol"] == "DEMO"
    assert records[0]["model"] == "stub-model-v1"


def test_prediction_history_is_user_scoped(
    client, session_factory, auth_headers, stub_predictor, fake_cache
):
    from app.auth.service import AuthService

    headers, _ = auth_headers
    client.post(
        "/api/v1/predict",
        headers=headers,
        json={"symbol": "DEMO", "history": history_payload()},
    )

    session = session_factory()
    try:
        other = AuthService(session).register(
            email="other@example.com", password="an0ther-secret", full_name=None
        )
        other_headers = {"Authorization": f"Bearer {AuthService.issue_token(other)}"}
    finally:
        session.close()

    response = client.get("/api/v1/predictions", headers=other_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_prediction_evaluation_summary(client, auth_headers):
    headers, _ = auth_headers

    response = client.get("/api/v1/predictions/evaluation", headers=headers)

    assert response.status_code == 200


def test_metrics_without_artifact(client, auth_headers, monkeypatch, tmp_path):
    headers, _ = auth_headers
    monkeypatch.chdir(tmp_path)

    response = client.get("/api/v1/metrics", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "not_available"


def test_metrics_with_artifact(client, auth_headers, monkeypatch, tmp_path):
    headers, _ = auth_headers
    monkeypatch.chdir(tmp_path)
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "metrics.json").write_text(json.dumps({"mae": 1.23}), encoding="utf-8")

    response = client.get("/api/v1/metrics", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"mae": 1.23}


def test_rate_limit_returns_429_after_exhaustion(
    client, auth_headers, monkeypatch
):
    headers, _ = auth_headers
    monkeypatch.setattr(settings, "rate_limit_requests", 1)
    monkeypatch.setattr(
        api_routes.enforce_rate_limit.__globals__["rate_limiter"],
        "client",
        fakeredis.FakeStrictRedis(),
    )

    assert client.get("/api/v1/health", headers=headers).status_code == 200
    first = client.get("/api/v1/metrics", headers=headers)
    second = client.get("/api/v1/metrics", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "retry-after" in {key.lower() for key in second.headers}


@pytest.fixture()
def fresh_overview_cache(monkeypatch):
    monkeypatch.setattr(api_routes, "_overview_cache", {"payload": None, "expires": 0.0})


def test_public_market_overview_returns_configured_symbols(
    client, fresh_overview_cache, monkeypatch
):
    monkeypatch.setattr(settings, "market_data_provider", "csv")
    monkeypatch.setattr(settings, "market_data_symbols", "DEMO")

    response = client.get("/api/v1/public/market-overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_source"] == "Twelve Data daily bars"
    assert "not investment advice" in payload["disclaimer"]
    symbols = payload["symbols"]
    assert len(symbols) == 1
    assert symbols[0]["symbol"] == "DEMO"
    assert symbols[0]["close"] > 0
    assert symbols[0]["change_pct"] is not None


def test_public_market_overview_tolerates_missing_data(
    client, fresh_overview_cache, monkeypatch
):
    monkeypatch.setattr(settings, "market_data_provider", "csv")
    monkeypatch.setattr(settings, "market_data_symbols", "UNKNOWN")

    response = client.get("/api/v1/public/market-overview")

    assert response.status_code == 200
    assert response.json()["symbols"] == []
