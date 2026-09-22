from __future__ import annotations

import time
from datetime import date

import httpx

from app.core.config import settings
from app.market_data.base import MarketBar


class TwelveDataError(RuntimeError):
    pass


class TwelveDataProvider:
    name = "twelve_data"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.twelve_data_api_key
        if not self.api_key:
            raise TwelveDataError("TWELVE_DATA_API_KEY is not configured")
        self.base_url = settings.twelve_data_base_url.rstrip("/")

    def history(self, symbol: str, limit: int = 100) -> list[MarketBar]:
        params = {
            "symbol": symbol,
            "interval": "1day",
            "outputsize": min(limit, settings.market_data_max_rows),
            "apikey": self.api_key,
        }

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=settings.market_data_timeout_seconds) as client:
                    response = client.get(f"{self.base_url}/time_series", params=params)
                    response.raise_for_status()
                    payload = response.json()

                if payload.get("status") == "error":
                    raise TwelveDataError(
                        str(payload.get("message", "Twelve Data returned an error"))
                    )

                values = payload.get("values")
                if not isinstance(values, list):
                    raise TwelveDataError("Twelve Data response did not contain time-series values")

                bars = [self._to_bar(symbol, item) for item in values]
                bars.sort(key=lambda item: item.date)
                return bars[-limit:]
            except (httpx.HTTPError, TwelveDataError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.5 * (2**attempt))

        raise TwelveDataError(f"Market data request failed: {last_error}") from last_error

    @staticmethod
    def _to_bar(symbol: str, item: dict[str, str]) -> MarketBar:
        trading_date = date.fromisoformat(item["datetime"][:10])
        return MarketBar(
            date=trading_date.isoformat(),
            symbol=symbol.upper(),
            open=float(item["open"]),
            high=float(item["high"]),
            low=float(item["low"]),
            close=float(item["close"]),
            volume=int(float(item.get("volume", 0))),
        )
