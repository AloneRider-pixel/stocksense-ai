"""Precious-metals and FX data with graceful degradation.

Primary source is Twelve Data (symbol form "XAU/USD", "USD/INR") when an API
key is configured: reliable and documented for forex and precious metals on
the free plan. Without a key, or when Twelve Data errors, fall back to
Yahoo Finance ("XAUUSD=X", "USDINR=X"), which is unofficial and rate-limited
but needs no key. Bars may be delayed or indicative either way; these are
not exchange-traded Indian contracts (no MCX) and not executable FX prices.
"""

from __future__ import annotations

from dataclasses import replace

from app.core.config import settings
from app.market_data.base import MarketBar
from app.market_data.twelve_data import TwelveDataError, TwelveDataProvider
from app.market_data.yfinance_provider import YFinanceError, YFinanceNSEProvider

# display symbol -> (Twelve Data symbol, Yahoo Finance symbol)
METALS_FX_SYMBOLS: dict[str, tuple[str, str]] = {
    "GOLD": ("XAU/USD", "XAUUSD=X"),
    "SILVER": ("XAG/USD", "XAGUSD=X"),
    "USDINR": ("USD/INR", "USDINR=X"),
    "EURINR": ("EUR/INR", "EURINR=X"),
    "GBPINR": ("GBP/INR", "GBPINR=X"),
}


class MetalsFXProvider:
    name = "metals_fx"

    def __init__(self) -> None:
        self._twelve_data = TwelveDataProvider()
        self._yfinance = YFinanceNSEProvider()

    def history(self, symbol: str, limit: int = 100) -> list[MarketBar]:
        normalized = symbol.strip().upper()
        if normalized not in METALS_FX_SYMBOLS:
            raise YFinanceError(f"Unknown metals/FX symbol: {symbol}")
        td_symbol, yf_symbol = METALS_FX_SYMBOLS[normalized]

        if settings.twelve_data_api_key:
            try:
                bars = self._twelve_data.history(td_symbol, limit=limit)
                return [self._as_display_symbol(bar, normalized) for bar in bars]
            except TwelveDataError:
                pass  # fall through to Yahoo

        bars = self._yfinance.history(yf_symbol, limit=limit)
        return [self._as_display_symbol(bar, normalized) for bar in bars]

    @staticmethod
    def _as_display_symbol(bar: MarketBar, display_symbol: str) -> MarketBar:
        """Tag bars with the universe display symbol (e.g. GOLD, USDINR).

        Providers return their native symbol ("XAU/USD", "XAUUSD=X"), but
        storage and downstream validation key on the display symbol.
        """
        return replace(bar, symbol=display_symbol)
