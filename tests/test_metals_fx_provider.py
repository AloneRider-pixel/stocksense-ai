"""Metals/FX chained provider: Twelve Data primary, Yahoo fallback."""

from __future__ import annotations

from app.market_data.base import MarketBar
from app.market_data.factory import get_provider_for_symbol
from app.market_data.metals_fx import METALS_FX_SYMBOLS, MetalsFXProvider
from app.market_data.twelve_data import TwelveDataError
from app.market_data.yfinance_provider import YFinanceNSEProvider


def _bar(symbol):
    return [
        MarketBar(
            date="2026-10-21", symbol=symbol, open=1.0, high=1.0, low=1.0,
            close=1.0, volume=0,
        )
    ]


def test_registry_routes_metals_and_fx_to_chain():
    for symbol in METALS_FX_SYMBOLS:
        assert isinstance(get_provider_for_symbol(symbol), MetalsFXProvider)


def test_twelve_data_symbol_mapping():
    assert METALS_FX_SYMBOLS["GOLD"] == ("XAU/USD", "GC=F")
    assert METALS_FX_SYMBOLS["SILVER"] == ("XAG/USD", "SI=F")
    assert METALS_FX_SYMBOLS["USDINR"] == ("USD/INR", "USDINR=X")


def test_prefers_twelve_data_when_key_configured(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.twelve_data_api_key", "k")
    calls = []
    provider = MetalsFXProvider()
    monkeypatch.setattr(
        provider._twelve_data, "history", lambda s, limit: calls.append(s) or _bar(s)
    )
    bars = provider.history("GOLD", limit=5)
    assert calls == ["XAU/USD"]
    # bars are tagged with the display symbol for storage and validation
    assert bars[0].symbol == "GOLD"


def test_falls_back_to_yahoo_on_twelve_data_error(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.twelve_data_api_key", "k")
    provider = MetalsFXProvider()

    def boom(symbol, limit):
        raise TwelveDataError("rate limited")

    calls = []
    monkeypatch.setattr(provider._twelve_data, "history", boom)
    monkeypatch.setattr(
        provider._yfinance, "history", lambda s, limit: calls.append(s) or _bar(s)
    )
    bars = provider.history("USDINR", limit=5)
    assert calls == ["USDINR=X"]
    assert bars[0].symbol == "USDINR"


def test_uses_yahoo_when_no_key(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.twelve_data_api_key", "")
    provider = MetalsFXProvider()
    calls = []
    monkeypatch.setattr(
        provider._yfinance, "history", lambda s, limit: calls.append(s) or _bar(s)
    )
    provider.history("EURINR", limit=5)
    assert calls == ["EURINR=X"]


def test_unknown_symbol_rejected():
    provider = MetalsFXProvider()
    try:
        provider.history("PLATINUM", limit=5)
    except Exception as exc:
        assert "Unknown metals/FX" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected rejection")


def test_yfinance_class_still_serves_nse():
    assert isinstance(get_provider_for_symbol("RELIANCE"), YFinanceNSEProvider)
