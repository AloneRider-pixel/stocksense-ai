from __future__ import annotations

from datetime import datetime, timezone

from app.market_data.base import MarketBar, drop_incomplete_bars


def bar(d):
    return MarketBar(date=d, symbol="X", open=1, high=1, low=1, close=1, volume=1)


def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_nse_today_bar_is_dropped_during_session_and_kept_after_close():
    bars = [bar("2026-11-25"), bar("2026-11-26")]
    # 10:00 IST on Thursday 26 Nov: session in progress
    during = drop_incomplete_bars(bars, exchange="NSE", timezone_name="Asia/Kolkata", now=utc("2026-11-26T04:30:00"))
    assert [b.date for b in during] == ["2026-11-25"]
    # 17:00 IST: session over, final
    after = drop_incomplete_bars(bars, exchange="NSE", timezone_name="Asia/Kolkata", now=utc("2026-11-26T11:30:00"))
    assert [b.date for b in after] == ["2026-11-25", "2026-11-26"]


def test_rolling_instruments_hold_back_today_and_yesterday_until_22_utc():
    bars = [bar("2026-11-24"), bar("2026-11-25"), bar("2026-11-26")]
    kw = dict(exchange="Indicative (source varies)", timezone_name="UTC")
    # 19:00 UTC on 26 Nov: a New York futures session dated 25 Nov may still be open, so hold it back
    assert [b.date for b in drop_incomplete_bars(bars, now=utc("2026-11-26T19:00:00"), **kw)] == ["2026-11-24"]
    # 23:00 UTC: yesterday released, today still never final
    assert [b.date for b in drop_incomplete_bars(bars, now=utc("2026-11-26T23:00:00"), **kw)] == ["2026-11-24", "2026-11-25"]
    # unknown venue is treated the same conservative way
    assert [b.date for b in drop_incomplete_bars(bars, exchange="???", timezone_name="UTC", now=utc("2026-11-26T23:00:00"))] == ["2026-11-24", "2026-11-25"]


def test_us_equity_session_cutoff_uses_new_york_time():
    bars = [bar("2026-11-25"), bar("2026-11-26")]
    kw = dict(exchange="US", timezone_name="America/New_York")
    assert [b.date for b in drop_incomplete_bars(bars, now=utc("2026-11-26T20:00:00"), **kw)] == ["2026-11-25"]  # 15:00 ET
    assert [b.date for b in drop_incomplete_bars(bars, now=utc("2026-11-26T22:30:00"), **kw)] == ["2026-11-25", "2026-11-26"]  # 17:30 ET


def test_empty_input_and_all_dropped_return_empty():
    assert drop_incomplete_bars([], exchange="US", timezone_name="America/New_York") == []
    assert drop_incomplete_bars([bar("2999-01-01")], exchange="NSE", timezone_name="Asia/Kolkata") == []


def test_final_bars_provider_wraps_every_symbol_and_keeps_name():
    from app.market_data.factory import FinalBarsProvider

    class Inner:
        name = "twelve_data"
        def history(self, symbol, limit=100):
            return [bar("2000-01-03"), bar("2999-01-01")]

    wrapped = FinalBarsProvider(Inner())
    assert wrapped.name == "twelve_data"
    assert [b.date for b in wrapped.history("MSFT")] == ["2000-01-03"]  # unregistered US symbol path


def test_metals_provider_drops_forming_bars_on_both_paths_and_raises_when_none_left(monkeypatch):
    from app.market_data.metals_fx import MetalsFXProvider
    from app.market_data.yfinance_provider import YFinanceError

    p = MetalsFXProvider()
    monkeypatch.setattr(p._twelve_data, "history", lambda s, limit=100: [bar("2000-01-03"), bar("2999-01-01")])
    monkeypatch.setattr("app.market_data.metals_fx.settings.twelve_data_api_key", "k")
    assert [b.date for b in p.history("GOLD")] == ["2000-01-03"]  # Twelve path
    monkeypatch.setattr("app.market_data.metals_fx.settings.twelve_data_api_key", "")
    monkeypatch.setattr(p._yfinance, "history", lambda s, limit=100: [bar("2000-01-03"), bar("2999-01-01")])
    assert [b.date for b in p.history("GOLD")] == ["2000-01-03"]  # Yahoo fallback path
    monkeypatch.setattr(p._yfinance, "history", lambda s, limit=100: [bar("2999-01-01")])
    import pytest
    with pytest.raises(YFinanceError):
        p.history("GOLD")


def test_twelve_data_normalizes_datetime_strings_before_the_filter():
    from app.market_data.twelve_data import TwelveDataProvider

    a = TwelveDataProvider._to_bar("MSFT", {"datetime": "2026-11-26", "open": "1", "high": "1", "low": "1", "close": "1", "volume": "1"})
    b = TwelveDataProvider._to_bar("MSFT", {"datetime": "2026-11-26 00:00:00", "open": "1", "high": "1", "low": "1", "close": "1", "volume": "1"})
    assert a.date == b.date == "2026-11-26"


def test_weekend_nse_today_bar_is_dropped():
    # Saturday 28 Nov 2026 18:00 IST: no session today, a bar dated today cannot be final
    kept = drop_incomplete_bars([bar("2026-11-28")], exchange="NSE", timezone_name="Asia/Kolkata", now=utc("2026-11-28T12:30:00"))
    assert kept == []
