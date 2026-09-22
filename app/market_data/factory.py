from __future__ import annotations

from app.core.config import settings
from app.market_data.base import MarketDataProvider
from app.market_data.csv_provider import CSVMarketDataProvider
from app.market_data.twelve_data import TwelveDataProvider


def get_market_data_provider() -> MarketDataProvider:
    provider = settings.market_data_provider.lower()

    if provider == "csv":
        return CSVMarketDataProvider()

    if provider == "twelve_data":
        return TwelveDataProvider()

    raise ValueError(f"Unsupported market-data provider: {provider}")
