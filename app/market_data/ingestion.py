from __future__ import annotations

import pandas as pd

from app.db.repository import MarketDataRepository, PredictionRepository
from app.market_data.base import MarketDataProvider
from app.market_data.service import MarketDataService


class MarketDataIngestionService:
    def __init__(
        self,
        provider: MarketDataProvider,
        repository: MarketDataRepository,
        prediction_repository: PredictionRepository | None = None,
    ) -> None:
        self.market_data = MarketDataService(provider)
        self.repository = repository
        self.prediction_repository = prediction_repository

    def ingest(self, symbol: str, limit: int = 500) -> dict[str, int | str]:
        bars = self.market_data.history(symbol, limit=limit)
        inserted = self.repository.upsert_many(
            [
                {
                    "date": pd.Timestamp(bar.date).date(),
                    "symbol": bar.symbol,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "source_provider": getattr(
                        self.market_data.provider,
                        "name",
                        "unknown",
                    ),
                }
                for bar in bars
            ]
        )

        evaluated = 0
        if self.prediction_repository is not None:
            evaluated = self.prediction_repository.evaluate_pending(symbol)

        return {
            "symbol": symbol.upper(),
            "fetched": len(bars),
            "inserted": inserted,
            "predictions_evaluated": evaluated,
        }
