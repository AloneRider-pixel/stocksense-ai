from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.market_data import factory
from app.market_data.base import MarketBar
from app.workers import tasks


class _Inner:
    name = "fake"

    def __init__(self, days: int) -> None:
        self.days = days
        self.requested: int | None = None

    def history(self, symbol: str, limit: int = 100) -> list[MarketBar]:
        self.requested = limit
        today = datetime.now(timezone.utc).date()
        n = min(limit, self.days)
        return [
            MarketBar(
                date=(today - timedelta(days=n - 1 - i)).isoformat(),
                symbol=symbol,
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=1,
            )
            for i in range(n)
        ]


def test_final_bars_provider_over_fetches_so_small_limits_still_return_final_bars():
    inner = _Inner(days=10)
    bars = factory.FinalBarsProvider(inner).history("AAPL", limit=2)
    assert inner.requested is not None and inner.requested > 2
    assert len(bars) == 2
    today = datetime.now(timezone.utc).date().isoformat()
    assert all(bar.date < today for bar in bars)


def test_refresh_skips_unsupported_suffix_symbol_and_continues(monkeypatch):
    seen: list[str] = []

    async def fake_refresh(ctx, symbol):
        seen.append(symbol)
        return {"fetched": 1, "inserted": 1, "predictions_evaluated": 0}

    monkeypatch.setattr(tasks, "refresh_market_data", fake_refresh)
    monkeypatch.setattr(tasks.settings, "market_data_symbols", "BAD.L,AAPL", raising=False)
    monkeypatch.setattr(type(tasks.settings), "market_data_symbol_list", property(lambda self: ["BAD.L", "AAPL"]))
    result = asyncio.run(tasks.refresh_configured_markets({}))
    assert seen == ["AAPL"]
    assert result["fetched"] == 1
