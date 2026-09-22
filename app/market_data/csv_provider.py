from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.market_data.base import MarketBar


class CSVMarketDataProvider:
    def __init__(self, path: str = "data/sample_prices.csv") -> None:
        self.path = Path(path)

    def history(self, symbol: str, limit: int = 100) -> list[MarketBar]:
        frame = pd.read_csv(self.path)
        frame["symbol"] = frame["symbol"].astype(str).str.upper()

        filtered = frame.loc[frame["symbol"] == symbol.upper()].tail(limit)
        return [
            MarketBar(
                date=str(row.date),
                symbol=str(row.symbol),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=int(row.volume),
            )
            for row in filtered.itertuples()
        ]
