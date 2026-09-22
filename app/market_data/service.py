from app.market_data.base import MarketDataProvider


class MarketDataService:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def history(self, symbol: str, limit: int = 100) :
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("Symbol is required")
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        return self.provider.history(normalized, limit)
