from __future__ import annotations

import pytest

from app.core.config import settings


@pytest.fixture()
def demo_session(session_factory, monkeypatch):
    import app.demo as demo

    monkeypatch.setattr(demo, "get_session", session_factory)
    monkeypatch.setattr(demo, "init_db", lambda: None)
    monkeypatch.setattr(settings, "demo_mode", True)
    return session_factory


def test_seed_demo_environment_is_idempotent(demo_session, monkeypatch, tmp_path):
    import app.demo as demo

    monkeypatch.setattr(demo, "_ensure_sample_model", lambda: None)
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "market_data_provider", "csv")

    demo.seed_demo_environment()
    demo.seed_demo_environment()

    session = demo_session()
    try:
        from app.auth.service import AuthService
        from app.db.repository import MarketDataRepository

        user = AuthService(session).authenticate(
            email=settings.demo_user_email,
            password=settings.demo_user_password,
        )
        assert user.is_active is True

        bars = MarketDataRepository(session).list_history("DEMO", limit=5000)
        assert len(bars) > 80
    finally:
        session.close()


def test_seed_demo_environment_skips_production(demo_session, monkeypatch):
    import app.demo as demo

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(
        demo,
        "init_db",
        lambda: pytest.fail("init_db must not run in production"),
    )

    demo.seed_demo_environment()


def test_seed_demo_environment_skips_sample_data_with_live_provider(
    demo_session, monkeypatch
):
    import app.demo as demo

    monkeypatch.setattr(demo, "_ensure_sample_model", lambda: None)
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "market_data_provider", "twelve_data")
    # No API key configured: ingestion fails fast and is skipped.
    monkeypatch.setattr(settings, "twelve_data_api_key", "")
    monkeypatch.setattr(settings, "nse_symbols", "")

    demo.seed_demo_environment()

    session = demo_session()
    try:
        from app.auth.service import AuthService
        from app.db.repository import MarketDataRepository

        user = AuthService(session).authenticate(
            email=settings.demo_user_email,
            password=settings.demo_user_password,
        )
        assert user.is_active is True

        # Live-provider demos ingest real symbols; no CSV sample rows are seeded.
        assert MarketDataRepository(session).list_history("DEMO", limit=5000) == []
    finally:
        session.close()


def test_live_seed_ingests_and_trains_per_symbol_model(
    demo_session, monkeypatch, tmp_path
):
    import app.demo as demo
    from app.market_data.base import MarketBar

    class StubProvider:
        name = "stub-live"

        @staticmethod
        def history(symbol, limit=100):
            return [
                MarketBar(
                    date=f"2025-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}",
                    symbol=symbol,
                    open=100.0 + i,
                    high=101.0 + i,
                    low=99.0 + i,
                    close=100.5 + i,
                    volume=1_000_000 + i,
                )
                for i in range(min(limit, 150))
            ]

    monkeypatch.setattr(demo, "_ensure_sample_model", lambda: None)
    monkeypatch.setattr(demo, "get_provider_for_symbol", lambda symbol: StubProvider())
    monkeypatch.setattr(demo, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "market_data_provider", "twelve_data")
    monkeypatch.setattr(settings, "market_data_symbols", "AAPL")
    monkeypatch.setattr(settings, "nse_symbols", "")

    demo.seed_demo_environment()

    session = demo_session()
    try:
        from app.db.repository import MarketDataRepository

        bars = MarketDataRepository(session).list_history("AAPL", limit=5000)
        assert len(bars) == 150
        assert bars[0].source_provider == "stub-live"
    finally:
        session.close()

    model_file = tmp_path / "stocksense_rf_AAPL.joblib"
    assert model_file.exists()

    from app.services.predictor import Predictor

    predictor = Predictor(model_path=tmp_path / "missing_global.joblib")
    history = [
        {"date": f"2025-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}", "close": 100.5 + i, "volume": 1_000_000}
        for i in range(100, 150)
    ]
    result = predictor.predict(symbol="AAPL", history=history)
    assert result["model"] == "random-forest-live-aapl"
    # Ratio-target model: prediction stays within a plausible daily move of the
    # last close (249.5 here), regardless of the absolute price level.
    last_close = history[-1]["close"]
    assert abs(result["predicted_close"] - last_close) / last_close < 0.05
