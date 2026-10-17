from __future__ import annotations

import pytest

from app.market_data.base import MarketBar
from app.market_data.service import MarketDataService


class FakeProvider:
    name = "fake"

    def __init__(self, bars):
        self._bars = bars

    def history(self, symbol, limit=100):
        return list(self._bars)


def make_bar(date, close=100.0, **overrides):
    values = {
        "date": date,
        "symbol": "DEMO",
        "open": close - 1,
        "high": close + 1,
        "low": close - 2,
        "close": close,
        "volume": 1000,
    }
    values.update(overrides)
    return MarketBar(**values)


def test_history_returns_sorted_validated_bars():
    provider = FakeProvider([make_bar("2025-01-03"), make_bar("2025-01-02")])
    service = MarketDataService(provider)

    bars = service.history("demo", limit=10)

    assert [bar.date for bar in bars] == ["2025-01-02", "2025-01-03"]


def test_history_normalizes_symbol_case():
    provider = FakeProvider([make_bar("2025-01-02")])
    service = MarketDataService(provider)

    bars = service.history("  demo  ", limit=10)

    assert len(bars) == 1


def test_history_rejects_blank_symbol():
    service = MarketDataService(FakeProvider([]))

    with pytest.raises(ValueError, match="Symbol is required"):
        service.history("   ")


@pytest.mark.parametrize("limit", [0, 5001])
def test_history_rejects_out_of_range_limit(limit):
    service = MarketDataService(FakeProvider([]))

    with pytest.raises(ValueError, match="limit must be between"):
        service.history("DEMO", limit=limit)


def test_history_returns_empty_when_provider_has_no_bars():
    service = MarketDataService(FakeProvider([]))

    assert service.history("DEMO") == []


def test_history_deduplicates_dates():
    provider = FakeProvider([make_bar("2025-01-02"), make_bar("2025-01-02")])
    service = MarketDataService(provider)

    bars = service.history("DEMO")

    assert len(bars) == 1


def test_history_rejects_mismatched_symbol():
    provider = FakeProvider([make_bar("2025-01-02", symbol="OTHER")])
    service = MarketDataService(provider)

    with pytest.raises(ValueError, match="mismatched symbol"):
        service.history("DEMO")


def test_history_rejects_non_positive_price():
    provider = FakeProvider([make_bar("2025-01-02", close=-5.0, open=-6.0, high=-4.0, low=-7.0)])
    service = MarketDataService(provider)

    with pytest.raises(ValueError, match="non-positive price"):
        service.history("DEMO")


def test_history_rejects_invalid_high():
    provider = FakeProvider([make_bar("2025-01-02", high=50.0)])
    service = MarketDataService(provider)

    with pytest.raises(ValueError, match="invalid high price"):
        service.history("DEMO")


def test_history_rejects_invalid_low():
    provider = FakeProvider([make_bar("2025-01-02", low=500.0, high=600.0)])
    service = MarketDataService(provider)

    with pytest.raises(ValueError, match="invalid low price"):
        service.history("DEMO")


def test_history_rejects_negative_volume():
    provider = FakeProvider([make_bar("2025-01-02", volume=-1)])
    service = MarketDataService(provider)

    with pytest.raises(ValueError, match="negative volume"):
        service.history("DEMO")


def test_history_applies_limit_to_latest_bars():
    provider = FakeProvider(
        [make_bar(f"2025-01-{day:02d}") for day in range(1, 8)]
    )
    service = MarketDataService(provider)

    bars = service.history("DEMO", limit=3)

    assert [bar.date for bar in bars] == ["2025-01-05", "2025-01-06", "2025-01-07"]
