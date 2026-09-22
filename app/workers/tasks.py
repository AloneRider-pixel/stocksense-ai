from __future__ import annotations

from app.market_data.csv_provider import CSVMarketDataProvider


async def refresh_market_snapshot(symbol: str) -> int:
    provider = CSVMarketDataProvider()
    return len(provider.history(symbol, limit=500))
