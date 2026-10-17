"""Universe screener: filter configured symbols on real computed metrics.

Everything is derived from stored bars (the same data the charts show); the
screener never fabricates values and skips symbols without enough history.
"""

from __future__ import annotations

import pandas as pd

from app.market_data.symbols import describe_symbol
from app.services.indicators import rsi as rsi_series
from app.services.indicators import sma as sma_series


def screen_universe(
    histories: dict[str, list[dict]],
    exchange: str | None = None,
    min_change_pct: float | None = None,
    max_change_pct: float | None = None,
    min_rsi: float | None = None,
    max_rsi: float | None = None,
    above_sma20: bool | None = None,
    min_volume: int | None = None,
) -> list[dict[str, object]]:
    """Score each symbol and apply filters.

    `histories` maps symbol -> stored bars (oldest first). Symbols with fewer
    than 21 bars are skipped (RSI/SMA20 need history). Results are sorted by
    absolute 1-day move, largest first.
    """
    rows: list[dict[str, object]] = []
    for symbol, bars in histories.items():
        if len(bars) < 21:
            continue
        info = describe_symbol(symbol)
        if exchange and info.exchange != exchange.upper():
            continue

        close = pd.Series([float(b["close"]) for b in bars])
        volumes = [int(b.get("volume") or 0) for b in bars]

        last_close = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])
        change_pct = ((last_close - prev_close) / prev_close) * 100 if prev_close else None
        rsi14 = rsi_series(close).iloc[-1]
        sma20 = sma_series(close, 20).iloc[-1]
        avg_volume20 = sum(volumes[-20:]) / 20
        last_volume = volumes[-1]

        if min_change_pct is not None and (change_pct is None or change_pct < min_change_pct):
            continue
        if max_change_pct is not None and (change_pct is None or change_pct > max_change_pct):
            continue
        if min_rsi is not None and (pd.isna(rsi14) or rsi14 < min_rsi):
            continue
        if max_rsi is not None and (pd.isna(rsi14) or rsi14 > max_rsi):
            continue
        is_above = None if pd.isna(sma20) else last_close > float(sma20)
        if above_sma20 is not None and is_above != above_sma20:
            continue
        if min_volume is not None and last_volume < min_volume:
            continue

        rows.append(
            {
                "symbol": info.symbol,
                "name": info.name,
                "exchange": info.exchange,
                "currency": info.currency,
                "date": str(bars[-1]["date"])[:10],
                "close": round(last_close, 4),
                "change_pct": round(change_pct, 2) if change_pct is not None else None,
                "rsi14": round(float(rsi14), 2) if not pd.isna(rsi14) else None,
                "above_sma20": is_above,
                "volume": last_volume,
                "rel_volume": round(last_volume / avg_volume20, 2) if avg_volume20 else None,
            }
        )

    rows.sort(key=lambda r: abs(r["change_pct"] or 0), reverse=True)
    return rows
