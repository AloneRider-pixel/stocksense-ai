"""India-first refocus: NIFTY 50 universe, metals/FX instruments, holidays,
index benchmark."""

from __future__ import annotations

from datetime import date

from app.core.config import settings
from app.market_data.holidays import is_trading_day, next_trading_day
from app.market_data.symbols import (
    currency_symbols,
    lookup_symbol,
    metal_symbols,
    nifty50_symbols,
)


def test_default_universe_is_india_first():
    universe = settings.market_data_symbol_list
    assert "RELIANCE" in universe and "TCS" in universe
    assert "GOLD" in universe and "SILVER" in universe
    assert "USDINR" in universe and "EURINR" in universe and "GBPINR" in universe
    assert "AAPL" not in universe  # US mega-caps demoted from the default


def test_nifty50_registry_complete():
    symbols = nifty50_symbols()
    assert len(symbols) == 50
    info = lookup_symbol("M&M")
    assert info is not None and info.provider_symbol == "M&M.NS"
    for symbol in symbols:
        info = lookup_symbol(symbol)
        assert info is not None
        assert info.exchange == "NSE" and info.currency == "INR"
        assert info.provider_symbol.endswith(".NS")
        assert info.timezone == "Asia/Kolkata"


def test_benchmark_index_entry():
    info = lookup_symbol(settings.benchmark_index_symbol)
    assert info is not None
    assert info.is_index and info.asset_class == "index"
    assert info.provider_symbol == "^NSEI"
    assert info.exchange == "NSE Index"


def test_metals_and_currencies():
    assert metal_symbols() == ["GOLD", "SILVER"]
    assert currency_symbols() == ["EURINR", "GBPINR", "USDINR"]
    gold = lookup_symbol("GOLD")
    assert gold.asset_class == "metal" and gold.provider_symbol == "XAUUSD=X"
    pair = lookup_symbol("USDINR")
    assert pair.asset_class == "currency" and pair.currency == "INR"
    assert pair.provider_symbol == "USDINR=X"


def test_nse_trading_calendar():
    assert not is_trading_day(date(2026, 10, 24))  # Saturday
    assert not is_trading_day(date(2026, 10, 25))  # Sunday
    assert not is_trading_day(date(2026, 12, 25))  # Christmas
    assert is_trading_day(date(2026, 10, 23))  # Friday
    # Friday 2026-10-23 -> next trading day is Monday 2026-10-26
    assert next_trading_day(date(2026, 10, 23)) == date(2026, 10, 26)
    # Christmas Eve 2026 (Thu) skips the holiday
    assert next_trading_day(date(2026, 12, 24)) == date(2026, 12, 28)


def test_index_benchmark_against_fake_bars(session_factory):
    from app.db.models import MarketBarRecord, PredictionRecord
    from app.db.repository import PredictionRepository

    session = session_factory()

    def bar(symbol, day, close):
        session.add(
            MarketBarRecord(
                symbol=symbol, date=day, open=close, high=close, low=close,
                close=close, volume=1000, source_provider="test",
            )
        )

    for sym in ("RELIANCE", "NIFTY50"):
        bar(sym, date(2026, 10, 20), 100.0)
        bar(sym, date(2026, 10, 21), 110.0 if sym == "RELIANCE" else 102.0)
    session.add(
        PredictionRecord(
            symbol="RELIANCE", prediction_date=date(2026, 10, 20),
            predicted_close=108.0, expected_change_pct=8.0, model="rf",
            actual_date=date(2026, 10, 21), actual_close=110.0,
            absolute_error=2.0, percentage_error=1.8, direction_correct=True,
        )
    )
    session.commit()

    repo = PredictionRepository(session)
    bench = repo.index_benchmark_for(repo.scored_records(), "NIFTY50")
    assert bench["compared_windows"] == 1
    assert bench["avg_symbol_return_pct"] == 10.0
    assert bench["avg_index_return_pct"] == 2.0
    assert bench["share_outperforming_index_pct"] == 100.0
