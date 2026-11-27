from __future__ import annotations

from app.core.config import settings
from app.market_data.base import MarketBar, MarketDataProvider, drop_incomplete_bars
from app.market_data.csv_provider import CSVMarketDataProvider
from app.market_data.metals_fx import MetalsFXProvider
from app.market_data.symbols import describe_symbol
from app.market_data.twelve_data import TwelveDataProvider
from app.market_data.yfinance_provider import YFinanceNSEProvider


class FinalBarsProvider:
    """Wraps a live provider so a still-forming current-session bar is never stored as a daily close."""

    def __init__(self, inner: MarketDataProvider) -> None:
        self._inner = inner
        self.name = getattr(inner, "name", inner.__class__.__name__)

    def history(self, symbol: str, limit: int = 100) -> list[MarketBar]:
        info = describe_symbol(symbol)
        return drop_incomplete_bars(
            self._inner.history(symbol, limit=limit), exchange=info.exchange, timezone_name=info.timezone
        )


def get_market_data_provider() -> MarketDataProvider:
    provider = settings.market_data_provider.lower()

    if provider == "csv":
        return CSVMarketDataProvider()

    if provider == "twelve_data":
        return FinalBarsProvider(TwelveDataProvider())

    raise ValueError(f"Unsupported market-data provider: {provider}")


def get_provider_for_symbol(symbol: str) -> MarketDataProvider:
    """Resolve the provider for one display symbol via the registry.

    NSE symbols always use Yahoo Finance; everything else follows the
    configured default provider (CSV for tests/sample, Twelve Data live).
    """
    info = describe_symbol(symbol)
    if info.provider == "yfinance_nse":
        return YFinanceNSEProvider()
    if info.provider == "metals_fx":
        return MetalsFXProvider()
    return get_market_data_provider()
