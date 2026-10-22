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

    def failing_provider(symbol):
        raise AssertionError("provider should not be called for fresh stored data")

    monkeypatch.setattr(api_routes, "get_provider_for_symbol", failing_provider)
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
    monkeypatch.setattr(settings, "nse_symbols", "")

    response = client.get("/api/v1/public/market-overview")

    assert response.status_code == 200
    payload = response.json()
    assert "Twelve Data" in payload["data_source"] and "Yahoo Finance" in payload["data_source"]
    assert "Not investment advice" in payload["disclaimer"]
    assert "SEBI" in payload["disclaimer"]
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
    monkeypatch.setattr(settings, "nse_symbols", "")

    response = client.get("/api/v1/public/market-overview")

    assert response.status_code == 200
    assert response.json()["symbols"] == []


@pytest.fixture()
def fresh_accuracy_cache(monkeypatch):
    monkeypatch.setattr(
        api_routes,
        "_accuracy_cache",
        {"payload": None, "key": None, "expires": 0.0},
    )


def test_public_accuracy_reports_reconciled_predictions(
    client, fresh_accuracy_cache, session_factory
):
    from datetime import date

    from app.db.repository import MarketDataRepository, PredictionRepository

    session = session_factory()
    market = MarketDataRepository(session)
    market.upsert_many(
        [
            {
                "date": date(2026, 1, 2),
                "symbol": "DEMO",
                "open": 100,
                "high": 102,
                "low": 99,
                "close": 100,
                "volume": 1000000,
                "source_provider": "test",
            },
            {
                "date": date(2026, 1, 5),
                "symbol": "DEMO",
                "open": 100,
                "high": 104,
                "low": 99,
                "close": 103,
                "volume": 1200000,
                "source_provider": "test",
            },
        ]
    )
    predictions = PredictionRepository(session)
    predictions.add(
        user_id=None,
        symbol="DEMO",
        prediction_date=date(2026, 1, 2),
        predicted_close=104,
        expected_change_pct=4,
        model="test-model",
        cached=False,
    )
    assert predictions.evaluate_pending("DEMO") == 1
    session.close()

    response = client.get("/api/v1/public/accuracy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "persistence" in payload["methodology"]
    assert "Not investment advice" in payload["disclaimer"]
    assert "SEBI" in payload["disclaimer"]
    assert "benchmark_index" in payload
    assert payload["overall"]["evaluated_predictions"] == 1
    assert payload["overall"]["mae"] == 1
    assert payload["overall"]["baseline_mae"] == 3
    assert payload["symbols"][0]["symbol"] == "DEMO"
    assert payload["symbols"][0]["directional_accuracy_pct"] == 100


def test_public_accuracy_empty_state_is_explicit(
    client, fresh_accuracy_cache
):
    response = client.get("/api/v1/public/accuracy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "insufficient_data"
    assert payload["overall"]["evaluated_predictions"] == 0
    assert payload["symbols"] == []


@pytest.fixture()
def fresh_latest_cache(monkeypatch):
    monkeypatch.setattr(
        api_routes,
        "_latest_predictions_cache",
        {"payload": None, "expires": 0.0},
    )


def test_public_latest_predictions_returns_most_recent_per_symbol(
    client, fresh_latest_cache, session_factory
):
    from datetime import date

    from app.db.repository import PredictionRepository

    session = session_factory()
    predictions = PredictionRepository(session)
    predictions.add(
        user_id=None,
        symbol="DEMO",
        prediction_date=date(2026, 1, 2),
        predicted_close=104,
        expected_change_pct=4,
        model="test-model",
        cached=False,
    )
    predictions.add(
        user_id=None,
        symbol="DEMO",
        prediction_date=date(2026, 1, 3),
        predicted_close=105,
        expected_change_pct=1,
        model="test-model",
        cached=False,
    )
    session.close()

    response = client.get("/api/v1/public/predictions/latest")

    assert response.status_code == 200
    payload = response.json()
    assert "Not investment advice" in payload["disclaimer"]
    assert "SEBI" in payload["disclaimer"]
    assert len(payload["predictions"]) == 1
    latest = payload["predictions"][0]
    assert latest["symbol"] == "DEMO"
    assert latest["prediction_date"] == "2026-01-03"
    assert latest["predicted_close"] == 105


def test_backtest_route_requires_enough_history(client, auth_headers):
    headers, _ = auth_headers
    response = client.get("/api/v1/backtest/DEMO", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INSUFFICIENT_HISTORY"


def test_backtest_route_returns_strategy_vs_buy_hold(
    client, auth_headers, session_factory
):
    import random
    from datetime import date, timedelta

    from app.db.repository import MarketDataRepository

    session = session_factory()
    market = MarketDataRepository(session)
    rng = random.Random(7)
    close = 100.0
    bars = []
    day = date(2025, 1, 6)
    for i in range(160):
        close += rng.uniform(-1.5, 1.8)
        bars.append(
            {
                "date": day,
                "symbol": "DEMO",
                "open": close - 0.5,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1_000_000 + i,
                "source_provider": "test",
            }
        )
        day += timedelta(days=1)
    market.upsert_many(bars)
    session.close()

    headers, _ = auth_headers
    response = client.get("/api/v1/backtest/DEMO", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "DEMO"
    assert "Not investment advice" in payload["disclaimer"]
    assert "SEBI" in payload["disclaimer"]
    metrics = payload["metrics"]
    assert metrics["periods"] == len(payload["equity_curve"]) > 0
    assert metrics["strategy_max_drawdown_pct"] <= 0
    first = payload["equity_curve"][0]
    assert set(first) == {"date", "strategy", "buy_hold"}


def test_prediction_evaluation_includes_persistence_baseline(
    client, auth_headers, session_factory
):
    from datetime import date

    from app.db.repository import MarketDataRepository, PredictionRepository

    headers, user = auth_headers
    session = session_factory()
    market = MarketDataRepository(session)
    market.upsert_many(
        [
            {
                "date": date(2026, 1, 2),
                "symbol": "DEMO",
                "open": 100,
                "high": 102,
                "low": 99,
                "close": 100,
                "volume": 1000000,
                "source_provider": "test",
            },
            {
                "date": date(2026, 1, 5),
                "symbol": "DEMO",
                "open": 100,
                "high": 104,
                "low": 99,
                "close": 103,
                "volume": 1200000,
                "source_provider": "test",
            },
        ]
    )
    predictions = PredictionRepository(session)
    predictions.add(
        user_id=user.id,
        symbol="DEMO",
        prediction_date=date(2026, 1, 2),
        predicted_close=102,
        expected_change_pct=2,
        model="test-model",
        cached=False,
    )
    assert predictions.evaluate_pending("DEMO") == 1
    session.close()

    response = client.get("/api/v1/predictions/evaluation", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluated_predictions"] == 1
    # Model predicted 102 vs actual 103 -> MAE 1; baseline was 100 -> MAE 3.
    assert payload["mae"] == 1
    assert payload["baseline_mae"] == 3
    # Baseline always-up: actual 103 >= 100 -> 100% baseline hit rate.
    assert payload["baseline_directional_accuracy_pct"] == 100
    assert payload["improvement_vs_persistence_pct"] == round((3 - 1) / 3 * 100, 4)


def test_prediction_history_includes_baseline_close(
    client, auth_headers, session_factory, stub_predictor, fake_cache
):
    from datetime import date

    from app.db.repository import MarketDataRepository

    headers, _ = auth_headers
    session = session_factory()
    MarketDataRepository(session).upsert_many(
        [
            {
                "date": date(2026, 1, 2),
                "symbol": "DEMO",
                "open": 100,
                "high": 102,
                "low": 99,
                "close": 100,
                "volume": 1000000,
                "source_provider": "test",
            }
        ]
    )
    session.close()

    client.post(
        "/api/v1/predict",
        headers=headers,
        json={"symbol": "DEMO", "history": history_payload()},
    )

    response = client.get("/api/v1/predictions", headers=headers)

    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    assert "baseline_close" in records[0]
