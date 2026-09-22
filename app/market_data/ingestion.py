from __future__ import annotations

import pandas as pd

from app.db.repository import MarketDataRepository
from app.market_data.base import MarketDataProvider
from app.market_data.service import MarketDataService


class MarketDataIngestionService:
    def __init__(
        self,
        provider: MarketDataProvider,
        repository: MarketDataRepository,
    ) -> None:
        self.market_data = MarketDataService(provider)
        self.repository = repository

    def ingest(self, symbol: str, limit: int = 500) -> int:
        bars = self.market_data.history(symbol, limit=limit)
        return self.repository.upsert_many(
            [
                {
                    "date": pd.Timestamp(bar.date).date(),
                    "symbol": bar.symbol,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "source_provider": getattr(self.market_data.provider, "name", "unknown"),
                }
                for bar in bars
            ]
        )
