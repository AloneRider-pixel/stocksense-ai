from __future__ import annotations

from app.market_data.base import MarketBar, MarketDataProvider


class MarketDataService:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def history(self, symbol: str, limit: int = 100) -> list[MarketBar]:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("Symbol is required")
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")

        bars = self.provider.history(normalized, limit)
        bars = sorted(bars, key=lambda bar: bar.date)

        if not bars:
            return []

        seen_dates: set[str] = set()
        validated: list[MarketBar] = []

        for bar in bars:
            if bar.symbol.upper() != normalized:
                raise ValueError("Provider returned a mismatched symbol")
            if bar.date in seen_dates:
                continue
            seen_dates.add(bar.date)

            if min(bar.open, bar.high, bar.low, bar.close) <= 0:
                raise ValueError("Provider returned a non-positive price")
            if bar.high < max(bar.open, bar.close):
                raise ValueError("Provider returned an invalid high price")
            if bar.low > min(bar.open, bar.close):
                raise ValueError("Provider returned an invalid low price")
            if bar.volume < 0:
                raise ValueError("Provider returned a negative volume")

            validated.append(bar)

        return validated[-limit:]
