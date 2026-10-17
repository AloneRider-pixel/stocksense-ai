"""NSE market data via Yahoo Finance (yfinance). Free, no API key.

Bars are daily and can be delayed; the UI discloses this. The provider takes
display symbols (e.g. "RELIANCE") and maps them to Yahoo tickers
("RELIANCE.NS") through the symbol registry.
"""

from __future__ import annotations

import time

from app.core.config import settings
from app.market_data.base import MarketBar
from app.market_data.symbols import describe_symbol


class YFinanceError(RuntimeError):
    pass


class YFinanceNSEProvider:
    name = "yfinance_nse"

    def history(self, symbol: str, limit: int = 100) -> list[MarketBar]:
        info = describe_symbol(symbol)
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise YFinanceError("yfinance is not installed") from exc

        # Request enough calendar time for `limit` trading days.
        if limit > 300:
            period = "5y"
        elif limit > 100:
            period = "2y"
        else:
            period = "1y"

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                ticker = yf.Ticker(info.provider_symbol)
                frame = ticker.history(period=period, interval="1d", timeout=settings.market_data_timeout_seconds)
                if frame is None or frame.empty:
                    raise YFinanceError(f"No data returned for {info.provider_symbol}")
                bars: list[MarketBar] = []
                for idx, row in frame.tail(limit).iterrows():
                    if row.isna().any():
                        continue
                    bars.append(
                        MarketBar(
                            date=idx.date().isoformat(),
                            symbol=info.symbol,
                            open=round(float(row["Open"]), 4),
                            high=round(float(row["High"]), 4),
                            low=round(float(row["Low"]), 4),
                            close=round(float(row["Close"]), 4),
                            volume=int(row["Volume"]),
                        )
                    )
                if not bars:
                    raise YFinanceError(f"No usable bars for {info.provider_symbol}")
                return bars
            except Exception as exc:  # yfinance raises varied error types
                last_error = exc
                if attempt < 2:
                    time.sleep(0.5 * (2**attempt))

        raise YFinanceError(f"Yahoo Finance request failed: {last_error}") from last_error
