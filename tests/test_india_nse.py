"""Phase 2: NSE symbol registry, provider routing, indicators."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.market_data.factory import get_provider_for_symbol
from app.market_data.symbols import describe_symbol, lookup_symbol
from app.market_data.yfinance_provider import YFinanceNSEProvider
from app.services.features import build_training_frame
from app.services.indicators import bollinger, compute_indicators, ema, macd, rsi, sma


def test_registry_resolves_nse_symbol():
    info = lookup_symbol("RELIANCE")
    assert info is not None
    assert info.exchange == "NSE"
    assert info.currency == "INR"
    assert info.provider == "yfinance_nse"
    assert info.provider_symbol == "RELIANCE.NS"
    assert info.timezone == "Asia/Kolkata"


def test_registry_resolves_us_symbol():
    info = lookup_symbol("AAPL")
    assert info is not None
    assert info.exchange == "US"
    assert info.currency == "USD"
    assert info.provider == "twelve_data"


def test_describe_unknown_symbol_defaults_to_us():
    info = describe_symbol("SOMEUSSTOCK")
    assert info.exchange == "US"
    assert info.provider == "twelve_data"


def test_provider_routing(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.market_data_provider", "csv")
    from app.market_data.csv_provider import CSVMarketDataProvider

    assert isinstance(get_provider_for_symbol("RELIANCE"), YFinanceNSEProvider)
    assert isinstance(get_provider_for_symbol("AAPL"), CSVMarketDataProvider)


def _fake_history(rows):
    idx = pd.date_range("2026-01-01", periods=len(rows), freq="B")
    return pd.DataFrame(
        {
            "Open": [r[0] for r in rows],
            "High": [r[1] for r in rows],
            "Low": [r[2] for r in rows],
            "Close": [r[3] for r in rows],
            "Volume": [r[4] for r in rows],
        },
        index=idx,
    )


def test_yfinance_provider_maps_bars(monkeypatch):
    rows = [(100.0, 105.0, 99.0, 103.0, 1000), (103.0, 106.0, 102.0, 105.0, 1200)]

    class FakeTicker:
        def __init__(self, symbol):
            assert symbol == "RELIANCE.NS"

        def history(self, period, interval, timeout):
            return _fake_history(rows)

    import yfinance as yf

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    bars = YFinanceNSEProvider().history("RELIANCE", limit=5)
    assert len(bars) == 2
    assert bars[0].symbol == "RELIANCE"
    assert bars[0].close == 103.0
    assert bars[1].volume == 1200


def test_yfinance_provider_raises_on_empty(monkeypatch):
    class FakeTicker:
        def __init__(self, symbol):
            pass

        def history(self, period, interval, timeout):
            return pd.DataFrame()

    import yfinance as yf

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    with pytest.raises(Exception, match="No data"):
        YFinanceNSEProvider().history("RELIANCE", limit=5)


def test_sma_ema_known_values():
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert sma(close, 3).iloc[-1] == pytest.approx(4.0)
    assert pd.isna(sma(close, 3).iloc[0])
    # EMA with adjust=False seeds on the first value.
    e = ema(close, 3)
    assert e.iloc[-1] == pytest.approx(4.0625)


def test_rsi_extremes_and_midpoint():
    up = pd.Series([float(v) for v in range(1, 40)])
    assert rsi(up).iloc[-1] == pytest.approx(100.0)
    down = pd.Series([float(v) for v in range(40, 1, -1)])
    assert rsi(down).iloc[-1] == pytest.approx(0.0)


def test_macd_and_bollinger_alignment():
    close = pd.Series(np.sin(np.arange(120) / 5) * 10 + 100)
    m, s, h = macd(close)
    assert len(m) == len(s) == len(h) == 120
    upper, mid, lower = bollinger(close)
    valid = ~(upper.isna() | lower.isna())
    assert (upper[valid] >= mid[valid]).all()
    assert (mid[valid] >= lower[valid]).all()


def test_compute_indicators_aligns_with_dates():
    bars = [
        {
            "date": f"2026-02-{(i % 28) + 1:02d}",
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1000 + i,
        }
        for i in range(80)
    ]
    out = compute_indicators(bars)
    assert len(out["dates"]) == 80
    assert len(out["sma20"]) == 80
    assert out["sma20"][18] is None
    assert out["sma20"][19] is not None
    assert out["rsi14"][-1] == pytest.approx(100.0)


def test_training_frame_drops_infinite_volume_change():
    # Zero-volume day followed by normal volume makes pct_change infinite.
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=30, freq="B"),
            "close": np.linspace(100, 120, 30),
            "volume": [1000] * 10 + [0] + [1000] * 19,
        }
    )
    frame = build_training_frame(df)
    assert np.isfinite(frame["volume_change5"]).all()
    assert len(frame) < 30  # the poisoned window rows are dropped, not kept


def test_symbols_endpoint(client, auth_headers):
    headers, _ = auth_headers
    response = client.get("/api/v1/symbols", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    by_symbol = {item["symbol"]: item for item in payload}
    assert by_symbol["AAPL"]["exchange"] == "US"
    assert by_symbol["RELIANCE"]["exchange"] == "NSE"
    assert by_symbol["RELIANCE"]["currency"] == "INR"


def test_indicators_endpoint_needs_history(client, auth_headers, monkeypatch):
    headers, _ = auth_headers
    monkeypatch.setattr("app.core.config.settings.market_data_provider", "csv")
    response = client.get("/api/v1/stocks/NOPE/indicators", headers=headers)
    assert response.status_code == 404


def test_indicators_endpoint_returns_series(client, auth_headers, monkeypatch):
    headers, _ = auth_headers
    monkeypatch.setattr("app.core.config.settings.market_data_provider", "csv")
    # Ingest sample data first.
    ingest = client.get("/api/v1/stocks/DEMO/history?limit=100", headers=headers)
    assert ingest.status_code == 200
    response = client.get("/api/v1/stocks/DEMO/indicators?limit=100", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "DEMO"
    assert len(payload["dates"]) == len(payload["rsi14"]) == 100
    assert payload["sma50"][-1] is not None
